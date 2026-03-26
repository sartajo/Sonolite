"""
B-mode Ultrasound Reconstruction
Input: one CSV per A-scan capture, with columns:
    Time (ms)  |  Channel A (V)
    (first two rows are header + unit label, data starts row 3)

Dependencies:
    pip install numpy scipy matplotlib pandas
"""

import glob
import numpy as np
import pandas as pd
from scipy.signal import hilbert
import matplotlib.pyplot as plt

# =========================
# Settings (edit if needed)
# =========================
pattern     = r'C:\Users\omarS\Documents\Capstone\Data2/dup\avg_*.csv'   # your file pattern
c           = 1480               # speed of sound in water (m/s)
dynRange_dB = 50                 # display dynamic range (e.g., 40-70)
useTGC      = True               # time gain compensation on/off
tgc_alpha   = 2                # strength of TGC (try 0.5 to 3)

# =========================
# Load file list
# =========================
files = sorted(glob.glob(pattern))
if not files:
    raise FileNotFoundError(f'No files found matching: {pattern}')

# =========================
# Helper: load one CSV A-scan
# CSV format:
#   Row 0: "Time"  "Channel A"         <- column names
#   Row 1: "(ms)"  "(V)"               <- units  (skipped)
#   Row 2+: numeric data
# =========================
def load_csv(path: str):
    # Read with header on row 0, then drop the units row (index 0 after read)
    df = pd.read_csv(path, header=0, skiprows=[1])
    df.columns = [c.strip() for c in df.columns]   # tidy whitespace

    # Accept various column name spellings
    time_col = next((c for c in df.columns if 'time' in c.lower()), None)
    volt_col = next((c for c in df.columns if 'channel' in c.lower() or
                     'ch' in c.lower() or 'volt' in c.lower() or c.strip() == 'A'), None)

    if time_col is None or volt_col is None:
        raise ValueError(f"Cannot identify Time/Voltage columns in {path}.\n"
                         f"Found columns: {list(df.columns)}")

    t_ms = pd.to_numeric(df[time_col], errors='coerce').to_numpy(dtype=np.float64)
    v    = pd.to_numeric(df[volt_col], errors='coerce').to_numpy(dtype=np.float64)

    # Drop any NaN rows
    mask = np.isfinite(t_ms) & np.isfinite(v)
    return t_ms[mask], v[mask]

# =========================
# Load first file for timing reference
# =========================
t_ms_ref, a_ref = load_csv(files[0])
N = len(t_ms_ref)
t = t_ms_ref * 1e-3   # convert ms -> seconds

K = len(files)
B = np.zeros((N, K), dtype=np.float32)

# =========================
# Load all A-scans
# =========================
for k, fname in enumerate(files):
    t_ms_k, a = load_csv(fname)
    a = a.astype(np.float32)

    if len(a) != N:
        print(f'Warning: length mismatch in {fname} '
              f'(got {len(a)}, expected {N}). Trunc/pad applied.')
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
# Envelope detection (Hilbert)
# =========================
B = B - np.mean(B, axis=0)
env = np.abs(hilbert(B.astype(np.float64), axis=0))   # N x K
env = env / (env.max() + np.finfo(float).eps)


# =========================
# Optional TGC (boost deeper echoes)
# =========================
if useTGC:
    g   = np.exp(tgc_alpha * (t / t.max()))   # shape (N,)
    env = env * g[:, np.newaxis]
    env = env / (env.max() + np.finfo(float).eps)

# =========================
# Log compression (dB)
# =========================
env_db = 20 * np.log10(env + 1e-12)

# =========================
# Convert time -> depth (mm)
# =========================
depth_mm = (c * t / 2) * 1000

# =========================
# Display B-mode style image
# =========================
fig, ax = plt.subplots(figsize=(10, 6))
im = ax.imshow(
    env_db,
    aspect='auto',
    cmap='gray',
    vmin=-dynRange_dB, vmax=0,
    extent=[1, K, depth_mm[-1], depth_mm[0]],
    origin='upper'
)
plt.colorbar(im, ax=ax, label='dB')
ax.set_xlabel('Capture Index')
ax.set_ylabel('Depth (mm)')
ax.set_title(f'B-mode (Envelope + Log) | Water c={c} m/s | DR={dynRange_dB} dB')
plt.tight_layout()
plt.show()

