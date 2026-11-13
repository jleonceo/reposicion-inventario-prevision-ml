"""Pruebas del método con datos pequeños escritos a mano: simulador, regla actual, previsión recursiva sin futuro,
stock de seguridad, veredicto y decisión. Cada pieza tiene al lado un caso que tiene que salir mal, para que un verde
no sea un verde falso.

Uso: python -W error tests/probar_metodo.py
"""

import numpy as np
import pandas as pd

from comun import Casos
from reposicion import evaluacion, modelo, simulador, stock
from reposicion.config import ACTUAL, CORREGIDA, PREVISION

c = Casos()

# =====================================================================================================================
# 1. El simulador, con un caso que se puede seguir a mano
# =====================================================================================================================

# Stock 10, demanda 4 al día, punto de pedido fijo 6, pedidos de 10 que tardan 2 días.
# Día 0: sirve 4, queda 6 → pide (llega el 2). Día 1: sirve 4, queda 2, posición 12. Día 2: llegan 10 → 12, sirve 4,
# queda 8. Día 3: sirve 4, queda 4, posición 4 → pide (llega el 5). Día 4: sirve 4, queda 0, posición 10. Día 5: llegan
# 10, sirve 4, queda 6, posición 6 → pide.
diario, lanzados = simulador.simular([4, 4, 4, 4, 4, 4], simulador.regla_de_puntos([6] * 6),
                                     simulador.PlazosReales([2, 2, 2]), 10, 10)
c.caso("simulador: stock final día a día como a mano", diario["stock_final"].tolist() == [6, 2, 8, 4, 0, 6])
c.caso("simulador: pide los días 0, 3 y 5", [o["dia_lanzado"] for o in lanzados] == [0, 3, 5])
c.caso("simulador: lo que llega entra antes de servir", diario["recibido"].tolist() == [0, 0, 10, 0, 0, 10])

# Rojo: con más demanda que stock, lo que falta se pierde y el stock nunca baja de cero
diario, _ = simulador.simular([7, 7], simulador.regla_de_puntos([-1, -1]), simulador.PlazosReales([]), 10, 10)
c.caso("simulador: la demanda que no cabe se pierde", diario["no_servido"].tolist() == [0, 4])
c.caso("simulador: el stock nunca baja de cero", (diario["stock_final"] >= 0).all())
c.lanza("ROJO simulador: una demanda negativa para",
        lambda: simulador.simular([-1], simulador.regla_de_puntos([0]), simulador.PlazosReales([]), 5, 5), ValueError)
c.lanza("ROJO simulador: más pedidos que plazos reales para",
        lambda: simulador.simular([5, 5], simulador.regla_de_puntos([99, 99]), simulador.PlazosReales([1]), 0, 5),
        ValueError)

# Mismo sorteo, mismo plazo para el pedido k-ésimo, sea cual sea la regla
a = simulador.PlazosSorteados([3, 5, 9], 42, (0, 1))
b = simulador.PlazosSorteados([3, 5, 9], 42, (0, 1))
otro = simulador.PlazosSorteados([3, 5, 9], 42, (1, 1))
sa, sb, so = [a.siguiente() for _ in range(20)], [b.siguiente() for _ in range(20)], [otro.siguiente() for _ in range(20)]
c.caso("sorteo: misma semilla y clave, mismos plazos", sa == sb)
c.caso("ROJO sorteo: otra repetición da otros plazos", sa != so)

# =====================================================================================================================
# 2. La regla actual: lo vendido, no la demanda
# =====================================================================================================================

punto = simulador.regla_actual(stock_seguridad=10, plazo_prometido=7, ventana=3)
c.caso("regla actual: media de lo vendido × plazo prometido + stock fijo",
       punto({"ventas": [1, 2, 3, 6], "demanda": [9, 9, 9, 9]}) == 11 / 3 * 7 + 10)

# =====================================================================================================================
# 3. La previsión recursiva no ve el futuro
# =====================================================================================================================

rng = np.random.default_rng(0)
fechas = pd.date_range("2023-01-01", periods=120)
demanda = rng.poisson(50, size=120).astype(float)
inv = pd.DataFrame({"fecha": fechas, "producto": "X", "anio": fechas.year, "demanda": demanda})
m = modelo.ajustar(modelo.filas_completas(modelo.crear_variables(inv)))
origenes = np.array([60, 70])
base = modelo.prevision_del_plazo(m, demanda, fechas, origenes, 7)
cambiada = demanda.copy()
cambiada[71:] = 10_000
c.caso("previsión: cambiar la demanda posterior al día de revisión no cambia su previsión",
       modelo.prevision_del_plazo(m, cambiada, fechas, origenes, 7)[1] == base[1])
cambiada[70] = 10_000
c.caso("ROJO previsión: cambiar la demanda del propio día sí la cambia",
       modelo.prevision_del_plazo(m, cambiada, fechas, origenes, 7)[1] != base[1])
c.caso("previsión: entera y no negativa", (base >= 0).all() and (base == np.round(base)).all())
v = modelo.crear_variables(inv)
c.caso("variables: el retardo 1 es la demanda de la víspera", v["dem_lag_1"].iloc[5] == demanda[4])
c.caso("variables: la media de 7 días no incluye el día que se prevé",
       np.isclose(v["dem_media_7"].iloc[40], demanda[33:40].mean()))

# =====================================================================================================================
# 4. Stock de seguridad
# =====================================================================================================================

real_acum = np.array([[10, 20, 30], [12, 22, 32]], dtype=float)
valores = stock.valores_error(real_acum, np.array([18.0, 20.0]), plazos=[2, 3, 3])
c.caso("stock de seguridad: real de los días 1 a L menos la previsión del plazo medio",
       valores.tolist() == [[2.0, 12.0, 12.0], [2.0, 12.0, 12.0]])
