import shutil
import os

# input file
src_file = r'C:\Users\omarS\Documents\Capstone\Data2\avg2\avg_000.csv'

# output folder
out_folder = r'C:\Users\omarS\Documents\Capstone\Data2\dup'
os.makedirs(out_folder, exist_ok=True)

# duplicate 64 times
for i in range(64):
    dst = os.path.join(out_folder, f'avg_{i:03d}.csv')
    shutil.copy(src_file, dst)

print("Done duplicating 64 files")