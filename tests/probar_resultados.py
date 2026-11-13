"""Las cifras que dejan los pasos del pipeline son las fijadas en `tests/cifras_de_referencia.json`.

Se comparan con tolerancia, porque otro sistema operativo puede mover el último decimal. Si una cifra se sale, la prueba
dice cuál y cuánto. Necesita el pipeline ejecutado (`python ejecutar_todo.py --rapido`).

Uso: python -W error tests/probar_resultados.py
"""

import json

from comun import RAIZ, Casos

c = Casos()
ref = json.loads((RAIZ / "tests" / "cifras_de_referencia.json").read_text(encoding="utf-8"))


def leer(nombre):
    """Un JSON de informes/."""
    return json.loads((RAIZ / "informes" / f"{nombre}.json").read_text(encoding="utf-8"))


def dentro(valor, esperado, euros=False):
    """Sí si `valor` está dentro de la tolerancia de `esperado`: un euro en los importes y una millonésima en el resto."""
    tol = ref["tolerancia_euros"] if euros else abs(esperado) * ref["tolerancia_relativa"] + 1e-9
    return abs(valor - esperado) <= tol


def cerca(nombre, valor, esperado, euros=False):
    """Un caso que pasa si `valor` está dentro de la tolerancia de `esperado`."""
    c.caso(nombre, dentro(valor, esperado, euros), f"da {valor}, se espera {esperado}, diferencia {valor - esperado:.6g}")


# El rojo primero: la misma comparación que usan los casos tiene que rechazar una cifra movida
real = ref["sistema_menos_coste_real_mediana"]
c.caso("ROJO: el ahorro movido 1,5 € se sale de la tolerancia", not dentro(real + 1.5, real, euros=True))
c.caso("ROJO: un error del modelo movido una milésima se sale",
       not dentro(ref["medida_2024_error_modelo"]["Producto_C"] + 0.001, ref["medida_2024_error_modelo"]["Producto_C"]))

m24, ss, p25, pf = leer("03_medida_2024"), leer("04_stock_de_seguridad"), leer("06_prevision_2025"), leer("07_prueba_final")
for p, v in ref["medida_2024_error_modelo"].items():
    cerca(f"medida 2024, error del modelo de {p}", m24["productos"][p]["mae"]["modelo"], v)
for p, reglas in ref["stock_de_seguridad_al_objetivo"].items():
    j = ss["niveles"].index(pf["lo_fijado"]["objetivo"][p])
    for r, v in reglas.items():
        cerca(f"stock de seguridad de {p}, {r}", ss["productos"][p]["stock_seguridad"][r][j], v)
for p, v in ref["stock_de_seguridad_oscilacion_media_al_objetivo"].items():
    j = ss["niveles"].index(pf["lo_fijado"]["objetivo"][p])
    cerca(f"stock de seguridad de {p}, oscilación de la media", ss["productos"][p]["stock_seguridad"]["oscilacion_media"][j], v)
for p, v in ref["stock_de_seguridad_formula_manual_a_su_objetivo"].items():
    j = ss["niveles_formula_manual"].index(pf["lo_fijado"]["objetivo_formula_manual"][p])
    cerca(f"stock de seguridad de {p}, fórmula de manual", ss["productos"][p]["stock_seguridad"]["formula_manual"][j], v)
for p, v in ref["prevision_2025_error_modelo"].items():
    cerca(f"previsión 2025, error del modelo de {p}", p25["productos"][p]["mae"]["modelo"], v)
c.caso("la elección producto a producto de la prueba final no cambia", pf["eleccion_por_producto"] ==
       ref["eleccion_por_producto"], f"da {pf.get('eleccion_por_producto')}")
c.caso("reproducción de 2025: 181 de 181 días en los tres productos",
       all(x["dias_que_casan"] == x["dias"] == 181 for x in pf["reproduccion"].values()))

# El sistema: la misma regla en los tres productos
s = pf["sistema"]
c.caso("el sistema usa la regla con previsión en los tres productos", s["regla"] == ref["regla_del_sistema"],
       f"da {s.get('regla')}")
c.caso("veredicto del sistema frente a la actual en cada producto",
       s["veredicto_frente_a_la_actual"] == ref["veredicto_del_sistema_frente_a_la_actual"],
       f"da {s.get('veredicto_frente_a_la_actual')}")
fr = s["frente_al_coste_real"]
cerca("coste real del semestre", fr["coste_real"], ref["coste_real_semestre"], euros=True)
cerca("el sistema frente al coste real, mediana", fr["sistema_menos_coste_real"]["mediana"],
      ref["sistema_menos_coste_real_mediana"], euros=True)
lo = s["frente_a_la_actual"]
cerca("el sistema frente a la actual, mediana", lo["coste_total"]["mediana"], ref["sistema_menos_actual_mediana"],
      euros=True)
cerca("el sistema frente a la actual, percentil 5", lo["coste_total"]["p5"], ref["sistema_menos_actual_p5"], euros=True)
cerca("el sistema frente a la actual, percentil 95", lo["coste_total"]["p95"], ref["sistema_menos_actual_p95"],
      euros=True)
cerca("stock de más en euros, mediana", lo["stock_medio_euros"]["mediana"], ref["stock_de_mas_euros_mediana"],
      euros=True)
cerca("fill rate, mediana de la diferencia", lo["fill_rate"]["mediana"], ref["fill_rate_puntos_mediana"])
# El bloque del sistema tiene que ser la regla con previsión de la comparación de los tres juntos, no otra
juntos = pf["comparacion"]["25"]["tres_juntos"]["frente_a_la_actual"][ref["regla_del_sistema"]]["coste_total"]
cerca("el sistema frente a la actual coincide con la regla con previsión en los tres juntos", lo["coste_total"]["mediana"],
      juntos["mediana"], euros=True)

# La configuración de producción aplica la regla del sistema, con el stock de seguridad y el plazo calculados
cp = json.loads((RAIZ / "produccion" / "config.json").read_text(encoding="utf-8"))["productos"]
c.caso("producción: los tres productos con la regla del sistema",
       all(x["regla"] == ref["regla_del_sistema"] for x in cp.values()), str({p: x["regla"] for p, x in cp.items()}))
c.caso("producción: el stock de seguridad es el calculado para la regla del sistema",
       all(abs(x["stock_seguridad"] - pf["lo_fijado"]["stock_de_seguridad"][p][x["regla"]]) < 1e-9
           for p, x in cp.items() if x["regla"] != "actual"))
c.caso("producción: el plazo es el plazo medio real y el objetivo, el fijado",
       all(x["plazo"] == pf["lo_fijado"]["plazo_medio"][p] and x["objetivo"] == pf["lo_fijado"]["objetivo"][p]
           for p, x in cp.items()))
for pct in ("15", "40"):
    dec = {p: x["eleccion"] for p, x in pf["comparacion"][pct]["productos"].items()}
    c.caso(f"la elección producto a producto no cambia con el {pct} % de coste de mantener",
           dec == ref["eleccion_por_producto"], f"da {dec}")

c.fin()
