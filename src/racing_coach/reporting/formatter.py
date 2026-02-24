"""Markdown report formatter — S4-US4."""

from __future__ import annotations

from pathlib import Path

from racing_coach.reporting.models import CornerReport, LapReport

_SEVERITY_LABEL: dict[str, str] = {
    "high": "高优先级",
    "medium": "中优先级",
    "low": "低优先级",
}


def _format_corner(cr: CornerReport) -> list[str]:
    lines: list[str] = []

    lines.append(f"### 弯道 {cr.corner_id}  (时间损失: {cr.delta_total:+.3f}s)")
    lines.append("")
    lines.append(
        "| 阶段 | 时间差 |\n"
        "|------|--------|\n"
        f"| 入弯 | {cr.delta_entry:+.3f}s |\n"
        f"| 弯心 | {cr.delta_apex:+.3f}s |\n"
        f"| 出弯 | {cr.delta_exit:+.3f}s |"
    )
    lines.append("")

    if cr.braking:
        b = cr.braking
        lock_str = " **⚠ 轮胎抱死**" if b.lock_detected else ""
        lines.append(
            f"- **刹车**: 刹车点偏差 {b.brake_point_delta_m:+.1f}m，"
            f"峰值压力 {b.peak_pressure:.2f}，"
            f"Trail brake 质量 {b.trail_brake_linearity:.2f}{lock_str}"
        )

    if cr.throttle:
        t = cr.throttle
        early_str = " **⚠ 过早全油门**" if t.too_early_full_throttle else ""
        lines.append(f"- **油门**: 重叠帧 {t.overlap_count} 个{early_str}")

    if cr.apex_speed:
        a = cr.apex_speed
        slow_str = " **⚠ 偏慢**" if a.too_slow else ""
        lines.append(f"- **弯心速度**: {a.delta_kph:+.1f} km/h vs 参考圈{slow_str}")

    if cr.suggestions:
        lines.append("")
        lines.append("**建议**:")
        for s in cr.suggestions:
            label = _SEVERITY_LABEL.get(s.severity, s.severity)
            lines.append(f"  - [{label}] {s.suggestion}")

    lines.append("")
    return lines


class MarkdownFormatter:
    """Format a :class:`~racing_coach.reporting.models.LapReport` as Markdown."""

    def format(self, report: LapReport) -> str:
        """Return the full Markdown report as a string."""
        lines: list[str] = []

        # Header
        lines += [
            "# 圈速分析报告",
            "",
            f"**赛道**: {report.track}  ",
            f"**车辆**: {report.car}  ",
            f"**Session**: {report.session_id} / 第 {report.lap_number} 圈  ",
            f"**总时间差**: {report.total_delta_s:+.3f}s",
            "",
        ]

        # Summary
        if report.summary:
            lines += ["## 概要", "", report.summary, ""]

        # Per-corner analysis
        lines += ["## 逐弯分析", ""]
        for corner in report.corners:
            lines.extend(_format_corner(corner))

        # Top improvements
        if report.top_improvements:
            lines += ["## 优先改进建议", ""]
            for i, s in enumerate(report.top_improvements[:3], 1):
                label = _SEVERITY_LABEL.get(s.severity, s.severity)
                lines.append(f"{i}. **弯道 {s.corner_id}** [{label}]: {s.suggestion}")
            lines.append("")

        return "\n".join(lines)

    def write(self, report: LapReport, path: str) -> None:
        """Write the formatted report to *path* (UTF-8)."""
        Path(path).write_text(self.format(report), encoding="utf-8")
