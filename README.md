# Working group details
Group 13
Team members: Maria, Hector Gutierrez, Lina.
The work showed on the following repo, was done and distributed in equal parts, divided in several in person sessions of work. Testing of the different sets of features was assisted by in person work, and the collaborative use of the LLM "Claude".

# TCP-Signal Visualization App

This project was developed and tested using Python 3.12.

## What this project is

This is a desktop application, built with PySide6, for watching and analyzing multi-channel signal
data (EMG, in our case) as it streams in over TCP from a separate server. Rather than the server
producing raw numbers you have to make sense of yourself, the app connects to it, receives packets
of data continuously, and turns them into something you can actually look at: live scrolling plots,
a full 32-channel overview, and a separate offline view for combing through everything that's been
recorded once the stream stops.

Under the hood it's organized around a fairly classic MVVM split — a model that only knows about
sockets and bytes, a view-model that holds the app's state and logic, and views that just draw
whatever the view-model tells them to. The idea is that the pieces stay decoupled enough that, say,
the signal processing or the TCP handling could be tested or reused without dragging the GUI along
with them.

A bit more concretely, the app:
- Opens and manages a TCP connection to the signal server, with a port field, connection-status
  feedback, and start/stop controls, so you're never left wondering whether it's connected or not.
- Reassembles the incoming byte stream — 32 channels × 18 samples per packet — into proper numeric
  arrays, since TCP gives no guarantee that one `recv()` call lines up neatly with one packet.
- Draws a live, scrolling view of whichever channel you're currently interested in, rendered with
  VisPy for performance, with readable axes and a moving time scale.
- Offers a "Plot All Channels" view so you can see everything at once, each channel stacked with a
  vertical offset so 32 overlapping lines don't turn into visual noise.
- Lets you switch between the raw signal, a rolling RMS envelope, and a smoothed/filtered version —
  in both the live view and after the fact — so you can compare how each one reads.
