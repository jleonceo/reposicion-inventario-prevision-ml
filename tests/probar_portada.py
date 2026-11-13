"""Cada cifra de `README.md` y `README.en.md` sale de lo que acaba de calcular el código, y las dos portadas dan las
mismas.

Las cifras de la portada se declaran aquí una a una, cada una con el resultado del que sale. Una cifra del texto que no
es ninguna de ellas hace fallar la prueba, aunque coincida por azar con algún número de los resultados: así un número
pequeño no pasa por casualidad. Cada cifra declarada tiene que estar en las dos portadas. La tabla del ejemplo de un día
se compara con la decisión que dejó la simulación ese día.

En `README.md` los miles van con punto y los decimales con coma («31.226 €», «4,7»); en `README.en.md`, al revés
(«€31,226», «4.7»).

Uso: python -W error tests/probar_portada.py
"""

import json
import re

import pandas as pd

from comun import RAIZ, Casos
from reposicion import config
from reposicion.produccion import config as config_produccion

c = Casos()
PORTADAS = {"README.md": (".", ","), "README.en.md": (",", ".")}
EJEMPLO = "2025-02-26"


def declaradas():
    """Las cifras que puede llevar la portada, calculadas de los resultados: {cifra: de dónde sale}."""
    pf = json.loads((RAIZ / "informes" / "07_prueba_final.json").read_text(encoding="utf-8"))
    real = pf["sistema"]["frente_al_coste_real"]
    coste_real = real["coste_real"]
    ahorro = real["sistema_menos_coste_real"]
    juntos = pf["sistema"]["frente_a_la_actual"]
    d = {
        round(coste_real): "coste real del semestre",
        round(coste_real + ahorro["mediana"]): "coste del sistema, mediana",
        round(abs(ahorro["mediana"])): "ahorro frente al coste real, mediana",
        round(100 * abs(ahorro["mediana"]) / coste_real): "porcentaje de ahorro",
        round(abs(ahorro["p95"])): "ahorro, extremo bajo de la banda",
        round(abs(ahorro["p5"])): "ahorro, extremo alto de la banda",
        round(100 * juntos["fill_rate"]["mediana"], 1): "subida del fill rate, puntos",
        abs(juntos["dias_sin_stock"]["mediana"]): "bajada de los días sin stock",
        round(juntos["stock_medio_euros"]["mediana"]): "subida del stock medio en euros",
        config.REPETICIONES: "sorteos del plazo",
    }
    return {float(k): v for k, v in d.items()}


# Lo que no es un resultado: los años del periodo y el 90 % central de la banda (del percentil 5 al 95)
FIJAS = {2023.0: "año", 2024.0: "año", 2025.0: "año", 90.0: "banda del 5 al 95"}


def cifras(texto, miles, decimal):
    """Las cifras de un texto, leídas con sus separadores: «31.226» → 31226 y «4,7» → 4.7."""
    patron = r"(?<![\w.,])\d{1,3}(?:" + re.escape(miles) + r"\d{3})+(?:" + re.escape(decimal) + r"\d+)?(?![\w])" \
             r"|(?<![\w.,])\d+(?:" + re.escape(decimal) + r"\d+)?(?![\w])"
    return [float(t.replace(miles, "").replace(decimal, ".")) for t in re.findall(patron, texto)]


def sin_lo_que_no_cuenta(texto):
    """El texto sin la tabla del ejemplo, las direcciones de los enlaces, el código, las fechas ni la versión de
    Python."""
    texto = re.sub(r"<!-- ejemplo.*?<!-- /ejemplo -->", " ", texto, flags=re.S)
    return re.sub(r"\]\([^)]*\)|```.*?```|`[^`]*`|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|Python \d+\.\d+", " ", texto,
                  flags=re.S)


def sueltas(texto, miles, decimal, validas):
    """Las cifras del texto que no son ninguna de las declaradas ni de las fijas."""
    return sorted({x for x in cifras(sin_lo_que_no_cuenta(texto), miles, decimal) if x not in validas})


