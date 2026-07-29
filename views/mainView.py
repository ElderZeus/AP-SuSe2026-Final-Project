from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from views.plotView import VisPyPlotWidget
from views.allChannelsPlotView import AllChannelsPlotWidget
from views.offlineView import OfflineInspectionView


class MainView(QMainWindow):
    """
    Main application window. Owns the visible widgets and wires ViewModel
    signals to them; the only direct reads of the underlying TcpClientModel
    are for sizing widgets (initial port value, channel count).
    """

    Y_SCALE_MIN = 0.01
    Y_SCALE_MAX = 100000.0
    Y_SCALE_DEFAULT = 300.0

    def __init__(self, view_model):
        super().__init__()

        self.view_model = view_model

        self.setWindowTitle("TCP EMG Viewer")
        self.resize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.time_label = QLabel("Signal time: 0.00 s")
        self.time_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)

        control_layout = QVBoxLayout()
        control_layout.setSpacing(8)

        self.port_label = QLabel("Port")
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(self.view_model.model.port)

        self.y_scale_label = QLabel("Y scale")
        self.y_scale_input = QDoubleSpinBox()
        # Deliberately wider than Y_SCALE_MIN/MAX: QDoubleSpinBox would
        # otherwise silently clamp an out-of-range value to the nearest
        # boundary on its own, before _validate_y_scale ever gets a look at
        # it - which would defeat the "reset to default" behavior below.
        self.y_scale_input.setRange(-1_000_000.0, 1_000_000.0)
        self.y_scale_input.setValue(self.Y_SCALE_DEFAULT)
        self.y_scale_input.setSingleStep(50.0)
        self.y_scale_input.setDecimals(2)

        self.auto_scale_button = QPushButton("Auto Scale Y")
        self.auto_scale_button.setCheckable(True)

        self.channel_label = QLabel("Channel")
        self.channel_input = QSpinBox()
        self.channel_input.setRange(0, max(0, self.view_model.model.channels - 1))
        self.channel_input.setValue(self.view_model.selected_channel)

        self.mode_label = QLabel("Signal mode")
        self.mode_input = QComboBox()
        self.mode_input.addItems(["original", "rms", "filtered"])
        mode_index = self.mode_input.findText(self.view_model.mode)
        if mode_index >= 0:
            self.mode_input.setCurrentIndex(mode_index)

        self.all_channels_button = QPushButton("Plot All Channels")
        self.all_channels_button.setCheckable(True)

        self.offline_button = QPushButton("Offline Inspection")

        self.info_label = QLabel("Start the TCP server first.")
        self.toggle_button = QPushButton("Start Plotting")

        control_layout.addWidget(self.port_label)
        control_layout.addWidget(self.port_input)
        control_layout.addWidget(self.y_scale_label)
        control_layout.addWidget(self.y_scale_input)
        control_layout.addWidget(self.auto_scale_button)
        control_layout.addWidget(self.channel_label)
        control_layout.addWidget(self.channel_input)
        control_layout.addWidget(self.mode_label)
        control_layout.addWidget(self.mode_input)
        control_layout.addWidget(self.all_channels_button)
        control_layout.addWidget(self.offline_button)
        control_layout.addStretch()
        control_layout.addWidget(self.info_label)
        control_layout.addWidget(self.toggle_button)

        self.plot_widget = VisPyPlotWidget(
            visible_duration_seconds=10.0,
            y_scale=self.y_scale_input.value(),
        )
        self.all_channels_widget = AllChannelsPlotWidget(
            num_channels=self.view_model.model.channels,
            channel_offset=self.view_model.CHANNEL_OFFSET,
        )

        self.plot_stack = QStackedWidget()
        self.plot_stack.addWidget(self.plot_widget)
        self.plot_stack.addWidget(self.all_channels_widget)

        self.offline_view = OfflineInspectionView(self.view_model, self)

        content_layout.addLayout(control_layout, stretch=0)
        content_layout.addWidget(self.plot_stack, stretch=1)

        main_layout.addWidget(self.time_label)
        main_layout.addLayout(content_layout)

        self.toggle_button.clicked.connect(self.toggle_plotting)
        self.y_scale_input.valueChanged.connect(self.plot_widget.set_y_scale)
        self.y_scale_input.editingFinished.connect(self._validate_y_scale)
        self.channel_input.valueChanged.connect(self.view_model.set_channel)
        self.mode_input.currentTextChanged.connect(self.view_model.set_mode)
        self.all_channels_button.toggled.connect(self.toggle_all_channels)
        self.offline_button.clicked.connect(self.show_offline_view)
        self.auto_scale_button.toggled.connect(self.toggle_auto_scale)

        self.view_model.plot_updated.connect(self.plot_widget.update_plot)
        self.view_model.all_channels_updated.connect(self.all_channels_widget.update_all_channels)
        self.view_model.status_updated.connect(self.info_label.setText)
        self.view_model.connection_state_changed.connect(self.update_connection_state)
        self.view_model.signal_time_updated.connect(self.update_signal_time)
        self.view_model.signal_time_updated.connect(self.plot_widget.set_signal_time)
        self.view_model.signal_time_updated.connect(self.all_channels_widget.set_signal_time)

    def toggle_plotting(self):
        if self.view_model.is_plotting:
            self.view_model.disconnect_from_server()
        else:
            self.view_model.connect_to_server(self.port_input.value())

    def toggle_all_channels(self, checked):
        self.view_model.set_plot_all_channels(checked)
        self.plot_stack.setCurrentIndex(1 if checked else 0)
        self.all_channels_button.setText(
            "Show Single Channel" if checked else "Plot All Channels"
        )

    def toggle_auto_scale(self, checked):
        self.plot_widget.set_auto_scale(checked)
        self.y_scale_input.setEnabled(not checked)
        if not checked:
            self.plot_widget.set_y_scale(self.y_scale_input.value())

    def _validate_y_scale(self):
        """Reset the Y scale field to its default once the user commits
        (Enter / focus-out) a value outside [Y_SCALE_MIN, Y_SCALE_MAX],
        rather than leaving whatever out-of-range number they typed in
        place."""
        value = self.y_scale_input.value()
        if not (self.Y_SCALE_MIN <= value <= self.Y_SCALE_MAX):
            self.y_scale_input.setValue(self.Y_SCALE_DEFAULT)

    def show_offline_view(self):
        self.offline_view.show()
        self.offline_view.raise_()
        self.offline_view.activateWindow()

    def update_connection_state(self, connected):
        self.toggle_button.setText("Stop Plotting" if connected else "Start Plotting")
        self.port_input.setEnabled(not connected)

    def update_signal_time(self, signal_time_seconds):
        self.time_label.setText(f"Signal time: {signal_time_seconds:.2f} s")