- Keeps the entire recording around (not just what's currently on screen) so that once you stop
  streaming, you can reopen it in a Matplotlib window and inspect the whole thing at your own pace.
- Tries hard not to crash. A server that isn't there, a wrong port, a connection that drops mid
  stream, an out-of-range channel — these should all show up as a message in the status bar, not a
  stack trace.

## Getting it running

You'll need Python 3.12 and Git.

**1. Clone the repository**

```
git clone https://github.com/ElderZeus/AP-SuSe2026-Final-Project.git
cd <your-repo-folder>
```

**2. Create a virtual environment**

On Linux/macOS:

```
python3 -m venv .venv
```

On Windows:

```
python -m venv .venv
```

This creates a `.venv` folder that Git won't track — it's just your local Python environment.

**3. Activate it**

On Linux/macOS:

```
source .venv/bin/activate
```

On Windows (PowerShell):

```
.venv\Scripts\Activate.ps1
```

You'll know it worked because your shell prompt will be prefixed with `(.venv)`.

**4. Install the dependencies**

```
pip install -r requirements.txt
```

This pulls in numpy, matplotlib, PySide6, and VisPy — everything the app needs.

**5. Run it**

```
python main.py
```

Just make sure the virtual environment is active whenever you run the app or install anything new.

## Connecting to the server

Once the app is open, connecting to a running server is meant to be quick:

1. Start the TCP server on whichever machine and port you're streaming
   from.
2. Type that port into the **Port** field in the top-left of the window. It defaults to `12345`,
   which is also what the app tries first if you don't change it. Once you're connected, this field
   locks so you can't edit it out from under an active stream.
3. Hit **Start Plotting**. If the connection succeeds, streaming begins immediately, the button
   relabels itself to **Stop Plotting**, and the status line confirms you're connected.
4. If something goes wrong — the server isn't up, the port's wrong, or the connection drops partway
   through — you'll get a status message instead of a crash. That's handled in
   `MainViewModel.connect_to_server`.
5. **Stop Plotting** disconnects, but it doesn't throw away what you've recorded. Everything received
   during the session stays available for offline inspection until you close the app.

Above the plot, a **Signal time** label keeps a running total of how much signal has been received
(samples received divided by the sampling rate) — this is independent of whatever slice of it
happens to be visible in the rolling window at the moment.

### What the server needs to match

The app currently expects a server with a specific shape, hardcoded in `MainViewModel.__init__`. If
your server is set up differently, this is the value to change:

| Parameter            | Value                          |
|-----------------------|--------------------------------|
| Host                  | `localhost`                     |
| Default port          | `12345` (changeable in the UI)  |
| Sampling rate         | `2000` Hz                       |
| Channels              | `32`                            |
| Samples per packet    | `18`                            |
| Live rolling window   | `10` seconds                    |

Each packet is expected to arrive as a raw `float64` byte blob shaped `(32, 18)` — in other words,
whatever `current_window.tobytes()` produces on the server side.

## Watching the live signal

By default, the main view shows one channel at a time, scrolling through a 10-second window with
VisPy, complete with axes and a moving time scale along the bottom.

- The **Channel** spin box picks which of the 32 channels you're currently watching.
- The **Signal mode** dropdown switches how that channel is processed before it's drawn:
  - `original` — the raw signal, untouched.
  - `rms` — a rolling root-mean-square envelope (a 50-sample window, roughly 25 ms at the server's
    2000 Hz sampling rate), which smooths the signal into something closer to an amplitude envelope.
  - `filtered` — a simple moving-average low-pass filter over a 5-sample window.

  These window sizes live as constants (`RMS_WINDOW`, `FILTER_WINDOW`) on `MainViewModel`
  (`viewmodels/mainViewModel.py`), and whichever mode you pick applies consistently across the live
  view, the all-channels view, and the offline view — so switching modes never gives you a different
  answer depending on which window happens to be open.
- The **Y scale** field controls the plot's vertical range by hand.
- **Auto Scale Y** does that for you instead — it continuously resizes the Y axis to fit whatever's
  currently on screen, with a bit of headroom (20%) so the signal doesn't touch the edges, and a
  floor so the axis doesn't collapse to nothing if the signal goes flat or hits zero. While it's on,
  the **Y scale** field is disabled; turning it back off hands control back to whatever value is
  sitting in that field.

## Looking at everything at once

**Plot All Channels** swaps the main view for an overview of all 32 channels simultaneously, each
one stacked vertically with a fixed offset so they don't pile on top of each other, and labeled on
the left so you can tell them apart. Click the button again — it now reads **Show Single Channel** —
to go back to the single-channel view. Both views are just two windows onto the same underlying
state, so they share the same rolling time window, signal mode, and moving time axis.

## Digging into a full recording afterward

**Offline Inspection** opens a separate Matplotlib-based window for looking at the *entire*
recording — not just whatever's currently in the rolling live window. It works whether you're still
streaming (it'll stop the stream for you first), already stopped, or never started a live view at
all.

- The **Channel** and **Mode** controls in that window work the same as the live ones, and the plot
  redraws itself automatically whenever you change either. There's also a **Refresh** button, useful
  if you've kept streaming since you opened the window and want to pull in what's new.
- If you open it before recording anything, you'll get a plain message saying so instead of a blank
  or broken chart.
- Channel and mode selection are shared between the offline view and the live view, so changing
  either one in one window is reflected in the other.

## When things go wrong

The app is written to fail gracefully rather than crash outright. That covers a server that isn't
running, a bad port, a connection that drops mid-stream, an invalid channel index, an unrecognized
signal mode, and asking for an offline plot before anything's been recorded. In every one of those
cases, what you get is a status message in the GUI (via the `status_updated` signal) rather than an
unhandled exception taking the whole app down.

## How the code is organized (MVVM)

- **`models/tcp_client_model.py`** — `TcpClientModel` owns the raw socket and is the only place that
  deals with bytes directly. It reassembles the incoming stream into fixed-size packets, and keeps
  two buffers: a rolling one trimmed to the live window, and a second, untrimmed one that holds the
  full recording for offline use. No Qt or GUI code touches this file.
- **`processing/signal_processing.py`** — plain NumPy functions (`compute_rms`, `apply_filter`,
  `process_signal`) with no knowledge of Qt or the rest of the app. This is the one place signal-mode
  logic lives, and it's used identically by the live, all-channels, and offline code paths.
- **`viewmodels/mainViewModel.py`** — `MainViewModel(QObject)` is where the app's state and behavior
  actually live. It polls the model on a timer, runs whatever signal mode is currently selected, and
  exposes everything the views need as Qt signals (`plot_updated`, `all_channels_updated`,
  `offline_data_ready`, `status_updated`, `connection_state_changed`, `signal_time_updated`).
- **`views/mainView.py`** — `MainView(QMainWindow)`, the main window. It wires the GUI controls to
  the view-model and never reaches into `TcpClientModel` directly.
- **`views/plotView.py`** — `VisPyPlotWidget`, the live single-channel plot, with axes and a moving
  time-tick scale.
- **`views/allChannelsPlotView.py`** — `AllChannelsPlotWidget`, the live overview of all 32 channels
  stacked with a fixed vertical offset.
- **`views/offlineView.py`** — `OfflineInspectionView`, the Matplotlib dialog for inspecting a full
  recording, with its own channel and mode controls.
- **`main.py`** — the entry point: builds a `MainViewModel`, hands it to `MainView`, and starts the
  Qt event loop.

Two of the view modules can also be run on their own, without a server or the rest of the app, which
is handy for quick manual checks: `python -m views.allChannelsPlotView` drives the all-channels
widget with synthetic sine waves, and `python -m views.offlineView` opens the offline dialog directly
against a fresh, empty `MainViewModel`.

## License

Licensed under the [GNU GPLv3](LICENSE).
