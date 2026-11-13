"""Simulador del almacén: un producto, día a día, con una regla de pedido.

Cada día, en este orden: llega lo que toca y entra en el stock; se sirve la demanda hasta donde llega el stock y lo que
falta se pierde; se revisa la posición (stock más lo que viene en camino) y se lanza un pedido de cantidad fija si está
en el punto de pedido o por debajo. El plazo de cada pedido lo da un asignador: los plazos reales en su orden, para
reproducir lo que pasó, o sorteados de los plazos reales del proveedor, para comparar reglas.
"""

import numpy as np
import pandas as pd

from . import config

# =====================================================================================================================
# 1. Asignadores de plazo
# =====================================================================================================================


class PlazosReales:
    """Da a cada pedido nuevo el plazo real del pedido que se lanzó en ese mismo orden; `None` es que no llega."""

    def __init__(self, plazos):
        """Guarda la lista de plazos en el orden en que se lanzaron los pedidos."""
        self._plazos = list(plazos)
        self._siguiente = 0

    def siguiente(self):
        """El plazo del siguiente pedido; para si se lanzan más pedidos que plazos reales hay."""
        if self._siguiente >= len(self._plazos):
            raise ValueError(f"se lanza el pedido {self._siguiente + 1} y solo hay {len(self._plazos)} plazos reales")
        plazo = self._plazos[self._siguiente]
        self._siguiente += 1
        return plazo


class PlazosSorteados:
    """Sortea el plazo de cada pedido, con reemplazo, de los plazos reales del proveedor.

    La `clave` (repetición, producto) separa los sorteos dentro de la misma semilla. El pedido k-ésimo recibe siempre el
    k-ésimo sorteo, así que dos reglas con la misma semilla y clave dan el mismo plazo a su k-ésimo pedido: la
    diferencia entre reglas no la pone el azar del plazo.
    """

    def __init__(self, valores, semilla, clave=()):
        """Prepara el generador con su semilla; sin semilla el resultado no se podría repetir."""
        if semilla is None:
            raise ValueError("un sorteo de plazos necesita semilla")
        self._valores = np.asarray(valores, dtype="int64")
        if len(self._valores) == 0 or (self._valores < 1).any():
            raise ValueError("los plazos para sortear tienen que ser días enteros de 1 o más")
        self._rng = np.random.default_rng(np.random.SeedSequence(semilla, spawn_key=clave))

    def siguiente(self):
        """El plazo del siguiente pedido."""
        return int(self._rng.choice(self._valores))


# =====================================================================================================================
# 2. Reglas del punto de pedido
# =====================================================================================================================


def regla_actual(stock_seguridad, plazo_prometido, ventana=config.VENTANA):
    """La regla actual: media de lo vendido en los 30 días que acaban el día de la revisión × plazo prometido + stock de
    seguridad fijo de la ficha."""
    def punto(historia):
        """El punto de pedido del día con lo conocido al cerrarlo."""
        ultimas = np.asarray(historia["ventas"][-ventana:], dtype="int64")
        return int(ultimas.sum()) / len(ultimas) * plazo_prometido + stock_seguridad
    return punto


def regla_de_puntos(puntos):
    """Una regla con el punto de pedido de cada día calculado de antemano."""
    puntos = np.asarray(puntos, dtype=float)

    def punto(historia):
        """El punto de pedido del día."""
        return float(puntos[historia["dia"]])
    return punto


# =====================================================================================================================
# 3. El día a día
# =====================================================================================================================


