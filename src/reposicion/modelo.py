"""Variables, modelo y previsión recursiva de la demanda.

El modelo prevé la demanda de un día con su día de la semana, su mes y la demanda de los 28 días anteriores. Para
prever varios días, cada día previsto entra como historia del siguiente: es la previsión recursiva. La demanda del
plazo es la suma de los días 1 al plazo medio desde el día de la revisión.
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Lasso
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from . import config

# =====================================================================================================================
# 1. Variables
# =====================================================================================================================

RETARDOS = [f"dem_lag_{k}" for k in range(1, config.HISTORIA + 1)]
MEDIAS = ["dem_media_7", "dem_media_28"]
VENTANAS_MEDIA = (7, 28)
NUMERICAS = RETARDOS + MEDIAS
COLUMNAS_ENTRADA = ["dia_semana", "mes"] + NUMERICAS
DIAS = [0, 1, 2, 3, 4, 5, 6]  # lunes = 0


def crear_variables(inv):
    """Retardos, medias y calendario de cada producto, con la tabla ordenada por producto y fecha.

    La media lleva `shift(1)` antes de `rolling`, para que no incluya el día que se prevé. `rolling(n)` cuenta filas:
    vale porque el calendario de cada producto va de día en día sin huecos.
    """
    df = inv.sort_values(["producto", "fecha"]).reset_index(drop=True)
    salida = df[["fecha", "producto", "anio", "demanda"]].copy()
    salida["dia_semana"] = df["fecha"].dt.day_of_week.astype("int64")
    salida["mes"] = df["fecha"].dt.month.astype("int64")
    por_producto = df.groupby("producto")["demanda"]
    for k in range(1, config.HISTORIA + 1):
        salida[f"dem_lag_{k}"] = por_producto.shift(k).astype("float64")
    for v in VENTANAS_MEDIA:
        salida[f"dem_media_{v}"] = por_producto.transform(lambda s, v=v: s.shift(1).rolling(v).mean())
    return salida


def filas_completas(variables):
    """Las filas con todas sus variables: los 28 primeros días de cada serie no tienen historia entera."""
    return variables.loc[~variables[NUMERICAS].isna().any(axis=1)].reset_index(drop=True)


# =====================================================================================================================
# 2. El modelo
# =====================================================================================================================

def _mes_ciclico(tabla):
    """Seno y coseno de 2π × mes / 12: diciembre queda al lado de enero."""
    mes = tabla["mes"].to_numpy(dtype=float)
    return pd.DataFrame({"mes_sen": np.sin(2 * np.pi * mes / 12), "mes_cos": np.cos(2 * np.pi * mes / 12)},
                        index=tabla.index)


def _nombres_mes(transformador, entrada):
    """Nombres de salida del mes."""
    return np.array(["mes_sen", "mes_cos"], dtype=object)


def _nombre_dia(variable, categoria):
    """Nombre de salida de una columna del día de la semana."""
    return f"{variable}_{categoria}_ohe"


def preprocesador(escalar=True):
    """Día de la semana en columnas de 0 y 1, mes en seno y coseno y la demanda pasada escalada (o tal cual)."""
    dia = OneHotEncoder(categories=[DIAS], sparse_output=False, handle_unknown="error",
                        feature_name_combiner=_nombre_dia)
    mes = FunctionTransformer(_mes_ciclico, feature_names_out=_nombres_mes)
    numericas = StandardScaler() if escalar else "passthrough"
    return ColumnTransformer([("dia", dia, ["dia_semana"]), ("mes", mes, ["mes"]), ("num", numericas, NUMERICAS)],
                             remainder="drop", verbose_feature_names_out=False).set_output(transform="pandas")


def nuevo_modelo(alpha=config.HIPERPARAMETROS["alpha"]):
    """El Pipeline del modelo elegido, sin ajustar: el preprocesador y un Lasso."""
    return Pipeline([("preparacion", preprocesador()),
                     ("modelo", Lasso(alpha=alpha, max_iter=10000, random_state=config.SEMILLA))])


def ajustar(filas, modelo=None):
    """Ajusta el modelo con las filas dadas, ordenadas por fecha."""
    filas = filas.sort_values("fecha").reset_index(drop=True)
    modelo = nuevo_modelo() if modelo is None else modelo
    return modelo.fit(filas[COLUMNAS_ENTRADA], filas["demanda"].to_numpy(dtype=float))


# =====================================================================================================================
# 3. La previsión recursiva
# =====================================================================================================================

def redondear_prevision(bruta):
    """La previsión de un día: acotada en cero y redondeada a unidades, con la mitad hacia arriba."""
    return np.floor(np.clip(np.asarray(bruta, dtype=float), 0, None) + 0.5)


def variables_del_dia(dias, ventana):
    """Las variables del día que se prevé: su fecha y los 28 días anteriores (el último es el retardo 1)."""
    datos = {"dia_semana": np.asarray(dias.day_of_week, dtype="int64"), "mes": np.asarray(dias.month, dtype="int64")}
    for k in range(1, config.HISTORIA + 1):
        datos[f"dem_lag_{k}"] = ventana[:, config.HISTORIA - k]
    datos["dem_media_7"] = ventana[:, -7:].mean(axis=1)
    datos["dem_media_28"] = ventana.mean(axis=1)
    return pd.DataFrame(datos)[COLUMNAS_ENTRADA]


def prever_recursivo(modelo, demanda, fechas, origenes, horizonte):
    """Previsión de los días 1 a `horizonte` desde cada origen, con lo conocido al cierre del origen.

    La historia de cada origen son sus 28 últimos días de demanda real, el origen incluido. Cada día previsto se acota
    en cero, se redondea y entra en la historia de los siguientes. Devuelve la previsión (orígenes × horizonte) y la
    previsión sin acotar ni redondear.
    """
    demanda = np.asarray(demanda, dtype=float)
    origenes = np.asarray(origenes, dtype=int)
    h_ = config.HISTORIA
    if len(origenes) == 0 or origenes.min() < h_ - 1 or origenes.max() >= len(demanda):
        raise ValueError("cada origen necesita sus 28 días de historia dentro de la serie")
    historia = np.full((len(origenes), h_ + horizonte), np.nan)
    for j in range(h_):
        historia[:, j] = demanda[origenes - (h_ - 1) + j]
    base = pd.DatetimeIndex(fechas)[origenes]
    prevision = np.empty((len(origenes), horizonte))
    bruta = np.empty((len(origenes), horizonte))
    for h in range(1, horizonte + 1):
        columna = h_ - 1 + h
        X = variables_del_dia(base + pd.Timedelta(days=h), historia[:, columna - h_:columna])
        bruta[:, h - 1] = np.asarray(modelo.predict(X), dtype=float)
        prevision[:, h - 1] = redondear_prevision(bruta[:, h - 1])
        historia[:, columna] = prevision[:, h - 1]
    return prevision, bruta


def acumulado(matriz, plazo):
    """La suma de los días 1 a `plazo` de cada origen."""
    return np.asarray(matriz, dtype=float)[:, :plazo].sum(axis=1)


def prevision_del_plazo(modelo, demanda, fechas, posiciones, plazo):
    """La demanda prevista durante el plazo desde cada día de revisión: la suma de los días 1 al plazo."""
    prevision, _ = prever_recursivo(modelo, demanda, fechas, posiciones, plazo)
    return acumulado(prevision, plazo)


# =====================================================================================================================
# 4. Lo real y las referencias sencillas
# =====================================================================================================================

def matriz_real(demanda, origenes, horizonte):
    """La demanda real de los días 1 a `horizonte` desde cada origen; vacía después del último día de la serie."""
    demanda = np.asarray(demanda, dtype=float)
    posiciones = np.asarray(origenes, dtype=int)[:, None] + np.arange(1, horizonte + 1)[None, :]
    dentro = posiciones < len(demanda)
    return np.where(dentro, demanda[np.minimum(posiciones, len(demanda) - 1)], np.nan)


def media_ventana(serie, origenes, ventana=config.VENTANA):
    """La media de los `ventana` días que acaban en el origen, el origen incluido."""
    serie = np.asarray(serie, dtype=float)
    return np.array([serie[o - ventana + 1:o + 1].mean() for o in origenes])


def semana_anterior(demanda, origenes, horizonte):
    """La demanda del mismo día de la semana anterior, repitiendo la última semana conocida hasta el horizonte."""
    h = np.arange(1, horizonte + 1)
    desfase = h - 7 * np.ceil(h / 7).astype(int)
    return np.asarray(demanda, dtype=float)[np.asarray(origenes, dtype=int)[:, None] + desfase[None, :]]


def origenes_de_medida(fechas, anio, plazo):
    """Posiciones de los días del año que sirven de origen: los que tienen el plazo entero dentro de ese año."""
    fechas = pd.DatetimeIndex(fechas)
    del_anio = np.flatnonzero(fechas.year == anio)
    return del_anio[del_anio + plazo <= del_anio.max()]


def remuestreo_bloques(abs_a, abs_b, bloques, n=1000, semilla=config.SEMILLA):
    """Intervalo del 95 % del error medio de A menos el de B, remuestreando meses enteros de orígenes con reposición.

    Los errores de orígenes seguidos comparten días y se solapan, así que no se remuestrean de uno en uno.
    """
    abs_a, abs_b, bloques = np.asarray(abs_a, float), np.asarray(abs_b, float), np.asarray(bloques)
    etiquetas = np.unique(bloques)
    por_bloque = [np.flatnonzero(bloques == e) for e in etiquetas]
    rng = np.random.default_rng(semilla)
    diferencias = []
    for _ in range(n):
        elegidos = rng.integers(0, len(etiquetas), len(etiquetas))
        filas = np.concatenate([por_bloque[k] for k in elegidos])
        diferencias.append(abs_a[filas].mean() - abs_b[filas].mean())
    return float(np.percentile(diferencias, 2.5)), float(np.percentile(diferencias, 97.5))
