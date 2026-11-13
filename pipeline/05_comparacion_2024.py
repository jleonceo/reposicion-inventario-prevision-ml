"""Paso 5 · Las reglas de pedido en el simulador del almacén con 2024, y el objetivo de servicio de cada producto.

1. Reproducción: la regla actual, con los plazos reales en su orden, tiene que dar día a día lo que registró el sistema
   en 2023 y 2024. Si no lo da, el simulador no vale y el paso para.
2. Las cinco reglas en 2024 con 200 sorteos del plazo de cada pedido; todas reciben los mismos plazos.
3. El objetivo de cada producto es el de menor coste total medio de la regla con previsión; la corregida y la
   oscilación de la media usan ese mismo objetivo, y la fórmula de manual también su objetivo propio.

Con `--rapido` no recorre la rejilla de objetivos: simula solo los objetivos ya elegidos, que guarda la configuración.
En 2024 la comparación es orientativa: el stock de seguridad se fijó con los errores de 2024. Decide la prueba final.

Uso: python pipeline/05_comparacion_2024.py [--rapido]
"""

# =====================================================================================================================
# CONFIGURACIÓN
# =====================================================================================================================

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reposicion import config, datos, evaluacion, salidas, simulador  # noqa: E402
from reposicion.config import ACTUAL, CORREGIDA, MANUAL, PREVISION, REGLAS  # noqa: E402

INDICADORES = ("coste_total", "fill_rate", "dias_sin_stock", "unidades_no_servidas", "stock_medio", "stock_medio_euros",
               "pedidos")

# =====================================================================================================================
# REPRODUCCIÓN Y SIMULACIÓN
# =====================================================================================================================


def reproducir(inv, ped, ficha, p):
    """2023 y 2024 con la regla actual y los plazos reales en orden; devuelve los días que no casan y el coste de 2024."""
    g = inv.loc[inv["producto"] == p].reset_index(drop=True)
    f = ficha.loc[p]
    plazos = [None if pd.isna(x) else int(x) for x in ped.loc[ped["producto"] == p, "plazo_real"]]
    diario, _ = simulador.simular(
        g["demanda"].to_numpy(), simulador.regla_actual(int(f["politica_stock_seguridad"]), int(f["lead_time_prometido"])),
        simulador.PlazosReales(plazos), int(g.loc[0, "stock_inicial"]), int(f["politica_cantidad_pedido"]),
        fechas=g["fecha"])
    fallan = simulador.dias_que_no_casan(diario, g)
    anio = diario.loc[pd.DatetimeIndex(diario["fecha"]).year == config.ANIO_MEDIDA]
    return {"dias": len(diario), "dias_que_casan": len(diario) - len(fallan),
            "coste_real_2024": simulador.indicadores(anio, f, config.PORCENTAJE_BASE)["coste_total"]}


def simular_2024(inv, ped, ficha, p, regla, plazos):
    """2024 desde el 01/01/2024 con el estado de la víspera, la historia de 2023 y una regla de punto de pedido."""
    g = inv.loc[inv["producto"] == p]
    antes, anio = g.loc[g["fecha"] < config.INICIO_2024], g.loc[g["fecha"] >= config.INICIO_2024]
    stock0, en_camino = simulador.estado_vispera(inv, ped, p, config.INICIO_2024)
    return simulador.simular(anio["demanda"].to_numpy(), regla, plazos, stock0,
                             int(ficha.loc[p, "politica_cantidad_pedido"]), en_camino_inicial=en_camino,
                             historia_previa={"ventas": antes["ventas"].to_numpy(),
                                              "demanda": antes["demanda"].to_numpy()})


def simular_todo(inv, ped, ficha, puntos, productos, rejilla):
    """Cada regla en cada objetivo de `rejilla` (por producto y regla), con los mismos 200 sorteos; una fila por
    simulación y porcentaje de mantener."""
    filas = []
    for i, p in enumerate(productos):
        f = ficha.loc[p]
        valores = datos.plazos_para_sortear(ped, p)
        reglas = {(r, float(n)): g.sort_values("fecha")["punto_pedido"].to_numpy(dtype=float)
                  for (r, n), g in puntos.loc[puntos["producto"] == p].groupby(["regla", "nivel"])}
        actual = simulador.regla_actual(int(f["politica_stock_seguridad"]), int(f["lead_time_prometido"]))
        for s in range(config.REPETICIONES):
            casos = [(ACTUAL, None, actual)] + [(r, n, simulador.regla_de_puntos(reglas[(r, n)]))
                                                 for r in REGLAS for n in rejilla[p][r]]
            for regla, nivel, punto in casos:
                diario, _ = simular_2024(inv, ped, ficha, p, punto,
                                         simulador.PlazosSorteados(valores, config.SEMILLA, (s, i)))
                for pct in config.PORCENTAJES:
                    ind = simulador.indicadores(diario, f, pct)
                    filas.append({"producto": p, "regla": regla, "nivel": nivel, "sorteo": s, "porcentaje": pct,
                                  "demanda": ind["demanda"], "servido": ind["servido"],
                                  **{k: ind[k] for k in INDICADORES}})
        print(f"{p}: {config.REPETICIONES} sorteos × {1 + sum(len(x) for x in rejilla[p].values())} simulaciones",
              flush=True)
    return pd.DataFrame(filas)


# =====================================================================================================================
# COMPARACIÓN
# =====================================================================================================================


