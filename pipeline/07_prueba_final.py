"""Paso 7 · La prueba final: enero a junio de 2025, que nada de lo anterior ha visto, mide el sistema.

1. Reproducción: la regla actual, con los plazos reales de 2025 y el stock al cierre de 2024, tiene que dar día a día
   lo que registró el sistema. Si no lo da, la comparación no vale y el paso para.
2. El punto de pedido de cada día de 2025: la regla con previsión, con la previsión del paso 6; la corregida, la
   oscilación de la media y la fórmula de manual, con la media de 30 días × plazo medio. Cada una con su stock de
   seguridad de 2024 en el objetivo fijado.
3. Las cinco reglas con 200 sorteos del plazo; los dos pedidos pendientes al cierre de 2024 toman el primer plazo de
   cada sorteo y los pedidos nuevos, los siguientes.
4. La comparación de cada producto, que se fijó antes de abrir 2025: la regla con previsión si es buena frente a la
   actual y frente a la corregida; si no, la corregida si es buena frente a la actual; si no, la actual. «Buena»: baja
   el coste total con toda la banda del 5 al 95 de la diferencia por debajo de cero, sin bajar el fill rate. Queda como
   elección por producto.
5. El sistema: la regla con previsión en los tres productos (`config.REGLA_DEL_SISTEMA`), una sola regla para que el
   proceso funcione solo con cualquier número de productos. Se decidió después de esta prueba.

Deja `informes/07_prueba_final.json`, con la cifra de la portada: lo que habría costado el sistema frente a lo que
costó de verdad el semestre.

Uso: python pipeline/07_prueba_final.py
"""

# =====================================================================================================================
# CONFIGURACIÓN
# =====================================================================================================================

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reposicion import config, datos, evaluacion, salidas, simulador, stock  # noqa: E402
from reposicion.config import ACTUAL, CORREGIDA, MANUAL, PREVISION, REGLAS, TODAS  # noqa: E402

INDICADORES = ("coste_total", "fill_rate", "dias_sin_stock", "unidades_no_servidas", "stock_medio", "stock_medio_euros",
               "pedidos")
JUNTOS = ("coste_total", "fill_rate", "stock_medio_euros", "dias_sin_stock")

# =====================================================================================================================
# LO FIJADO Y LOS DATOS DE 2025
# =====================================================================================================================


def stock_fijado(cifras_stock, p):
    """El stock de seguridad de cada regla en el objetivo fijado, leído del paso 4 sin recalcular nada."""
    s = cifras_stock["productos"][p]["stock_seguridad"]
    j = cifras_stock["niveles"].index(config.OBJETIVO[p])
    salida = {r: float(s[r][j]) for r in REGLAS if r != MANUAL}
    salida[MANUAL] = float(s[MANUAL][cifras_stock["niveles_formula_manual"].index(config.OBJETIVO_MANUAL[p])])
    return salida


def registro_2025():
    """Lo que registró el sistema en 2025, por producto y día, y los pedidos de 2025 con su plazo."""
    inv, ped, _ = datos.leer_tablas(config.DATOS_PRUEBA)
    ped = datos.transformar_pedidos(ped)
    return datos.transformar_inventario(inv, ped), ped


def ciclos_en_filas(diario, cantidad):
    """El nivel de servicio por reposición de una simulación, para añadirlo a su fila."""
    c = simulador.ciclos(diario, cantidad)
    return {"ciclos": c["ciclos"], "ciclos_sin_rotura": c["sin_rotura"], "nivel_ciclo": c["nivel"]}


# =====================================================================================================================
# COMPARACIÓN Y DECISIÓN
# =====================================================================================================================


def comparar(tabla, productos, pct):
    """Con un porcentaje de mantener: diferencias emparejadas, decisión por producto y los tres juntos."""
    t = tabla.loc[np.isclose(tabla["porcentaje"], pct)]
    por_producto, partes = {}, {r: [] for r in TODAS}
    for p in productos:
        g = {r: t.loc[(t["producto"] == p) & (t["regla"] == r)].sort_values("sorteo") for r in TODAS}
        for r in TODAS:
            partes[r].append(g[r])

        def dif(a, b):
            """Diferencia emparejada por sorteo de cada indicador."""
            return {k: evaluacion.diferencias(a, b, k) for k in INDICADORES}
        d = {"prevision_actual": dif(g[PREVISION], g[ACTUAL]), "prevision_corregida": dif(g[PREVISION], g[CORREGIDA]),
             "corregida_actual": dif(g[CORREGIDA], g[ACTUAL])}
        eleccion, veredictos = evaluacion.decidir(d)
        por_producto[p] = {"indicadores": {r: {k: evaluacion.bandas(g[r][k]) for k in INDICADORES} for r in TODAS},
                           "frente_a_la_actual": {r: dif(g[r], g[ACTUAL]) for r in REGLAS},
                           "prevision_menos_corregida": d["prevision_corregida"],
                           "prevision_menos_formula_manual": dif(g[PREVISION], g[MANUAL]),
                           "nivel_por_reposicion": {r: evaluacion.bandas(g[r]["nivel_ciclo"].dropna()) for r in TODAS},
                           "veredictos": veredictos, "eleccion": eleccion}

    # Los tres juntos: cada regla en los tres productos frente a la actual en los tres
    juntos = {r: evaluacion.juntar(partes[r]) for r in TODAS}
    tres = {"frente_a_la_actual": {r: {k: evaluacion.diferencias(juntos[r], juntos[ACTUAL], k) for k in JUNTOS}
                                   for r in REGLAS}}
    return {"porcentaje": pct, "productos": por_producto, "tres_juntos": tres}, partes


