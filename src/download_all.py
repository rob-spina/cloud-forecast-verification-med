"""Scarica tutti i dati del progetto:
- copertura nuvolosa totale (tcc) prevista da IFS e AIFS (ECMWF Open Data);
- maschere nubi MTG FCI (EUMETSAT Data Store) alle stesse ore di validita.
Si puo interrompere e rilanciare: i file gia scaricati vengono saltati."""
import glob
import subprocess
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ecmwf.opendata import Client

INIT_DATES = [datetime(2026, 11, 12) + timedelta(days=i) for i in range(10)]  # corse 00 UTC
STEPS = [12, 36, 60, 84, 108]                                                 # ore di anticipo
MODELS = {"ifs": "aws", "aifs-single": "aws"}                                 # modello: fonte
CLM_COLLECTION = "EO:EUM:DAT:0678"                                            # Cloud Mask MTG (netCDF)

ECMWF_DIR = Path("data/ecmwf")
CLM_DIR = Path("data/clm")
LOG = Path("data/download_log.txt")
# Solo ore di validita gia passate da almeno 2 ore (i dati devono essere pubblicati)
LIMIT = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def download_forecasts():
    for model, source in MODELS.items():
        client = Client(source=source, model=model)
        for init in INIT_DATES:
            steps = [s for s in STEPS if init + timedelta(hours=s) <= LIMIT]
            if not steps:
                continue
            target = ECMWF_DIR / f"{model}_{init:%Y%m%d}00_tcc_s{'-'.join(map(str, steps))}.grib2"
            if target.exists():
                log(f"gia presente: {target.name}")
                continue
            try:
                client.retrieve(date=init.strftime("%Y%m%d"), time=0, stream="oper", type="fc",
                                step=steps, param="tcc", target=str(target))
                log(f"OK  {target.name} ({target.stat().st_size / 1e6:.1f} MB)")
            except Exception as e:
                log(f"ERRORE {model} {init:%Y-%m-%d}: {type(e).__name__}: {e}")
                target.unlink(missing_ok=True)


def valid_times():
    times = {init + timedelta(hours=s) for init in INIT_DATES for s in STEPS}
    return sorted(t for t in times if t <= LIMIT)


def download_clm():
    for t in valid_times():
        if glob.glob(str(CLM_DIR / f"*CLM*_OPE_{t:%Y%m%d%H%M}00_*.nc")):
            log(f"gia presente: maschera nubi {t:%Y-%m-%d %H:%M}")
            continue
        start, end = t + timedelta(minutes=2), t + timedelta(minutes=5)
        before = set(CLM_DIR.glob("*.zip"))
        cmd = ["eumdac", "download", "-c", CLM_COLLECTION,
               "--start", f"{start:%Y-%m-%dT%H:%M}", "--end", f"{end:%Y-%m-%dT%H:%M}",
               "--limit", "1", "-o", str(CLM_DIR)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        new = set(CLM_DIR.glob("*.zip")) - before
        if r.returncode != 0 or not new:
            log(f"ERRORE maschera nubi {t:%Y-%m-%d %H:%M}: {(r.stderr or r.stdout)[-300:]}")
            continue
        for z in new:
            with zipfile.ZipFile(z) as zf:
                for member in zf.namelist():
                    if member.endswith(".nc"):
                        zf.extract(member, CLM_DIR)
            z.unlink()
        log(f"OK  maschera nubi {t:%Y-%m-%d %H:%M}")


if __name__ == "__main__":
    ECMWF_DIR.mkdir(parents=True, exist_ok=True)
    CLM_DIR.mkdir(parents=True, exist_ok=True)
    log(f"=== inizio download (ore di validita fino a {LIMIT:%Y-%m-%d %H:%M} UTC) ===")
    download_clm()          # prima le maschere: sono veloci
    download_forecasts()    # poi ECMWF: possono esserci attese per errori 503
    log("=== fine ===")
