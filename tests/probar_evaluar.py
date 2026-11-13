"""Pruebas de `produccion/evaluar.py`: con lo que pasó de verdad en enero a junio de 2025 da el coste y los días sin
stock registrados, no cuenta nada posterior al día, y no absuelve: una venta perdida, un día de más o un stock mayor
cambian lo que mide. En una carpeta temporal.

Uso: python -W error tests/probar_evaluar.py
"""

import json
import tempfile
from pathlib import Path

import pandas as pd

from comun import RAIZ, Casos
from evaluar import evaluar
from reposicion import datos
from reposicion.produccion import config

c = Casos()
ref = json.loads((RAIZ / "tests" / "cifras_de_referencia.json").read_text(encoding="utf-8"))
FIN = "2025-06-30"


def escribir(carpeta, inv, ped):
    """Escribe la entrada en el formato del contrato."""
    carpeta.mkdir(parents=True, exist_ok=True)
    i, p = inv.copy(), ped.copy()
    i["fecha"] = i["fecha"].dt.strftime("%Y-%m-%d")
    for k in ("fecha_pedido", "fecha_llegada"):
        p[k] = p[k].dt.strftime("%Y-%m-%d")
    i.to_csv(carpeta / "inventario_diario.csv", index=False, encoding="utf-8")
    p.to_csv(carpeta / "pedidos.csv", index=False, encoding="utf-8")
    return carpeta


cf = config()
inv = pd.concat([datos.leer_inventario(cf[k] / "inventario_diario.csv") for k in ("datos_historia", "datos_nuevos")])
h = datos.leer_pedidos(cf["datos_historia"] / "pedidos.csv")
n = datos.leer_pedidos(cf["datos_nuevos"] / "pedidos.csv")
ped = pd.concat([h.loc[~h["id_pedido"].isin(n["id_pedido"])], n])

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    cf["salidas"] = tmp / "salidas"
    base = evaluar(FIN, escribir(tmp / "real", inv, ped), cf)
    c.caso("con lo que pasó, el coste del semestre es el real",
           abs(base["coste_total_tres"] - ref["coste_real_semestre"]) <= ref["tolerancia_euros"],
           f"da {base['coste_total_tres']}")
    dias = {p: x["dias_sin_stock"] for p, x in base["productos"].items()}
    c.caso("con lo que pasó, los días sin stock son 4, 16 y 21", list(dias.values()) == [4, 16, 21], str(dias))
    c.caso("mide los 181 días del semestre", all(x["dias"] == 181 for x in base["productos"].values()))
    c.caso("deja evaluacion.json en la carpeta del día", (cf["salidas"] / FIN / "evaluacion.json").is_file())

    # No cuenta nada posterior al día que mide: un día del futuro sin stock no cambia nada
    futuro = inv.loc[inv["fecha"] == inv["fecha"].max()].copy()
    futuro["fecha"] = futuro["fecha"] + pd.Timedelta(days=1)
    futuro["ventas"], futuro["ventas_perdidas"] = 0, 500
    futuro["stock_final"] = futuro["stock_inicial"] + futuro["unidades_recibidas"]
    d = evaluar(FIN, escribir(tmp / "futuro", pd.concat([inv, futuro]), ped), cf)
    c.caso("un día posterior con ventas perdidas no cuenta", d["coste_total_tres"] == base["coste_total_tres"])

    # No absuelve: lo que cambia dentro del periodo cambia la medida
    perdida = inv.copy()
    i = perdida.index[(perdida["producto"] == "Producto_A") & (perdida["fecha"] == "2025-03-03")][0]
    perdida.loc[i, "ventas_perdidas"] += 50
    d = evaluar(FIN, escribir(tmp / "perdida", perdida, ped), cf)
    c.caso("ROJO: una venta perdida más suma un día sin stock en A",
           d["productos"]["Producto_A"]["dias_sin_stock"] == dias["Producto_A"] + 1)
    c.caso("ROJO: y sube el coste en su margen, 50 × (12 - 7) = 250 €",
           abs(d["coste_total_tres"] - base["coste_total_tres"] - 250) < 1e-6)
    lleno = inv.copy()
    sel = (lleno["producto"] == "Producto_C") & (lleno["fecha"] >= "2025-01-01")
    lleno.loc[sel, ["stock_inicial", "stock_final"]] += 100
    d = evaluar(FIN, escribir(tmp / "lleno", lleno, ped), cf)
    c.caso("ROJO: 100 unidades más de stock en C suben su stock medio en 100",
           abs(d["productos"]["Producto_C"]["stock_medio"] - base["productos"]["Producto_C"]["stock_medio"] - 100) < 1e-9)
    corto = evaluar("2025-03-31", escribir(tmp / "corto", inv, ped), cf)
    c.caso("ROJO: medir hasta el 31/03 no da el coste del semestre",
           corto["coste_total_tres"] < base["coste_total_tres"]
           and all(x["dias"] == 90 for x in corto["productos"].values()))

    # Bordes: sin ningún pedido mide igual; un día anterior al periodo para en vez de dar un coste de cero
    sin = evaluar(FIN, escribir(tmp / "sin_pedidos", inv, ped.iloc[0:0]), cf)
    c.caso("ROJO del revisor: sin pedidos mide los mismos días sin stock",
           {p: x["dias_sin_stock"] for p, x in sin["productos"].items()} == dias)
    c.lanza("ROJO del revisor: medir un día anterior al periodo para",
            lambda: evaluar("2024-12-15", escribir(tmp / "antes", inv, ped), cf), ValueError)

c.fin()
