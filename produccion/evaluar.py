"""Compara lo decidido con lo que pasó: días sin stock, unidades no servidas y coste de cada producto hasta un día.

Lee la carpeta de entrada (lo que registró el almacén) y escribe `evaluacion.json` en la carpeta del día: por
producto, los días con demanda sin servir, las unidades no servidas, el stock medio y el coste del periodo con la ficha
de producto (mantener el stock, el margen de lo no servido y el coste de cada pedido).

Uso:  python produccion/evaluar.py --dia 2025-01-15 [--entrada carpeta]
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from reposicion import datos, salidas, simulador  # noqa: E402
from reposicion.produccion import config, hasta_el_dia, leer_entrada  # noqa: E402


def evaluar(dia, entrada=None, c=None, desde=None):
    """Mide lo que pasó desde `desde` (por defecto, el primer día de la simulación) hasta `dia`; devuelve el resumen."""
    c = c or config()
    entrada = Path(entrada) if entrada else c["entrada"]
    desde = pd.Timestamp(desde or c["simulacion"]["desde"])
    ficha = datos.leer_ficha(c["datos_historia"] / "productos.csv").set_index("producto")
    inv, ped = hasta_el_dia(*leer_entrada(entrada), dia)
    inv = datos.transformar_inventario(inv, datos.transformar_pedidos(ped))
    periodo = inv.loc[inv["fecha"] >= desde]
    if periodo.empty:
        raise ValueError(f"no hay días que medir entre el {desde.date()} y el {dia}")
    d = {"dia": dia, "desde": desde.date().isoformat(), "productos": {}}
    for p, g in periodo.groupby("producto"):
        diario = pd.DataFrame({"demanda": g["demanda"], "servido": g["ventas"], "no_servido": g["ventas_perdidas"],
                               "stock_final": g["stock_final"], "pedido_lanzado": g["pedido_lanzado"]})
        ind = simulador.indicadores(diario, ficha.loc[p])
        d["productos"][p] = {k: ind[k] for k in ("dias", "dias_sin_stock", "unidades_no_servidas", "fill_rate",
                                                  "stock_medio", "pedidos", "coste_total")}
    d["coste_total_tres"] = sum(x["coste_total"] for x in d["productos"].values())
    carpeta = c["salidas"] / dia
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "evaluacion.json").write_text(json.dumps(salidas.limpio(d), ensure_ascii=False, indent=2),
                                             encoding="utf-8")
    return d


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--dia", required=True, help="último día que se mide, AAAA-MM-DD")
    argumentos.add_argument("--entrada", default=None, help="carpeta con inventario_diario.csv y pedidos.csv")
    a = argumentos.parse_args()
    d = evaluar(a.dia, a.entrada)
    for p, x in d["productos"].items():
        print(f"{p}: {x['dias_sin_stock']} días sin stock, {x['unidades_no_servidas']} unidades no servidas, "
              f"coste {x['coste_total']:.0f} €")
