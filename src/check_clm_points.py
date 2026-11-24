"""Legge cloud_state in alcuni punti geografici noti, per capire i valori
(sereno su terra / sereno su mare / nuvoloso) e l'orientamento dell'immagine."""
import glob

import numpy as np
import xarray as xr
from pyproj import Proj

f = sorted(glob.glob("data/clm/*CLM*.nc"))[0]
ds = xr.open_dataset(f)
p = ds.mtg_geos_projection.attrs
h = float(p["perspective_point_height"])
geos = Proj(proj="geos", h=h, lon_0=float(p["longitude_of_projection_origin"]),
            a=float(p["semi_major_axis"]), b=float(p["semi_minor_axis"]),
            sweep=p["sweep_angle_axis"])

x = ds.x.values          # radianti
y = ds.y.values
print(f"y della prima riga: {y[0]:.4f}  (positivo = nord in alto)")

points = {
    "Sahara (Libia)":            (25.0, 17.0),
    "Deserto arabico":           (22.0, 47.0),
    "Atlantico sud aperto":      (-25.0, -15.0),
    "Golfo di Guinea (0,0)":     (0.0, 0.0),
    "Mediterraneo centrale":     (35.0, 18.0),
    "Atlantico al largo Marocco": (30.0, -20.0),
}
for name, (lat, lon) in points.items():
    xm, ym = geos(lon, lat)                  # metri nella proiezione
    i = int(np.abs(y - ym / h).argmin())     # riga
    j = int(np.abs(x - xm / h).argmin())     # colonna
    window = ds.cloud_state.values[i-2:i+3, j-2:j+3]
    vals, counts = np.unique(window, return_counts=True)
    print(f"{name:28s} lat {lat:6.1f} lon {lon:6.1f} -> valori {dict(zip(vals.tolist(), counts.tolist()))}")
