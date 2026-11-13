"""Paso 2 · Las variables del modelo y el reparto en ajuste (2023) y medida (2024).

Para cada producto y día: día de la semana, mes, la demanda de los 28 días anteriores y sus medias de 7 y 28 días. Los
28 primeros días de 2023 no tienen la historia entera y no entran. Deja `salidas_pipeline/variables.parquet` y sus
cifras en `informes/02_variables.json`.

Uso: python pipeline/02_variables.py
"""

# =====================================================================================================================
# CONFIGURACIÓN
# =====================================================================================================================

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reposicion import config, modelo, salidas  # noqa: E402

# =====================================================================================================================
# VARIABLES Y COMPROBACIONES
# =====================================================================================================================


def main():
    """Crea las variables, comprueba que ninguna ve el día que se prevé y guarda."""
    inv = salidas.leer_tabla("inventario_dia")
    variables = modelo.filas_completas(modelo.crear_variables(inv))

    # Cada retardo k es la demanda de k días antes y cada media, la de sus retardos: si una variable usara la demanda del
    # día que se prevé, no casaría
    demanda = inv.set_index(["producto", "fecha"])["demanda"]
    distintos = 0
    for k in range(1, config.HISTORIA + 1):
        antes = demanda.reindex(list(zip(variables["producto"], variables["fecha"] - np.timedelta64(k, "D"))))
        distintos += int((antes.to_numpy(dtype=float) != variables[f"dem_lag_{k}"].to_numpy()).sum())
    medias = {w: int((~np.isclose(variables[f"dem_media_{w}"],
                                  variables[[f"dem_lag_{k}" for k in range(1, w + 1)]].mean(axis=1))).sum())
              for w in modelo.VENTANAS_MEDIA}
    por_anio = variables.groupby(["producto", "anio"]).size().unstack()
    comprobaciones = {
        "retardos_sin_el_dia_previsto": {"ok": distintos == 0, "detalle": f"retardos distintos: {distintos}"},
        "medias_de_sus_retardos": {"ok": not any(medias.values()), "detalle": f"medias distintas: {medias}"},
        "filas_por_anio": {"ok": bool((por_anio[config.ANIO_AJUSTE] == 365 - config.HISTORIA).all()
                                      and (por_anio[config.ANIO_MEDIDA] == 366).all()),
                           "detalle": f"filas por producto y año: {por_anio.to_dict()}"},
    }
    salidas.comprobar(comprobaciones)

    salidas.escribir_tabla("variables", variables)
    salidas.escribir_json("02_variables", {
        "variables": modelo.COLUMNAS_ENTRADA, "filas_por_producto_y_anio": por_anio.to_dict(orient="index"),
        "reparto": {"ajuste": config.ANIO_AJUSTE, "medida": config.ANIO_MEDIDA},
        "comprobaciones": comprobaciones})
    print(f"variables: {len(variables)} filas, {len(modelo.COLUMNAS_ENTRADA)} columnas de entrada")


if __name__ == "__main__":
    main()
