"""
Image Constructor (B-mode Ultrasound Reconstruction)

This script reconstructs a B-mode ultrasound image from a set of captured
A-scan waveforms stored as CSV files.

Workflow:
    - Loads all scan_XXX.csv files from a specified capture folder
    - Extracts time (time_raw) and signal amplitude (mv) from each file
    - Stacks all A-scans to form a 2D data matrix (depth × scan index)
    - Applies signal processing:
        • DC offset removal
        • Envelope detection using the Hilbert transform
        • Optional Time Gain Compensation (TGC)
        • Log compression (dB scaling)
    - Converts time-of-flight to depth using:
        depth = (c * t) / 2
    - Displays and saves the final grayscale B-mode image

Key Notes:
    - Each CSV corresponds to one scan position (angle)
    - Scan order determines the horizontal axis of the image
    - Speed of sound (c) is assumed constant (e.g., water = 1480 m/s)
    - Output image is saved in the same capture folder as bmode.png

Inputs:
    - Capture folder containing scan_XXX.csv files

Output:
    - B-mode image (grayscale, depth vs. scan index)

Dependencies:
    - numpy, pandas, scipy, matplotlib

Usage:
    python3 image_constructor.py <capture_folder>
    
    Authored by Omar Sartaj
    
"""

import sys
import os
import glob
import numpy as np
import pandas as pd
from scipy.signal import hilbert
import matplotlib.pyplot as plt

# =========================
# Settings
# =========================
c = 1480               # speed of sound in water (m/s)
dynRange_dB = 50       # display dynamic range
useTGC = True          # time gain compensation on/off
tgc_alpha = 3         # TGC strength

# =========================
# Parse input folder
# =========================
if len(sys.argv) < 2:
    raise ValueError("Usage: python3 bMode.py <capture_folder>")

capture_folder = sys.argv[1]
pattern = os.path.join(capture_folder, "scan_*.csv")

files = sorted(glob.glob(pattern))
if not files:
    raise FileNotFoundError(f"No files found matching: {pattern}")

print(f"Found {len(files)} scan files in {capture_folder}")

# =========================
# Helper: load one CSV A-scan
# =========================
def load_csv(path: str):
    df = pd.read_csv(path)
    df.columns = [col.strip().lower() for col in df.columns]

    if 'time_raw' not in df.columns or 'mv' not in df.columns:
        raise ValueError(
            f"Expected columns time_raw and mv in {path}, found {list(df.columns)}"
        )

    t_raw = pd.to_numeric(df['time_raw'], errors='coerce').to_numpy(dtype=np.float64)
    v_mv = pd.to_numeric(df['mv'], errors='coerce').to_numpy(dtype=np.float64)

    mask = np.isfinite(t_raw) & np.isfinite(v_mv)
    t_raw = t_raw[mask]
    v_mv = v_mv[mask]

    return t_raw, v_mv

# =========================
# Load first file for reference
# =========================
t_raw_ref, a_ref = load_csv(files[0])
N = len(t_raw_ref)
K = len(files)

# IMPORTANT:
# Your C code writes time_raw directly from ps2000_get_times_and_values().
# Depending on the selected Pico timebase, that may be ns/us/ms/etc.
#
# For now, this assumes time_raw is in microseconds and converts to seconds.
# If your depth axis looks wrong, this is the FIRST thing to adjust.
t = t_raw_ref * 1e-6   # assume microseconds -> seconds

B = np.zeros((N, K), dtype=np.float32)

# =========================
# Load all A-scans
# =========================
for k, fname in enumerate(files):
    t_raw_k, a = load_csv(fname)
    a = a.astype(np.float32)

    if len(a) != N:
        print(f"Warning: length mismatch in {fname} "
              f"(got {len(a)}, expected {N}). Trunc/pad applied.")
        aa = np.zeros(N, dtype=np.float32)
        nmin = min(N, len(a))
        aa[:nmin] = a[:nmin]
        a = aa

    B[:, k] = a

# =========================
# Crop pre-trigger (t < 0)
# =========================
valid = t >= 0
t = t[valid]
B = B[valid, :]

# =========================
# Envelope detection
# =========================
B = B - np.mean(B, axis=0)
env = np.abs(hilbert(B.astype(np.float64), axis=0))
env = env / (env.max() + np.finfo(float).eps)

# =========================
# Optional TGC
# =========================
if useTGC and len(t) > 0 and t.max() > 0:
    g = np.exp(tgc_alpha * (t / t.max()))
    env = env * g[:, np.newaxis]
    env = env / (env.max() + np.finfo(float).eps)

# =========================
# Log compression
# =========================
env_db = 20 * np.log10(env + 1e-12)

# =========================
# Convert time -> depth (mm)
# =========================
depth_mm = (c * t / 2.0) * 1000.0

# =========================
# Plot and save
# =========================
fig, ax = plt.subplots(figsize=(10, 6))
im = ax.imshow(
    env_db,
    aspect='auto',
    cmap='gray',
    vmin=-dynRange_dB,
    vmax=0,
    extent=[0, K - 1, depth_mm[-1], depth_mm[0]],
    origin='upper'
)

plt.colorbar(im, ax=ax, label='dB')
ax.set_xlabel('Capture Index')
ax.set_ylabel('Depth (mm)')
ax.set_title(f'B-mode (Envelope + Log) | Water c={c} m/s | DR={dynRange_dB} dB')

plt.tight_layout()

output_png = os.path.join(capture_folder, "bmode.png")
plt.savefig(output_png, dpi=300, bbox_inches='tight')
print(f"Saved image to {output_png}")

plt.show()
