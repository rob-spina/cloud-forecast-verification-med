"""Primo confronto: copertura nuvolosa prevista (IFS, AIFS) e osservata (MTG FCI)."""
import glob

import cartopy.crs as ccrs
import earthkit.data as ekd
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

obs = xr.open_dataset(sorted(glob.glob("data/obs/clm_*.nc"))[0])


def load_tcc(path, scale):
    """Legge tcc da GRIB, converte in %, longitudini -180..180, ritaglia sulla griglia osservata."""
    da = ekd.from_source("file", path).to_xarray()["tcc"] * scale
    da = da.squeeze(drop=True)
    if float(da.longitude.max()) > 180:
        da = da.assign_coords(longitude=((da.longitude + 180) % 360) - 180).sortby("longitude")
    da = da.sortby("latitude")
    return da.sel(latitude=obs.latitude, longitude=obs.longitude, method="nearest")


ifs = load_tcc(sorted(glob.glob("data/ecmwf/ifs_*_tcc_step12.grib2"))[0], 100)      # frazione -> %
aifs = load_tcc(sorted(glob.glob("data/ecmwf/aifs-single_*_tcc_step12.grib2"))[0], 1)  # gia in %

for name, da in [("IFS ", ifs), ("AIFS", aifs)]:
    for ref in ["cloud_frac_full", "cloud_frac_any"]:
        d = np.asarray(da) - obs[ref].values
        m = np.isfinite(d)
        print(f"{name} vs {ref:16s}: bias {d[m].mean():+6.1f}   RMSE {np.sqrt((d[m] ** 2).mean()):5.1f}")
print(f"Media sull'area: IFS {float(ifs.mean()):.1f}%  AIFS {float(aifs.mean()):.1f}%  "
      f"MTG solo 3 {float(obs.cloud_frac_full.mean()):.1f}%  MTG 2+3 {float(obs.cloud_frac_any.mean()):.1f}%")

fields = [("IFS (fisico), previsione +12 h", ifs),
          ("AIFS (AI), previsione +12 h", aifs),
          ("MTG FCI osservato: solo 3", obs.cloud_frac_full),
          ("MTG FCI osservato: 2+3", obs.cloud_frac_any)]
extent = [float(obs.longitude.min()), float(obs.longitude.max()),
          float(obs.latitude.min()), float(obs.latitude.max())]

fig, axes = plt.subplots(2, 2, figsize=(14, 6.5), constrained_layout=True,
                         subplot_kw={"projection": ccrs.PlateCarree()})
for ax, (title, da) in zip(axes.flat, fields):
    im = ax.pcolormesh(obs.longitude, obs.latitude, np.asarray(da), vmin=0, vmax=100,
                       cmap="Greys_r", shading="auto", transform=ccrs.PlateCarree())
    ax.coastlines(resolution="50m", linewidth=0.7, color="gold")
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.set_title(title)
fig.colorbar(im, ax=axes, shrink=0.8, label="Copertura nuvolosa (%)")
fig.suptitle("Copertura nuvolosa sul Mediterraneo, 20/11/2026 12 UTC")
fig.savefig("figures/first_comparison_20261120_12.png", dpi=130)
print("salvato figures/first_comparison_20261120_12.png")
