from PySide6.QtCore import QObject, QTimer, Signal
 
from models.tcp_client_model import TcpClientModel
from processing.signal_processing import process_signal
 
 
class MainViewModel(QObject):
    """
    ViewModel for the live plotting view.
    - connects/disconnects the TCP model
    - polls for new data on a QTimer
    - tracks selected channel, signal mode, and plot-all-channels toggle
    - runs processing on the data before sending it to the View
    """
 
    plot_updated = Signal(object, object)          # (x, y) single channel
    all_channels_updated = Signal(object)          # list of 32 processed channel arrays
    status_updated = Signal(str)
    connection_state_changed = Signal(bool)        # True = connected
    offline_data_ready = Signal(object, object)     # (x, y) for matplotlib
    signal_time_updated = Signal(float)             # elapsed signal time in seconds
 
    RMS_WINDOW = 50        # samples (~25ms at 2000Hz)
    FILTER_WINDOW = 5      # samples, moving average
    CHANNEL_OFFSET = 5.0   # vertical spacing for plot-all-channels
 
    def __init__(self):
        super().__init__()
        self.model = TcpClientModel(
            host="localhost",
            port=12345,
            sampling_rate=2000,
            channels=32,
            samples_per_packet=18,
            window_seconds=10,
            selected_channel=1,
        )
 
        self.is_plotting = False
        self.selected_channel = 1
        self.mode = "original"           # "original" | "rms" | "filtered"
        self.show_all_channels = False
 
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
 
    def connect_to_server(self, port: int):
        """Connect to the server on the given port and start updating the plot."""
        if self.is_plotting:
            return
        self.model.port = port
        try:
            self.model.connect()
        except OSError as error:
            self.status_updated.emit(f"Could not connect to server: {error}")
            self.connection_state_changed.emit(False)
            return
        self.is_plotting = True
        self.status_updated.emit("Connected to TCP server.")
        self.connection_state_changed.emit(True)
        self.timer.start(10)
 
    def disconnect_from_server(self):
        """Stop updating the plot and close the TCP connection."""
        if not self.is_plotting:
            return
        self.timer.stop()
        self.model.disconnect()
        self.is_plotting = False
        self.status_updated.emit("Disconnected from TCP server.")
        self.connection_state_changed.emit(False)
 
    def set_channel(self, channel_index: int):
        """Called when the channel dropdown changes."""
        if channel_index < 0 or channel_index >= self.model.channels:
            self.status_updated.emit(f"Invalid channel: {channel_index}")
            return
        self.selected_channel = channel_index
        self.model.selected_channel = channel_index
 
    def set_mode(self, mode: str):
        """Called when the user switches between original/rms/filtered."""
        if mode not in ("original", "rms", "filtered"):
            self.status_updated.emit(f"Invalid signal mode: {mode}")
            return
        self.mode = mode
 
    def set_plot_all_channels(self, enabled: bool):
        """Called when the "Plot All Channels" button is toggled."""
        self.show_all_channels = enabled
 
    def request_offline_plot(self):
        """
        Called by the View to switch to offline (matplotlib) inspection.
        Stops live streaming if still connected, pulls the full recorded
        buffer for the selected channel, processes it with the current
        mode, and emits it for the offline view.
 
        Assumes TcpClientModel exposes a method to get the full recorded
        signal for a channel (not just the rolling live window) - confirm
        the exact method name/shape with whoever owns the model.
        """
        if self.is_plotting:
            self.disconnect_from_server()
 
        x, y = self.model.get_full_recording(self.selected_channel)
        y_processed = process_signal(
            y,
            mode=self.mode,
            rms_window=self.RMS_WINDOW,
            filter_window=self.FILTER_WINDOW,
        )
        self.offline_data_ready.emit(x, y_processed)
 
    def update_plot(self):
        """
        Called on every timer tick. Pulls new data, processes it according
        to the current mode, and emits it to the View.
        """
        self.model.receive_data()
        self.signal_time_updated.emit(self.model.get_signal_time_seconds())

        if not self.model.has_data():
            return
 
        if self.show_all_channels:
            self._emit_all_channels()
        else:
            self._emit_single_channel()
 
    def _emit_single_channel(self):
        x, y = self.model.get_window()
        y_processed = process_signal(
            y,
            mode=self.mode,
            rms_window=self.RMS_WINDOW,
            filter_window=self.FILTER_WINDOW,
        )
        self.plot_updated.emit(x, y_processed)
 
    def _emit_all_channels(self):
        # needs model.get_all_channels_window() -> (x, Y) with Y shape (32, n_samples)
        x, channel_matrix = self.model.get_all_channels_window()
 
        processed_channels = []
        for i, channel_data in enumerate(channel_matrix):
            processed = process_signal(
                channel_data,
                mode=self.mode,
                rms_window=self.RMS_WINDOW,
                filter_window=self.FILTER_WINDOW,
            )
            offset_signal = processed + i * self.CHANNEL_OFFSET
            processed_channels.append(offset_signal)
 
        self.all_channels_updated.emit(processed_channels)
 