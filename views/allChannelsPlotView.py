from PySide6.QtWidgets import QVBoxLayout, QWidget
from vispy import scene
import numpy as np
import math


class AllChannelsPlotWidget(QWidget):
    """
    VisPy "Plot All Channels" overview widget: all channels stacked
    vertically with a fixed offset.

    Channel i is expected to arrive pre-offset at y = i * channel_offset;
    this widget does not add any offset itself. The y camera range is fixed
    from num_channels/channel_offset with no zoom control, since this is a
    deliberate stacked overview rather than a single-channel view.
    Standalone widget - no shared base class with VisPyPlotWidget.
    """

    def __init__(self, num_channels=32, channel_offset=5.0, visible_duration_seconds=10.0):
        super().__init__()

        self.num_channels = int(num_channels)
        self.channel_offset = float(channel_offset)
        self.visible_duration_seconds = float(visible_duration_seconds)

        self.current_signal_time = 0.0
        self.time_tick_step = 5.0

        self.plot_y_min = -self.channel_offset * 0.5
        self.plot_y_max = (self.num_channels - 1) * self.channel_offset + self.channel_offset * 0.5
        self._full_y_range = self.plot_y_max - self.plot_y_min

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.canvas = scene.SceneCanvas(
            keys="interactive",
            show=False,
            bgcolor="white",
            size=(1000, 700),
        )

        self.view = self.canvas.central_widget.add_view()
        self.view.camera = "panzoom"

        # Only .set_data() is called on these afterwards - never recreated per frame.
        self.channel_lines = []
        placeholder = np.array([[0.0, 0.0], [0.0, 0.0]], dtype=float)
        for _ in range(self.num_channels):
            line = scene.Line(
                pos=placeholder,
                color=(0.1, 0.3, 0.8, 1.0),
                parent=self.view.scene,
                width=1.5,
            )
            self.channel_lines.append(line)

        # Per-channel label in scene/data space (not a floating QLabel) so it
        # pans/zooms with its line. Shown as 1-indexed "Ch {i+1}".
        self.channel_labels = []
        label_x = -0.3
        for i in range(self.num_channels):
            label = scene.Text(
                text=f"Ch {i + 1}",
                color="black",
                font_size=8,
                anchor_x="right",
                anchor_y="center",
                parent=self.view.scene,
            )
            label.pos = (label_x, i * self.channel_offset)
            self.channel_labels.append(label)

        self.x_axis_line = scene.Line(
            pos=np.array(
                [[0.0, self.plot_y_min], [self.visible_duration_seconds, self.plot_y_min]],
                dtype=float,
            ),
            color=(0.0, 0.0, 0.0, 1.0),
            parent=self.view.scene,
            width=1,
        )

        self.y_axis_line = scene.Line(
            pos=np.array(
                [[0.0, self.plot_y_min], [0.0, self.plot_y_max]],
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

        self._update_time_ticks()
        self._update_camera()

    def update_all_channels(self, x, channel_arrays):
        """Slot for all_channels_updated(x, channel_arrays); each array
        arrives with its offset already applied. Anchors the newest sample to
        the window's right edge per channel, same trick as
        VisPyPlotWidget.update_plot."""
        if channel_arrays is None:
            return

        x = np.asarray(x, dtype=float)

        if x.size < 2:
            return

        newest_time = x[-1]

        # Same right-edge-anchor trick as VisPyPlotWidget.update_plot.
        display_x = x - newest_time + self.visible_duration_seconds

        keep = (display_x >= 0.0) & (display_x <= self.visible_duration_seconds)
        display_x = display_x[keep]

        if display_x.size < 2:
            return

        n = min(len(channel_arrays), self.num_channels)
        for i in range(n):
            y = np.asarray(channel_arrays[i], dtype=float)

            # Guard against short/mismatched channel arrays - skip this
            # channel's line rather than crashing.
            if y.size < 2 or y.shape[0] != keep.shape[0]:
                continue

            y_kept = y[keep]

            if y_kept.size < 2:
                continue

            pos = np.column_stack((display_x, y_kept))
            self.channel_lines[i].set_data(pos=pos)

    def set_signal_time(self, signal_time_seconds):
        self.current_signal_time = float(signal_time_seconds)
        self._update_time_ticks()

    def _update_time_ticks(self):
        """Update moving tick labels (same logic as
        VisPyPlotWidget._update_time_ticks, scaled against the fixed
        stacked-channel range instead of a single y_scale)."""
        tick_height = 0.04 * self._full_y_range
        label_y = self.plot_y_min - 0.06 * self._full_y_range

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
            tick_positions.append([display_x, self.plot_y_min])
            tick_positions.append([display_x, self.plot_y_min + tick_height])

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
        """
        Fixed, non-interactive-scale camera range, computed once from
        num_channels/channel_offset (small padding above/below), plus room
        below the x-axis for the moving time-tick labels, and a bit of
        room left of x = 0 for the channel labels.
        """
        label_space = 0.16 * self._full_y_range

        self.view.camera.set_range(
            x=(-1.0, self.visible_duration_seconds),
            y=(self.plot_y_min - label_space, self.plot_y_max),
            margin=0.02,
        )


if __name__ == "__main__":
    # Standalone demo: run with `python -m views.allChannelsPlotView`.
    # No TCP server, no main app, no other files involved - fabricates
    # synthetic data for all 32 channels the same way MainViewModel would
    # (offset already baked in) and feeds it via a QTimer.
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    widget = AllChannelsPlotWidget()
    widget.setWindowTitle("AllChannelsPlotWidget demo")
    widget.resize(1000, 700)
    widget.show()

    NUM_CHANNELS = 32
    CHANNEL_OFFSET = 5.0
    SAMPLE_RATE = 200.0     # samples/second (kept light for a demo)
    WINDOW_SECONDS = 10.0
    N_SAMPLES = int(SAMPLE_RATE * WINDOW_SECONDS)

    state = {"t": 0.0}

    def on_timer():
        state["t"] += 1.0 / 30.0
        current_time = state["t"]

        x = np.linspace(current_time - WINDOW_SECONDS, current_time, N_SAMPLES)

        channel_arrays = []
        for i in range(NUM_CHANNELS):
            freq = 0.5 + 0.05 * i
            phase = i * 0.3
            raw = np.sin(2 * np.pi * freq * x + phase)
            offset_signal = raw + i * CHANNEL_OFFSET
            channel_arrays.append(offset_signal)

        widget.update_all_channels(x, channel_arrays)
        widget.set_signal_time(current_time)

    from PySide6.QtCore import QTimer

    timer = QTimer()
    timer.timeout.connect(on_timer)
    timer.start(33)  # ~30 fps

    sys.exit(app.exec())
