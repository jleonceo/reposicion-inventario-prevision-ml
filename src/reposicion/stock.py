"""Stock de seguridad y punto de pedido de cada regla.

El stock de seguridad de las reglas corregida y con previsión sale del error medido en 2024: para cada día de revisión y
cada plazo real del proveedor, la demanda real de esos días menos la previsión sobre el plazo medio. El stock de
seguridad de un objetivo del 95 % es el percentil 95 de esos errores. Así el stock de seguridad recoge a la vez el
error de la previsión y lo que de verdad tarda el proveedor, sin suponer ninguna distribución.
"""

import numpy as np
import pandas as pd
from scipy import stats

from . import config
from .modelo import media_ventana

# =====================================================================================================================
# 1. El error y su percentil
# =====================================================================================================================


def valores_error(real_acum, prevision, plazos):
    """Demanda real de los días 1 a L menos la previsión sobre el plazo medio, por origen (fila) y plazo L (columna).

    `real_acum`: demanda real acumulada de los días 1 a h desde cada origen. `prevision`: previsión sobre el plazo
    medio desde cada origen. `plazos`: los plazos reales del proveedor, con sus repetidos, así que todos los pares
    origen × plazo pesan igual.
    """
    real_acum = np.asarray(real_acum, dtype=float)
    prevision = np.asarray(prevision, dtype=float)
    plazos = np.asarray(plazos, dtype=int)
    if plazos.min() < 1 or plazos.max() > real_acum.shape[1]:
        raise ValueError(f"los plazos van de {plazos.min()} a {plazos.max()} y el horizonte medido es "
                         f"{real_acum.shape[1]}: falta demanda para algún plazo")
    if np.isnan(real_acum[:, plazos - 1]).any() or np.isnan(prevision).any():
        raise ValueError("algún origen no tiene la demanda o la previsión de todos sus plazos")
    return real_acum[:, plazos - 1] - prevision[:, None]


def stock_seguridad(valores, niveles):
    """El percentil de cada objetivo sobre todos los valores, con el método por defecto de numpy (lineal)."""
    return np.percentile(np.asarray(valores, dtype=float).ravel(), niveles)


# =====================================================================================================================
# 2. Las dos referencias de manual
# =====================================================================================================================


def stock_seguridad_oscilacion_media(previsiones_anio, niveles):
    """Oscilación de la media: percentil del objetivo de los valores media × plazo medio del año, menos su media."""
    x = np.asarray(previsiones_anio, dtype=float)
    return np.percentile(x, niveles) - x.mean()


def parametros_formula_manual(fechas, demanda, plazos, anio=config.ANIO_MEDIDA):
    """σ y d de la demanda diaria del año y σL de los plazos del proveedor, las tres muestrales (ddof = 1)."""
    fechas = pd.DatetimeIndex(fechas)
    demanda_anio = np.asarray(demanda, dtype=float)[np.asarray(fechas.year == anio)]
    plazos = np.asarray(plazos, dtype=float)
    return {"sigma": float(demanda_anio.std(ddof=1)), "d": float(demanda_anio.mean()),
            "sigma_plazo": float(plazos.std(ddof=1))}


def stock_seguridad_formula_manual(sigma, d, sigma_plazo, plazo_medio, niveles):
    """La fórmula de manual: z × √(L × σ² + d² × σL²), con z el cuantil de una cola de la normal tipificada."""
    z = stats.norm.ppf(np.asarray(niveles, dtype=float) / 100)
    return z * np.sqrt(plazo_medio * sigma ** 2 + d ** 2 * sigma_plazo ** 2)


# =====================================================================================================================
# 3. La previsión de la media y el punto de pedido
# =====================================================================================================================


def prevision_media(demanda, posiciones, plazo_medio):
    """La media de la demanda de los 30 días que acaban en el día de la revisión, incluido, × plazo medio."""
    posiciones = np.asarray(posiciones, dtype=int)
    if posiciones.min() < config.VENTANA - 1:
        raise ValueError(f"cada día necesita sus {config.VENTANA} días de historia")
    return media_ventana(demanda, posiciones) * plazo_medio


def punto_de_pedido(prevision, stock):
    """Punto de pedido = previsión sobre el plazo medio + stock de seguridad del objetivo."""
    return np.asarray(prevision, dtype=float) + float(stock)
