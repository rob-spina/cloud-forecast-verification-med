"""Mappe per un singolo caso: copertura nuvolosa prevista da IFS e AIFS e osservata da MTG FCI."""
import glob
from datetime import datetime, timedelta

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

INIT = datetime(2026, 11, 20)        # corsa delle 00 UTC
STEP = 12                            # anticipo in ore
VALID = INIT + timedelta(hours=STEP)

obs = xr.open_dataset(f"data/obs/clm_{VALID:%Y%m%d%H%M}.nc")


def load_tcc(model, scale):
    """tcc di una corsa e un anticipo, in %, sulla griglia delle osservazioni."""
    path = sorted(glob.glob(f"data/ecmwf/{model}_{INIT:%Y%m%d}00_tcc_s[0-9]*.grib2"))[0]
    ds = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})
    da = ds["tcc"].sel(step=np.timedelta64(STEP, "h")) * scale
    da = da.squeeze(drop=True)
    if float(da.longitude.max()) > 180:
        da = da.assign_coords(longitude=((da.longitude + 180) % 360) - 180).sortby("longitude")
    da = da.sortby("latitude")
    return da.sel(latitude=obs.latitude, longitude=obs.longitude, method="nearest")


ifs = load_tcc("ifs", 100)            # IFS: frazione 0-1 -> %
aifs = load_tcc("aifs-single", 1)     # AIFS: gia in %

if __name__ == "__main__":
    fields = [(f"IFS (physics-based), +{STEP} h", ifs),
              (f"AIFS (data-driven), +{STEP} h", aifs),
              ("MTG FCI observed (cloudy + partly cloudy)", obs.cloud_frac_any)]
    extent = [float(obs.longitude.min()), float(obs.longitude.max()),
              float(obs.latitude.min()), float(obs.latitude.max())]
    fig, axes = plt.subplots(1, 3, figsize=(18, 3.1), constrained_layout=True,
                             subplot_kw={"projection": ccrs.PlateCarree()})
    for ax, (title, da) in zip(axes, fields):
        im = ax.pcolormesh(obs.longitude, obs.latitude, np.asarray(da), vmin=0, vmax=100,
                           cmap="Greys_r", shading="auto", transform=ccrs.PlateCarree())
        ax.coastlines(resolution="50m", linewidth=0.7, color="gold")
        ax.set_extent(extent, crs=ccrs.PlateCarree())
        ax.set_title(title)
    fig.colorbar(im, ax=axes, shrink=0.9, pad=0.01, label="Total cloud cover (%)")
    fig.suptitle(f"Cloud cover over the Mediterranean, valid {VALID:%d %b %Y %H} UTC")
    out = f"figures/maps_{VALID:%Y%m%d_%H}utc_step{STEP}.png"
    fig.savefig(out, dpi=130)
    print(f"salvato {out}")