c.lanza("ROJO stock de seguridad: un plazo más largo que el horizonte medido para",
        lambda: stock.valores_error(real_acum, np.array([18.0, 20.0]), plazos=[4]), ValueError)
c.caso("stock de seguridad: el percentil 50 de [2, 12, 12] es 12", stock.stock_seguridad([2, 12, 12], [50])[0] == 12)

# =====================================================================================================================
# 5. Veredicto y decisión
# =====================================================================================================================


def banda(mediana, p5, p95):
    """Una banda escrita a mano."""
    return {"media": mediana, "mediana": mediana, "p5": p5, "p95": p95}


baja = {"coste_total": banda(-100, -150, -50), "fill_rate": banda(0.01, 0.0, 0.02)}
cruza = {"coste_total": banda(-100, -150, 20), "fill_rate": banda(0.01, 0.0, 0.02)}
sube = {"coste_total": banda(50, 10, 90), "fill_rate": banda(0.01, 0.0, 0.02)}
c.caso("veredicto: toda la banda del coste bajo cero es buena",
       evaluacion.veredicto(baja["coste_total"], baja["fill_rate"]) == "buena")
c.caso("ROJO veredicto: si la banda cruza el cero no se puede afirmar",
       evaluacion.veredicto(cruza["coste_total"], cruza["fill_rate"]) == "no se puede afirmar")
c.caso("ROJO veredicto: si baja el coste pero baja el fill rate, no es buena",
       evaluacion.veredicto(baja["coste_total"], banda(-0.01, -0.02, 0.0)) == "no buena")
c.caso("decisión: buena frente a las dos, la regla con previsión",
       evaluacion.decidir({"prevision_actual": baja, "prevision_corregida": baja, "corregida_actual": baja})[0]
       == PREVISION)
c.caso("decisión: sin ventaja clara frente a la corregida, la corregida",
       evaluacion.decidir({"prevision_actual": baja, "prevision_corregida": cruza, "corregida_actual": baja})[0]
       == CORREGIDA)
c.caso("ROJO decisión: si ninguna es buena, se queda la actual",
       evaluacion.decidir({"prevision_actual": cruza, "prevision_corregida": sube, "corregida_actual": cruza})[0]
       == ACTUAL)

# =====================================================================================================================
# 6. Piezas sin prueba propia (revisión externa)
# =====================================================================================================================

c.lanza("ROJO simulador: un pedido en camino que ya debía haber llegado para",
        lambda: simulador.simular([1], simulador.regla_de_puntos([0]), simulador.PlazosReales([]), 5, 5,
                                  en_camino_inicial=[{"dia_llegada": -1, "unidades": 5}]), ValueError)

# Reposiciones: llegadas los días 1, 4 y 6; la primera tiene una rotura el día 2 y la segunda no
diario = pd.DataFrame({"recibido": [0, 10, 0, 0, 10, 0, 10], "no_servido": [0, 0, 3, 0, 0, 0, 0]})
r = simulador.ciclos(diario, 10)
c.caso("reposiciones: dos enteras, una sin rotura", (r["ciclos"], r["sin_rotura"], r["nivel"]) == (2, 1, 0.5), str(r))

# Arranque sorteado: un plazo que llega antes del primer día para; uno que llega después cuenta desde el pedido
pend = pd.DataFrame({"id_pedido": ["P1"], "fecha_pedido": [pd.Timestamp("2024-12-28")], "cantidad": [5]})
c.lanza("ROJO arranque: un plazo que pone la llegada antes del primer día para",
        lambda: simulador.arranque_sorteado(pend, simulador.PlazosReales([2]), pd.Timestamp("2025-01-01")), ValueError)
r = simulador.arranque_sorteado(pend, simulador.PlazosReales([5]), pd.Timestamp("2025-01-01"))
c.caso("arranque: pedido del 28/12 con 5 días llega el segundo día", r[0]["dia_llegada"] == 1, str(r))

# Estado de la víspera: el stock del cierre y solo los pedidos que no han llegado
dias = pd.DataFrame({"producto": "X", "fecha": pd.date_range("2024-12-30", periods=2), "stock_final": [7, 9]})
peds = pd.DataFrame({"id_pedido": ["A", "B"], "producto": "X", "cantidad": [3, 4],
                     "fecha_pedido": pd.to_datetime(["2024-12-20", "2024-12-29"]),
                     "fecha_llegada": pd.to_datetime(["2024-12-30", "2025-01-03"])})
s, e = simulador.estado_vispera(dias, peds, "X", pd.Timestamp("2025-01-01"))
c.caso("víspera: stock del 31/12 y solo el pedido que no ha llegado, el día 2",
       s == 9 and [(o["id_pedido"], o["dia_llegada"]) for o in e] == [("B", 2)], f"{s}, {e}")

# Objetivo de menor coste medio; con empate, el más bajo
t = pd.DataFrame({"nivel": [80.0, 80.0, 90.0, 90.0, 95.0, 95.0], "sorteo": [0, 1] * 3,
                  "coste_total": [10, 12, 8, 8, 8, 8]})
c.caso("objetivo: el de menor coste medio y, con empate, el más bajo",
       evaluacion.elegir_nivel(t, [80.0, 90.0, 95.0])["nivel"] == 90.0)
c.caso("objetivo de la fórmula de manual: si cae en el último, se mira la rejilla ampliada",
       evaluacion.elegir_nivel_manual(pd.DataFrame({"nivel": [80.0, 95.0, 99.0], "sorteo": [0, 0, 0],
                                                    "coste_total": [9, 5, 4]}), [80.0, 95.0], [99.0])
       == {"nivel": 99.0, "coste_medio": 4.0, "en_extremo": True, "ampliada": True})

c.fin()
