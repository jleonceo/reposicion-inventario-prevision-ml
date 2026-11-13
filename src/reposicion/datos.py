"""Lectura de las tres tablas y su transformación a una fila por producto y día.

Las tablas llegan en CSV: inventario diario, pedidos al proveedor y ficha de producto. La transformación añade lo que
el resto del método necesita: la demanda (ventas más ventas perdidas), lo que viene en camino cada día, la posición de
stock y el plazo real de cada pedido. No se quita ni se corrige ningún registro.
"""

from pathlib import Path

import pandas as pd

from . import config

# =====================================================================================================================
# 1. Lectura
# =====================================================================================================================

FORMATO_FECHA = "%Y-%m-%d"


def leer_inventario(ruta):
    """El inventario diario con sus tipos: una fila por producto y día."""
    inv = pd.read_csv(ruta, encoding="utf-8", dtype={"producto": "str", "demanda_estimada": "bool"})
    inv["fecha"] = pd.to_datetime(inv["fecha"], format=FORMATO_FECHA)
    return inv


def leer_pedidos(ruta, pendientes_sin_llegada=True):
    """Los pedidos al proveedor con sus tipos.

    Un pedido pendiente al cierre de los datos llega después: su fecha de llegada, si la trae, es información del
    futuro y se deja vacía.
    """
    ped = pd.read_csv(ruta, encoding="utf-8",
                      dtype={"id_pedido": "str", "producto": "str", "estado": "str", "fecha_llegada": "str"})
    ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], format=FORMATO_FECHA)
    ped["fecha_llegada"] = pd.to_datetime(ped["fecha_llegada"], format=FORMATO_FECHA)
    if pendientes_sin_llegada:
        ped.loc[ped["estado"] == "pendiente", "fecha_llegada"] = pd.NaT
    return ped


def leer_ficha(ruta):
    """La ficha de producto: precio, coste, plazo prometido y regla actual de cada producto."""
    return pd.read_csv(ruta, encoding="utf-8", dtype={"producto": "str"})


def leer_tablas(carpeta=config.DATOS):
    """Las tres tablas de una carpeta: inventario, pedidos y ficha."""
    carpeta = Path(carpeta)
    return (leer_inventario(carpeta / "inventario_diario.csv"), leer_pedidos(carpeta / "pedidos.csv"),
            leer_ficha(carpeta / "productos.csv"))


# =====================================================================================================================
# 2. Transformación
# =====================================================================================================================

def transformar_pedidos(ped):
    """Añade el plazo real de cada pedido: días naturales entre el pedido y la llegada; vacío si no ha llegado."""
    df = ped.copy()
    df["plazo_real"] = (df["fecha_llegada"] - df["fecha_pedido"]).dt.days.astype("Int64")
    return df


def dias_en_camino(ped, fecha_fin):
    """Una fila por pedido y día en que está en camino: del día del pedido a la víspera de su llegada.

    Un pedido sin llegada sigue en camino hasta el último día de los datos.
    """
    filas = []
    for p in ped.itertuples(index=False):
        ultimo = fecha_fin if pd.isna(p.fecha_llegada) else p.fecha_llegada - pd.Timedelta(days=1)
        dias = pd.date_range(p.fecha_pedido, ultimo, freq="D")
        filas.append(pd.DataFrame({"producto": p.producto, "fecha": dias, "cantidad": p.cantidad}))
    # Sin pedidos no hay nada en camino: una tabla vacía con sus columnas y tipos
    vacia = pd.DataFrame({"producto": pd.Series(dtype="str"), "fecha": pd.Series(dtype="datetime64[ns]"),
                          "cantidad": pd.Series(dtype="int64")})
    return pd.concat(filas, ignore_index=True) if filas else vacia


def transformar_inventario(inv, ped):
    """El inventario por producto y día con demanda, unidades en camino, posición de stock y día de pedido.

    Solo quedan los días del inventario: un pedido lanzado antes del primer día suma en camino desde ese primer día.
    """
    camino = (dias_en_camino(ped, inv["fecha"].max()).groupby(["producto", "fecha"], as_index=False)
              .agg(en_camino=("cantidad", "sum")))
    lanzados = ped[["producto", "fecha_pedido"]].drop_duplicates().rename(columns={"fecha_pedido": "fecha"})
    lanzados["pedido_lanzado"] = True

    # Un día sin pedidos en camino ni lanzados vale cero y falso: todos los pedidos están en la tabla de pedidos
    df = inv.merge(camino, on=["producto", "fecha"], how="left", validate="1:1")
    df = df.merge(lanzados, on=["producto", "fecha"], how="left", validate="1:1")
    df["en_camino"] = df["en_camino"].fillna(0).astype("int64")
    df["pedido_lanzado"] = df["pedido_lanzado"].astype("boolean").fillna(False).astype("bool")

    # Demanda: lo que pidieron los clientes, servido o no; la posición cuenta lo que ya viene en camino
    df["demanda"] = (df["ventas"] + df["ventas_perdidas"]).astype("int64")
    df["posicion_stock"] = (df["stock_final"] + df["en_camino"]).astype("int64")
    df["anio"] = df["fecha"].dt.year.astype("int64")
    return df.sort_values(["producto", "fecha"]).reset_index(drop=True)


def construir(carpeta=config.DATOS):
    """El inventario por día, los pedidos con su plazo y la ficha indexada por producto, del periodo 2023-2024."""
    inv, ped, ficha = leer_tablas(carpeta)
    ped = transformar_pedidos(ped).sort_values(["producto", "fecha_pedido", "id_pedido"]).reset_index(drop=True)
    return transformar_inventario(inv, ped), ped, ficha.set_index("producto")


def plazos_para_sortear(pedidos, producto):
    """Los plazos reales de los pedidos recibidos de un producto, en el orden en que se lanzaron.

    Son los valores de los que se sortea el plazo de cada pedido simulado; el orden importa, porque el sorteo elige
    posiciones de esta lista.
    """
    g = pedidos.loc[(pedidos["producto"] == producto) & (pedidos["estado"] == "recibido")]
    return g.sort_values("fecha_pedido")["plazo_real"].astype("int64").to_numpy()
