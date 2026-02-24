"""ACC 会话录制脚本 — 将实时遥测数据保存至 SQLite。

用法：
  uv run python scripts/record_session.py
  uv run python scripts/record_session.py --db my_session.db

录制完成后（Ctrl+C），脚本会打印 session_id 和后续分析命令。
"""

from __future__ import annotations

import argparse
import time

from racing_coach.telemetry.acc_parser import ACCParser
from racing_coach.telemetry.acc_reader import ACCLiveConnection
from racing_coach.telemetry.storage import TelemetryStorage

_TARGET_HZ = 60
_SLEEP = 1.0 / _TARGET_HZ


def _make_session_id() -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    return f"session_{ts}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Record ACC telemetry to SQLite")
    ap.add_argument("--db", default="session.db", help="Output SQLite file path")
    args = ap.parse_args()

    session_id = _make_session_id()
    storage = TelemetryStorage(args.db)
    conn = ACCLiveConnection()
    parser = ACCParser()

    print(f"Session ID : {session_id}")
    print(f"Database   : {args.db}")
    print("Connecting to ACC...")

    if not conn.connect():
        print("\n× 连接失败：ACC 未运行，或车辆不在赛道上。")
        storage.close()
        return

    print("✓ 已连接。Ctrl+C 停止录制。\n")
    print(f"{'圈号':>4}  {'帧数':>6}  {'圈时(s)':>8}  {'速度km/h':>10}  坐标(X, Z)")
    print("-" * 60)

    lap_frames: dict[int, int] = {}  # lap_number → frame count
    current_lap = -1

    try:
        while True:
            raw = conn.read_frame()
            if raw is None:
                time.sleep(0.1)
                continue

            frame = parser.parse(raw)
            ts = time.time()
            lap = frame.lap_number

            # Detect lap change and print lap summary
            if lap != current_lap:
                if current_lap >= 0:
                    print(
                        f"{current_lap:>4}  {lap_frames.get(current_lap, 0):>6}  "
                        f"{'完成':>8}"
                    )
                current_lap = lap
                lap_frames[lap] = 0

            lap_frames[lap] = lap_frames.get(lap, 0) + 1

            storage.save_frame(session_id, lap, ts, frame)

            # Save world coordinates (only when non-zero — indicates ACC sent valid data)
            car_x = raw.get("carX", 0.0)
            car_z = raw.get("carZ", 0.0)
            if car_x != 0.0 or car_z != 0.0:
                storage.save_position(session_id, lap, frame.lap_dist_pct, car_x, car_z)

            # Live status line (overwrite in place)
            print(
                f"\r{lap:>4}  {lap_frames[lap]:>6}  "
                f"{frame.lap_time:>8.2f}  "
                f"{frame.speed * 3.6:>9.1f}  "
                f"({car_x:>8.1f}, {car_z:>8.1f})",
                end="",
                flush=True,
            )

            time.sleep(_SLEEP)

    except KeyboardInterrupt:
        print("\n\n录制停止。")
    finally:
        storage.close()
        conn.disconnect()

    total = sum(lap_frames.values())
    laps_recorded = sorted(lap_frames.keys())
    print(f"共录制 {total} 帧，{len(laps_recorded)} 圈（圈号 {laps_recorded}）")
    print("\n分析命令（替换 --lap 和 --ref-lap 为实际圈号）：")
    print(
        f"  uv run python scripts/analyze_session.py \\\n"
        f"    --db {args.db} \\\n"
        f"    --session {session_id} \\\n"
        f"    --lap <分析圈号> \\\n"
        f"    --ref-lap <参考圈号> \\\n"
        f"    --track <赛道名> \\\n"
        f"    --car <车辆名>"
    )


if __name__ == "__main__":
    main()
