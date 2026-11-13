"""Pruebas del proceso diario que buscan romperlo: datos del futuro, fichero de ayer, un producto de menos, filas
desordenadas, productos cambiados de sitio y un día sin fichero. Todo en una carpeta temporal: no toca los modelos ni
las salidas del repositorio.

Uso: python -W error tests/probar_produccion.py
"""

import tempfile
from pathlib import Path

import pandas as pd

from comun import Casos
from ejecutar import ejecutar
from reentrenar import reentrenar
from reposicion import datos
from reposicion.produccion import EntradaIncorrecta, config

c = Casos()
DIA = "2025-03-10"


def entrada_real(carpeta, dia, inv=None, ped=None):
    """Escribe la entrada del cierre de `dia` con lo que pasó de verdad: la historia y 2025 hasta ese día, y los
    pedidos con su llegada solo si ya ha llegado."""
    cf = config()
    if inv is None:
        inv = pd.concat([datos.leer_inventario(cf[k] / "inventario_diario.csv") for k in ("datos_historia",
                                                                                         "datos_nuevos")])
        inv = inv.loc[inv["fecha"] <= dia]
    if ped is None:
        h = datos.leer_pedidos(cf["datos_historia"] / "pedidos.csv")
        n = datos.leer_pedidos(cf["datos_nuevos"] / "pedidos.csv")
        ped = pd.concat([h.loc[~h["id_pedido"].isin(n["id_pedido"])], n])
        ped = ped.loc[ped["fecha_pedido"] <= dia].copy()
        ped.loc[ped["fecha_llegada"] > dia, "fecha_llegada"] = pd.NaT
        ped["estado"] = ped["fecha_llegada"].notna().map({True: "recibido", False: "pendiente"})
    carpeta.mkdir(parents=True, exist_ok=True)
    i, p = inv.copy(), ped.copy()
    i["fecha"] = pd.to_datetime(i["fecha"]).dt.strftime("%Y-%m-%d")
    p["fecha_pedido"] = p["fecha_pedido"].dt.strftime("%Y-%m-%d")
    p["fecha_llegada"] = p["fecha_llegada"].dt.strftime("%Y-%m-%d")
    i.to_csv(carpeta / "inventario_diario.csv", index=False, encoding="utf-8")
    p.to_csv(carpeta / "pedidos.csv", index=False, encoding="utf-8")
    return inv, ped


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    cf = config()
    cf.update({"modelos": tmp / "modelos", "salidas": tmp / "salidas"})
    reentrenar("2024-12-31", cf)
    inv, ped = entrada_real(tmp / "e_ok", DIA)
    base = ejecutar(DIA, tmp / "e_ok", cf)
    c.caso("un día correcto deja la línea de los tres productos",
           sorted(base["producto"]) == sorted(cf["productos"]) and (cf["salidas"] / DIA / "decision.csv").is_file())

    # Datos del futuro: filas posteriores al día con valores absurdos no cambian la decisión
    futuro = inv.loc[inv["fecha"] == inv["fecha"].max()].copy()
    futuro["fecha"] = futuro["fecha"] + pd.Timedelta(days=1)
    futuro[["ventas", "stock_inicial", "stock_final"]] = [0, 999_999, 999_999]
    entrada_real(tmp / "e_futuro", DIA, pd.concat([inv, futuro]), ped)
    d = ejecutar(DIA, tmp / "e_futuro", cf)
    c.caso("no ve ningún dato posterior al día: las filas del futuro no cambian la decisión", d.equals(base))

    # Rojo: el mismo día con la entrada de la víspera para
    entrada_real(tmp / "e_ayer", "2025-03-09")
    c.lanza("ROJO: con el fichero de ayer para", lambda: ejecutar(DIA, tmp / "e_ayer", cf), EntradaIncorrecta)
    c.caso("ROJO: con el fichero de ayer no deja decisión nueva",
           pd.read_csv(cf["salidas"] / "ejecuciones.csv")["estado"].iloc[-1] == "ERROR")

    # Rojo: un producto de menos
    entrada_real(tmp / "e_menos", DIA, inv.loc[inv["producto"] != "Producto_B"], ped)
    motivo = c.lanza("ROJO: con un producto de menos para", lambda: ejecutar(DIA, tmp / "e_menos", cf),
                     EntradaIncorrecta)
    c.caso("el motivo nombra el producto que falta", motivo is not None and "Producto_B" in motivo)

    # Filas en otro orden: la misma decisión; productos cambiados de sitio: otra
    entrada_real(tmp / "e_desorden", DIA, inv.sample(frac=1, random_state=1), ped.sample(frac=1, random_state=1))
    c.caso("con las filas desordenadas la decisión es la misma", ejecutar(DIA, tmp / "e_desorden", cf).equals(base))
    cambiado = inv.copy()
    cambiado["producto"] = cambiado["producto"].replace({"Producto_A": "Producto_C", "Producto_C": "Producto_A"})
    entrada_real(tmp / "e_cambiado", DIA, cambiado, ped)
    d = ejecutar(DIA, tmp / "e_cambiado", cf)
    c.caso("ROJO: con los productos cambiados de sitio la decisión cambia",
           not d[["posicion", "punto_pedido"]].equals(base[["posicion", "punto_pedido"]]))

    # Rojo: sin fichero del día no deja salida y lo anota
    c.lanza("ROJO: sin fichero del día para", lambda: ejecutar("2025-03-11", tmp / "no_existe", cf), EntradaIncorrecta)
    c.caso("sin fichero del día no deja carpeta de salida", not (cf["salidas"] / "2025-03-11").exists())
    c.caso("sin fichero del día lo anota en el registro con su motivo",
           "no llega el fichero" in pd.read_csv(cf["salidas"] / "ejecuciones.csv")["motivo"].iloc[-1])

    # Rojo: un stock que no cuadra
    roto = inv.copy()
    roto.loc[roto.index[-1], "stock_final"] += 5
    entrada_real(tmp / "e_roto", DIA, roto, ped)
    c.lanza("ROJO: con el stock descuadrado para", lambda: ejecutar(DIA, tmp / "e_roto", cf), EntradaIncorrecta)

    # Volver a ejecutar un día archiva la salida anterior en vez de pisarla
    ejecutar(DIA, tmp / "e_ok", cf)
    c.caso("repetir un día archiva la salida anterior", any((cf["salidas"] / "_archivo").glob(f"{DIA}_*")))

    # -----------------------------------------------------------------------------------------------------------------
    # Las entradas malas que cambiaban la decisión sin avisar (revisión externa), con un día en que C tiene un pedido
    # en camino. Cada una tiene que parar.
    # -----------------------------------------------------------------------------------------------------------------
    D2 = "2025-02-06"
    inv2, ped2 = entrada_real(tmp / "f_ok", D2)
    inv2, ped2 = inv2.reset_index(drop=True), ped2.reset_index(drop=True)
    base2 = ejecutar(D2, tmp / "f_ok", cf).set_index("producto")
    c.caso("el día de control tiene un pedido de C en camino", base2.loc["Producto_C", "en_camino"] > 0)
    pend = ped2.index[(ped2["producto"] == "Producto_C") & ped2["fecha_llegada"].isna()][0]
    ultima_a = inv2.index[(inv2["producto"] == "Producto_A") & (inv2["fecha"] == D2)][0]

    def para(nombre, inv_m=None, ped_m=None):
        """Un caso que pasa si la entrada cambiada para la ejecución."""
        carpeta = tmp / f"f_{c.total}"
        entrada_real(carpeta, D2, inv2 if inv_m is None else inv_m, ped2 if ped_m is None else ped_m)
        c.lanza(f"ROJO: {nombre} para", lambda: ejecutar(D2, carpeta, cf), EntradaIncorrecta)

    def con(tabla, fila, cambios):
        """Una copia de la tabla con los valores de una fila cambiados; el stock final se recalcula si cambia algo
        del cuadre, para que lo único malo sea el cambio que se prueba."""
        t = tabla.copy()
        for columna, valor in cambios.items():
            t.loc[fila, columna] = valor
        if "stock_final" in t.columns and "stock_final" not in cambios:
            t.loc[fila, "stock_final"] = (t.loc[fila, "stock_inicial"] + t.loc[fila, "unidades_recibidas"]
                                          - t.loc[fila, "ventas"])
        return t

    para("un pedido con el producto mal escrito", ped_m=con(ped2, pend, {"producto": "producto_c"}))
    para("un pedido sin fecha de pedido", ped_m=con(ped2, pend, {"fecha_pedido": pd.NaT}))
    para("una llegada anterior a su pedido", ped_m=con(ped2, pend, {
        "fecha_llegada": ped2.loc[pend, "fecha_pedido"] - pd.Timedelta(days=2), "estado": "recibido"}))
    para("un pedido repetido", ped_m=pd.concat([ped2, ped2.loc[[pend]]]))
    para("un estado que no es recibido ni pendiente", ped_m=con(ped2, pend, {"estado": "en_ruta"}))
    para("un pedido recibido sin llegada", ped_m=con(ped2, pend, {"estado": "recibido"}))
    para("un pedido sin unidades", ped_m=con(ped2, pend, {"cantidad": 0}))
    para("ventas perdidas negativas", inv_m=con(inv2, ultima_a, {"ventas_perdidas": -5000}))
    para("ventas negativas con el stock cuadrado", inv_m=con(inv2, ultima_a, {"ventas": -300}))
    para("unidades recibidas negativas", inv_m=con(inv2, ultima_a, {"unidades_recibidas": -50}))
    para("un stock inicial distinto del final de la víspera",
         inv_m=con(inv2, ultima_a, {"stock_inicial": inv2.loc[ultima_a, "stock_inicial"] + 100_000}))
    para("un día repetido", inv_m=pd.concat([inv2, inv2.loc[[ultima_a]]]))
    para("un hueco en la historia", inv_m=inv2.drop(index=inv2.index[(inv2["producto"] == "Producto_B")
                                                                     & (inv2["fecha"] == "2025-01-15")]))
    para("menos de 30 días de historia", inv_m=inv2.loc[(inv2["producto"] != "Producto_A")
                                                        | (inv2["fecha"] > pd.Timestamp(D2) - pd.Timedelta(days=10))])
    decimal = inv2.astype({"ventas_perdidas": "float64"})
    decimal.loc[ultima_a, "ventas_perdidas"] += 0.5
    para("una columna de unidades con decimales", inv_m=decimal)
    para("un stock final negativo", inv_m=con(inv2, ultima_a, {
        "ventas": int(inv2.loc[ultima_a, "stock_inicial"] + inv2.loc[ultima_a, "unidades_recibidas"]) + 1}))

    # Lo del futuro en los pedidos no se usa: una llegada posterior al día y un pedido lanzado después no cambian nada
    futuro = con(ped2, pend, {"fecha_llegada": pd.Timestamp(D2) + pd.Timedelta(days=3), "estado": "recibido"})
    nuevo = ped2.loc[[pend]].copy()
    nuevo["id_pedido"], nuevo["producto"] = "PED-9999", "Producto_A"
    nuevo["fecha_pedido"] = pd.Timestamp(D2) + pd.Timedelta(days=1)
    entrada_real(tmp / "f_futuro", D2, inv2, pd.concat([futuro, nuevo]))
    d = ejecutar(D2, tmp / "f_futuro", cf).set_index("producto")
    c.caso("ROJO del revisor: un pedido y una llegada posteriores al día no cambian la decisión",
           d[["en_camino", "posicion", "pedir"]].equals(base2[["en_camino", "posicion", "pedir"]]),
           f"en camino {d['en_camino'].to_dict()} frente a {base2['en_camino'].to_dict()}")

    # Los fallos que no son del contrato también paran y se anotan
    def ultimo_motivo():
        """El estado y el motivo de la última fila del registro de ejecuciones."""
        r = pd.read_csv(cf["salidas"] / "ejecuciones.csv", keep_default_na=False).iloc[-1]
        return r["estado"], r["motivo"]

    for mala in ("2025-2-30", "2025-02-06 ", "hoy"):
        c.lanza(f"ROJO: la fecha «{mala}» para", lambda: ejecutar(mala, tmp / "f_ok", cf), EntradaIncorrecta)
        c.caso(f"la fecha «{mala}» queda anotada como error", ultimo_motivo()[0] == "ERROR")
    sin_modelo = {**cf, "modelos": tmp / "no_hay_modelos"}
    c.lanza("ROJO: sin modelo para", lambda: ejecutar(D2, tmp / "f_ok", sin_modelo), EntradaIncorrecta)
    c.caso("sin modelo queda anotado con su motivo", "no hay modelo" in ultimo_motivo()[1])

    # Aviso por ausencia: si falta la decisión de la víspera, decide igual y lo anota
    entrada_real(tmp / "g_08", "2025-02-08")
    ejecutar("2025-02-08", tmp / "g_08", cf)
    estado, motivo = ultimo_motivo()
    c.caso("ROJO: sin la decisión del 07/02, la del 08/02 lleva el aviso por ausencia",
           estado == "OK" and "ausencia" in motivo, f"{estado}: {motivo}")
    entrada_real(tmp / "g_09", "2025-02-09")
    ejecutar("2025-02-09", tmp / "g_09", cf)
    c.caso("con la decisión de la víspera no hay aviso", ultimo_motivo() == ("OK", ""), str(ultimo_motivo()))

c.fin()
