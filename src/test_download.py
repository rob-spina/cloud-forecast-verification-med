"""Prova: scarica la copertura nuvolosa totale (tcc) prevista da IFS e AIFS
per la corsa del 20/11/2026 alle 00 UTC, valida alle 12 UTC (step +12 h)."""
from pathlib import Path

import earthkit.data as ekd
from ecmwf.opendata import Client

DATA = Path("data/ecmwf")
DATA.mkdir(parents=True, exist_ok=True)
DATE = "20261120"

for model in ["ifs", "aifs-single"]:
    target = DATA / f"{model}_{DATE}00_tcc_step12.grib2"
    client = Client(source="aws", model=model)
    result = client.retrieve(
        date=DATE, time=0, stream="oper", type="fc",
        step=12, param="tcc", target=str(target),
    )
    ds = ekd.from_source("file", str(target)).to_xarray()
    var = list(ds.data_vars)[0]
    values = ds[var]
    print(
        f"{model}: run {result.datetime} | variabile '{var}' | griglia {dict(ds.sizes)} | "
        f"min {float(values.min()):.2f}  max {float(values.max()):.2f} | "
        f"{target.stat().st_size / 1e6:.1f} MB"
    )
