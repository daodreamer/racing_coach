"""Prompt construction for LLM feedback generation — S4-US2."""

from __future__ import annotations

from racing_coach.reporting.models import CornerReport, LapReport

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """你是一位专业的赛车教练AI助手，专注于为赛车驾驶员提供基于遥测数据的精准驾驶建议。

重要约束（必须严格遵守）：
1. 你只能基于以下提供的遥测数据进行分析，严禁编造或推测数据中不存在的信息。
2. 必须严格按照指定的JSON格式输出，不得添加任何JSON之外的文字。
3. 每条建议必须直接对应数据中的具体观测值，并给出可操作的改进方向。
4. severity字段只能使用 'high'、'medium'、'low' 三个值。"""

_USER_TEMPLATE = """以下是一圈的遥测分析结果：

赛道：{track}
车辆：{car}
总时间差：{total_delta:+.3f}s（正值=比参考圈慢）

逐弯详情：
{corners_text}

请严格按照以下JSON格式输出（不要输出任何JSON之外的内容）：
{{
  "summary": "1-2句对整圈表现的总体评价",
  "suggestions": [
    {{"corner_id": <整数>, "severity": "high|medium|low", "suggestion": "<具体可操作的改进建议>"}}
  ]
}}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_corner(cr: CornerReport) -> str:
    lines = [f"[弯道 {cr.corner_id}] 时间损失={cr.delta_total:+.3f}s"]

    if cr.braking:
        b = cr.braking
        lock = "⚠抱死" if b.lock_detected else "无抱死"
        lines.append(
            f"  刹车: 刹车点偏差={b.brake_point_delta_m:+.1f}m, "
            f"峰值压力={b.peak_pressure:.2f}, "
            f"Trail brake评分={b.trail_brake_linearity:.2f}, {lock}"
        )

    if cr.throttle:
        t = cr.throttle
        early = "⚠过早全油门" if t.too_early_full_throttle else "油门时机正常"
        lines.append(f"  油门: {early}, 重叠帧={t.overlap_count}")

    if cr.apex_speed:
        a = cr.apex_speed
        slow = "⚠偏慢" if a.too_slow else "正常"
        lines.append(f"  弯心速度: {a.delta_kph:+.1f}km/h vs参考圈 ({slow})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Return a conservative token count estimate for *text*.

    Uses ``len(text) // 3`` as a rough approximation that accounts for
    Chinese characters (which occupy more bytes but typically one token each).
    """
    return len(text) // 3


class PromptBuilder:
    """Build LLM prompts from a :class:`~racing_coach.reporting.models.LapReport`."""

    @property
    def system_prompt(self) -> str:
        """Return the system role prompt string."""
        return _SYSTEM_PROMPT

    def build(self, report: LapReport) -> str:
        """Build the user-turn prompt from *report*."""
        corners_text = "\n\n".join(_format_corner(c) for c in report.corners)
        return _USER_TEMPLATE.format(
            track=report.track,
            car=report.car,
            total_delta=report.total_delta_s,
            corners_text=corners_text,
        )

    def build_messages(self, report: LapReport) -> tuple[str, str]:
        """Return ``(system_prompt, user_prompt)`` ready for the chat API."""
        return self.system_prompt, self.build(report)
