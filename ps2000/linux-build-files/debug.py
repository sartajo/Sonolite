import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =========================
# Settings
# =========================
capture_folder = "captures"   # change this
dt = 80e-9                      # 80 ns (adjust if needed)

align_pulses = True             # align big pulse to same position
overlay_all = False             # plot all on one graph
max_plots = 20                  # limit number of plots (None = all)

# =========================
# Load CSV
# =========================
def load_csv(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    if 'mv' not in df.columns:
        raise ValueError(f"'mv' column missing in {path}")

    v = pd.to_numeric(df['mv'], errors='coerce').to_numpy(dtype=float)
    v = v[np.isfinite(v)]

    return v


# =========================
# Align waveform
# =========================
def align_waveform(v):
    idx = np.argmax(np.abs(v))
    return np.roll(v, -idx)


# =========================
# Load all files
# =========================
pattern = os.path.join(capture_folder, "scan_*.csv")
files = sorted(glob.glob(pattern))

if not files:
    raise RuntimeError("No scan files found")

print(f"Found {len(files)} files")

if max_plots:
    files = files[:max_plots]

all_waveforms = []

# =========================
# Process
# =========================
for f in files:
    try:
        v = load_csv(f)

        if align_pulses:
            v = align_waveform(v)

        all_waveforms.append(v)

    except Exception as e:
        print(f"Skipping {f}: {e}")

# =========================
# Plot
# =========================
if overlay_all:
    plt.figure(figsize=(10, 6))

    for v in all_waveforms:
        t = np.arange(len(v)) * dt * 1e6  # us
        plt.plot(t, v, alpha=0.4)

    plt.title("Overlay of All A-scans")
    plt.xlabel("Time (us)")
    plt.ylabel("Voltage (mV)")
    plt.grid()
    plt.show()

else:
    for i, v in enumerate(all_waveforms):
        t = np.arange(len(v)) * dt * 1e6

        plt.figure(figsize=(8, 4))
        plt.plot(t, v)

        plt.title(f"A-scan {i}")
        plt.xlabel("Time (us)")
        plt.ylabel("Voltage (mV)")
        plt.grid()

        plt.tight_layout()
        plt.show()