def filas_del_ejemplo(texto, miles, decimal):
    """Las filas de la tabla del ejemplo: {producto: [previsión, stock de seguridad, punto, posición, cantidad o 0]}."""
    bloque = re.search(r"<!-- ejemplo (\S+) -->(.*?)<!-- /ejemplo -->", texto, flags=re.S)
    if not bloque:
        return None, {}
    filas = {}
    for linea in bloque.group(2).strip().splitlines()[2:]:
        celdas = [x.strip() for x in linea.strip().strip("|").split("|")]
        numeros = [x for celda in celdas[1:5] for x in cifras(celda, miles, decimal)]
        pedido = cifras(celdas[5], miles, decimal)
        filas[f"Producto_{celdas[0]}"] = numeros + [pedido[0] if pedido else 0.0]
    return bloque.group(1), filas


def filas_de_la_simulacion(dia):
    """Lo mismo, leído de la decisión que dejó la simulación ese día, redondeado a unidades."""
    ruta = config_produccion()["simulacion"]["salidas"] / dia / "decision.csv"
    if not ruta.is_file():
        return None
    d = pd.read_csv(ruta, encoding="utf-8")
    return {r.producto: [float(round(r.prevision_plazo)), float(round(r.stock_seguridad)), float(round(r.punto_pedido)),
                         float(r.posicion), float(r.cantidad if r.pedir else 0)] for r in d.itertuples()}


validas = set(declaradas()) | set(FIJAS)

# Los rojos primero: con estos textos la prueba tiene que fallar
c.caso("ROJO: una cifra que no está en los resultados se detecta",
       sueltas("habría costado 31.227 € menos", ".", ",", validas) == [31227.0])
c.caso("ROJO: un número pequeño que solo coincide por azar con un resultado se detecta",
       sueltas("en 4 de los 3 productos", ".", ",", validas) == [3.0, 4.0])
c.caso("ROJO: una cifra con los separadores del otro idioma se detecta",
       sueltas("de €40.707 a €9.481", ",", ".", validas) != [])
c.caso("ROJO: una cifra entre paréntesis no se salta",
       sueltas("(unas 12 unidades)", ".", ",", validas) == [12.0])
buenas = filas_de_la_simulacion(EJEMPLO)
c.caso(f"la simulación dejó la decisión del {EJEMPLO}", buenas is not None)
fila_a = "| A | {} | 131 | 1.036 | 918 | pide 1.500 unidades |"
_, iguales = filas_del_ejemplo(f"<!-- ejemplo 2025-02-26 -->\n|a|b|\n|---|---|\n{fila_a.format(905)}\n<!-- /ejemplo -->",
                               ".", ",")
_, malas = filas_del_ejemplo(f"<!-- ejemplo 2025-02-26 -->\n|a|b|\n|---|---|\n{fila_a.format(906)}\n<!-- /ejemplo -->",
                             ".", ",")
c.caso("la fila de A tal como la escribe la portada casa con la simulación",
       buenas is not None and iguales.get("Producto_A") == buenas.get("Producto_A"), f"{iguales} · {buenas}")
c.caso("ROJO: la misma fila con un número cambiado no casa con la simulación",
       buenas is not None and malas.get("Producto_A") != buenas.get("Producto_A"))

leidas = {}
for portada, (miles, decimal) in PORTADAS.items():
    ruta = RAIZ / portada
    if not ruta.is_file():
        c.caso(f"{portada} existe", False, "todavía no está escrita")
        continue
    texto = ruta.read_text(encoding="utf-8")
    s = sueltas(texto, miles, decimal, validas)
    c.caso(f"{portada}: cada cifra es una de las declaradas", not s, f"sueltas: {s}")
    leidas[portada] = set(cifras(sin_lo_que_no_cuenta(texto), miles, decimal))
    faltan = {k: v for k, v in declaradas().items() if k not in leidas[portada]}
    c.caso(f"{portada}: están todas las cifras declaradas", not faltan, f"faltan: {faltan}")
    dia, filas = filas_del_ejemplo(texto, miles, decimal)
    c.caso(f"{portada}: el ejemplo es del {EJEMPLO}", dia == EJEMPLO, f"dice {dia}")
    c.caso(f"{portada}: el ejemplo da lo que decidió la simulación ese día", buenas is not None and filas == buenas,
           f"portada {filas} · simulación {buenas}")

if len(leidas) == 2:
    c.caso("las dos portadas llevan las mismas cifras", leidas["README.md"] == leidas["README.en.md"],
           f"solo en una: {sorted(leidas['README.md'] ^ leidas['README.en.md'])}")

c.fin()
