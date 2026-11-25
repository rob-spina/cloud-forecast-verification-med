"""Verifica della copertura nuvolosa prevista da IFS e AIFS (ECMWF) rispetto a quella
osservata da MTG FCI (EUMETSAT), per ogni corsa e anticipo, sul Mediterraneo.

Uso:  python src/compute_scores.py              # griglia 0.25 gradi
      python src/compute_scores.py --coarsen 4  # campi mediati su blocchi 4x4 (1 grado)
"""
import argparse
import glob
import warnings
from datetime import timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

MODELS = {"ifs": 100.0, "aifs-single": 1.0}      # fattore per avere la copertura in %
LABELS = {"ifs": "IFS (fisico)", "aifs-single": "AIFS (AI)"}
COLORS = {"ifs": "#257de0", "aifs-single": "#f47230"}
MARKERS = {"ifs": "o", "aifs-single": "s"}
OBS_VAR = "cloud_frac_any"   # pixel con cloud_state 2 o 3
MIN_PIXELS = 20              # celle con meno pixel satellitari validi vengono escluse
RESULTS, FIG = Path("results"), Path("figures")


def load_obs():
    obs = {}
    for f in sorted(glob.glob("data/obs/clm_*.nc")):
        ds = xr.open_dataset(f).load()
        obs[pd.Timestamp(ds.time.values).to_pydatetime()] = ds
    return obs


def to_obs_grid(da, grid):
    """Porta un campo ECMWF sulla griglia delle osservazioni (longitudini -180..180)."""
    da = da.squeeze(drop=True)
    if float(da.longitude.max()) > 180:
        da = da.assign_coords(longitude=((da.longitude + 180) % 360) - 180).sortby("longitude")
    da = da.sortby("latitude")
    return da.sel(latitude=grid.latitude, longitude=grid.longitude, method="nearest").values


def coarsen(a, k):
    """Media su blocchi k x k (ignora le celle mancanti); k=1 lascia il campo invariato."""
    if k == 1:
        return a
    ny, nx = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    blocks = a[:ny, :nx].reshape(ny // k, k, nx // k, k)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # blocchi tutti vuoti -> NaN
        return np.nanmean(blocks, axis=(1, 3))


def scores(fc, ob):
    m = np.isfinite(fc) & np.isfinite(ob)
    d = fc[m] - ob[m]
    return {"bias": d.mean(), "rmse": np.sqrt((d ** 2).mean()), "mae": np.abs(d).mean(),
            "corr": np.corrcoef(fc[m], ob[m])[0, 1], "n_cells": int(m.sum())}


def main(k):
    suffix = "" if k == 1 else f"_{0.25 * k:g}deg"
    res_label = f"{0.25 * k:g}°"
    obs = load_obs()
    rows = []
    for model, scale in MODELS.items():
        # [0-9] esclude i file di prova *_tcc_step12.grib2
        for path in sorted(glob.glob(f"data/ecmwf/{model}_*_tcc_s[0-9]*.grib2")):
            ds = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})
            init = pd.Timestamp(ds.time.values).to_pydatetime()
            tcc = ds["tcc"]
            if "step" not in tcc.dims:
                tcc = tcc.expand_dims("step")
            for st in tcc.step.values:
                step = int(st / np.timedelta64(1, "h"))
                valid = init + timedelta(hours=step)
                if valid not in obs:
                    print(f"  manca l'osservazione per {valid:%Y-%m-%d %H:%M}, salto")
                    continue
                grid = obs[valid]
                ob = grid[OBS_VAR].where(grid.n_pixels >= MIN_PIXELS).values
                fc = to_obs_grid(tcc.sel(step=st), grid) * scale
                if np.nanmax(fc) > 100.5:
                    print(f"  ATTENZIONE {model} {init:%Y-%m-%d} +{step}h: max {np.nanmax(fc):.1f}%")
                fc = np.where(np.isfinite(ob), fc, np.nan)   # stessa area per previsione e osservazione
                rows.append({"model": model, "init": init, "step": step, "valid": valid,
                             **scores(coarsen(fc, k), coarsen(ob, k))})

    df = pd.DataFrame(rows)
    RESULTS.mkdir(exist_ok=True)
    df.to_csv(RESULTS / f"scores_by_case{suffix}.csv", index=False)
    print(f"\n[{res_label}] {len(df)} casi salvati in results/scores_by_case{suffix}.csv\n")

    summary = df.groupby(["step", "model"])[["bias", "rmse", "corr"]].mean().unstack("model").round(2)
    print(summary.to_string(), "\n")

    pair = df.pivot_table(index=["init", "step"], columns="model", values="rmse").dropna()
    wins = (pair["aifs-single"] < pair["ifs"]).groupby("step").agg(["sum", "count"])
    for step, r in wins.iterrows():
        print(f"+{step:3d} h: AIFS ha RMSE minore di IFS in {int(r['sum'])} casi su {int(r['count'])}")

    FIG.mkdir(exist_ok=True)
    panels = [("rmse", "RMSE", "punti percentuali"),
              ("bias", "Bias (previsto - osservato)", "punti percentuali"),
              ("corr", "Correlazione spaziale", "")]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4), constrained_layout=True)
    steps = sorted(df.step.unique())
    for ax, (metric, title, ylab) in zip(axes, panels):
        for model in MODELS:
            g = df[df.model == model].groupby("step")[metric]
            mean, std = g.mean(), g.std()
            ax.fill_between(mean.index, mean - std, mean + std, color=COLORS[model], alpha=0.12, lw=0)
            ax.plot(mean.index, mean.values, color=COLORS[model], lw=2, marker=MARKERS[model],
                    ms=7, mec="white", mew=1.5, label=LABELS[model])
        if metric == "bias":
            ax.axhline(0, color="#555555", lw=0.8)
        ax.set_xticks(steps)
        ax.set_xlabel("Anticipo della previsione (ore)")
        ax.set_ylabel(ylab)
        ax.set_title(title)
        ax.grid(color="#dddddd", lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False)
    fig.suptitle(f"Copertura nuvolosa sul Mediterraneo alle 12 UTC, griglia {res_label}: IFS e AIFS contro MTG FCI "
                 f"({df.valid.min():%d/%m}-{df.valid.max():%d/%m/%Y}; banda = ±1 dev. standard tra i casi)")
    out = FIG / f"scores_vs_leadtime{suffix}.png"
    fig.savefig(out, dpi=130)
    print(f"\nsalvato {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--coarsen", type=int, default=1,
                        help="media i campi su blocchi NxN celle da 0.25 gradi prima del confronto")
    main(parser.parse_args().coarsen)
