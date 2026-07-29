import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from models.tcp_client_model import InvalidDataError, TcpClientModel
from processing.signal_processing import process_signal
 
 
class MainViewModel(QObject):
    """
    ViewModel for live plotting and offline inspection: connects/disconnects
    the TCP model, polls it on a QTimer, applies the current signal mode, and
    emits Qt signals driving both the live plot and the offline Matplotlib view.
    """
 
    plot_updated = Signal(object, object)          # (x, y) single channel
    all_channels_updated = Signal(object, object)  # (x, list of 32 processed channel arrays)
    status_updated = Signal(str)
    connection_state_changed = Signal(bool)        # True = connected
    offline_data_ready = Signal(object, object)     # (x, y) for matplotlib
    signal_time_updated = Signal(float)             # elapsed signal time in seconds
 
    RMS_WINDOW = 50        # samples (~25ms at 2000Hz)
    FILTER_WINDOW = 5      # samples, moving average
    CHANNEL_OFFSET = 5.0   # vertical spacing for plot-all-channels

    # In plot-all-channels, each channel is independently rescaled to its
    # own peak so it fits within this fraction of CHANNEL_OFFSET (on each
    # side of its center line) before the offset is applied. Per-channel
    # (rather than one shared scale) keeps every channel's own waveform
    # detail visible, at the cost of absolute amplitude no longer being
    # comparable by eye between channels.
    ALL_CHANNELS_SCALE_FRACTION = 0.4
 
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
        self.mode = "original"
        self.show_all_channels = False
 
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
 
    def connect_to_server(self, port: int):
        if self.is_plotting:
            return

        # The Port spin box already restricts input to integers in range,
        # but that's a UI-layer guarantee, not a guarantee on this method -
        # validate here too so a bad value can never reach socket.connect()
        # (which raises TypeError, not OSError, on a non-int port).
        if not isinstance(port, int) or isinstance(port, bool) or not (1 <= port <= 65535):
            self.status_updated.emit(
                f"Invalid port: {port!r}. Must be an integer between 1 and 65535."
            )
            self.connection_state_changed.emit(False)
            return

        self.model.port = port
        try:
            self.model.connect()
        except (OSError, TypeError, ValueError) as error:
            self.status_updated.emit(f"Could not connect to server: {error}")
            self.connection_state_changed.emit(False)
            return
        self.is_plotting = True
        self.status_updated.emit("Connected to TCP server.")
        self.connection_state_changed.emit(True)
        self.timer.start(10)
 
    def disconnect_from_server(self):
        if not self.is_plotting:
            return
        self.timer.stop()
        self.model.disconnect()
        self.is_plotting = False
        self.status_updated.emit("Disconnected from TCP server.")
        self.connection_state_changed.emit(False)

    def _abort_stream(self, message: str):
        """Shared teardown for update_plot() bailing out mid-stream (bad
        data or a dropped connection): stop polling, make sure the socket
        is closed, and surface the reason instead of leaving the timer
        running against a dead/invalid stream."""
        self.timer.stop()
        self.model.disconnect()
        self.is_plotting = False
        self.status_updated.emit(message)
        self.connection_state_changed.emit(False)

    def set_channel(self, channel_index: int):
        if channel_index < 0 or channel_index >= self.model.channels:
            self.status_updated.emit(f"Invalid channel: {channel_index}")
            return
        self.selected_channel = channel_index
        self.model.selected_channel = channel_index
 
    def set_mode(self, mode: str):
        if mode not in ("original", "rms", "filtered"):
            self.status_updated.emit(f"Invalid signal mode: {mode}")
            return
        self.mode = mode
 
    def set_plot_all_channels(self, enabled: bool):
        self.show_all_channels = enabled

    def request_offline_plot(self):
        """Switch to offline (matplotlib) inspection: stop live streaming if
        connected, then pull, process, and emit the full recorded buffer for
        the selected channel."""
        if self.is_plotting:
            self.disconnect_from_server()

        if self.model.full_data_buffer.shape[1] == 0:
            self.status_updated.emit(
                "No recorded data yet - connect and stream before inspecting offline."
            )
            self.offline_data_ready.emit(None, None)
            return

        x, y = self.model.get_full_recording(self.selected_channel)
        y_processed = process_signal(
            y,
            mode=self.mode,
            rms_window=self.RMS_WINDOW,
            filter_window=self.FILTER_WINDOW,
        )
        self.offline_data_ready.emit(x, y_processed)
 
    def update_plot(self):
        try:
            self.model.receive_data()
        except InvalidDataError:
            self._abort_stream(
                "Invalid data received - please provide a valid TCP port data source."
            )
            return
        except OSError as error:
            self._abort_stream(f"Connection lost: {error}")
            return

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
        x, channel_matrix = self.model.get_all_channels_window()

        processed_channels = []
        for i, channel_data in enumerate(channel_matrix):
            processed = process_signal(
                channel_data,
                mode=self.mode,
                rms_window=self.RMS_WINDOW,
                filter_window=self.FILTER_WINDOW,
            )

            # Scaled to its own peak so quiet channels don't get flattened
            # out by a louder one elsewhere in the stack - see
            # ALL_CHANNELS_SCALE_FRACTION.
            peak = np.max(np.abs(processed)) if processed.size else 0.0
            scale = (self.CHANNEL_OFFSET * self.ALL_CHANNELS_SCALE_FRACTION) / peak if peak > 0 else 1.0

            offset_signal = processed * scale + i * self.CHANNEL_OFFSET
            processed_channels.append(offset_signal)

        self.all_channels_updated.emit(x, processed_channels)
 