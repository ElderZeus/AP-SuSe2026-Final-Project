import socket
import numpy as np


class InvalidDataError(ValueError):
    """Raised when bytes received on the socket decode into non-finite
    (NaN/Inf) values - a sign the source at this host/port isn't actually
    sending the expected float64 (channels, samples_per_packet) signal
    stream, rather than a transient glitch in otherwise-valid data."""


class TcpClientModel:
    """
    TCP client model for receiving EMG data: reassembles the raw float64 byte
    stream (server sends current_window.tobytes()) into
    (channels, samples_per_packet) packets. Keeps a rolling window_seconds
    buffer for live plotting and a separate untrimmed buffer for offline
    inspection.
    """

    def __init__(
        self,
        host,
        port,
        sampling_rate,
        channels,
        samples_per_packet,
        window_seconds,
        selected_channel,
    ):
        self.host = host
        self.port = port
        self.sampling_rate = sampling_rate
        self.channels = channels
        self.samples_per_packet = samples_per_packet
        self.window_seconds = window_seconds
        self.selected_channel = selected_channel

        # IMPORTANT:
        # This must match the dtype used by the server before calling .tobytes().
        self.dtype = np.float64

        self.socket = None
        self.is_connected = False

        self.packet_size = self.channels * self.samples_per_packet
        self.packet_size_bytes = self.packet_size * np.dtype(self.dtype).itemsize

        self.window_size = int(self.sampling_rate * self.window_seconds)

        self.byte_buffer = bytearray()
        self.data_buffer = np.empty((self.channels, 0), dtype=self.dtype)

        # Unlike data_buffer, this is never trimmed. It holds the entire
        # recording since connect() so it can be inspected offline later.
        self.full_data_buffer = np.empty((self.channels, 0), dtype=self.dtype)

        self.total_samples_received = 0

    def connect(self):
        if self.is_connected:
            return

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

        # Non-blocking means recv() will not freeze the GUI if no data is available.
        self.socket.setblocking(False)

        self.is_connected = True

    def disconnect(self):
        self.is_connected = False

        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def receive_data(self):
        """
        TCP is a byte stream: one recv() call may not contain exactly one
        packet, so we first collect bytes, then extract complete packets of
        the expected size.
        """
        if not self.is_connected or self.socket is None:
            return

        while True:
            try:
                new_bytes = self.socket.recv(4096)

                if not new_bytes:
                    self.disconnect()
                    return

                self.byte_buffer.extend(new_bytes)

            except BlockingIOError:
                break

        self._extract_packets_from_buffer()

    def _extract_packets_from_buffer(self):
        packets = []

        while len(self.byte_buffer) >= self.packet_size_bytes:
            packet_bytes = self.byte_buffer[:self.packet_size_bytes]
            del self.byte_buffer[:self.packet_size_bytes]

            packet = np.frombuffer(packet_bytes, dtype=self.dtype)
            packet = packet.reshape(self.channels, self.samples_per_packet)

            packets.append(packet)

        if len(packets) == 0:
            return

        new_data = np.concatenate(packets, axis=1)

        if not np.isfinite(new_data).all():
            # Whatever is on this port, it isn't sending valid float64
            # signal data - stop here rather than plotting garbage or
            # letting NaN/Inf propagate into downstream processing/plotting.
            self.disconnect()
            raise InvalidDataError(
                "Received non-numeric (NaN/Inf) values decoding the byte "
                "stream as float64 signal data."
            )

        self.data_buffer = np.concatenate(
            (self.data_buffer, new_data),
            axis=1,
        )
        self.full_data_buffer = np.concatenate(
            (self.full_data_buffer, new_data),
            axis=1,
        )

        self.total_samples_received += new_data.shape[1]

        if self.data_buffer.shape[1] > self.window_size:
            self.data_buffer = self.data_buffer[:, -self.window_size:]

    def has_data(self):
        return self.data_buffer.shape[1] >= 2

    def get_window(self):
        """x/y for the current rolling window: x in seconds, y is the selected channel."""
        y = self.data_buffer[self.selected_channel, :]

        number_of_samples = y.shape[0]
        x = np.arange(number_of_samples) / self.sampling_rate

        return x, y

    def get_full_recording(self, channel_id):
        """Full-recording counterpart to get_window() - x/y for the entire
        recording since connect(), not just the rolling window."""
        y = self.full_data_buffer[channel_id, :]

        number_of_samples = y.shape[0]
        x = np.arange(number_of_samples) / self.sampling_rate

        return x, y

    def get_all_channels_window(self):
        """x/y for all channels within the current rolling window; y is the
        full (channels, samples) matrix."""
        number_of_samples = self.data_buffer.shape[1]
        x = np.arange(number_of_samples) / self.sampling_rate

        return x, self.data_buffer

    def get_signal_time_seconds(self):
        """Signal time in seconds: total_samples_received / sampling_rate."""
        return self.total_samples_received / self.sampling_rate
