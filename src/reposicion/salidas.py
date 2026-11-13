"""Escritura y lectura de lo que deja cada paso: JSON sin NaN, tablas en parquet y huellas de los ficheros."""

import hashlib
import json
import math
import platform
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import config


def huella(ruta):
    """SHA-256 de un fichero, para dejar escrito de qué datos sale un resultado."""
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def relativa(ruta):
    """La ruta de un fichero, relativa a la raíz del repositorio si está dentro; si no, solo su carpeta y su nombre,
    para que ningún mensaje ni JSON lleve rutas de la máquina."""
    ruta = Path(ruta).resolve()
    if ruta.is_relative_to(config.RAIZ):
        return ruta.relative_to(config.RAIZ).as_posix()
    return f"{ruta.parent.name}/{ruta.name}"


def limpio(valor):
    """Un valor para el JSON: números de Python, claves de texto y null en lugar de NaN o infinito."""
    if isinstance(valor, dict):
        return {str(k): limpio(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [limpio(v) for v in valor]
    if isinstance(valor, (np.integer,)):
        return int(valor)
    if isinstance(valor, (np.floating, float)):
        return None if not math.isfinite(float(valor)) else float(valor)
    if isinstance(valor, np.bool_):
        return bool(valor)
    if isinstance(valor, (pd.Timestamp,)):
        return valor.date().isoformat()
    return valor


def entorno():
    """Versiones con que se ejecutó, para poder repetirlo."""
    import sklearn
    return {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
            "scikit-learn": sklearn.__version__}


def escribir_json(nombre, datos):
    """Escribe `informes/<nombre>.json` con la fecha de ejecución y el entorno."""
    config.INFORMES.mkdir(exist_ok=True)
    datos = {"fecha_ejecucion": datetime.now().replace(microsecond=0).isoformat(), "entorno": entorno(), **datos}
    ruta = config.INFORMES / f"{nombre}.json"
    ruta.write_text(json.dumps(limpio(datos), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return ruta


def leer_json(nombre):
    """Lee `informes/<nombre>.json`; para con un mensaje claro si el paso que lo deja no se ha ejecutado."""
    ruta = config.INFORMES / f"{nombre}.json"
    if not ruta.is_file():
        raise SystemExit(f"Falta {relativa(ruta)}: ejecuta antes el paso que lo deja")
    return json.loads(ruta.read_text(encoding="utf-8"))


def escribir_tabla(nombre, tabla):
    """Guarda una tabla de trabajo en `salidas_pipeline/<nombre>.parquet`."""
    config.PROCESADOS.mkdir(exist_ok=True)
    ruta = config.PROCESADOS / f"{nombre}.parquet"
    tabla.to_parquet(ruta, index=False)
    return ruta


def leer_tabla(nombre):
    """Lee una tabla de trabajo; para si el paso que la deja no se ha ejecutado."""
    ruta = config.PROCESADOS / f"{nombre}.parquet"
    if not ruta.is_file():
        raise SystemExit(f"Falta {relativa(ruta)}: ejecuta antes el paso que la deja")
    return pd.read_parquet(ruta)


def comprobar(comprobaciones):
    """Para con la lista de lo que falla si alguna comprobación no pasa."""
    fallan = [f"{k}: {v['detalle']}" for k, v in comprobaciones.items() if not v["ok"]]
    if fallan:
        raise SystemExit("Fallan comprobaciones:\n  " + "\n  ".join(fallan))
