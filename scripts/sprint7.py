"""Sprint 7 — TTS voice commentary + overlay entry point.

Combines the Sprint 6 hot-path (brake cues + lock alerts) with:
- Per-corner TTS commentary after each corner exit
- Always-on-top overlay showing delta and pedal comparison

Requires ACC running on the same machine.  Press Ctrl+C to quit.

Usage:
    uv run python scripts/sprint7.py
    uv run python scripts/sprint7.py --db session.db --session <id> --ref-lap 1
    uv run python scripts/sprint7.py --no-audio --no-overlay
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
from racing_coach.overlay.renderer import OverlayData  # noqa: E402
from racing_coach.overlay.window import OverlayWindow  # noqa: E402
from racing_coach.telemetry.acc_parser import ACCParser  # noqa: E402
from racing_coach.telemetry.acc_reader import ACCLiveConnection  # noqa: E402
from racing_coach.telemetry.storage import TelemetryStorage  # noqa: E402
from racing_coach.tts.commentary import CornerCommentary  # noqa: E402
from racing_coach.tts.engine import NullTTSEngine, Win32TTSEngine  # noqa: E402

# ---------------------------------------------------------------------------
# Reference data helpers
# ---------------------------------------------------------------------------


def _load_reference_data(
    storage: TelemetryStorage, session_id: str, ref_lap: int
) -> tuple[dict[int, float], dict[int, float], dict[int, float], list]:
    """Load brake, throttle, apex-speed reference data and corner list.

    Returns (brake_pcts, throttle_pcts, apex_speeds_kmh, corners).
    """
    from racing_coach.analysis.apex_speed import ApexSpeedAnalyzer
    from racing_coach.analysis.braking import BrakingAnalyzer
    from racing_coach.analysis.models import LapFrame
    from racing_coach.analysis.throttle import ThrottleAnalyzer
    from racing_coach.track.centerline import CenterlineExtractor
    from racing_coach.track.detector import CornerDetector

    ref_rows = storage.get_lap(session_id, ref_lap)
    if not ref_rows:
        print("WARNING: No reference lap frames found.", file=sys.stderr)
        return {}, {}, {}, []

    pts = storage.get_lap_as_track_points(session_id, ref_lap)
    if not pts:
        print("WARNING: No track points for reference lap.", file=sys.stderr)
        return {}, {}, {}, []

    ref_frames = [LapFrame.from_storage_dict(r) for r in ref_rows]
    centerline = CenterlineExtractor().extract([pts])
    corners = CornerDetector().detect(centerline)
    if not corners:
        return {}, {}, {}, []

    # Braking
    braking_events = BrakingAnalyzer().analyze(ref_frames, ref_frames, corners)
    brake_pcts = {
        ev.corner_id: ev.brake_point_pct
        for ev in braking_events
        if ev.brake_point_pct is not None
    }

    # Throttle
    throttle_events = ThrottleAnalyzer().analyze(ref_frames, ref_frames, corners)
    throttle_pcts = {ev.corner_id: ev.throttle_point_pct for ev in throttle_events}

    # Apex speeds
    apex_results = ApexSpeedAnalyzer().analyze(ref_frames, ref_frames, corners)
    apex_speeds = {r.corner_id: r.ref_min_speed_mps * 3.6 for r in apex_results}

    return brake_pcts, throttle_pcts, apex_speeds, corners


def _load_ref_lap_frames(
    storage: TelemetryStorage, session_id: str, ref_lap: int
) -> list:
    """Load reference lap frames for the overlay pedal comparison."""
    from racing_coach.analysis.models import LapFrame

    rows = storage.get_lap(session_id, ref_lap)
    return [LapFrame.from_storage_dict(r) for r in rows] if rows else []


def _find_ref_pedals(
    ref_frames: list, lap_dist_pct: float
) -> tuple[float, float]:
    """Interpolate reference throttle/brake at the given track position."""
    if not ref_frames:
        return 0.0, 0.0
    # Binary-search closest frame
    lo, hi = 0, len(ref_frames) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if ref_frames[mid].lap_dist_pct < lap_dist_pct:
            lo = mid + 1
        else:
            hi = mid
    f = ref_frames[lo]
    return f.throttle, f.brake


# ---------------------------------------------------------------------------
# Audio helpers (carry over from sprint6)
# ---------------------------------------------------------------------------


def _play_brake_cue(audio, cfg: AudioConfig) -> None:
    audio.play(cfg.brake_freq, 80)
    time.sleep(0.10)
    audio.play(cfg.brake_freq, 80)


def _play_lock_alert(audio, cfg: AudioConfig) -> None:
    audio.play(cfg.lock_freq, 350)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Racing Coach — Sprint 7 (TTS + Overlay)")
    ap.add_argument("--db", default="session.db")
    ap.add_argument("--session", default="")
    ap.add_argument("--ref-lap", type=int, default=1)
    ap.add_argument("--track-length", type=float, default=4000.0)
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--no-tts", action="store_true")
    ap.add_argument("--no-overlay", action="store_true")
    args = ap.parse_args()

    # ---- Audio (beeps) ----
    cfg = AudioConfig()
    audio = NullAudioPlayer() if args.no_audio or sys.platform != "win32" else WinsoundPlayer(cfg)

    # ---- TTS ----
    tts = NullTTSEngine() if args.no_tts or sys.platform != "win32" else Win32TTSEngine()

    # ---- Reference data ----
    brake_pcts: dict[int, float] = {}
    throttle_pcts: dict[int, float] = {}
    apex_speeds: dict[int, float] = {}
    corners: list = []
    ref_frames: list = []

    if args.session:
        storage = TelemetryStorage(args.db)
        try:
            brake_pcts, throttle_pcts, apex_speeds, corners = _load_reference_data(
                storage, args.session, args.ref_lap
            )
            ref_frames = _load_ref_lap_frames(storage, args.session, args.ref_lap)
        finally:
            storage.close()
        print(
            f"Reference lap {args.ref_lap}: {len(corners)} corners, "
            f"{len(brake_pcts)} brake cues loaded."
        )

    # ---- Corner commentary ----
    commentary = CornerCommentary(
        tts,
        corners,
        silence_s=3.0,
        ref_apex_speeds=apex_speeds,
        ref_brake_pcts=brake_pcts,
        ref_throttle_pcts=throttle_pcts,
    )

    # ---- Overlay ----
    overlay: OverlayWindow | None = None
    if not args.no_overlay:
        overlay = OverlayWindow()
        overlay.start()

    # ---- Telemetry stream ----
    conn = ACCLiveConnection()
    if not conn.connect():
        print("ACC not detected — waiting for connection...", flush=True)

    stream = TelemetryEventStream(conn, ACCParser(), target_hz=60)
    brake_cue = BrakePointCue(brake_pcts, track_length_m=args.track_length)
    lock_rule = LockAlertRule()
    engine = HotPathEngine(stream, brake_cue, lock_rule, audio, cfg)

    print()
    print("  音效说明:")
    print("    双短音 (bi-bi)  — 制动点提示")
    print("    单长音 (beeeep) — 锁轮警报")
    print("    TTS 语音        — 过弯评语")
    print()
    engine.start()
    print("Sprint 7 running. Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            if not conn.is_connected:
                conn.connect()

            event = stream.get_event(timeout=0.0)
            if event:
                frame = event.frame

                # Hot-path: brake cues and lock alert
                for corner_id in brake_cue.check(frame):
                    _play_brake_cue(audio, cfg)
                    print(f"  [制动点] C{corner_id}  前方 50m", flush=True)

                if lock_rule.check(frame):
                    _play_lock_alert(audio, cfg)
                    print("  [锁轮！] 检测到锁轮", flush=True)
                    commentary.interrupt("Wheel lock detected. Reduce braking pressure.")

                # Warm-path: TTS corner commentary
                commentary.update(frame)

                # Overlay update
                if overlay is not None:
                    ref_thr, ref_brk = _find_ref_pedals(ref_frames, frame.lap_dist_pct)
                    overlay_data = OverlayData(
                        delta_s=0.0,  # cumulative delta requires DeltaCalculator integration
                        throttle=frame.throttle,
                        brake=frame.brake,
                        ref_throttle=ref_thr,
                        ref_brake=ref_brk,
                        lap_dist_pct=frame.lap_dist_pct,
                    )
                    overlay.update(overlay_data)

            time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        if overlay is not None:
            overlay.stop()
        if not args.no_tts:
            tts.shutdown()
        print("\nSprint 7 stopped.")


if __name__ == "__main__":
    main()
