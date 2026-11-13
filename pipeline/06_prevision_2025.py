"""Paso 6 · El modelo reentrenado con 2023 y 2024 y su previsión de cada día de la prueba final (enero a junio de 2025).

Con todo fijado, se reentrena el mismo Lasso con los dos años y se prevé, desde cada día de 2025 y con lo conocido al
cerrarlo, la demanda de los días 1 al plazo medio. Se mide su error frente a los tres métodos sencillos en los días de
2025 donde cabe el plazo. Deja `salidas_pipeline/prevision_2025.parquet` y `informes/06_prevision_2025.json`.

Uso: python pipeline/06_prevision_2025.py
"""

# =====================================================================================================================
# CONFIGURACIÓN
# =====================================================================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reposicion import config, datos, modelo, salidas  # noqa: E402

REFERENCIAS = ("media de 30 días de lo vendido (regla actual)", "media de 30 días de la demanda",
               "demanda del mismo día de la semana anterior")

# =====================================================================================================================
# EJECUCIÓN
# =====================================================================================================================


def serie_con_prueba(inv):
    """La serie de cada producto de 2023 a junio de 2025: la de construcción con la de la prueba final detrás."""
    prueba = datos.leer_inventario(config.DATOS_PRUEBA / "inventario_diario.csv")
    prueba["demanda"] = (prueba["ventas"] + prueba["ventas_perdidas"]).astype("int64")
    prueba["anio"] = prueba["fecha"].dt.year.astype("int64")
    columnas = ["fecha", "producto", "anio", "demanda", "ventas"]
    return pd.concat([inv[columnas], prueba[columnas]], ignore_index=True).sort_values(["producto", "fecha"])


def main():
    """Reentrena, prevé 2025, mide y guarda."""
    inv, variables = salidas.leer_tabla("inventario_dia"), salidas.leer_tabla("variables")
    serie = serie_con_prueba(inv)
    productos, filas = {}, []
    for p in sorted(inv["producto"].unique()):
        plazo = config.PLAZO_MEDIO[p]
        reentreno = variables.loc[(variables["producto"] == p)
                                  & variables["anio"].isin([config.ANIO_AJUSTE, config.ANIO_MEDIDA])]
        m = modelo.ajustar(reentreno)
        s = serie.loc[serie["producto"] == p].reset_index(drop=True)
        fechas = pd.DatetimeIndex(s["fecha"])
        demanda, ventas = s["demanda"].to_numpy(dtype=float), s["ventas"].to_numpy(dtype=float)

        # La previsión desde cada día de 2025: solo usa la demanda hasta el día de la revisión
        posiciones = np.flatnonzero(fechas.year == config.ANIO_PRUEBA)
        prev = modelo.prevision_del_plazo(m, demanda, fechas, posiciones, plazo)
        filas.append(pd.DataFrame({"producto": p, "fecha": fechas[posiciones], "prevision_plazo": prev}))

        # El error donde cabe el plazo entero dentro de los datos de 2025, frente a los tres métodos sencillos
        origenes = modelo.origenes_de_medida(fechas, config.ANIO_PRUEBA, plazo)
        real = modelo.acumulado(modelo.matriz_real(demanda, origenes, plazo), plazo)
        unos = np.ones((len(origenes), plazo))
        refs = {REFERENCIAS[0]: modelo.media_ventana(ventas, origenes)[:, None] * unos,
                REFERENCIAS[1]: modelo.media_ventana(demanda, origenes)[:, None] * unos,
                REFERENCIAS[2]: modelo.semana_anterior(demanda, origenes, plazo)}
        prev_o = prev[np.searchsorted(posiciones, origenes)]
        mae = {"modelo": float(np.abs(real - prev_o).mean()),
               **{k: float(np.abs(real - modelo.acumulado(v, plazo)).mean()) for k, v in refs.items()}}
        mejor = min(REFERENCIAS, key=lambda k: (mae[k], REFERENCIAS.index(k)))
        intervalo = modelo.remuestreo_bloques(np.abs(real - prev_o),
                                              np.abs(real - modelo.acumulado(refs[mejor], plazo)),
                                              fechas[origenes].month.to_numpy())
        productos[p] = {"filas_del_reentreno": len(reentreno), "dias_previstos": len(posiciones),
                        "origenes_medidos": len(origenes), "mae": mae, "mejor_referencia": mejor,
                        "intervalo_95_diferencia": list(intervalo),
                        "se_da_por_bueno": bool(mae["modelo"] < mae[mejor] and intervalo[1] < 0)}
    salidas.escribir_tabla("prevision_2025", pd.concat(filas, ignore_index=True))
    salidas.escribir_json("06_prevision_2025", {
        "reentrenado_con": f"{config.ANIO_AJUSTE} y {config.ANIO_MEDIDA}",
        "que": "error absoluto medio de la demanda de los días 1 al plazo medio, desde cada día de 2025 donde cabe",
        "productos": productos})
    for p, c in productos.items():
        print(f"{p}: error {c['mae']['modelo']:.2f} frente a {c['mae'][c['mejor_referencia']]:.2f} del mejor método "
              f"sencillo; se da por bueno: {c['se_da_por_bueno']}")


if __name__ == "__main__":
    main()
