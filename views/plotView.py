from PySide6.QtWidgets import QVBoxLayout, QWidget
from vispy import scene
import numpy as np
import math


class VisPyPlotWidget(QWidget):
    """
    Minimal VisPy plot widget: signal line, axes, and moving time-tick
    labels over a fixed-width rolling window (visible_duration_seconds).

    Time labels move right-to-left from the start, so the visible
    signal-time range is allowed to go negative during the first seconds.
    """

    _AUTO_SCALE_PADDING = 1.2    # 20% headroom above the visible peak
    _AUTO_SCALE_MIN_FLOOR = 1.0  # prevents the axis collapsing on a flat/zero signal

    def __init__(self, visible_duration_seconds=10.0, y_scale=300.0):
        super().__init__()

        self.visible_duration_seconds = visible_duration_seconds
        self.y_scale = y_scale
        self.auto_scale = False

        self.current_signal_time = 0.0
        self.time_tick_step = 5.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.canvas = scene.SceneCanvas(
            keys="interactive",
            show=False,
            bgcolor="white",
            size=(1000, 600),
        )

        self.view = self.canvas.central_widget.add_view()
        self.view.camera = "panzoom"

        self.signal_line = scene.Line(
            pos=np.array([[0.0, 0.0], [0.0, 0.0]], dtype=float),
            color=(0.1, 0.3, 0.8, 1.0),
            parent=self.view.scene,
            width=2,
        )

        self.x_axis_line = scene.Line(
            pos=np.array(
                [[0.0, -self.y_scale], [self.visible_duration_seconds, -self.y_scale]],
                dtype=float,
            ),
            color=(0.0, 0.0, 0.0, 1.0),
            parent=self.view.scene,
            width=1,
        )

        self.y_axis_line = scene.Line(
            pos=np.array(
                [[0.0, -self.y_scale], [0.0, self.y_scale]],
                dtype=float,
            ),
            color=(0.0, 0.0, 0.0, 1.0),
            parent=self.view.scene,
            width=1,
        )

        self.tick_line = scene.Line(
            pos=np.empty((0, 2), dtype=float),
            color=(0.0, 0.0, 0.0, 1.0),
            parent=self.view.scene,
            width=1,
            connect="segments",
        )

        self.time_texts = []
        for _ in range(8):
            text = scene.Text(
                text="",
                color="black",
                font_size=10,
                anchor_x="center",
                anchor_y="top",
                parent=self.view.scene,
            )
            self.time_texts.append(text)

        layout.addWidget(self.canvas.native)

        self._update_axes()
        self._update_time_ticks()
        self._update_camera()

    def set_y_scale(self, y_scale):
        self.y_scale = float(y_scale)
        self._update_axes()
        self._update_time_ticks()
        self._update_camera()

    def set_auto_scale(self, enabled):
        """Toggle continuous Y-axis auto-scaling; a pure flag flip that does
        not itself restore the manual scale when disabled."""
        self.auto_scale = bool(enabled)

    def _compute_auto_y_scale(self, y):
        """Half-height that fits the visible signal, with headroom and a floor."""
        peak = float(np.max(np.abs(y))) if y.size else 0.0
        return max(peak * self._AUTO_SCALE_PADDING, self._AUTO_SCALE_MIN_FLOOR)

    def set_signal_time(self, signal_time_seconds):
        self.current_signal_time = float(signal_time_seconds)
        self._update_time_ticks()

    def update_plot(self, x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        if x.size < 2 or y.size < 2:
            return

        newest_time = x[-1]

        # Anchor the newest sample to the window's right edge instead of
        # stretching to fill it, so the signal enters from the right early on.
        display_x = x - newest_time + self.visible_duration_seconds

        keep = (display_x >= 0.0) & (display_x <= self.visible_duration_seconds)
        display_x = display_x[keep]
        y = y[keep]

        if display_x.size < 2:
            return

        pos = np.column_stack((display_x, y))
        self.signal_line.set_data(pos=pos)

        if self.auto_scale:
            self.set_y_scale(self._compute_auto_y_scale(y))
        else:
            self._update_camera()

    def _update_axes(self):
        y_min = -self.y_scale
        y_max = self.y_scale

        self.x_axis_line.set_data(
            pos=np.array(
                [[0.0, y_min], [self.visible_duration_seconds, y_min]],
                dtype=float,
            )
        )

        self.y_axis_line.set_data(
            pos=np.array(
                [[0.0, y_min], [0.0, y_max]],
                dtype=float,
            )
        )

    def _update_time_ticks(self):
        """
        Update moving tick labels for the visible window
        [current_signal_time - visible_duration_seconds, current_signal_time],
        intentionally not clamped to zero (e.g. at current_signal_time=1 the
        range is -9..1, so tick 0 sits near the right edge).
        """
        y_min = -self.y_scale

        tick_height = 0.04 * (2 * self.y_scale)
        label_y = y_min - 0.06 * (2 * self.y_scale)

        visible_start_time = self.current_signal_time - self.visible_duration_seconds
        visible_end_time = self.current_signal_time

        first_tick = math.floor(visible_start_time / self.time_tick_step) * self.time_tick_step

        tick_values = []
        tick_time = first_tick

        while tick_time <= visible_end_time + self.time_tick_step:
            display_x = tick_time - visible_start_time

            # Only non-negative time labels are shown.
            if tick_time >= 0.0 and 0.0 <= display_x <= self.visible_duration_seconds:
                tick_values.append((tick_time, display_x))

            tick_time += self.time_tick_step

        tick_positions = []
        for _, display_x in tick_values:
            tick_positions.append([display_x, y_min])
            tick_positions.append([display_x, y_min + tick_height])

        if tick_positions:
            self.tick_line.set_data(pos=np.asarray(tick_positions, dtype=float))
        else:
            self.tick_line.set_data(pos=np.empty((0, 2), dtype=float))

        for index, text in enumerate(self.time_texts):
            if index < len(tick_values):
                tick_time, display_x = tick_values[index]
                text.text = f"{tick_time:.0f}"
                text.pos = (display_x, label_y)
                text.visible = True
            else:
                text.visible = False

    def _update_camera(self):
        label_space = 0.16 * (2 * self.y_scale)

        self.view.camera.set_range(
            x=(0.0, self.visible_duration_seconds),
            y=(-self.y_scale - label_space, self.y_scale),
            margin=0.02,
        )
