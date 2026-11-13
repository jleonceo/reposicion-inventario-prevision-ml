"""Reentrena el modelo de cada producto con la historia hasta una fecha, sin pisar el que está en uso.

Para cada producto: en los últimos días (los de `config.json`) mide un modelo entrenado sin ellos, el modelo vigente y
la media de 30 días, los tres en los mismos días, y después entrena con toda la historia hasta la fecha. Guarda en
`modelos/candidato/`. Pasa a vigente si tiene al menos la historia del vigente, no es un modelo retirado, se equivoca
menos que la media de 30 días y no más que el vigente; el anterior se guarda en `modelos/anteriores/`. Si no, el
vigente sigue en uso y el candidato se queda para revisarlo.

Uso:  python produccion/reentrenar.py [--hasta AAAA-MM-DD]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from reposicion import config as config_metodo  # noqa: E402
from reposicion import datos, modelo, salidas  # noqa: E402
from reposicion.produccion import carpetas_modelos, cargar_modelos, config, guardar_modelos, promover  # noqa: E402


def historia_hasta(c, hasta):
    """El inventario por día de todos los datos disponibles, hasta la fecha dada."""
    partes = [datos.leer_inventario(c[k] / "inventario_diario.csv") for k in ("datos_historia", "datos_nuevos")]
    inv = pd.concat(partes, ignore_index=True)
    inv = inv.loc[inv["fecha"] <= pd.Timestamp(hasta)].sort_values(["producto", "fecha"]).reset_index(drop=True)
    inv["demanda"] = (inv["ventas"] + inv["ventas_perdidas"]).astype("int64")
    inv["anio"] = inv["fecha"].dt.year.astype("int64")
    return inv


def validar(inv_p, variables_p, plazo, dias, vigente=None):
    """El error de la demanda del plazo en los últimos `dias` (donde cabe el plazo) de un modelo entrenado sin ellos,
    el del modelo vigente y el de la media de 30 días, los tres en los mismos días.

    El vigente puede haberse entrenado con parte de esos días: si es así, juega con ventaja, y el candidato solo lo
    sustituye si aun así se equivoca menos.
    """
    fechas = pd.DatetimeIndex(inv_p["fecha"])
    demanda = inv_p["demanda"].to_numpy(dtype=float)
    corte = fechas.max() - pd.Timedelta(days=dias)
    filas = variables_p.loc[variables_p["fecha"] <= corte]
    m = modelo.ajustar(filas)
    origenes = np.flatnonzero((fechas > corte) & (fechas + pd.Timedelta(days=plazo) <= fechas.max()))
    real = modelo.acumulado(modelo.matriz_real(demanda, origenes, plazo), plazo)
    prev = modelo.prevision_del_plazo(m, demanda, fechas, origenes, plazo)
    ref = modelo.media_ventana(demanda, origenes) * plazo
    error_vigente = (None if vigente is None else
                     float(np.abs(real - modelo.prevision_del_plazo(vigente, demanda, fechas, origenes, plazo)).mean()))
    return {"origenes": int(len(origenes)), "ajustado_hasta": filas["fecha"].max().date().isoformat(),
            "medido_desde": fechas[origenes].min().date().isoformat(), "error": float(np.abs(real - prev).mean()),
            "error_vigente": error_vigente, "referencia": float(np.abs(real - ref).mean())}


def reentrenar(hasta=None, c=None):
    """Entrena el candidato con la historia hasta `hasta` y decide si pasa a vigente; devuelve la decisión."""
    c = c or config()
    hasta = hasta or c["entrenar_hasta"]
    inv = historia_hasta(c, hasta)
    if inv["fecha"].max() < pd.Timestamp(hasta):
        raise ValueError(f"no hay datos hasta el {hasta}: el último día es el {inv['fecha'].max().date()}")
    variables = modelo.filas_completas(modelo.crear_variables(inv))
    try:
        vigentes, _ = cargar_modelos(c=c)
    except RuntimeError:
        vigentes = {}
    modelos, validacion = {}, {}
    for p in sorted(c["productos"]):
        # Cada modelo se valida sobre el plazo medio real de su proveedor, que es el que prevé la regla con previsión
        validacion[p] = validar(inv.loc[inv["producto"] == p], variables.loc[variables["producto"] == p],
                                config_metodo.PLAZO_MEDIO[p], c["reentreno"]["dias_validacion"], vigentes.get(p))
        modelos[p] = modelo.ajustar(variables.loc[variables["producto"] == p])
    huellas = {salidas.relativa(r): salidas.huella(r) for k in ("datos_historia", "datos_nuevos")
               for r in sorted(c[k].glob("*.csv"))}
    guardar_modelos(modelos, validacion, hasta, huellas, carpetas_modelos(c)[1])
    return promover(c) | {"entrenado_hasta": hasta}


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--hasta", default=None, help="último día de la historia con que se entrena")
    d = reentrenar(argumentos.parse_args().hasta)
    estado = "pasa a vigente" if d["promovido"] else "NO pasa a vigente"
    print(f"OK: candidato entrenado hasta el {d['entrenado_hasta']}, error frente a la media de 30 días "
          f"{d['nuevo']:.3f}; {estado} ({d['motivo']})")
