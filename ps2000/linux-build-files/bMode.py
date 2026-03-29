import glob
import numpy as np
import pandas as pd
from scipy.signal import hilbert
import matplotlib.pyplot as plt

pattern = r'/home/omar/Documents/picosdk-c-examples/ps2000/linux-build-files/captures/scan_*.csv'
c = 1480
dynRange_dB = 50
useTGC = False
tgc_alpha = 3

files = sorted(glob.glob(pattern))
if not files:
    raise FileNotFoundError(f'No files found matching: {pattern}')

def load_csv(path: str):
    df = pd.read_csv(path)
    df.columns = [col.strip().lower() for col in df.columns]

    if 'time_raw' not in df.columns or 'mv' not in df.columns:
        raise ValueError(f"Expected columns time_raw and mv in {path}, found {list(df.columns)}")

    t_raw = pd.to_numeric(df['time_raw'], errors='coerce').to_numpy(dtype=np.float64)
    v = pd.to_numeric(df['mv'], errors='coerce').to_numpy(dtype=np.float64)

    mask = np.isfinite(t_raw) & np.isfinite(v)
    t_raw = t_raw[mask]
    v = v[mask]

    return t_raw, v

t_raw_ref, a_ref = load_csv(files[0])
N = len(t_raw_ref)
K = len(files)

B = np.zeros((N, K), dtype=np.float32)

for k, fname in enumerate(files):
    t_raw_k, a = load_csv(fname)

    if len(a) != N:
        aa = np.zeros(N, dtype=np.float32)
        nmin = min(N, len(a))
        aa[:nmin] = a[:nmin]
        a = aa

    B[:, k] = a.astype(np.float32)

# Change this depending on what time_raw actually is
# try ONE of these only:
t = t_raw_ref * 1e-6   # if time_raw is us
# t = t_raw_ref * 1e-3 # if time_raw is ms

valid = t >= 0
t = t[valid]
B = B[valid, :]

# show raw stacked data first
plt.figure(figsize=(10, 6))
plt.imshow(B, aspect='auto', cmap='gray', origin='upper')
plt.title('Raw stacked A-scans')
plt.xlabel('Capture Index')
plt.ylabel('Sample')
plt.tight_layout()
plt.show()

B = B - np.mean(B, axis=0)

env = np.abs(hilbert(B.astype(np.float64), axis=0))
env = env / (env.max() + np.finfo(float).eps)

if useTGC and len(t) > 0 and t.max() > 0:
    g = np.exp(tgc_alpha * (t / t.max()))
    env = env * g[:, np.newaxis]
    env = env / (env.max() + np.finfo(float).eps)

env_db = 20 * np.log10(env + 1e-12)
depth_mm = (c * t / 2) * 1000

plt.figure(figsize=(10, 6))
plt.imshow(
    env_db,
    aspect='auto',
    cmap='gray',
    vmin=-dynRange_dB,
    vmax=0,
    extent=[0, K - 1, depth_mm[-1], depth_mm[0]],
    origin='upper'
)
plt.colorbar(label='dB')
plt.xlabel('Capture Index')
plt.ylabel('Depth (mm)')
plt.title('B-mode (debugged)')
plt.tight_layout()
plt.show()
