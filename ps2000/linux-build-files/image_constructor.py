"""
Ultrasound B-mode Image Reconstruction with Continuity-Based Echo Tracking

This script processes raw A-scan ultrasound data stored in CSV files and
reconstructs a 2D B-mode image. Each scan is aligned using transmit (TX)
pulse detection, followed by ringdown suppression and time-of-flight
windowing to isolate echo signals.

The RF data is converted to an envelope using the Hilbert transform,
normalized, and log-compressed to generate a grayscale image.

For tracking, the script follows one dominant reflector across scans using
continuity: after the first scan, it prefers peaks close to the previously
tracked depth. This allows gradual motion in depth while remaining more
robust than simple per-scan strongest-peak selection.

Outputs:
- Standard B-mode image (grayscale)
- Hybrid figure with tracked reflector and depth plot
"""

import sys
import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import hilbert, find_peaks
from scipy.ndimage import median_filter

# =========================
# Settings
# =========================
dt = 80e-9
c = 1480.0

pulse_threshold_mv = 220.0
min_pulse_width = 6
refractory_us = 12.0

# Broad echo window
echo_start_us = 50.0
echo_end_us   = 200.0

dynRange_dB = 40
threshold_frac_bmode = 0.08

# Peak detection for tracking
peak_height_frac = 0.18
peak_min_distance_samples = 8

# Continuity tracking
max_depth_jump_mm = 12.0
fallback_to_strongest = True
track_smooth_size = 3

# Optional manual depth guard band
# Leave as None for no manual restriction
track_min_mm = None
track_max_mm = None

# =========================
# Input
# =========================
if len(sys.argv) < 2:
    raise ValueError("Usage: python3 image_constructor_continuity.py <capture_folder>")

capture_folder = sys.argv[1]
pattern = os.path.join(capture_folder, "scan_*.csv")
files = sorted(glob.glob(pattern))

if not files:
    raise FileNotFoundError("No scan files found")

print(f"Found {len(files)} scans")

echo_start_idx = int(round(echo_start_us * 1e-6 / dt))
echo_end_idx   = int(round(echo_end_us   * 1e-6 / dt))
refractory_idx = int(round(refractory_us * 1e-6 / dt))
win_len = echo_end_idx - echo_start_idx

if win_len <= 0:
    raise ValueError("Invalid echo window")

