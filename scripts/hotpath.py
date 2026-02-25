"""Sprint 6 — real-time hot-path entry point.

Requires ACC running on the same machine.  Press Ctrl+C to quit.

Usage:
    uv run python scripts/hotpath.py
    uv run python scripts/hotpath.py --db session.db --session <id> --ref-lap 1
    uv run python scripts/hotpath.py --no-audio          # disable beeps
"""

from __future__ import annotations

import argparse
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from racing_coach.hotpath.audio import AudioConfig, NullAudioPlayer, WinsoundPlayer  # noqa: E402
from racing_coach.hotpath.engine import HotPathEngine  # noqa: E402
from racing_coach.hotpath.event_stream import TelemetryEventStream  # noqa: E402
from racing_coach.hotpath.rules import BrakePointCue, LockAlertRule  # noqa: E402
from racing_coach.telemetry.acc_parser import ACCParser  # noqa: E402
from racing_coach.telemetry.acc_reader import ACCLiveConnection  # noqa: E402
from racing_coach.telemetry.storage import TelemetryStorage  # noqa: E402


def _build_brake_pcts(
    storage: TelemetryStorage, session_id: str, ref_lap: int
) -> dict[int, float]:
    """Load reference lap and extract per-corner brake points."""
    from racing_coach.analysis.braking import BrakingAnalyzer
    from racing_coach.analysis.models import LapFrame
    from racing_coach.track.centerline import CenterlineExtractor
    from racing_coach.track.detector import CornerDetector

    ref_rows = storage.get_lap(session_id, ref_lap)
    if not ref_rows:
        print("WARNING: No reference lap frames found; brake cue disabled.", file=sys.stderr)
        return {}

    ref_frames = [LapFrame.from_storage_dict(r) for r in ref_rows]
    pts = storage.get_lap_as_track_points(session_id, ref_lap)
    if not pts:
        print("WARNING: No track points for reference lap; brake cue disabled.", file=sys.stderr)
        return {}

    centerline = CenterlineExtractor().extract([pts])
    corners = CornerDetector().detect(centerline)
    if not corners:
        return {}

    events = BrakingAnalyzer().analyze(ref_frames, ref_frames, corners)
    return {ev.corner_id: ev.brake_point_pct for ev in events if ev.brake_point_pct is not None}


def _play_brake_cue(audio, cfg: AudioConfig) -> None:
    """Double short beep — approaching brake point."""
    audio.play(cfg.brake_freq, 80)
    time.sleep(0.10)
    audio.play(cfg.brake_freq, 80)


def _play_lock_alert(audio, cfg: AudioConfig) -> None:
    """Single long high beep — wheel lock detected."""
    audio.play(cfg.lock_freq, 350)


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Racing Coach — real-time hot path")
    ap.add_argument("--db", default="session.db", help="SQLite database path")
    ap.add_argument("--session", default="", help="Session ID for reference lap")
    ap.add_argument("--ref-lap", type=int, default=1, help="Reference lap number")
    ap.add_argument("--track-length", type=float, default=4000.0, help="Track length in metres")
    ap.add_argument("--no-audio", action="store_true", help="Disable audio feedback")
    args = ap.parse_args()

    cfg = AudioConfig()
    audio = NullAudioPlayer() if args.no_audio or sys.platform != "win32" else WinsoundPlayer(cfg)

    brake_pcts: dict[int, float] = {}
    if args.session:
        storage = TelemetryStorage(args.db)
        try:
            brake_pcts = _build_brake_pcts(storage, args.session, args.ref_lap)
        finally:
            storage.close()
        print(f"Loaded {len(brake_pcts)} brake cue point(s) from ref lap {args.ref_lap}.")

    conn = ACCLiveConnection()
    connected = conn.connect()
    if not connected:
        print("ACC not detected — waiting for connection...", flush=True)

    stream = TelemetryEventStream(conn, ACCParser(), target_hz=60)
    cue = BrakePointCue(brake_pcts, track_length_m=args.track_length)
    lock = LockAlertRule()
    engine = HotPathEngine(stream, cue, lock, audio, cfg)

    print()
    print("  音效说明:")
    print("    双短音 (bi-bi)  — 制动点提示，参考圈制动点前 50 m")
    print("    单长音 (beeeep) — 锁轮警报，刹车时检测到轮速突降")
    print()
    engine.start()
    print("Hot path running. Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            if not conn.is_connected:
                conn.connect()

            event = stream.get_event(timeout=0.0)
            if event:
                frame = event.frame
                for corner_id in cue.check(frame):
                    _play_brake_cue(audio, cfg)
                    print(f"  [制动点] C{corner_id}  前方 50m 制动点", flush=True)
                if lock.check(frame):
                    _play_lock_alert(audio, cfg)
                    print("  [锁轮！] 检测到锁轮，减小制动力", flush=True)

            time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        print("\nHot path stopped.")


if __name__ == "__main__":
    main()
