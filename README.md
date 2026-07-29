# group details:
group 13
Team members: Maria, Hector, Lina
# TCP-Signal Visualization App
This project was developed and tested using Python 3.12.
## Project goal
The goal of this project is to develop a PySide6 desktop application for live visualization and offline inspection of multi‑channel signal data streamed via TCP from a dedicated server. The software will act as a client that connects to the existing TCP server, receives continuous data packets, and makes them accessible for analysis in an intuitive graphical user interface.

Specifically, the application aims to:
- Provide a reliable TCP connection interface, including port configuration, connection status feedback, and start/stop streaming controls.
- Implement robust data handling for 32 channels × 18 samples per packet, converting raw byte streams into numerical arrays suitable for processing.
- Offer real-time visualization of selected channels using VisPy, with a rolling time window, readable axes, and a clear way to switch between channels.
- Enable a Plot All Channels view to quickly inspect simultaneous activity across all 32 channels, using vertical offsets to keep the signals readable.
- Support multiple signal modes (original, RMS, and filtered) for both live and offline views, allowing users to compare different processing approaches.
- Provide offline inspection of recorded signals with Matplotlib, including channel selection and mode switching after streaming has stopped.
- Follow an MVVM-style architecture to separate concerns between data models, viewmodels (application logic and state), and views (GUI and plotting).
- Include basic error handling for common issues such as unavailable server, wrong port, lost connection, or invalid user selections, without crashing the application.
- Deliver clear documentation and dependency management so that the application can be installed and run on a clean environment using only the listed packages.

## Setup
### Prerequisites
Python 3.12 installed on your system.
Git installed to clone the repository.
1. Clone the repository

    git clone <your-repo-url>
    cd <your-repo-folder>

2. Create a virtual environment

On Linux/macOS:

    python3 -m venv .venv

On Windows:

    python -m venv .venv

This creates a local virtual environment in the .venv folder (not tracked by Git).
3. Activate the virtual environment

On Linux/macOS:

    source .venv/bin/activate

On Windows (PowerShell):

    .venv\Scripts\Activate.ps1

After activation, your shell prompt should show (.venv) indicating that you are using the project’s environment.
4. Install dependencies

With the virtual environment activated, install all required packages:

    pip install -r requirements.txt

This will install packages such as numpy, scipy, matplotlib, PySide6, and vispy that are needed for the application.
5. Run the application

    python main.py

Make sure you are inside the activated virtual environment whenever you run the application or install new dependencies.

## Connecting to the TCP server

1. Start the provided TCP server (from Exercise 5) on the machine/port you want to stream from.
2. Enter the server's port in the **Port** field (top-left of the window).
3. Click **Start Plotting** to connect. Streaming starts automatically on a successful connection;
   the button switches to **Stop Plotting** and the status label confirms the connection.
4. If the server isn't running, the wrong port is entered, or the connection drops mid-stream, a
   status message is shown instead of the app crashing (see `MainViewModel.connect_to_server`).
5. Click **Stop Plotting** to disconnect. Disconnecting does not discard the recording — the full
   signal received so far remains available for offline inspection until the app is closed.

## Live plot, channel selection, and signal modes

- The main view plots one selected channel at a time in a rolling 10-second VisPy window, with
  visible axes and moving time labels.
- Use the **Channel** spin box to switch which of the 32 channels is displayed live.
- Use the **Signal mode** dropdown to switch between:
  - `original` — the raw signal, unprocessed.
  - `rms` — a rolling RMS (root-mean-square) envelope, window size `RMS_WINDOW = 50` samples
    (~25 ms at the server's 2000 Hz sampling rate).
  - `filtered` — a moving-average low-pass filter, window size `FILTER_WINDOW = 5` samples.
  Both parameters are defined as class constants on `MainViewModel` (`viewmodels/mainViewModel.py`)
  and apply identically to the live view, the all-channels view, and the offline view.
- Use the **Y scale** field to adjust the live plot's vertical amplitude scaling.

## Plot All Channels

Click **Plot All Channels** to switch the main view to an overview of all 32 channels at once,
stacked vertically with a fixed offset between them so each channel's activity stays readable.
Channel labels are shown to the left of the plot. Click the button again (now labeled
**Show Single Channel**) to return to the single-channel live view. Both views share the same
rolling time window, signal mode, and moving time axis.

## Offline inspection (Matplotlib)

Click **Offline Inspection** to open a separate window for inspecting the *entire* recorded signal
(not just the rolling live window) with Matplotlib. This works whether streaming is currently active
(it will be stopped automatically), already stopped, or was never started at all.

- Use the **Channel** and **Mode** controls in that window to pick what to inspect; the plot
  refreshes automatically on each change, and a **Refresh** button re-pulls the latest recording
  (useful if you've streamed more data since opening the window).
- If no data has been recorded yet, the window shows a friendly message instead of an empty or
  broken plot.
- The offline view and the live view share the same channel/mode selection state, so switching
  channel or mode in one is reflected in the other.

## Error handling

The application avoids crashing on common problems, including: a server that isn't running, a wrong
port, a lost connection mid-stream, an invalid channel index, an invalid signal mode, and requesting
an offline plot before any data has been recorded. In each case a status message is shown in the GUI
(`status_updated`) instead of raising an unhandled exception.

## Project structure (MVVM)

- `models/tcp_client_model.py` — `TcpClientModel`: owns the raw TCP socket, reassembles the byte
  stream into fixed-size packets, and maintains both a rolling live-window buffer and an untrimmed
  full-recording buffer for offline use. Contains no Qt/GUI code.
- `processing/signal_processing.py` — pure NumPy signal processing (`compute_rms`, `apply_filter`,
  `process_signal`), used identically by the live, all-channels, and offline paths.
- `viewmodels/mainViewModel.py` — `MainViewModel(QObject)`: polls the model on a timer, applies the
  selected signal mode, and exposes Qt signals/slots that the views bind to
  (`plot_updated`, `all_channels_updated`, `offline_data_ready`, `status_updated`,
  `connection_state_changed`, `signal_time_updated`). Holds UI-facing state such as the selected
  channel, mode, and plot-all-channels toggle.
- `views/mainView.py` — `MainView(QMainWindow)`: the main window; wires GUI controls to the
  ViewModel and never touches `TcpClientModel` directly.
- `views/plotView.py` — `VisPyPlotWidget`: live single-channel VisPy plot with axes and moving
  time-tick labels.
- `views/allChannelsPlotView.py` — `AllChannelsPlotWidget`: live VisPy overview of all 32 channels,
  stacked with a fixed vertical offset.
- `views/offlineView.py` — `OfflineInspectionView`: Matplotlib-based dialog for offline inspection
  of the full recorded signal, with channel/mode controls.
- `main.py` — entry point: constructs `MainViewModel`, passes it into `MainView`, runs the Qt event
  loop.