def simular(demanda, regla, plazos, stock_inicial, cantidad, en_camino_inicial=(), historia_previa=None, fechas=None):
    """Simula un producto día a día y devuelve una tabla por día y la lista de pedidos lanzados.

    - `demanda`: unidades pedidas por los clientes cada día.
    - `regla`: función de la historia conocida al cierre del día (`ventas`, `demanda` y `dia`) que da el punto de pedido.
    - `plazos`: asignador con `siguiente()`, que da el plazo de cada pedido nuevo en días (o `None`: no llega).
    - `stock_inicial`: stock al empezar el primer día; `cantidad`: unidades fijas de cada pedido.
    - `en_camino_inicial`: pedidos en camino al empezar, con `dia_llegada` (0 es el primer día) y `unidades`.
    - `historia_previa`: `ventas` y `demanda` anteriores al periodo, que ve la regla.
    """
    demanda = np.asarray(demanda, dtype="int64")
    if (demanda < 0).any():
        raise ValueError("una demanda negativa es imposible")
    n = len(demanda)
    previa = historia_previa or {"ventas": [], "demanda": []}
    n_previa = len(previa["ventas"])

    # La historia que ve la regla, con lo anterior delante; se le pasa hasta el día de hoy
    ventas_hist = np.zeros(n_previa + n, dtype="int64")
    demanda_hist = np.zeros(n_previa + n, dtype="int64")
    ventas_hist[:n_previa] = np.asarray(previa["ventas"], dtype="int64")
    demanda_hist[:n_previa] = np.asarray(previa["demanda"], dtype="int64")

    # Un pedido en camino al empezar llega como pronto el primer día: uno de antes ya lo habría registrado el periodo
    # anterior, y aquí no llegaría nunca y contaría en la posición para siempre
    if any(o["dia_llegada"] is not None and o["dia_llegada"] < 0 for o in en_camino_inicial):
        raise ValueError("un pedido en camino al empezar no puede haber llegado antes del primer día")
    en_camino = [{"dia_lanzado": None, "plazo": None, "dia_llegada": o["dia_llegada"], "unidades": int(o["unidades"])}
                 for o in en_camino_inicial]
    stock = int(stock_inicial)
    if stock < 0:
        raise ValueError("un stock negativo es imposible")
    filas, lanzados = [], []
    for t in range(n):
        # Paso 1 · llega lo que toca y entra en el stock
        stock_inicial_dia = stock
        recibido = sum(o["unidades"] for o in en_camino if o["dia_llegada"] == t)
        en_camino = [o for o in en_camino if o["dia_llegada"] != t]
        stock += recibido

        # Paso 2 · se sirve la demanda hasta donde llega el stock; lo que falta se pierde
        servido = min(stock, int(demanda[t]))
        no_servido = int(demanda[t]) - servido
        stock -= servido
        ventas_hist[n_previa + t] = servido
        demanda_hist[n_previa + t] = demanda[t]

        # Paso 3 · se revisa la posición y se pide si está en el punto de pedido o por debajo
        posicion_revision = stock + sum(o["unidades"] for o in en_camino)
        punto = regla({"ventas": ventas_hist[:n_previa + t + 1], "demanda": demanda_hist[:n_previa + t + 1], "dia": t})
        pide = posicion_revision <= punto
        if pide:
            plazo = plazos.siguiente()
            if plazo is not None and (int(plazo) != plazo or plazo < 1):
                raise ValueError(f"plazo {plazo} el día {t}: un pedido llega como pronto al día siguiente")
            nuevo = {"dia_lanzado": t, "plazo": None if plazo is None else int(plazo),
                     "dia_llegada": None if plazo is None else t + int(plazo), "unidades": int(cantidad)}
            en_camino.append(nuevo)
            lanzados.append(dict(nuevo))

        # Cierre del día: el pedido lanzado hoy ya cuenta en camino
        unidades_en_camino = sum(o["unidades"] for o in en_camino)
        filas.append({"dia": t, "stock_inicial": stock_inicial_dia, "recibido": recibido, "demanda": int(demanda[t]),
                      "servido": servido, "no_servido": no_servido, "stock_final": stock,
                      "posicion_revision": posicion_revision, "punto_pedido": float(punto), "pedido_lanzado": bool(pide),
                      "en_camino": unidades_en_camino, "posicion": stock + unidades_en_camino})

    diario = pd.DataFrame(filas)
    if fechas is not None:
        diario.insert(0, "fecha", pd.to_datetime(pd.Series(fechas)).to_numpy())
    return diario, lanzados


# =====================================================================================================================
# 4. Indicadores del periodo
# =====================================================================================================================


def indicadores(diario, ficha_producto, porcentaje=None):
    """Fill rate, días sin stock, unidades no servidas, stock medio, pedidos y coste total del periodo.

    Mantener = stock medio × coste unitario × porcentaje anual × días / 365. Margen perdido = no servidas × (precio −
    coste). Pedir = pedidos × coste de pedido. Coste total = las tres.
    """
    f = ficha_producto
    pct = float(f["coste_almacen_anual_pct"]) if porcentaje is None else float(porcentaje)
    dias = len(diario)
    demanda, servido = int(diario["demanda"].sum()), int(diario["servido"].sum())
    stock_medio = float(diario["stock_final"].mean())
    pedidos = int(diario["pedido_lanzado"].sum())
    mantener = stock_medio * float(f["coste_unitario"]) * pct * dias / config.DIAS_DEL_ANIO
    margen = int(diario["no_servido"].sum()) * (float(f["precio_venta"]) - float(f["coste_unitario"]))
    pedir = pedidos * float(f["coste_pedido"])
    return {"dias": dias, "demanda": demanda, "servido": servido,
            "fill_rate": servido / demanda if demanda > 0 else None,
            "dias_sin_stock": int((diario["no_servido"] > 0).sum()),
            "unidades_no_servidas": int(diario["no_servido"].sum()),
            "stock_medio": stock_medio, "stock_medio_euros": stock_medio * float(f["coste_unitario"]),
            "pedidos": pedidos, "coste_mantener": float(mantener), "margen_perdido": float(margen),
            "coste_pedir": float(pedir), "coste_total": float(mantener + margen + pedir)}


