import sys

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class OfflineInspectionView(QDialog):
    """
    Matplotlib-based offline inspection dialog.

    Shows the FULL recorded signal (not the rolling live window), with
    channel/mode selection, driven directly through MainViewModel
    (set_channel/set_mode/request_offline_plot plus the offline_data_ready/
    status_updated signals). The one exception to the MVVM boundary is
    reading view_model.model.channels directly, to bound the channel spinbox.
    """

    def __init__(self, view_model, parent=None):
        super().__init__(parent)

        self.view_model = view_model

        self.setWindowTitle("Offline Signal Inspection")
        self.resize(900, 600)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        self.channel_label = QLabel("Channel")
        self.channel_input = QSpinBox()
        self.channel_input.setRange(0, max(0, self.view_model.model.channels - 1))
        self.channel_input.setValue(self.view_model.selected_channel)

        self.mode_label = QLabel("Mode")
        self.mode_input = QComboBox()
        self.mode_input.addItems(["original", "rms", "filtered"])
        mode_index = self.mode_input.findText(self.view_model.mode)
        if mode_index >= 0:
            self.mode_input.setCurrentIndex(mode_index)

        self.refresh_button = QPushButton("Refresh")

        controls_layout.addWidget(self.channel_label)
        controls_layout.addWidget(self.channel_input)
        controls_layout.addWidget(self.mode_label)
        controls_layout.addWidget(self.mode_input)
        controls_layout.addStretch()
        controls_layout.addWidget(self.refresh_button)

        self.figure = Figure(figsize=(8, 5))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111)

        self.status_label = QLabel("")

        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self.canvas, stretch=1)
        main_layout.addWidget(self.status_label)

        self.channel_input.valueChanged.connect(self._on_channel_changed)
        self.mode_input.currentTextChanged.connect(self._on_mode_changed)
        self.refresh_button.clicked.connect(self.view_model.request_offline_plot)

        self.view_model.offline_data_ready.connect(self._on_offline_data_ready)
        self.view_model.status_updated.connect(self.status_label.setText)

    def _on_channel_changed(self, channel_index: int):
        self.view_model.set_channel(channel_index)
        self.view_model.request_offline_plot()

    def _on_mode_changed(self, mode: str):
        self.view_model.set_mode(mode)
        self.view_model.request_offline_plot()

    def _on_offline_data_ready(self, x, y):
        if x is None:
            self.ax.clear()
            self.ax.text(
                0.5,
                0.5,
                "No recorded data yet — connect and stream before inspecting offline.",
                transform=self.ax.transAxes,
                ha="center",
                va="center",
            )
            self.canvas.draw()
            return

        mode = self.view_model.mode
        channel = self.view_model.selected_channel

        self.ax.clear()
        self.ax.plot(x, y)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel(f"Amplitude ({mode})")
        self.ax.set_title(f"Channel {channel} - {mode}")
        self.canvas.draw()

    def showEvent(self, event):
        super().showEvent(event)
        self.view_model.request_offline_plot()


if __name__ == "__main__":
    from viewmodels.mainViewModel import MainViewModel

    app = QApplication(sys.argv)

    view_model = MainViewModel()
    view = OfflineInspectionView(view_model)
    view.show()

    sys.exit(app.exec())