# =========================
# Load CSV
# =========================
def load_csv(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    if 'mv' not in df.columns:
        raise ValueError(f"'mv' column not found in {path}")

    v = pd.to_numeric(df['mv'], errors='coerce').to_numpy(dtype=np.float64)
    v = v[np.isfinite(v)]

    if len(v) == 0:
        raise ValueError(f"No valid mv data in {path}")

    return v

# =========================
# TX Detection
# =========================
def find_tx_pulse(v):
    a = np.abs(v)
    above = a > pulse_threshold_mv
    idxs = np.where(above)[0]

    if len(idxs) == 0:
        return int(np.argmax(a))

    best_idx = None
    best_peak = -np.inf

    run_start = idxs[0]
    run_len = 1

    for k in range(1, len(idxs)):
        if idxs[k] == idxs[k - 1] + 1:
            run_len += 1
        else:
            if run_len >= min_pulse_width:
                peak = np.max(a[run_start:idxs[k]])
                if peak > best_peak:
                    best_peak = peak
                    best_idx = run_start
            run_start = idxs[k]
            run_len = 1

    if run_len >= min_pulse_width:
        peak = np.max(a[run_start:idxs[-1] + 1])
        if peak > best_peak:
            best_peak = peak
            best_idx = run_start

    if best_idx is None:
        return int(np.argmax(a))

    return int(best_idx)

# =========================
# Process one scan
# =========================
def process_ascan(v):
    tx_idx = find_tx_pulse(v)

    v = np.roll(v, -tx_idx)

    # gate TX / ringdown
    gate_end = min(refractory_idx, len(v))
    v[:gate_end] = 0.0

    raw = np.zeros(win_len, dtype=np.float64)
    src1 = min(echo_end_idx, len(v))
    if src1 > echo_start_idx:
        raw[:src1 - echo_start_idx] = v[echo_start_idx:src1]

    # simple detrend
    raw -= np.median(raw)

    env = np.abs(hilbert(raw))
    env /= (np.max(env) + 1e-12)

    bmode = env.copy()
    bmode[bmode < threshold_frac_bmode] = 0.0

    return env, bmode, tx_idx

# =========================
# Candidate peaks in one scan
# =========================
def detect_candidates(env, depth_mm):
    peaks, props = find_peaks(
        env,
        height=peak_height_frac,
        distance=peak_min_distance_samples
    )

    if len(peaks) == 0:
        return []

    heights = props["peak_heights"]
    candidates = []

    for p, h in zip(peaks, heights):
        d = float(depth_mm[p])

        if track_min_mm is not None and d < track_min_mm:
            continue
        if track_max_mm is not None and d > track_max_mm:
            continue

        candidates.append({
            "sample_idx": int(p),
            "depth_mm": d,
            "strength": float(h)
        })

    # strongest first
    candidates.sort(key=lambda x: x["strength"], reverse=True)
    return candidates

# =========================
# Continuity-based tracking
# =========================
def track_reflector(all_candidates):
    tracked_depth = []
    tracked_strength = []
    prev_depth = None

    for i, candidates in enumerate(all_candidates):
        if len(candidates) == 0:
            tracked_depth.append(np.nan)
            tracked_strength.append(np.nan)
            continue

        chosen = None

        # first valid scan: pick strongest candidate
        if prev_depth is None or not np.isfinite(prev_depth):
            chosen = candidates[0]

        else:
            # choose strongest candidate within jump band
            nearby = [
                c for c in candidates
                if abs(c["depth_mm"] - prev_depth) <= max_depth_jump_mm
            ]

            if len(nearby) > 0:
                nearby.sort(key=lambda x: x["strength"], reverse=True)
                chosen = nearby[0]
            elif fallback_to_strongest:
                chosen = candidates[0]

        if chosen is None:
            tracked_depth.append(np.nan)
            tracked_strength.append(np.nan)
        else:
            tracked_depth.append(chosen["depth_mm"])
            tracked_strength.append(chosen["strength"])
            prev_depth = chosen["depth_mm"]

    tracked_depth = np.array(tracked_depth, dtype=float)
    tracked_strength = np.array(tracked_strength, dtype=float)

    # smooth valid values only
    smoothed = tracked_depth.copy()
    valid = np.isfinite(tracked_depth)

    if np.count_nonzero(valid) >= track_smooth_size:
        temp = tracked_depth.copy()
        valid_idx = np.where(valid)[0]
        for i in np.where(~valid)[0]:
            nearest = valid_idx[np.argmin(np.abs(valid_idx - i))]
            temp[i] = tracked_depth[nearest]
        smoothed = median_filter(temp, size=track_smooth_size)
        smoothed[~valid] = np.nan

    return tracked_depth, tracked_strength, smoothed

# =========================
# Process all scans
# =========================
env_cols = []
bmode_cols = []
tx_indices = []

for f in files:
    v = load_csv(f)
    env, bmode, tx_idx = process_ascan(v)

    env_cols.append(env)
    bmode_cols.append(bmode)
    tx_indices.append(tx_idx)

B = np.column_stack(bmode_cols)
E = np.column_stack(env_cols)

B /= (np.max(B) + 1e-12)
E /= (np.max(E) + 1e-12)

# =========================
# Axes
# =========================
t = np.arange(echo_start_idx, echo_end_idx) * dt
depth_mm = (c * t / 2.0) * 1000.0
scan_idx = np.arange(B.shape[1])

# =========================
# Build candidates + track one object
# =========================
all_candidates = []
for col in range(E.shape[1]):
    candidates = detect_candidates(E[:, col], depth_mm)
    all_candidates.append(candidates)

tracked_depth, tracked_strength, tracked_smooth = track_reflector(all_candidates)

valid_tracked = np.isfinite(tracked_depth)
if np.any(valid_tracked):
    print(
        f"Tracked reflector mean depth: "
        f"{np.nanmean(tracked_depth):.2f} mm"
    )
    print(
        f"Tracked reflector depth range: "
        f"{np.nanmin(tracked_depth):.2f} mm to {np.nanmax(tracked_depth):.2f} mm"
    )
else:
    print("No valid reflector track found.")

# =========================
# Log compression
# =========================
B_db = 20 * np.log10(B + 1e-12)
B_db = np.maximum(B_db, -dynRange_dB)

# =========================
# Popup 1: Regular image
# =========================
fig1, ax1 = plt.subplots(figsize=(10, 6))
im1 = ax1.imshow(
    B_db,
    cmap='gray',
    vmin=-dynRange_dB,
    vmax=0,
    aspect='auto',
    extent=[0, B.shape[1] - 1, depth_mm[-1], depth_mm[0]],
    origin='upper'
)
plt.colorbar(im1, ax=ax1, label='dB')
ax1.set_title('Regular Envelope B-mode Image')
ax1.set_xlabel('Capture Index')
ax1.set_ylabel('Depth (mm)')
plt.tight_layout()

regular_output = os.path.join(capture_folder, "final_regular_image.png")
plt.savefig(regular_output, dpi=300, bbox_inches='tight')
print(f"Saved regular image: {regular_output}")

# =========================
# Popup 2: Hybrid tracking figure
# =========================
fig2 = plt.figure(figsize=(10, 10))

# Top
ax2 = plt.subplot(3, 1, 1)
im2 = ax2.imshow(
    B_db,
    cmap='gray',
    vmin=-dynRange_dB,
    vmax=0,
    aspect='auto',
    extent=[0, B.shape[1] - 1, depth_mm[-1], depth_mm[0]],
    origin='upper'
)
ax2.plot(scan_idx, tracked_smooth, 'r-', linewidth=2, label='Tracked reflector')
ax2.set_title('Envelope B-mode with Continuity-Based Reflector Tracking')
ax2.set_xlabel('Capture Index')
ax2.set_ylabel('Depth (mm)')
ax2.legend(loc='upper right')
plt.colorbar(im2, ax=ax2, label='dB')

# Middle
ax3 = plt.subplot(3, 1, 2)
if np.any(np.isfinite(tracked_smooth)):
    zoom_min = max(np.nanmin(tracked_smooth) - 15, depth_mm.min())
    zoom_max = min(np.nanmax(tracked_smooth) + 15, depth_mm.max())
else:
    zoom_min = depth_mm.min()
    zoom_max = depth_mm.max()

zoom_mask = (depth_mm >= zoom_min) & (depth_mm <= zoom_max)
B_zoom = B_db[zoom_mask, :]
depth_zoom = depth_mm[zoom_mask]

im3 = ax3.imshow(
    B_zoom,
    cmap='gray',
    vmin=-dynRange_dB,
    vmax=0,
    aspect='auto',
    extent=[0, B.shape[1] - 1, depth_zoom[-1], depth_zoom[0]],
    origin='upper'
)
ax3.plot(scan_idx, tracked_smooth, 'r-', linewidth=2)
ax3.set_title('Zoomed View Around Tracked Reflector')
ax3.set_xlabel('Capture Index')
ax3.set_ylabel('Depth (mm)')

# Bottom
ax4 = plt.subplot(3, 1, 3)
ax4.plot(scan_idx, tracked_depth, 'o--', alpha=0.5, label='Raw')
ax4.plot(scan_idx, tracked_smooth, 'r-', linewidth=2, label='Smoothed')
ax4.set_title('Tracked Reflector Depth vs Scan')
ax4.set_xlabel('Capture Index')
ax4.set_ylabel('Depth (mm)')
ax4.grid(True)
ax4.legend(loc='best')

plt.tight_layout()

hybrid_output = os.path.join(capture_folder, "final_demo_tracking.png")
plt.savefig(hybrid_output, dpi=300, bbox_inches='tight')
print(f"Saved tracking figure: {hybrid_output}")

print("\n=== FINAL OUTPUT ===")
print(f"Regular image:  {regular_output}")
print(f"Tracking image: {hybrid_output}")

plt.show()
