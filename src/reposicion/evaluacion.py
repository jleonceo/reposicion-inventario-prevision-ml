"""Comparar reglas con los mismos sorteos: bandas, diferencias emparejadas, veredicto, objetivo y decisión.

Todas las cifras de la comparación se dan con la mediana de los 200 sorteos y la banda del 5 al 95. La diferencia entre
dos reglas se calcula sorteo a sorteo, con los mismos plazos en las dos, para que el azar del plazo no entre en ella.
"""

import numpy as np
import pandas as pd

from . import config

COLUMNAS_JUNTAS = ("coste_total", "dias_sin_stock", "servido", "demanda", "stock_medio_euros")


def bandas(valores):
    """Media, mediana y banda del 5 al 95 (percentiles de numpy, interpolación lineal)."""
    v = np.asarray(valores, dtype=float)
    return {"media": float(v.mean()), "mediana": float(np.median(v)),
            f"p{config.BANDA[0]}": float(np.percentile(v, config.BANDA[0])),
            f"p{config.BANDA[1]}": float(np.percentile(v, config.BANDA[1]))}


def diferencias(regla, referencia, columna):
    """Diferencia regla − referencia en el mismo sorteo, emparejada por el número de sorteo, con su banda."""
    unida = regla[["sorteo", columna]].merge(referencia[["sorteo", columna]], on="sorteo", suffixes=("", "_ref"),
                                             validate="one_to_one")
    if len(unida) != len(regla) or len(unida) != len(referencia):
        raise ValueError("las dos reglas no tienen los mismos sorteos")
    return bandas(unida[columna] - unida[f"{columna}_ref"])


def veredicto(dif_coste, dif_fill):
    """Buena si baja el coste total, con toda la banda de su diferencia por debajo de cero, sin bajar el fill rate
    (mediana de su diferencia en cero o más). Si la mediana baja pero la banda cruza el cero, no se puede afirmar."""
    if dif_coste["mediana"] < 0 and dif_fill["mediana"] >= 0 and dif_coste["p95"] < 0:
        return "buena"
    if dif_coste["mediana"] < 0 and dif_fill["mediana"] >= 0:
        return "no se puede afirmar"
    return "no buena"


def decidir(d):
    """La regla de cada producto: la de previsión, si es buena frente a la actual y frente a la corregida; si no, la
    corregida, si es buena frente a la actual; si no, la actual.

    `d`: las diferencias «prevision_actual», «prevision_corregida» y «corregida_actual», cada una con la banda de la
    diferencia del coste total y la del fill rate.
    """
    v = {k: veredicto(x["coste_total"], x["fill_rate"]) for k, x in d.items()}
    if v["prevision_actual"] == "buena" and v["prevision_corregida"] == "buena":
        return config.PREVISION, v
    if v["corregida_actual"] == "buena":
        return config.CORREGIDA, v
    return config.ACTUAL, v


def juntar(partes):
    """Los tres productos sumados por sorteo; el fill rate, servidas entre demanda de los tres; el stock, en euros."""
    s = pd.concat(partes).groupby("sorteo")[list(COLUMNAS_JUNTAS)].sum()
    s["fill_rate"] = s["servido"] / s["demanda"]
    return s.reset_index()


def elegir_nivel(tabla, niveles):
    """El objetivo de menor coste total medio entre los sorteos; con empate, el más bajo."""
    medias = tabla.groupby("nivel")["coste_total"].mean().reindex(niveles)
    nivel = float(medias.index[int(np.argmin(medias.to_numpy()))])
    return {"nivel": nivel, "coste_medio": float(medias.loc[nivel]),
            "en_extremo": bool(nivel in (min(niveles), max(niveles)))}


def elegir_nivel_manual(tabla, niveles, ampliados):
    """El objetivo propio de la fórmula de manual; si cae en el último de la rejilla común, se elige con la ampliada."""
    eleccion = elegir_nivel(tabla, niveles)
    if eleccion["nivel"] == max(niveles):
        return {**elegir_nivel(tabla, list(niveles) + list(ampliados)), "ampliada": True}
    return {**eleccion, "ampliada": False}
