"""Moonshot AI (Kimi) LLM client — S4-US3.

Reads the API key from the ``MOONSHOT_API_KEY`` environment variable by
default.  Pass ``api_key`` explicitly in tests or when integrating with
secret managers.
"""

from __future__ import annotations

import json
import logging
import os

from openai import APIError, OpenAI, OpenAIError

from racing_coach.reporting.models import LapReport, Suggestion
from racing_coach.reporting.prompt import PromptBuilder

_logger = logging.getLogger(__name__)

_SEVERITY_LEVELS = frozenset({"high", "medium", "low"})

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def parse_llm_response(raw: str) -> tuple[str, list[Suggestion]]:
    """Parse a JSON LLM response into ``(summary, suggestions)``.

    Returns ``("", [])`` on any parse or structure error.
    """
    try:
        data = json.loads(raw)
        summary = str(data.get("summary", ""))
        suggestions: list[Suggestion] = []
        for item in data.get("suggestions", []):
            severity = item.get("severity", "medium")
            if severity not in _SEVERITY_LEVELS:
                severity = "medium"
            suggestions.append(
                Suggestion(
                    corner_id=int(item["corner_id"]),
                    severity=severity,
                    suggestion=str(item["suggestion"]),
                )
            )
        return summary, suggestions
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return "", []


def fallback_suggestions(report: LapReport) -> list[Suggestion]:
    """Generate rule-based suggestions when the LLM API is unavailable."""
    suggestions: list[Suggestion] = []

    for corner in report.corners:
        if corner.braking and corner.braking.lock_detected:
            suggestions.append(
                Suggestion(
                    corner_id=corner.corner_id,
                    severity="high",
                    suggestion=f"弯道{corner.corner_id}检测到轮胎抱死，请适当减轻刹车压力。",
                )
            )
        elif corner.braking and corner.braking.brake_point_delta_m > 10:
            suggestions.append(
                Suggestion(
                    corner_id=corner.corner_id,
                    severity="medium",
                    suggestion=(
                        f"弯道{corner.corner_id}刹车点偏晚"
                        f"{corner.braking.brake_point_delta_m:.0f}m，建议提前刹车。"
                    ),
                )
            )

        if corner.throttle and corner.throttle.too_early_full_throttle:
            suggestions.append(
                Suggestion(
                    corner_id=corner.corner_id,
                    severity="medium",
                    suggestion=(
                        f"弯道{corner.corner_id}过早全油门，等待车头稳定后再大脚油门。"
                    ),
                )
            )

        if corner.apex_speed and corner.apex_speed.too_slow:
            suggestions.append(
                Suggestion(
                    corner_id=corner.corner_id,
                    severity="medium",
                    suggestion=(
                        f"弯道{corner.corner_id}弯心速度偏低"
                        f"{abs(corner.apex_speed.delta_kph):.1f}km/h，尝试优化进弯线路。"
                    ),
                )
            )

    return suggestions


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class MoonshotClient:
    """Moonshot AI (Kimi) chat completion client.

    Args:
        api_key: API key; falls back to ``MOONSHOT_API_KEY`` env variable.
        model: Model identifier (e.g. ``"kimi-k2"``).
        timeout: Request timeout in seconds.
    """

    BASE_URL = "https://api.moonshot.cn/v1"
    DEFAULT_MODEL = "kimi-k2"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout: float = 30.0,
    ) -> None:
        key = api_key or os.environ.get("MOONSHOT_API_KEY", "")
        self._client = OpenAI(api_key=key, base_url=self.BASE_URL, timeout=timeout)
        self._model = model

    def generate(self, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
        """Call the LLM API and return ``(response_text, usage_dict)``.

        Returns ``("", {})`` on timeout or any API error.
        API token usage is logged at ``INFO`` level.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            _logger.info(
                "Moonshot API usage — prompt: %d, completion: %d, total: %d tokens",
                usage["prompt_tokens"],
                usage["completion_tokens"],
                usage["total_tokens"],
            )
            return response.choices[0].message.content, usage
        except (OpenAIError, APIError) as exc:
            _logger.warning("Moonshot API call failed: %s", exc)
            return "", {}

    def analyze(self, report: LapReport, builder: PromptBuilder | None = None) -> LapReport:
        """Generate LLM feedback and apply to *report* (mutates + returns it).

        Falls back to rule-based suggestions when the API is unavailable.
        """
        if builder is None:
            builder = PromptBuilder()

        system_prompt, user_prompt = builder.build_messages(report)
        raw_text, _ = self.generate(system_prompt, user_prompt)

        if raw_text:
            summary, suggestions = parse_llm_response(raw_text)
            if suggestions or summary:
                corner_map = {c.corner_id: c for c in report.corners}
                for s in suggestions:
                    if s.corner_id in corner_map:
                        corner_map[s.corner_id].suggestions.append(s)
                report.summary = summary
                report.top_improvements = sorted(
                    suggestions,
                    key=lambda s: -(
                        corner_map[s.corner_id].delta_total
                        if s.corner_id in corner_map
                        else 0.0
                    ),
                )[:3]
                return report

        # Fallback: rule-based suggestions
        suggestions = fallback_suggestions(report)
        corner_map = {c.corner_id: c for c in report.corners}
        for s in suggestions:
            if s.corner_id in corner_map:
                corner_map[s.corner_id].suggestions.append(s)
        report.top_improvements = suggestions[:3]
        report.summary = "基于规则引擎生成的分析（LLM服务不可用）。"
        return report
