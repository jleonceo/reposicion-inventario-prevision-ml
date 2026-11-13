"""Paso 3 · El modelo, ajustado con 2023 y medido en 2024 frente a cuatro métodos sencillos.

Para cada producto: Lasso ajustado con los días de 2023; desde cada día de 2024, la previsión recursiva hasta el plazo
más largo del proveedor; y el error de la demanda de los días 1 al plazo medio, frente a la media de 30 días de lo
vendido (lo que hace hoy la empresa), la media de 30 días de la demanda, la semana anterior y la media diaria de 2023.
El modelo se da por bueno si se equivoca menos que el mejor de los cuatro y el intervalo del 95 % de la diferencia no
toca el cero. Deja la tabla de errores para el stock de seguridad y sus cifras en `informes/03_medida_2024.json`.

Uso: python pipeline/03_medida_2024.py
"""

# =====================================================================================================================
# CONFIGURACIÓN
# =====================================================================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reposicion import config, modelo, salidas  # noqa: E402

REF_VENTAS = "media de 30 días de lo vendido (regla actual)"
REF_DEMANDA = "media de 30 días de la demanda"
REF_SEMANA = "demanda del mismo día de la semana anterior"
REF_2023 = "media diaria de 2023"
REFERENCIAS = (REF_VENTAS, REF_DEMANDA, REF_SEMANA, REF_2023)

# =====================================================================================================================
# MEDIDA DE UN PRODUCTO
# =====================================================================================================================


def medir_producto(p, serie, filas_ajuste, plazo_maximo):
    """Ajusta, prevé 2024 y mide; devuelve las cifras y la tabla de errores por origen y día del horizonte."""
    plazo = config.PLAZO_MEDIO[p]
    m = modelo.ajustar(filas_ajuste)
    serie = serie.sort_values("fecha").reset_index(drop=True)
    fechas = pd.DatetimeIndex(serie["fecha"])
    demanda, ventas = serie["demanda"].to_numpy(dtype=float), serie["ventas"].to_numpy(dtype=float)

    # Los orígenes de 2024 con el plazo medio dentro del año; la previsión llega al plazo más largo
    origenes = modelo.origenes_de_medida(fechas, config.ANIO_MEDIDA, plazo)
    prevision, _ = modelo.prever_recursivo(m, demanda, fechas, origenes, plazo_maximo)
    real = modelo.matriz_real(demanda, origenes, plazo_maximo)

    # Las cuatro referencias con los mismos orígenes, sumadas sobre el plazo medio
    unos = np.ones((len(origenes), plazo))
    refs = {REF_VENTAS: modelo.media_ventana(ventas, origenes)[:, None] * unos,
            REF_DEMANDA: modelo.media_ventana(demanda, origenes)[:, None] * unos,
            REF_SEMANA: modelo.semana_anterior(demanda, origenes, plazo),
            REF_2023: float(demanda[fechas.year == config.ANIO_AJUSTE].mean()) * unos}
    real_l, prev_l = modelo.acumulado(real, plazo), modelo.acumulado(prevision, plazo)
    refs_l = {k: modelo.acumulado(v, plazo) for k, v in refs.items()}
    mae = {"modelo": float(np.abs(real_l - prev_l).mean()),
           **{k: float(np.abs(real_l - v).mean()) for k, v in refs_l.items()}}
    sesgo = float((prev_l - real_l).mean())
    mejor = min(REFERENCIAS, key=lambda k: (mae[k], REFERENCIAS.index(k)))

    # El intervalo de la diferencia con el mejor método sencillo, remuestreando meses enteros de orígenes
    intervalo = modelo.remuestreo_bloques(np.abs(real_l - prev_l), np.abs(real_l - refs_l[mejor]),
                                          fechas[origenes].month.to_numpy())
    supera = mae["modelo"] < mae[mejor] and intervalo[1] < 0

    # La tabla de errores: demanda real y prevista acumuladas por origen y día del horizonte, solo donde lo real se conoce
    real_acum, prev_acum = np.cumsum(real, axis=1), np.cumsum(prevision, axis=1)
    base = fechas[origenes]
    errores = []
    for h in range(1, plazo_maximo + 1):
        conocido = ~np.isnan(real_acum[:, h - 1])
        errores.append(pd.DataFrame({"producto": p, "origen": base[conocido], "h": h,
                                     "demanda_real_acumulada": real_acum[conocido, h - 1],
                                     "prevision_acumulada": prev_acum[conocido, h - 1]}))
    cifras = {"plazo_medio": plazo, "plazo_maximo": plazo_maximo, "origenes": len(origenes),
              "desde": base.min(), "hasta": base.max(), "mae": mae, "sesgo_modelo": sesgo, "mejor_referencia": mejor,
              "diferencia_con_la_mejor": mae["modelo"] - mae[mejor], "intervalo_95_diferencia": list(intervalo),
              "se_da_por_bueno": bool(supera), "mejora_frente_a_la_mejor": 1 - mae["modelo"] / mae[mejor],
              "coeficientes_distintos_de_cero": int((m.named_steps["modelo"].coef_ != 0).sum())}
    return cifras, pd.concat(errores, ignore_index=True)


# =====================================================================================================================
# EJECUCIÓN
# =====================================================================================================================


def main():
    """Mide los tres productos y guarda."""
    inv, ped = salidas.leer_tabla("inventario_dia"), salidas.leer_tabla("pedidos")
    variables = salidas.leer_tabla("variables")
    productos, tablas = {}, []
    for p in sorted(inv["producto"].unique()):
        recibidos = ped.loc[(ped["producto"] == p) & (ped["estado"] == "recibido"), "plazo_real"]
        ajuste = variables.loc[(variables["producto"] == p) & (variables["anio"] == config.ANIO_AJUSTE)]
        productos[p], errores = medir_producto(p, inv.loc[inv["producto"] == p], ajuste, int(recibidos.max()))
        tablas.append(errores)
    salidas.escribir_tabla("errores_2024", pd.concat(tablas, ignore_index=True))
    salidas.escribir_json("03_medida_2024", {
        "que": "error absoluto medio de la demanda de los días 1 al plazo medio, desde cada día de 2024",
        "modelo": {"algoritmo": config.ALGORITMO, "hiperparametros": config.HIPERPARAMETROS,
                   "ajustado_con": f"los días de {config.ANIO_AJUSTE}"},
        "productos": productos})
    for p, c in productos.items():
        print(f"{p}: error {c['mae']['modelo']:.2f} frente a {c['mae'][c['mejor_referencia']]:.2f} del mejor método "
              f"sencillo; se da por bueno: {c['se_da_por_bueno']}")


if __name__ == "__main__":
    main()