def ciclos(diario, cantidad):
    """Nivel de servicio por reposición: una reposición va de una llegada a la víspera de la siguiente, y cumple si
    ningún día suyo deja demanda sin servir. Lo anterior a la primera llegada y lo posterior a la última no cuentan."""
    recibido = np.asarray(diario["recibido"], dtype="int64")
    rotura = np.asarray(diario["no_servido"], dtype="int64") > 0
    llegadas = np.flatnonzero(recibido > 0)
    n = max(len(llegadas) - 1, 0)
    sin_rotura = sum(1 for a, b in zip(llegadas[:-1], llegadas[1:]) if not rotura[a:b].any())
    return {"ciclos": int(n), "sin_rotura": int(sin_rotura), "nivel": sin_rotura / n if n else None,
            "llegadas_el_mismo_dia": int((recibido > cantidad).sum())}


# =====================================================================================================================
# 5. Comparación día a día con lo registrado
# =====================================================================================================================

# Columnas simuladas → registradas que tienen que casar cada día
CASAN = {"stock_final": "stock_final", "servido": "ventas", "no_servido": "ventas_perdidas",
         "pedido_lanzado": "pedido_lanzado", "stock_inicial": "stock_inicial", "recibido": "unidades_recibidas",
         "en_camino": "en_camino", "posicion": "posicion_stock"}


def dias_que_no_casan(simulado, registro, columnas=None):
    """Días en que alguna columna simulada no es igual a la registrada, con las columnas que fallan."""
    columnas = CASAN if columnas is None else columnas
    if len(simulado) != len(registro):
        raise ValueError("el simulado y el registro no tienen los mismos días")
    fallan = []
    for i in range(len(simulado)):
        malas = [reg for sim, reg in columnas.items() if simulado[sim].iloc[i] != registro[reg].iloc[i]]
        if malas:
            fallan.append({"dia": i, "columnas": malas})
    return fallan


# =====================================================================================================================
# 6. Arranque desde el registro
# =====================================================================================================================


def estado_vispera(dias, pedidos, producto, inicio):
    """Stock al cierre de la víspera y pedidos en camino con su llegada real, desde el registro."""
    vispera = inicio - pd.Timedelta(days=1)
    stock = int(dias.loc[(dias["producto"] == producto) & (dias["fecha"] == vispera), "stock_final"].iloc[0])
    p = pedidos.loc[(pedidos["producto"] == producto) & (pedidos["fecha_pedido"] <= vispera)
                    & ~(pedidos["fecha_llegada"] <= vispera)]
    en_camino = [{"id_pedido": o["id_pedido"], "unidades": int(o["cantidad"]),
                  "dia_llegada": None if pd.isna(o["fecha_llegada"]) else int((o["fecha_llegada"] - inicio).days)}
                 for _, o in p.iterrows()]
    return stock, en_camino


def arranque_sorteado(pendientes, asignador, inicio):
    """Los pedidos pendientes al empezar, cada uno con el siguiente plazo del asignador contado desde su fecha de
    pedido. Para si un plazo pone la llegada antes del primer día: esa llegada ya la habría registrado el periodo
    anterior."""
    en_camino = []
    for o in pendientes.sort_values(["fecha_pedido", "id_pedido"]).itertuples(index=False):
        plazo = int(asignador.siguiente())
        llegada = pd.Timestamp(o.fecha_pedido) + pd.Timedelta(days=plazo)
        if llegada < inicio:
            raise ValueError(f"{o.id_pedido}: el plazo sorteado de {plazo} días pone su llegada el {llegada.date()}, "
                             f"antes del {inicio.date()}")
        en_camino.append({"id_pedido": o.id_pedido, "plazo": plazo, "dia_llegada": int((llegada - inicio).days),
                          "unidades": int(o.cantidad)})
    return en_camino
