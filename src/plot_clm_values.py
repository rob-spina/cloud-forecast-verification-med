"""Mappa dei valori di cloud_state, per capire il significato di ogni valore."""
import glob

import matplotlib.pyplot as plt
import xarray as xr
from matplotlib.colors import BoundaryNorm, ListedColormap

f = sorted(glob.glob("data/clm/*CLM*.nc"))[0]
cs = xr.open_dataset(f).cloud_state.values[::4, ::4]   # 1 pixel su 4, basta per vedere

values = [0, 1, 2, 3, 4, 8]
colors = ["black", "tab:blue", "tab:green", "white", "red", "orange"]
cmap = ListedColormap(colors)
norm = BoundaryNorm([v - 0.5 for v in values] + [8.5], cmap.N)

fig, ax = plt.subplots(figsize=(8, 8))
im = ax.imshow(cs, cmap=cmap, norm=norm)
cbar = fig.colorbar(im, ax=ax, ticks=values, shrink=0.8)
cbar.set_label("valore di cloud_state")
ax.set_title("FCI cloud_state - 20/11/2026 12:00 UTC")
ax.set_axis_off()
fig.savefig("figures/clm_values.png", dpi=120, bbox_inches="tight")
print("salvato figures/clm_values.png")
