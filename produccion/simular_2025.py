"""Simula seis meses de funcionamiento: los 181 días de enero a junio de 2025, uno detrás de otro.

1. Reentrena con la historia hasta el 31/12/2024, como la prueba final. Todo en sus propias carpetas
   (`produccion/salidas_simulacion/` y `modelos_simulacion/`): no toca las salidas ni el modelo del proceso diario.
2. Hace de almacén cada día: llegan los pedidos que tocan, se sirve la demanda real de 2025 y se escriben los ficheros
   de entrada del día. Después lanza `ejecutar` y `evaluar` para ese día y, si la decisión es pedir, lanza el pedido.
3. Los pedidos de las reglas nuevas no tienen plazo real, porque salen otros días que los de verdad: llegan con el
   plazo sorteado de la prueba final (sorteo 0), en el mismo orden. Con `--control` los tres productos siguen la regla
   actual y los pedidos llegan cuando llegaron de verdad.
4. Comprueba el despliegue de principio a fin y escribe `informes/despliegue.json`: que no falte ningún día (aviso por
   ausencia) y que el proceso da, día a día, lo mismo que el simulador de la prueba final con el mismo sorteo; con
   `--control`, que da lo que pasó de verdad, día a día, y su coste.

Enero a junio de 2025 ya se usó como prueba final: esta simulación demuestra cómo funciona el proceso día a día, no es
una prueba nueva. Las salidas y el modelo de una simulación anterior se borran al empezar, porque se regeneran
enteros.

Uso:  python produccion/simular_2025.py [--control] [--sin-reentrenar]
"""

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "produccion"))

from ejecutar import ejecutar  # noqa: E402
from evaluar import evaluar  # noqa: E402
from reentrenar import reentrenar  # noqa: E402

from reposicion import config as metodo  # noqa: E402
from reposicion import datos, salidas, simulador, stock  # noqa: E402
from reposicion.produccion import EntradaIncorrecta, cargar_modelos, config  # noqa: E402

CAMPOS = ["dia", "pedidos_lanzados", "dias_sin_stock", "unidades_no_servidas", "coste_acumulado"]
COLUMNAS_INV = ["fecha", "producto", "stock_inicial", "unidades_recibidas", "ventas", "ventas_perdidas", "stock_final",
                "demanda_estimada"]
COLUMNAS_PED = ["id_pedido", "producto", "fecha_pedido", "fecha_llegada", "cantidad", "estado"]

# =====================================================================================================================
# 1. El almacén
# =====================================================================================================================


def reglas_de_control(c):
    """La configuración con la regla actual en los tres productos, con los parámetros de la ficha."""
    ficha = datos.leer_ficha(c["datos_historia"] / "productos.csv").set_index("producto")
    c = dict(c)
    c["productos"] = {p: {"regla": metodo.ACTUAL, "objetivo": None,
                          "stock_seguridad": int(ficha.loc[p, "politica_stock_seguridad"]),
                          "plazo": int(ficha.loc[p, "lead_time_prometido"]),
                          "cantidad": int(ficha.loc[p, "politica_cantidad_pedido"])} for p in c["productos"]}
    return c


def asignadores(c, control, historia_ped, nuevos_ped, productos, inicio):
    """El plazo de cada pedido: el real, en orden, con --control; si no, el sorteo de la prueba final."""
    if control:
        # Un pedido que seguía pendiente al cierre del 30/06/2025 no tiene plazo: no llega dentro de la ventana
        return {p: simulador.PlazosReales(
            [None if pd.isna(x) else int(x) for x in nuevos_ped.loc[(nuevos_ped["producto"] == p)
                                                                    & (nuevos_ped["fecha_pedido"] >= inicio)]
             .sort_values(["fecha_pedido", "id_pedido"])["plazo_real"]]) for p in productos}
    s = c["simulacion"]
    return {p: simulador.PlazosSorteados(datos.plazos_para_sortear(historia_ped, p), s["semilla"], (s["sorteo"], i))
            for i, p in enumerate(productos)}


def llegadas_iniciales(control, historia_ped, nuevos_ped, asignador, productos, inicio):
    """Cuándo llegan los pedidos pendientes al cierre de 2024: su fecha real con --control; si no, el primer plazo
    sorteado de su producto, contado desde su fecha de pedido, como en la prueba final."""
    llegada = {}
    for p in productos:
        pend = historia_ped.loc[(historia_ped["producto"] == p) & historia_ped["fecha_llegada"].isna()]
        if control:
            reales = nuevos_ped.set_index("id_pedido")["fecha_llegada"]
            llegada.update({i: reales.loc[i] for i in pend["id_pedido"]})
        else:
            for o in simulador.arranque_sorteado(pend, asignador[p], inicio):
                llegada[o["id_pedido"]] = inicio + pd.Timedelta(days=o["dia_llegada"])
    return llegada