def comparar(tabla, productos, objetivos):
    """Con el 25 % de mantener: cada regla a su objetivo frente a la actual, por producto y de los tres juntos."""
    t = tabla.loc[np.isclose(tabla["porcentaje"], config.PORCENTAJE_BASE)]
    salida, partes = {}, {r: [] for r in config.TODAS}
    for p in productos:
        tp = t.loc[t["producto"] == p]
        grupos = {ACTUAL: tp.loc[tp["regla"] == ACTUAL].sort_values("sorteo")}
        for r in REGLAS:
            nivel = objetivos[p]["manual"] if r == MANUAL else objetivos[p]["nivel"]
            grupos[r] = tp.loc[(tp["regla"] == r) & (tp["nivel"] == nivel)].sort_values("sorteo")
        for r, g in grupos.items():
            partes[r].append(g)
        salida[p] = {"objetivo": objetivos[p],
                     "indicadores": {r: {k: evaluacion.bandas(g[k]) for k in INDICADORES} for r, g in grupos.items()},
                     "frente_a_la_actual": {r: {k: evaluacion.diferencias(grupos[r], grupos[ACTUAL], k)
                                                for k in ("coste_total", "fill_rate", "dias_sin_stock",
                                                          "stock_medio_euros")} for r in REGLAS}}
    juntos = {r: evaluacion.juntar(v) for r, v in partes.items()}
    tres = {r: {k: evaluacion.diferencias(juntos[r], juntos[ACTUAL], k)
                for k in ("coste_total", "fill_rate", "stock_medio_euros")} for r in REGLAS}
    return salida, tres, juntos


# =====================================================================================================================
# EJECUCIÓN
# =====================================================================================================================


def main():
    """Reproduce, simula, elige el objetivo, compara y guarda."""
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--rapido", action="store_true", help="usa los objetivos ya elegidos")
    rapido = argumentos.parse_args().rapido
    inicio = time.perf_counter()
    inv, ped = salidas.leer_tabla("inventario_dia"), salidas.leer_tabla("pedidos")
    ficha = datos.leer_ficha(config.DATOS / "productos.csv").set_index("producto")
    puntos = salidas.leer_tabla("puntos_de_pedido_2024")
    productos = sorted(inv["producto"].unique())

    # 1. La reproducción de 2023 y 2024 con la regla actual: si no casa, para
    reproduccion = {p: reproducir(inv, ped, ficha, p) for p in productos}
    salidas.comprobar({f"reproduccion_{p}": {"ok": r["dias_que_casan"] == r["dias"],
                                             "detalle": f"casan {r['dias_que_casan']} de {r['dias']} días"}
                       for p, r in reproduccion.items()})

    # 2. Las simulaciones: la rejilla entera o solo los objetivos elegidos
    if rapido:
        rejilla = {p: {r: [config.OBJETIVO_MANUAL[p], config.OBJETIVO[p]] if r == MANUAL else [config.OBJETIVO[p]]
                       for r in REGLAS} for p in productos}
    else:
        rejilla = {p: {r: config.NIVELES_MANUAL if r == MANUAL else config.NIVELES for r in REGLAS} for p in productos}
    tabla = simular_todo(inv, ped, ficha, puntos, productos, rejilla)

    # 3. El objetivo de cada producto: en modo completo se elige y tiene que salir el de la configuración
    base = tabla.loc[np.isclose(tabla["porcentaje"], config.PORCENTAJE_BASE)]
    if rapido:
        objetivos = {p: {"nivel": config.OBJETIVO[p], "manual": config.OBJETIVO_MANUAL[p], "elegido": "configuración"}
                     for p in productos}
    else:
        objetivos = {}
        for p in productos:
            tp = base.loc[base["producto"] == p]
            e = evaluacion.elegir_nivel(tp.loc[tp["regla"] == PREVISION], config.NIVELES)
            m = evaluacion.elegir_nivel_manual(tp.loc[tp["regla"] == MANUAL], config.NIVELES, config.NIVELES_AMPLIADOS)
            objetivos[p] = {"nivel": e["nivel"], "manual": m["nivel"], "en_extremo": e["en_extremo"],
                            "elegido": "menor coste total medio de los 200 sorteos"}
        salidas.comprobar({f"objetivo_{p}": {"ok": (o["nivel"], o["manual"]) == (config.OBJETIVO[p],
                                                                                 config.OBJETIVO_MANUAL[p]),
                                             "detalle": f"elegido {o['nivel']} y {o['manual']}; en la configuración "
                                                        f"{config.OBJETIVO[p]} y {config.OBJETIVO_MANUAL[p]}"}
                           for p, o in objetivos.items()})
        curvas = base.groupby(["producto", "regla", "nivel"], dropna=False)["coste_total"].agg(["mean", "median"])
        salidas.escribir_tabla("curvas_2024", curvas.reset_index())

    por_producto, tres, juntos = comparar(tabla, productos, objetivos)
    coste_real = sum(r["coste_real_2024"] for r in reproduccion.values())
    salidas.escribir_json("05_comparacion_2024", {
        "modo": "rápido: objetivos de la configuración" if rapido else "completo: rejilla entera de objetivos",
        "orientativo": "el stock de seguridad se fijó con 2024; decide la prueba final de 2025",
        "reproduccion_2023_2024": reproduccion, "objetivos": objetivos, "productos": por_producto,
        "tres_juntos": tres,
        "frente_al_coste_real_2024": {"coste_real": coste_real,
                                      "regla_con_prevision_menos_coste_real": evaluacion.bandas(
                                          juntos[PREVISION]["coste_total"] - coste_real)},
        "simulaciones": int(len(tabla) // len(config.PORCENTAJES)),
        "segundos": round(time.perf_counter() - inicio, 1)})
    for p in productos:
        d = por_producto[p]["frente_a_la_actual"]
        print(f"{p}: objetivo {objetivos[p]['nivel']} %; regla con previsión − actual: "
              f"{d[PREVISION]['coste_total']['mediana']:.0f} €; corregida − actual: "
              f"{d[CORREGIDA]['coste_total']['mediana']:.0f} €")


if __name__ == "__main__":
    main()
