import pandas as pd, matplotlib.pyplot as plt
df = pd.read_csv('bmode_output.csv', index_col=0)
plt.imshow(df, aspect='auto', cmap='gray', vmin=-50, vmax=0, origin='upper')
plt.colorbar(); plt.show()