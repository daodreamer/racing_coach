"""ACC 赛后分析脚本 — 从 SQLite 录制数据生成 Markdown 报告。

用法：
  uv run python scripts/analyze_session.py \\
      --db session.db \\
      --session session_20260224_153000 \\
      --lap 3 \\
      --ref-lap 1 \\
      --track monza \\
      --car ferrari_296gt3 \\
      --track-length-m 5793 \\
      --output report.md

需要 MOONSHOT_API_KEY 环境变量（不设置时自动使用规则引擎兜底）。
"""

from __future__ import annotations

import argparse
import sys

from racing_coach.analysis.apex_speed import ApexSpeedAnalyzer
from racing_coach.analysis.braking import BrakingAnalyzer
from racing_coach.analysis.delta import DeltaCalculator
from racing_coach.analysis.models import LapFrame
from racing_coach.analysis.throttle import ThrottleAnalyzer
from racing_coach.reporting.aggregator import LapReportAggregator
from racing_coach.reporting.formatter import MarkdownFormatter
from racing_coach.reporting.llm_client import MoonshotClient
from racing_coach.telemetry.storage import TelemetryStorage
from racing_coach.track.centerline import CenterlineExtractor
from racing_coach.track.detector import CornerDetector


def _load_frames(storage: TelemetryStorage, session_id: str, lap: int) -> list[LapFrame]:
    rows = storage.get_lap(session_id, lap)
    if not rows:
        print(f"  [!] 未找到数据：session={session_id!r}, lap={lap}", file=sys.stderr)
        sys.exit(1)
    return [LapFrame.from_storage_dict(r) for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate ACC lap analysis report")
    ap.add_argument("--db", required=True, help="SQLite database path")
    ap.add_argument("--session", required=True, help="Session ID from record_session.py")
    ap.add_argument("--lap", type=int, required=True, help="Lap number to analyze")
    ap.add_argument("--ref-lap", type=int, required=True, help="Reference lap number")
    ap.add_argument("--track", default="unknown_track", help="Track name (for report)")
    ap.add_argument("--car", default="unknown_car", help="Car name (for report)")
    ap.add_argument(
        "--track-length-m",
        type=float,
        default=4000.0,
        help="Track length in metres (used for braking distance calculation)",
    )
    ap.add_argument("--output", default="lap_report.md", help="Output Markdown file path")
    args = ap.parse_args()

    print(f"数据库    : {args.db}")
    print(f"Session   : {args.session}")
    print(f"分析圈    : {args.lap}  参考圈: {args.ref_lap}")
    print(f"赛道/车   : {args.track} / {args.car}")
    print()

    storage = TelemetryStorage(args.db)

    # ------------------------------------------------------------------
    # 1. Load telemetry frames
    # ------------------------------------------------------------------
    print("1/6  加载遥测帧...")
    user_frames = _load_frames(storage, args.session, args.lap)
    ref_frames = _load_frames(storage, args.session, args.ref_lap)
    print(f"     分析圈 {len(user_frames)} 帧 / 参考圈 {len(ref_frames)} 帧")

    # ------------------------------------------------------------------
    # 2. Load world coordinates → centerline → corners
    # ------------------------------------------------------------------
    print("2/6  提取赛道中心线与弯道...")
    user_pts = storage.get_lap_as_track_points(args.session, args.lap)
    ref_pts = storage.get_lap_as_track_points(args.session, args.ref_lap)

    if not user_pts or not ref_pts:
        print(
            "  [!] 未找到位置数据（carX/carZ）。\n"
            "    请确认录制时车辆在赛道上，且 ACC 返回了有效世界坐标。",
            file=sys.stderr,
        )
        sys.exit(1)

    centerline = CenterlineExtractor().extract([user_pts, ref_pts])
    corners = CornerDetector().detect(centerline)
    print(f"     检测到 {len(corners)} 个弯道")

    if not corners:
        print("  [!] 未检测到弯道，无法进行逐弯分析。", file=sys.stderr)
        sys.exit(1)

    storage.close()

    # ------------------------------------------------------------------
    # 3. Delta analysis
    # ------------------------------------------------------------------
    print("3/6  计算时间差...")
    corner_deltas = DeltaCalculator().compute_corner_deltas(user_frames, ref_frames, corners)
    total_delta = sum(cd.delta_total for cd in corner_deltas)
    sign = "+" if total_delta >= 0 else ""
    print(f"     总 Delta: {sign}{total_delta:.3f}s")

    # ------------------------------------------------------------------
    # 4. Detailed diagnostics
    # ------------------------------------------------------------------
    print("4/6  刹车 / 油门 / 弯心速度分析...")
    braking_events = BrakingAnalyzer().analyze(
        user_frames, ref_frames, corners, args.track_length_m
    )
    throttle_events = ThrottleAnalyzer().analyze(user_frames, ref_frames, corners)
    apex_results = ApexSpeedAnalyzer().analyze(user_frames, ref_frames, corners)

    # ------------------------------------------------------------------
    # 5. Aggregate + LLM feedback
    # ------------------------------------------------------------------
    print("5/6  聚合报告并调用 LLM...")
    report = LapReportAggregator().aggregate(
        session_id=args.session,
        lap_number=args.lap,
        track=args.track,
        car=args.car,
        total_delta_s=total_delta,
        corner_deltas=corner_deltas,
        braking_events=braking_events,
        throttle_events=throttle_events,
        apex_results=apex_results,
    )
    report = MoonshotClient().analyze(report)

    # ------------------------------------------------------------------
    # 6. Write Markdown
    # ------------------------------------------------------------------
    print(f"6/6  写出报告 → {args.output}")
    MarkdownFormatter().write(report, args.output)
    print(f"\n[OK] 完成：{args.output}")


if __name__ == "__main__":
    main()
