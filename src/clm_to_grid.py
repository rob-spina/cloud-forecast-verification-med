"""Converte la maschera nubi FCI (MTG, EUMETSAT) nella frazione nuvolosa (%)
su una griglia regolare lat-lon a 0.25 gradi, la stessa degli Open Data ECMWF."""
import glob
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Proj

# Area di studio: Mediterraneo (gradi)
LAT_MIN, LAT_MAX = 30.0, 46.0
LON_MIN, LON_MAX = -6.0, 37.0
RES = 0.25

# Valori di cloud_state (da confermare con la documentazione EUMETSAT)
CLEAR, PARTIAL, CLOUDY = 1, 2, 3


def geos_projection(ds):
    """Proiezione geostazionaria del satellite, dai parametri nel file."""
    p = ds.mtg_geos_projection.attrs
    h = float(p["perspective_point_height"])
    proj = Proj(proj="geos", h=h, lon_0=float(p["longitude_of_projection_origin"]),
                a=float(p["semi_major_axis"]), b=float(p["semi_minor_axis"]),
                sweep=p["sweep_angle_axis"])
    return proj, h


def grid_centers_and_edges():
    """Centri delle celle sui punti della griglia ECMWF, e bordi a +-RES/2."""
    lat_c = np.round(np.arange(LAT_MIN, LAT_MAX + RES / 2, RES), 4)
    lon_c = np.round(np.arange(LON_MIN, LON_MAX + RES / 2, RES), 4)
    lat_e = np.append(lat_c - RES / 2, lat_c[-1] + RES / 2)
    lon_e = np.append(lon_c - RES / 2, lon_c[-1] + RES / 2)
    return lat_c, lon_c, lat_e, lon_e


def clm_to_grid(path):
    ds = xr.open_dataset(path)
    proj, h = geos_projection(ds)
    x = -ds.x.values.astype("float64")      # radianti
    y = ds.y.values.astype("float64")

    # 1. Rettangolo di pixel che contiene l'area (con 1 grado di margine)
    LO, LA = np.meshgrid(np.linspace(LON_MIN - 1, LON_MAX + 1, 60),
                         np.linspace(LAT_MIN - 1, LAT_MAX + 1, 60))
    xm, ym = proj(LO, LA)
    ok = np.isfinite(xm) & np.isfinite(ym) & (np.abs(xm) < 1e10)
    xa, ya = xm[ok] / h, ym[ok] / h
    cols = np.where((x >= xa.min()) & (x <= xa.max()))[0]
    rows = np.where((y >= ya.min()) & (y <= ya.max()))[0]
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1

    # 2. Latitudine e longitudine di ogni pixel del rettangolo
    cs = ds.cloud_state.values[r0:r1, c0:c1]
    XX, YY = np.meshgrid(x[c0:c1] * h, y[r0:r1] * h)
    plon, plat = proj(XX, YY, inverse=True)

    # 3. Pixel validi: sulla Terra e con valore 1, 2 o 3
    valid = (np.isfinite(plon) & np.isfinite(plat) & (np.abs(plon) <= 180)
             & np.isin(cs, [CLEAR, PARTIAL, CLOUDY]))
    la, lo, v = plat[valid], plon[valid], cs[valid]

    # 4. Conteggi per cella da 0.25 gradi
    lat_c, lon_c, lat_e, lon_e = grid_centers_and_edges()
    n_all, _, _ = np.histogram2d(la, lo, bins=[lat_e, lon_e])
    n_full, _, _ = np.histogram2d(la, lo, bins=[lat_e, lon_e], weights=(v == CLOUDY).astype(float))
    n_any, _, _ = np.histogram2d(la, lo, bins=[lat_e, lon_e], weights=(v >= PARTIAL).astype(float))
    with np.errstate(invalid="ignore", divide="ignore"):
        frac_full = np.where(n_all > 0, 100 * n_full / n_all, np.nan)
        frac_any = np.where(n_all > 0, 100 * n_any / n_all, np.nan)

    time = pd.to_datetime(str(ds.attrs["date_time_position"]), format="%Y%m%d%H%M%S")
    out = xr.Dataset(
        {
            "cloud_frac_full": (("latitude", "longitude"), frac_full,
                                {"units": "%", "long_name": "Cloud-filled pixels (cloud_state=3)"}),
            "cloud_frac_any": (("latitude", "longitude"), frac_any,
                               {"units": "%", "long_name": "Cloudy or partly cloudy pixels (cloud_state=2,3)"}),
            "n_pixels": (("latitude", "longitude"), n_all.astype("int32"),
                         {"long_name": "Valid FCI pixels per grid cell"}),
        },
        coords={"latitude": lat_c, "longitude": lon_c, "time": time},
        attrs={"source": Path(path).name,
               "description": "FCI L2 cloud mask aggregated to a 0.25 degree grid"},
    )
    return out


if __name__ == "__main__":
    outdir = Path("data/obs")
    outdir.mkdir(parents=True, exist_ok=True)
    for f in sorted(glob.glob("data/clm/*CLM*.nc")):
        grid = clm_to_grid(f)
        name = outdir / f"clm_{pd.Timestamp(grid.time.values):%Y%m%d%H%M}.nc"
        grid.to_netcdf(name)
        print(f"{name}: celle {dict(grid.sizes)}, "
              f"pixel per cella (mediana) {int(np.nanmedian(grid.n_pixels))}, "
              f"nuvolosita media 2+3 = {float(grid.cloud_frac_any.mean()):.1f}%")
