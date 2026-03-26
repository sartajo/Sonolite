import glob
import numpy as np
import pandas as pd
import os

# =========================
# Settings
# =========================
pattern     = r'C:\Users\omarS\Documents\Capstone\Data2\python_Test2_*.csv'
group_size  = 64
out_folder  = r'C:\Users\omarS\Documents\Capstone\Data2\avg2'

os.makedirs(out_folder, exist_ok=True)

# =========================
# Load files
# =========================
files = sorted(glob.glob(pattern))
num_groups = len(files) // group_size

if num_groups == 0:
    raise ValueError(f'Need at least {group_size} files')

def load_csv(path):
    df = pd.read_csv(path, header=0, skiprows=[1])
    df.columns = [c.strip() for c in df.columns]

    time_col = next(c for c in df.columns if 'time' in c.lower())
    volt_col = next(c for c in df.columns if 'channel' in c.lower() or 'ch' in c.lower())

    t = pd.to_numeric(df[time_col], errors='coerce').to_numpy()
    v = pd.to_numeric(df[volt_col], errors='coerce').to_numpy()

    mask = np.isfinite(t) & np.isfinite(v)
    return t[mask], v[mask]

# =========================
# Process groups
# =========================
for g in range(num_groups):
    group_files = files[g*group_size : (g+1)*group_size]

    waveforms = []
    
    t_ref, v_ref = load_csv(group_files[0])
    N = len(v_ref)

    for f in group_files:
        t, v = load_csv(f)
        
        if len(v) != N:
            vv = np.zeros(N)
            nmin = min(len(v), N)
            vv[:nmin] = v[:nmin]
            v = vv
        
        waveforms.append(v)

    waveforms = np.array(waveforms)   # shape: (64, N)

    # average (use abs to avoid cancellation)
    avg_wave = np.mean(np.abs(waveforms), axis=0)

    # use time from first file
    t, _ = load_csv(group_files[0])

    # save new CSV
    df_out = pd.DataFrame({
        'Time (ms)': t,
        'Channel A (V)': avg_wave
    })

    out_path = os.path.join(out_folder, f'avg_{g:03d}.csv')
    df_out.to_csv(out_path, index=False)

    print(f'Saved: {out_path}')