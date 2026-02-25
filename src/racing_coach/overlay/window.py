"""Tkinter-based always-on-top transparent overlay window."""

from __future__ import annotations

import contextlib
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from racing_coach.overlay.renderer import OverlayData

# Colour constants
_BG = "#1a1a1a"
_FG_DELTA_FAST = "#00e676"  # green — faster than reference
_FG_DELTA_SLOW = "#ff5252"  # red — slower
_FG_NEUTRAL = "#ffffff"
_THROTTLE_CLR = "#00e676"
_BRAKE_CLR = "#ff5252"
_REF_CLR = "#888888"
_BAR_W = 20   # pixel width of each pedal bar
_BAR_H = 120  # pixel height of pedal bar


class OverlayWindow:
    """Transparent, always-on-top HUD overlay.

    Displays:
    - Cumulative delta vs reference lap (colour-coded)
    - Throttle/brake bars for the driver and the reference lap

    The Tk event loop runs in a daemon thread.  Call :meth:`update` from any
    thread to push new data; the next ``after`` tick will repaint the canvas.

    Parameters
    ----------
    x, y:
        Initial screen position (pixels from top-left).
    alpha:
        Window transparency 0.0 (invisible) – 1.0 (opaque).  Default 0.85.
    refresh_ms:
        Canvas repaint interval in ms; ≤ 33 gives ≥ 30 fps.
    headless:
        When True, skip Tk initialisation (for unit testing).
    """

    def __init__(
        self,
        x: int = 20,
        y: int = 20,
        alpha: float = 0.85,
        refresh_ms: int = 33,
        headless: bool = False,
    ) -> None:
        self._x = x
        self._y = y
        self._alpha = alpha
        self._refresh_ms = refresh_ms
        self._headless = headless

        self._data: OverlayData | None = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._root = None  # tkinter.Tk, set by _run()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the overlay in a daemon thread."""
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="OverlayThread"
        )
        self._thread.start()

    def update(self, data: OverlayData) -> None:
        """Push new data to the overlay (thread-safe)."""
        with self._lock:
            self._data = data

    def stop(self) -> None:
        """Destroy the overlay window."""
        root = self._root
        if root is not None:
            with contextlib.suppress(Exception):
                root.quit()

    # ------------------------------------------------------------------
    # Internal — runs inside the overlay thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        if self._headless:
            return
        try:
            import tkinter as tk
        except ImportError:
            return

        root = tk.Tk()
        self._root = root
        root.title("Racing Coach HUD")
        root.geometry(f"+{self._x}+{self._y}")
        root.configure(bg=_BG)
        root.wm_attributes("-topmost", True)
        root.wm_attributes("-alpha", self._alpha)
        root.overrideredirect(True)  # remove title bar

        # Delta label
        delta_var = tk.StringVar(value="+0.000")
        delta_lbl = tk.Label(
            root,
            textvariable=delta_var,
            font=("Consolas", 28, "bold"),
            bg=_BG,
            fg=_FG_NEUTRAL,
            width=8,
        )
        delta_lbl.grid(row=0, column=0, columnspan=4, padx=8, pady=(8, 4))

        # Pedal canvas
        canvas = tk.Canvas(root, width=110, height=_BAR_H + 20, bg=_BG, highlightthickness=0)
        canvas.grid(row=1, column=0, columnspan=4, padx=8, pady=(0, 8))

        bar_refs: dict[str, int] = {}  # canvas item ids

        def _create_bars() -> None:
            labels = [("T", 10), ("T ref", 40), ("B", 70), ("B ref", 100)]
            for label, x0 in labels:
                tk.Label(root, text=label, font=("Consolas", 8), bg=_BG, fg=_FG_NEUTRAL)
                # Background track
                canvas.create_rectangle(
                    x0, 5, x0 + _BAR_W, _BAR_H + 5, fill="#333333", outline=""
                )
                # Foreground bar (starts at 0 height)
                colour = (
                    _THROTTLE_CLR
                    if "B" not in label
                    else _BRAKE_CLR
                    if "ref" not in label
                    else _REF_CLR
                )
                bar_id = canvas.create_rectangle(
                    x0, _BAR_H + 5, x0 + _BAR_W, _BAR_H + 5, fill=colour, outline=""
                )
                bar_refs[label] = bar_id

        _create_bars()

        def _refresh() -> None:
            with self._lock:
                data = self._data
            if data is not None:
                # Delta
                sign = "+" if data.delta_s >= 0 else ""
                delta_str = f"{sign}{data.delta_s:.3f}"
                delta_var.set(delta_str)
                colour = _FG_DELTA_SLOW if data.delta_s >= 0 else _FG_DELTA_FAST
                delta_lbl.configure(fg=colour)

                # Bars: height proportional to pedal value
                def _bar_top(pct: float) -> int:
                    return round(_BAR_H + 5 - pct * _BAR_H)

                for label, pct in [
                    ("T", data.throttle),
                    ("T ref", data.ref_throttle),
                    ("B", data.brake),
                    ("B ref", data.ref_brake),
                ]:
                    item = bar_refs.get(label)
                    if item is not None:
                        x0 = canvas.coords(item)[0]
                        x1 = canvas.coords(item)[2]
                        canvas.coords(item, x0, _bar_top(pct), x1, _BAR_H + 5)

            root.after(self._refresh_ms, _refresh)

        root.after(self._refresh_ms, _refresh)
        root.mainloop()
