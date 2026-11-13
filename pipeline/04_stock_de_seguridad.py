"""Paso 4 · El stock de seguridad de cada regla en cada objetivo de servicio, y el punto de pedido de cada día de 2024.

- Regla con previsión: el percentil del objetivo de los errores del modelo en 2024, con cada plazo real del proveedor.
- Regla corregida: lo mismo con la previsión de la media de 30 días de la demanda × plazo medio.
- Oscilación de la media: el percentil del objetivo de la media × plazo medio de los días de 2024, menos su media.
- Fórmula de manual: z × √(L × σ² + d² × σL²), que supone demanda y plazo normales e independientes.

El punto de pedido es la previsión sobre el plazo medio más el stock de seguridad. Deja la tabla de puntos de pedido de
2024 y las cifras en `informes/04_stock_de_seguridad.json`.

Uso: python pipeline/04_stock_de_seguridad.py
"""

# =====================================================================================================================
# CONFIGURACIÓN
# =====================================================================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reposicion import config, datos, modelo, salidas, stock  # noqa: E402
from reposicion.config import CORREGIDA, MANUAL, OSCILACION, PREVISION  # noqa: E402

# =====================================================================================================================
# UN PRODUCTO
# =====================================================================================================================


def niveles_de(regla):
    """La rejilla de objetivos de una regla: la fórmula de manual lleva además los ampliados."""
    return config.NIVELES_MANUAL if regla == MANUAL else config.NIVELES


def un_producto(p, serie, errores_p, pedidos, ajuste):
    """El stock de seguridad de las cuatro reglas y su tabla de puntos de pedido de 2024."""
    plazo_medio = config.PLAZO_MEDIO[p]
    serie = serie.sort_values("fecha").reset_index(drop=True)
    fechas = pd.DatetimeIndex(serie["fecha"])
    demanda = serie["demanda"].to_numpy(dtype=float)
    posicion = pd.Series(np.arange(len(fechas)), index=fechas)
    plazos = datos.plazos_para_sortear(pedidos, p)

    # Los orígenes donde cabe el plazo más largo: los que tienen la demanda real de todos los días del horizonte
    horizonte = int(errores_p["h"].max())
    origenes = pd.DatetimeIndex(sorted(errores_p.loc[errores_p["h"] == horizonte, "origen"].unique()))
    usados = errores_p.loc[errores_p["origen"].isin(origenes)]
    real_acum = (usados.pivot(index="origen", columns="h", values="demanda_real_acumulada").reindex(origenes)
                 .reindex(columns=range(1, horizonte + 1)).to_numpy(dtype=float))
    prev_medida = (usados.loc[usados["h"] == plazo_medio].set_index("origen")["prevision_acumulada"]
                   .reindex(origenes).to_numpy(dtype=float))
    pos_origenes = posicion.reindex(origenes).to_numpy(dtype=int)

    # La previsión de cada día de 2024: la del modelo ajustado con 2023 y la de la media de 30 días
    m = modelo.ajustar(ajuste)
    pos_anio = np.flatnonzero(fechas.year == config.ANIO_MEDIDA)
    prev_modelo = modelo.prevision_del_plazo(m, demanda, fechas, pos_anio, plazo_medio)
    prev_media = stock.prevision_media(demanda, pos_anio, plazo_medio)

    # Comprobación: la previsión del modelo de cada día es la de la tabla de errores en el mismo origen
    todos = errores_p.loc[errores_p["h"] == plazo_medio].set_index("origen")["prevision_acumulada"]
    en_anio = pd.Series(np.arange(len(pos_anio)), index=fechas[pos_anio])
    dif = float(np.abs(prev_modelo[en_anio.reindex(todos.index).to_numpy(dtype=int)] - todos.to_numpy()).max())

    # El stock de seguridad de cada regla en cada objetivo de su rejilla
    manual = stock.parametros_formula_manual(fechas, demanda, plazos)
    ss = {PREVISION: stock.stock_seguridad(stock.valores_error(real_acum, prev_medida, plazos), config.NIVELES),
          CORREGIDA: stock.stock_seguridad(
              stock.valores_error(real_acum, stock.prevision_media(demanda, pos_origenes, plazo_medio), plazos),
              config.NIVELES),
          OSCILACION: stock.stock_seguridad_oscilacion_media(prev_media, config.NIVELES),
          MANUAL: stock.stock_seguridad_formula_manual(manual["sigma"], manual["d"], manual["sigma_plazo"], plazo_medio,
                                                       config.NIVELES_MANUAL)}

    # La tabla de puntos de pedido: un día de 2024, una regla y un objetivo por fila
    previsiones = {PREVISION: prev_modelo, CORREGIDA: prev_media, OSCILACION: prev_media, MANUAL: prev_media}
    partes = [pd.DataFrame({"producto": p, "fecha": fechas[pos_anio], "regla": regla, "nivel": nivel,
                            "prevision": previsiones[regla], "stock_seguridad": float(ss[regla][j]),
                            "punto_pedido": stock.punto_de_pedido(previsiones[regla], ss[regla][j])})
              for regla in config.REGLAS for j, nivel in enumerate(niveles_de(regla))]
    cifras = {"plazo_medio": plazo_medio, "horizonte": horizonte, "origenes": len(origenes),
              "valores_por_regla": int(len(origenes) * len(plazos)),
              "plazos_del_proveedor": {"pedidos": len(plazos), "media": float(plazos.mean()),
                                       "minimo": int(plazos.min()), "maximo": int(plazos.max())},
              "formula_manual": manual, "stock_seguridad": {k: list(v) for k, v in ss.items()},
              "comprobaciones": {"prevision_igual_a_la_medida": {"ok": dif == 0.0,
                                                                 "detalle": f"diferencia máxima {dif}"}}}
    return cifras, pd.concat(partes, ignore_index=True)


# =====================================================================================================================
# EJECUCIÓN
# =====================================================================================================================


def main():
    """Calcula los tres productos, comprueba y guarda."""
    inv, ped = salidas.leer_tabla("inventario_dia"), salidas.leer_tabla("pedidos")
    errores, variables = salidas.leer_tabla("errores_2024"), salidas.leer_tabla("variables")
    productos, tablas = {}, []
    for p in sorted(inv["producto"].unique()):
        ajuste = variables.loc[(variables["producto"] == p) & (variables["anio"] == config.ANIO_AJUSTE)]
        productos[p], tabla = un_producto(p, inv.loc[inv["producto"] == p], errores.loc[errores["producto"] == p],
                                          ped, ajuste)
        tablas.append(tabla)
    puntos = pd.concat(tablas, ignore_index=True)
    salidas.comprobar({f"{p}: {k}": v for p, c in productos.items() for k, v in c["comprobaciones"].items()})
    salidas.escribir_tabla("puntos_de_pedido_2024", puntos)
    salidas.escribir_json("04_stock_de_seguridad", {
        "niveles": config.NIVELES, "niveles_formula_manual": config.NIVELES_MANUAL,
        "metodo": "percentil del objetivo de la demanda real de los días 1 a L menos la previsión sobre el plazo "
                  "medio, para cada día de revisión de 2024 y cada plazo real L de los pedidos recibidos",
        "productos": productos})
    for p, c in productos.items():
        j = config.NIVELES.index(config.OBJETIVO[p])
        print(f"{p}: stock de seguridad al {config.OBJETIVO[p]} %: con previsión "
              f"{c['stock_seguridad'][PREVISION][j]:.1f}, corregida {c['stock_seguridad'][CORREGIDA][j]:.1f}")


if __name__ == "__main__":
    main()
