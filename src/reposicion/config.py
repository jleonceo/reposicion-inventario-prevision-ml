"""Constantes del método: periodos, plazos, sorteos, niveles, reglas de pedido y rutas.

Todo lo que el resto del código da por fijado vive aquí, con el motivo al lado. Las rutas salen de la carpeta del
repositorio, así que el código funciona lo lance quien lo lance y desde donde lo lance.
"""

from pathlib import Path

import numpy as np
import pandas as pd

# =====================================================================================================================
# 1. Rutas
# =====================================================================================================================

# La raíz del repositorio: dos carpetas por encima de este fichero (src/reposicion/config.py)
RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "datos"
DATOS_PRUEBA = DATOS / "prueba_final"
INFORMES = RAIZ / "informes"
PROCESADOS = RAIZ / "salidas_pipeline"

# =====================================================================================================================
# 2. Periodos
# =====================================================================================================================

# 2023 ajusta el modelo, 2024 lo mide y fija el stock de seguridad, y enero a junio de 2025 queda apartado para la
# prueba final, que se abre una sola vez con todo lo demás ya fijado
ANIO_AJUSTE, ANIO_MEDIDA, ANIO_PRUEBA = 2023, 2024, 2025
INICIO_2024 = pd.Timestamp("2024-01-01")
FIN_CONSTRUCCION = pd.Timestamp("2024-12-31")
INICIO_PRUEBA, FIN_PRUEBA = pd.Timestamp("2025-01-01"), pd.Timestamp("2025-06-30")
DIAS_DEL_ANIO = 365

# =====================================================================================================================
# 3. Previsión
# =====================================================================================================================

# Plazo medio del proveedor de cada producto en días enteros: el redondeo del plazo real medio de 2023 y 2024
PLAZO_MEDIO = {"Producto_A": 7, "Producto_B": 8, "Producto_C": 12}
# El modelo mira los 28 días anteriores; la regla actual y la previsión de la media, los 30 que acaban en el día
HISTORIA = 28
VENTANA = 30
# El modelo de los tres productos: Lasso con alpha 0,1, ganador de la competición de algoritmos
ALGORITMO = "lasso"
HIPERPARAMETROS = {"alpha": 0.1}
SEMILLA = 42

# =====================================================================================================================
# 4. Stock de seguridad, sorteos y costes
# =====================================================================================================================

# Rejilla de objetivos de servicio: del 80 % al 99,5 %, de medio en medio punto. La fórmula de manual lleva además del
# 99,6 % al 99,9 %, por si su objetivo de menor coste cae en el extremo
NIVELES = [float(x) for x in np.arange(80.0, 99.5 + 0.25, 0.5)]
NIVELES_AMPLIADOS = [round(float(x), 1) for x in np.arange(99.6, 99.9 + 0.05, 0.1)]
NIVELES_MANUAL = NIVELES + NIVELES_AMPLIADOS

# El objetivo de cada producto, el de menor coste de la regla con previsión en 2024, y el propio de la fórmula de manual.
# Los usa el modo rápido; el modo completo los vuelve a elegir y comprueba que salen estos
OBJETIVO = {"Producto_A": 93.0, "Producto_B": 94.5, "Producto_C": 97.5}
OBJETIVO_MANUAL = {"Producto_A": 98.0, "Producto_B": 98.0, "Producto_C": 99.0}

# Sorteo de plazos: 200 repeticiones con semilla fija; las cifras se dan con su mediana y la banda del 5 al 95
REPETICIONES = 200
BANDA = (5, 95)
SORTEOS_DE_REFERENCIA = 400

# Coste de mantener el stock: el 25 % anual decide; el 15 % y el 40 % dicen si la conclusión aguanta otra estimación
PORCENTAJES = (0.15, 0.25, 0.40)
PORCENTAJE_BASE = 0.25

# =====================================================================================================================
# 5. Las reglas de pedido
# =====================================================================================================================

# La regla actual: media de lo vendido en 30 días × plazo prometido + un stock de seguridad fijo de la ficha
ACTUAL = "actual"
# La regla corregida: media de la demanda en 30 días × plazo medio real + stock de seguridad del error medido
CORREGIDA = "corregida"
# La regla con previsión: previsión del modelo sobre el plazo medio + stock de seguridad del error medido
PREVISION = "prevision"
# Dos referencias de manual: la oscilación de la media y la fórmula con la distribución normal
OSCILACION = "oscilacion_media"
MANUAL = "formula_manual"
REGLAS = (PREVISION, CORREGIDA, OSCILACION, MANUAL)
TODAS = (ACTUAL,) + REGLAS
NOMBRE = {ACTUAL: "regla actual", CORREGIDA: "regla corregida", PREVISION: "regla con previsión",
          OSCILACION: "oscilación de la media", MANUAL: "fórmula de manual"}

# La regla del sistema: la misma en todos los productos, para que funcione solo con cualquier número de productos.
# Se decidió después de la prueba final, que comparaba las reglas producto a producto: en A no baja el coste (sube 10 € de
# mediana en el semestre), y en B y C lo baja frente a la actual
REGLA_DEL_SISTEMA = PREVISION