def escribir_entrada(carpeta, inv, ped, dia):
    """Los dos ficheros de entrada del día, como los dejaría el sistema del almacén: nada posterior al día."""
    carpeta.mkdir(parents=True, exist_ok=True)
    i = inv.copy()
    i["fecha"] = i["fecha"].dt.strftime("%Y-%m-%d")
    i[COLUMNAS_INV].to_csv(carpeta / "inventario_diario.csv", index=False, encoding="utf-8")
    p = ped.copy()
    conocida = p["llegada_prevista"].notna() & (p["llegada_prevista"] <= dia)
    p["fecha_llegada"] = p["llegada_prevista"].where(conocida).dt.strftime("%Y-%m-%d")
    p["estado"] = np.where(conocida, "recibido", "pendiente")
    p["fecha_pedido"] = p["fecha_pedido"].dt.strftime("%Y-%m-%d")
    p[COLUMNAS_PED].to_csv(carpeta / "pedidos.csv", index=False, encoding="utf-8")


# =====================================================================================================================
# 2. La simulación de los días
# =====================================================================================================================


def simular(control=False, reentrenar_antes=True):
    """Los días de la ventana de `config.json`; devuelve el informe del despliegue y el registro."""
    # La simulación escribe y entrena en sus propias carpetas: nunca toca las salidas ni el modelo del proceso diario
    c = config()
    c.update({"salidas": c["simulacion"]["salidas"], "modelos": c["simulacion"]["modelos"]})
    c_reglas = {**reglas_de_control(c), "salidas": c["salidas"]} if control else c
    dias = pd.date_range(c["simulacion"]["desde"], c["simulacion"]["hasta"])
    inicio = dias[0]
    if c["salidas"].exists():
        shutil.rmtree(c["salidas"])
    if reentrenar_antes and c["modelos"].exists():
        shutil.rmtree(c["modelos"])
    decision_reentreno = reentrenar(c=c) if reentrenar_antes else None
    modelos, manifiesto = cargar_modelos(c=c)
    entrada = c["salidas"] / "entrada"

    # El punto de partida: la historia hasta la víspera del primer día y la demanda real de la ventana
    hist_inv, hist_ped, _ = datos.leer_tablas(c["datos_historia"])
    nuevos_inv, nuevos_ped, _ = datos.leer_tablas(c["datos_nuevos"])
    nuevos_inv = nuevos_inv.loc[nuevos_inv["fecha"].isin(dias)]
    nuevos_ped = datos.transformar_pedidos(nuevos_ped)
    productos = sorted(c["productos"])
    asignador = asignadores(c, control, datos.transformar_pedidos(hist_ped), nuevos_ped, productos, inicio)
    llegada = llegadas_iniciales(control, datos.transformar_pedidos(hist_ped), nuevos_ped, asignador, productos, inicio)
    ped = hist_ped.copy()
    ped["llegada_prevista"] = ped["fecha_llegada"].where(ped["fecha_llegada"].notna(), ped["id_pedido"].map(llegada))
    inv = hist_inv.copy()
    demanda = nuevos_inv.assign(demanda=nuevos_inv["ventas"] + nuevos_inv["ventas_perdidas"]).set_index(
        ["producto", "fecha"])["demanda"]
    stock_actual = {p: int(hist_inv.loc[(hist_inv["producto"] == p) & (hist_inv["fecha"] == inicio - pd.Timedelta(days=1)),
                                        "stock_final"].iloc[0]) for p in productos}
    siguiente_id = int(ped["id_pedido"].str[4:].astype(int).max()) + 1
    filas_registro = []

    for dia in dias:
        # El día en el almacén: llega lo que toca y se sirve la demanda hasta donde llega el stock
        nuevas = []
        for p in productos:
            recibido = int(ped.loc[(ped["producto"] == p) & (ped["llegada_prevista"] == dia), "cantidad"].sum())
            inicial = stock_actual[p]
            disponible = inicial + recibido
            ventas = min(disponible, int(demanda.loc[(p, dia)]))
            stock_actual[p] = disponible - ventas
            nuevas.append({"fecha": dia, "producto": p, "stock_inicial": inicial, "unidades_recibidas": recibido,
                           "ventas": ventas, "ventas_perdidas": int(demanda.loc[(p, dia)]) - ventas,
                           "stock_final": stock_actual[p], "demanda_estimada": False})
        inv = pd.concat([inv, pd.DataFrame(nuevas)], ignore_index=True)
        escribir_entrada(entrada, inv, ped, dia)

        # El proceso al cierre del día: decide con los ficheros de entrada y lo mide con lo que pasó
        # Si un día falla, ejecutar lo anota y ese día no se pide; al final, el aviso por ausencia lo recoge
        try:
            d = ejecutar(dia.strftime("%Y-%m-%d"), entrada, c_reglas, modelos, manifiesto)
        except EntradaIncorrecta:
            d = pd.DataFrame(columns=["producto", "pedir", "cantidad"]).astype({"pedir": bool})
        lanzados = []
        for f in d.loc[d["pedir"]].itertuples(index=False):
            plazo = asignador[f.producto].siguiente()
            ped = pd.concat([ped, pd.DataFrame([{
                "id_pedido": f"PED-{siguiente_id:04d}", "producto": f.producto, "fecha_pedido": dia,
                "fecha_llegada": pd.NaT, "cantidad": int(f.cantidad), "estado": "pendiente",
                "llegada_prevista": pd.NaT if plazo is None else dia + pd.Timedelta(days=int(plazo))}])],
                ignore_index=True)
            siguiente_id += 1
            lanzados.append(f.producto)
        escribir_entrada(entrada, inv, ped, dia)
        e = evaluar(dia.strftime("%Y-%m-%d"), entrada, c)
        filas_registro.append({"dia": dia.strftime("%Y-%m-%d"), "pedidos_lanzados": " ".join(lanzados),
                               "dias_sin_stock": sum(x["dias_sin_stock"] for x in e["productos"].values()),
                               "unidades_no_servidas": sum(x["unidades_no_servidas"] for x in e["productos"].values()),
                               "coste_acumulado": round(e["coste_total_tres"], 2)})
    with (c["salidas"] / "registro.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas_registro)

    # Aviso por ausencia: tiene que estar la decisión de todos los días de la ventana, en OK
    ejecuciones = pd.read_csv(c["salidas"] / "ejecuciones.csv", dtype={"dia": str})
    hechos = set(ejecuciones.loc[ejecuciones["estado"] == "OK", "dia"])
    faltan = [x for x in dias.strftime("%Y-%m-%d") if x not in hechos]
    control_ok = (comparar_con_lo_que_paso(inv, nuevos_inv, inicio) if control else
                  comparar_con_el_simulador(inv, c, productos, inicio))
    informe = {
        "forma": "proceso por lotes, una ejecución al cierre de cada día",
        "configuracion": "produccion/config.json", "programacion": c["programacion"], "avisos": c["avisos"],
        "vuelta_atras": {"modelo": "python produccion/volver_atras.py", "codigo": "git checkout <etiqueta>"},
        "modo": "control: la regla actual con los plazos reales" if control else
                "la regla del sistema en todos los productos, con el plazo sorteado número 0",
        "reglas": {p: x["regla"] for p, x in c_reglas["productos"].items()},
        "reentreno": decision_reentreno,
        "modelo_en_uso": {"entrenado_hasta": manifiesto["entrenado_hasta"], "fecha": manifiesto["fecha"]},
        "ventana": {"desde": filas_registro[0]["dia"], "hasta": filas_registro[-1]["dia"], "esperados": len(dias),
                    "hechos": len(hechos), "faltan": faltan},
        "final": filas_registro[-1],
        "prueba_de_principio_a_fin": {**control_ok,
                                      "resultado": "OK" if (control_ok["ok"] and not faltan) else "ERROR"}}
    c["informe_despliegue"].parent.mkdir(exist_ok=True)
    c["informe_despliegue"].write_text(json.dumps(salidas.limpio(informe), ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    return informe


# =====================================================================================================================
# 3. Las comprobaciones de principio a fin
# =====================================================================================================================


def comparar_con_lo_que_paso(inv, nuevos_inv, inicio):
    """Con la regla actual y los plazos reales, el almacén simulado tiene que ser el registrado, día a día."""
    columnas = ["stock_inicial", "unidades_recibidas", "ventas", "ventas_perdidas", "stock_final"]
    sim = inv.loc[inv["fecha"] >= inicio].sort_values(["producto", "fecha"]).reset_index(drop=True)
    real = nuevos_inv.sort_values(["producto", "fecha"]).reset_index(drop=True)
    iguales = (sim[columnas].to_numpy() == real[columnas].to_numpy()).all(axis=1)
    por_producto = {p: f"{int(iguales[(sim['producto'] == p).to_numpy()].sum())} de "
                       f"{int((sim['producto'] == p).sum())} días iguales" for p in sorted(sim["producto"].unique())}
    return {"que": "con la regla actual y los plazos reales, el almacén simulado es el registrado",
            "ok": bool(iguales.all()), "por_producto": por_producto}


def comparar_con_el_simulador(inv, c, productos, inicio):
    """Con la regla del sistema y el sorteo 0, el proceso día a día da lo mismo que el simulador de la prueba final."""
    cons, ped = salidas.leer_tabla("inventario_dia"), salidas.leer_tabla("pedidos")
    prevision = salidas.leer_tabla("prevision_2025")
    ficha = datos.leer_ficha(c["datos_historia"] / "productos.csv").set_index("producto")
    sim = inv.loc[inv["fecha"] >= inicio]
    resultado = {}
    for i, p in enumerate(productos):
        x, f = c["productos"][p], ficha.loc[p]
        g = cons.loc[cons["producto"] == p].sort_values("fecha")
        anio24 = g.loc[g["fecha"].dt.year == metodo.ANIO_MEDIDA]
        dem = sim.loc[sim["producto"] == p].sort_values("fecha")
        dem25 = (dem["ventas"] + dem["ventas_perdidas"]).to_numpy()
        if x["regla"] == metodo.ACTUAL:
            regla = simulador.regla_actual(int(f["politica_stock_seguridad"]), int(f["lead_time_prometido"]))
        else:
            toda = np.concatenate([g["demanda"].to_numpy(dtype=float), dem25.astype(float)])
            prev = (prevision.loc[prevision["producto"] == p].sort_values("fecha")["prevision_plazo"].to_numpy()
                    if x["regla"] == metodo.PREVISION else
                    stock.prevision_media(toda, np.arange(len(g), len(toda)), x["plazo"]))
            regla = simulador.regla_de_puntos(stock.punto_de_pedido(prev, x["stock_seguridad"]))
        s = c["simulacion"]
        asignador = simulador.PlazosSorteados(datos.plazos_para_sortear(ped, p), s["semilla"], (s["sorteo"], i))
        en_camino = simulador.arranque_sorteado(ped.loc[(ped["producto"] == p) & ped["fecha_llegada"].isna()],
                                                asignador, inicio)
        diario, _ = simulador.simular(dem25, regla, asignador, int(g["stock_final"].iloc[-1]), int(x["cantidad"]),
                                      en_camino_inicial=en_camino,
                                      historia_previa={"ventas": anio24["ventas"].to_numpy(),
                                                       "demanda": anio24["demanda"].to_numpy()})
        iguales = ((diario["stock_final"].to_numpy() == dem["stock_final"].to_numpy())
                   & (diario["servido"].to_numpy() == dem["ventas"].to_numpy())
                   & (diario["recibido"].to_numpy() == dem["unidades_recibidas"].to_numpy()))
        resultado[p] = {"dias_iguales": int(iguales.sum()), "dias": int(len(iguales))}
    return {"que": "el proceso día a día da lo mismo que el simulador de la prueba final con el sorteo 0",
            "ok": all(r["dias_iguales"] == r["dias"] for r in resultado.values()), "por_producto": resultado}


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--control", action="store_true", help="la regla actual con los plazos reales")
    argumentos.add_argument("--sin-reentrenar", action="store_true", help="usar el modelo vigente sin reentrenar")
    a = argumentos.parse_args()
    informe = simular(a.control, not a.sin_reentrenar)
    p = informe["prueba_de_principio_a_fin"]
    if informe["ventana"]["faltan"]:
        sys.exit(f"ERROR: faltan ejecuciones (aviso por ausencia): {informe['ventana']['faltan']}")
    if p["resultado"] != "OK":
        sys.exit(f"ERROR: la prueba de principio a fin no pasa: {json.dumps(p, ensure_ascii=False)}")
    f = informe["final"]
    print(f"OK: {informe['ventana']['hechos']} días simulados, ninguno falta; {f['dias_sin_stock']} días sin stock "
          f"sumando los tres productos, coste del semestre {f['coste_acumulado']:.0f} €; {p['que']}")
