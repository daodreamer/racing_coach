"""手动验证脚本：检查 ACC 共享内存连接是否正常工作。

用法：
  1. 启动 ACC，进入任意练习/比赛会话（车辆需上赛道）
  2. 在另一个终端运行：uv run python scripts/check_acc.py
  3. 观察输出，确认数据随时间变化

退出：Ctrl+C
"""

import time

from racing_coach.telemetry.acc_parser import ACCParser
from racing_coach.telemetry.acc_reader import ACCLiveConnection


def on_state_change(connected: bool) -> None:
    status = "已连接 ✓" if connected else "已断开 ✗"
    print(f"\n[连接状态变化] → {status}\n")


def main() -> None:
    conn = ACCLiveConnection()
    parser = ACCParser()

    conn.register_callback(on_state_change)

    print("正在尝试连接 ACC 共享内存...")
    if not conn.connect():
        print(
            "× 连接失败：ACC 未运行，或不在 Windows 上。\n"
            "  请先启动 ACC 并进入会话，然后重新运行本脚本。"
        )
        return

    print("按 Ctrl+C 退出\n")
    print(
        f"{'速度(km/h)':>10} {'油门':>6} {'刹车':>6} {'档位':>4} "
        f"{'转速':>7} {'纵向G':>7} {'横向G':>7} {'圈位置%':>8} {'圈时(s)':>8}"
    )
    print("-" * 75)

    try:
        while True:
            raw = conn.read_frame()
            if raw is None:
                print("  (未收到数据帧，ACC 可能已退出)")
                time.sleep(1.0)
                continue

            frame = parser.parse(raw)
            speed_kmh = frame.speed * 3.6

            print(
                f"{speed_kmh:>10.1f} "
                f"{frame.throttle:>6.2f} "
                f"{frame.brake:>6.2f} "
                f"{frame.gear:>4d} "
                f"{frame.rpm:>7.0f} "
                f"{frame.g_force_lon:>7.2f} "
                f"{frame.g_force_lat:>7.2f} "
                f"{frame.lap_dist_pct * 100:>7.1f}% "
                f"{frame.lap_time:>8.2f}",
                end="\r",
            )
            time.sleep(0.1)  # 10 Hz 刷新

    except KeyboardInterrupt:
        print("\n\n已退出。")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