# =====================================================================================================================
# EJECUCIÓN
# =====================================================================================================================


def main():
    """Reproduce 2025, simula las cinco reglas, compara, decide y guarda."""
    inicio_reloj = time.perf_counter()
    inv, ped = salidas.leer_tabla("inventario_dia"), salidas.leer_tabla("pedidos")
    ficha = datos.leer_ficha(config.DATOS_PRUEBA / "productos.csv").set_index("producto")
    prevision = salidas.leer_tabla("prevision_2025")
    cifras_stock = salidas.leer_json("04_stock_de_seguridad")
    reg, ped25 = registro_2025()
    productos = sorted(reg["producto"].unique())

    # Lo de cada producto: serie con la historia delante, estado al empezar y punto de pedido de cada regla
    d = {}
    for p in productos:
        cons = inv.loc[inv["producto"] == p].sort_values("fecha")
        prueba = reg.loc[reg["producto"] == p].sort_values("fecha").reset_index(drop=True)
        demanda_toda = np.concatenate([cons["demanda"].to_numpy(dtype=float), prueba["demanda"].to_numpy(dtype=float)])
        pos25 = np.arange(len(cons), len(demanda_toda))
        media = stock.prevision_media(demanda_toda, pos25, config.PLAZO_MEDIO[p])
        prev_p = prevision.loc[prevision["producto"] == p].sort_values("fecha")
        if not np.array_equal(prev_p["fecha"].to_numpy(), prueba["fecha"].to_numpy()):
            raise SystemExit(f"{p}: los días de la previsión no son los de la prueba")
        previsiones = {PREVISION: prev_p["prevision_plazo"].to_numpy(dtype=float), CORREGIDA: media,
                       config.OSCILACION: media, MANUAL: media}
        ss = stock_fijado(cifras_stock, p)
        anio24 = cons.loc[cons["fecha"].dt.year == config.ANIO_MEDIDA]
        f = ficha.loc[p]
        d[p] = {"prueba": prueba, "ss": ss,
                "stock": int(cons.loc[cons["fecha"] == config.FIN_CONSTRUCCION, "stock_final"].iloc[0]),
                "pendientes": ped.loc[(ped["producto"] == p) & ped["fecha_llegada"].isna()],
                "historia": {"ventas": anio24["ventas"].to_numpy(), "demanda": anio24["demanda"].to_numpy()},
                "cantidad": int(f["politica_cantidad_pedido"]),
                "reglas": {ACTUAL: simulador.regla_actual(int(f["politica_stock_seguridad"]),
                                                          int(f["lead_time_prometido"])),
                           **{r: simulador.regla_de_puntos(stock.punto_de_pedido(previsiones[r], ss[r]))
                              for r in REGLAS}}}

    # 1. La reproducción con la regla actual y los plazos reales de 2025: si no casa, para
    reproduccion, lo_que_paso = {}, {}
    reales = ped25.set_index("id_pedido")
    for p in productos:
        x = d[p]
        en_camino = [{"unidades": int(o.cantidad),
                      "dia_llegada": int((reales.loc[o.id_pedido, "fecha_llegada"] - config.INICIO_PRUEBA).days)}
                     for o in x["pendientes"].sort_values(["fecha_pedido", "id_pedido"]).itertuples(index=False)]
        nuevos = ped25.loc[(ped25["producto"] == p) & (ped25["fecha_pedido"] >= config.INICIO_PRUEBA)].sort_values(
            ["fecha_pedido", "id_pedido"])
        plazos = [None if pd.isna(v) else int(v) for v in nuevos["plazo_real"]]
        diario, _ = simulador.simular(x["prueba"]["demanda"].to_numpy(), x["reglas"][ACTUAL],
                                      simulador.PlazosReales(plazos), x["stock"], x["cantidad"],
                                      en_camino_inicial=en_camino, historia_previa=x["historia"],
                                      fechas=x["prueba"]["fecha"])
        fallan = simulador.dias_que_no_casan(diario, x["prueba"])
        reproduccion[p] = {"dias": len(diario), "dias_que_casan": len(diario) - len(fallan)}
        lo_que_paso[p] = simulador.indicadores(diario, ficha.loc[p])
    salidas.comprobar({f"reproduccion_{p}": {"ok": r["dias_que_casan"] == r["dias"],
                                             "detalle": f"casan {r['dias_que_casan']} de {r['dias']} días"}
                       for p, r in reproduccion.items()})

    # 2. Las cinco reglas con los mismos 200 sorteos; los pendientes toman el primer plazo de cada sorteo
    filas = []
    for i, p in enumerate(productos):
        x = d[p]
        valores = datos.plazos_para_sortear(ped, p)
        for s in range(config.REPETICIONES):
            for r in TODAS:
                asignador = simulador.PlazosSorteados(valores, config.SEMILLA, (s, i))
                en_camino = simulador.arranque_sorteado(x["pendientes"], asignador, config.INICIO_PRUEBA)
                diario, _ = simulador.simular(x["prueba"]["demanda"].to_numpy(), x["reglas"][r], asignador, x["stock"],
                                              x["cantidad"], en_camino_inicial=en_camino, historia_previa=x["historia"])
                ciclos = ciclos_en_filas(diario, x["cantidad"])
                for pct in config.PORCENTAJES:
                    ind = simulador.indicadores(diario, ficha.loc[p], pct)
                    filas.append({"producto": p, "regla": r, "sorteo": s, "porcentaje": pct, "demanda": ind["demanda"],
                                  "servido": ind["servido"], **{k: ind[k] for k in INDICADORES}, **ciclos})
    tabla = pd.DataFrame(filas)

    # 3. Comparar con cada porcentaje de mantener; decide el 25 %
    comparaciones, partes_base = {}, None
    for pct in config.PORCENTAJES:
        comparaciones[str(int(round(100 * pct)))], partes = comparar(tabla, productos, pct)
        if np.isclose(pct, config.PORCENTAJE_BASE):
            partes_base = partes
    base = comparaciones[str(int(round(100 * config.PORCENTAJE_BASE)))]
    eleccion = {p: base["productos"][p]["eleccion"] for p in productos}

    # 4. El sistema frente a lo que costó de verdad el semestre: una sola cifra real, restada a cada sorteo
    regla = config.REGLA_DEL_SISTEMA
    coste_real = {p: lo_que_paso[p]["coste_total"] for p in productos}
    i = {p: k for k, p in enumerate(productos)}
    costes = pd.concat([partes_base[regla][i[p]][["sorteo", "coste_total"]] for p in productos])
    total = costes.groupby("sorteo")["coste_total"].sum()
    frente_real = {"coste_real": sum(coste_real.values()),
                   "sistema_menos_coste_real": evaluacion.bandas(total - sum(coste_real.values())),
                   "por_producto": {p: {"coste_real": coste_real[p],
                                        "menos_coste_real": evaluacion.bandas(
                                            partes_base[regla][i[p]]["coste_total"] - coste_real[p])}
                                    for p in productos}}
    sistema = {"regla": regla,
               "veredicto_frente_a_la_actual": {p: base["productos"][p]["veredictos"]["prevision_actual"]
                                                for p in productos} if regla == PREVISION else None,
               "frente_a_la_actual": base["tres_juntos"]["frente_a_la_actual"][regla],
               "frente_al_coste_real": frente_real,
               "coste_sorteo_0": float(total.loc[0])}

    salidas.escribir_json("07_prueba_final", {
        "periodo": {"desde": config.INICIO_PRUEBA, "hasta": config.FIN_PRUEBA},
        "lo_fijado": {"objetivo": config.OBJETIVO, "objetivo_formula_manual": config.OBJETIVO_MANUAL,
                      "stock_de_seguridad": {p: d[p]["ss"] for p in productos}, "plazo_medio": config.PLAZO_MEDIO,
                      "sorteos": f"{config.REPETICIONES} repeticiones, semilla {config.SEMILLA}"},
        "reproduccion": reproduccion, "lo_que_paso": lo_que_paso,
        "eleccion_por_producto": eleccion, "comparacion": comparaciones, "sistema": sistema,
        "simulaciones": int(len(tabla) // len(config.PORCENTAJES)),
        "segundos": round(time.perf_counter() - inicio_reloj, 1)})
    lo = sistema["frente_a_la_actual"]["coste_total"]
    print(f"Elección producto a producto: {eleccion}; el sistema: {regla} en los tres")
    print(f"El sistema frente a lo que costó de verdad: {frente_real['sistema_menos_coste_real']['mediana']:.0f} €"
          f"; frente a la regla actual con los mismos plazos: {lo['mediana']:.0f} € "
          f"({lo['p5']:.0f} a {lo['p95']:.0f})")


if __name__ == "__main__":
    main()
