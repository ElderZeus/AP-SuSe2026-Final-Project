import numpy as np
 
 
def get_channel_data(data: np.ndarray, channel_id: int) -> np.ndarray:
    """Get the samples for one channel out of the full (channels, samples) array."""
    if data.ndim == 1:
        return data
    return data[channel_id, :]
 
 
def compute_rms(data: np.ndarray, window: int) -> np.ndarray:
    """
    Rolling RMS of a 1D signal, same length as the input.
    rms[i] = sqrt(mean(data[i-window+1 : i+1] ** 2))
    Uses a cumulative sum so it doesn't have to resum the window every step.
    """
    data = np.asarray(data, dtype=np.float64)
    squared = data ** 2
    cumsum = np.cumsum(np.insert(squared, 0, 0.0))
 
    rms = np.empty_like(data)
    for i in range(len(data)):
        start = max(0, i - window + 1)
        count = i - start + 1
        window_sum = cumsum[i + 1] - cumsum[start]
        rms[i] = np.sqrt(window_sum / count)
    return rms
 
 
def apply_filter(data: np.ndarray, window: int = 5) -> np.ndarray:
    """Simple moving-average low-pass filter, same length as the input."""
    data = np.asarray(data, dtype=np.float64)
    kernel = np.ones(window) / window
    return np.convolve(data, kernel, mode="same")
 
 
def process_signal(
    data: np.ndarray,
    mode: str,
    rms_window: int = 50,
    filter_window: int = 5,
) -> np.ndarray:
    """Apply original / rms / filtered processing depending on the current mode."""
    if mode == "original":
        return data
    elif mode == "rms":
        return compute_rms(data, rms_window)
    elif mode == "filtered":
        return apply_filter(data, filter_window)
    else:
        raise ValueError(f"Unknown signal mode: {mode!r}")
 