"""Paso 1 · De las tres tablas a una fila por producto y día, con demanda, unidades en camino y plazo real.

Lee `datos/` (2023 y 2024), comprueba lo que el resto del método da por hecho y deja el inventario por día y los
pedidos con su plazo en `salidas_pipeline/`, y sus cifras en `informes/01_transformacion.json`.

Uso: python pipeline/01_transformacion.py
"""

# =====================================================================================================================
# CONFIGURACIÓN
# =====================================================================================================================

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reposicion import config, datos, salidas  # noqa: E402

# =====================================================================================================================
# TRANSFORMACIÓN Y COMPROBACIONES
# =====================================================================================================================


def main():
    """Transforma, comprueba y guarda."""
    inv, ped, ficha = datos.construir()

    # Lo que el simulador y el modelo dan por hecho: calendario sin huecos, el stock cuadra, un pedido por día y producto
    # con la cantidad de la ficha, y el plazo medio redondeado es el que usa el método
    sin_huecos = all((np.diff(g["fecha"].values) == np.timedelta64(1, "D")).all() for _, g in inv.groupby("producto"))
    cuadre = (inv["stock_inicial"] + inv["unidades_recibidas"] - inv["ventas"] - inv["stock_final"] == 0).all()
    un_pedido = not ped.duplicated(["producto", "fecha_pedido"]).any()
    cantidad = (ped["cantidad"] == ped["producto"].map(ficha["politica_cantidad_pedido"])).all()
    plazo_medio = ped.loc[ped["estado"] == "recibido"].groupby("producto")["plazo_real"].mean()
    redondeo = {p: int(np.floor(float(m) + 0.5)) for p, m in plazo_medio.items()}
    comprobaciones = {
        "calendario_sin_huecos": {"ok": bool(sin_huecos), "detalle": "cada producto, de día en día"},
        "stock_cuadra": {"ok": bool(cuadre), "detalle": "stock inicial + recibido − ventas = stock final cada día"},
        "un_pedido_por_dia": {"ok": bool(un_pedido), "detalle": "como mucho un pedido por producto y día"},
        "cantidad_de_la_ficha": {"ok": bool(cantidad), "detalle": "todos los pedidos con la cantidad fija"},
        "plazo_medio_redondeado": {"ok": redondeo == config.PLAZO_MEDIO,
                                   "detalle": f"medido {plazo_medio.round(2).to_dict()}; fijado {config.PLAZO_MEDIO}"},
    }
    salidas.comprobar(comprobaciones)

    # Las tablas y sus cifras
    salidas.escribir_tabla("inventario_dia", inv)
    salidas.escribir_tabla("pedidos", ped)
    entradas = sorted(config.DATOS.glob("*.csv"))
    salidas.escribir_json("01_transformacion", {
        "entradas": [{"ruta": salidas.relativa(r), "sha256": salidas.huella(r)} for r in entradas],
        "filas": {"inventario_dia": len(inv), "pedidos": len(ped)},
        "desde": inv["fecha"].min(), "hasta": inv["fecha"].max(),
        "pedidos_por_producto": ped.groupby("producto").size().to_dict(),
        "plazo_real_medio": plazo_medio.to_dict(), "plazo_medio_fijado": config.PLAZO_MEDIO,
        "demanda_media_diaria": inv.groupby("producto")["demanda"].mean().to_dict(),
        "dias_sin_stock": inv.loc[inv["ventas_perdidas"] > 0].groupby("producto").size().to_dict(),
        "comprobaciones": comprobaciones})
    print(f"inventario_dia: {len(inv)} filas; pedidos: {len(ped)}")


if __name__ == "__main__":
    main()
