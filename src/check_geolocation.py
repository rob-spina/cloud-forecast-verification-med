"""Test di geolocalizzazione della maschera nubi FCI: ricalcola la griglia con gli assi x/y
invertiti o no e misura la correlazione spaziale con IFS e AIFS. La variante corretta e'
quella con la correlazione piu alta. Con la correzione gia presente in clm_to_grid.py
(segno di x invertito) la variante 'come nel codice' deve risultare la migliore."""
import glob

import numpy as np
import xarray as xr

import clm_to_grid as cg
from plot_first_comparison import VALID, aifs, ifs


def regrid_with_signs(path, sx, sy):
    ds = xr.open_dataset(path)
    ds = ds.assign_coords(x=sx * ds.x, y=sy * ds.y)
    tmp = "data/obs/_tmp.nc"
    ds.to_netcdf(tmp)
    return cg.clm_to_grid(tmp)


def corr(a, b):
    a, b = np.asarray(a).ravel(), np.asarray(b).ravel()
    m = np.isfinite(a) & np.isfinite(b)
    return np.corrcoef(a[m], b[m])[0, 1]


f = sorted(glob.glob(f"data/clm/*CLM*_OPE_{VALID:%Y%m%d%H%M}00_*.nc"))[0]
variants = {"come nel codice": (1, 1), "x invertito": (-1, 1),
            "y invertito": (1, -1), "x e y invertiti": (-1, -1)}
print(f"{'variante':18s} {'IFS~3':>7s} {'IFS~2+3':>8s} {'AIFS~3':>7s} {'AIFS~2+3':>9s}")
for name, (sx, sy) in variants.items():
    g = regrid_with_signs(f, sx, sy)
    print(f"{name:18s} {corr(ifs, g.cloud_frac_full):7.2f} {corr(ifs, g.cloud_frac_any):8.2f} "
          f"{corr(aifs, g.cloud_frac_full):7.2f} {corr(aifs, g.cloud_frac_any):9.2f}")
print(f"\nriferimento, correlazione IFS~AIFS: {corr(ifs, aifs):.2f}")
