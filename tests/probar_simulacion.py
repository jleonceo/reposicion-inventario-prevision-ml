"""Pruebas de la simulación de los 181 días de 2025: una carpeta y una fila del registro por día; con la regla actual y
los plazos reales, el almacén simulado es el registrado y cuesta lo que costó (40.707 €); con la regla del sistema, el
proceso día a día da lo mismo que el simulador de la prueba final. Y la simulación no toca las salidas ni el modelo del
proceso diario: escribe y entrena en sus propias carpetas.

Uso: python -W error tests/probar_simulacion.py
"""

import json
import shutil

import pandas as pd

from comun import RAIZ, Casos
from reposicion.produccion import config
from simular_2025 import simular

c = Casos()
cf = config()
sim = cf["simulacion"]["salidas"]
ref = json.loads((RAIZ / "tests" / "cifras_de_referencia.json").read_text(encoding="utf-8"))

# Testigos en las carpetas del proceso diario: la simulación no los puede borrar
testigos = [cf["salidas"] / "_testigo_simulacion" / "decision.csv", cf["modelos"] / "_testigo_simulacion.txt"]
for t in testigos:
    t.parent.mkdir(parents=True, exist_ok=True)
    t.write_text("no se borra", encoding="utf-8")

# Con la regla actual y los plazos reales: lo que pasó
informe = simular(control=True, reentrenar_antes=True)
registro = pd.read_csv(sim / "registro.csv")
p = informe["prueba_de_principio_a_fin"]
c.caso("control: 181 días iguales a lo registrado en cada producto",
       all(v == "181 de 181 días iguales" for v in p["por_producto"].values()), str(p["por_producto"]))
c.caso("control: el coste del semestre es el real", abs(registro["coste_acumulado"].iloc[-1]
                                                       - ref["coste_real_semestre"]) <= ref["tolerancia_euros"],
       f"da {registro['coste_acumulado'].iloc[-1]}")

# Con la regla del sistema en los tres productos
informe = simular(control=False, reentrenar_antes=False)
registro = pd.read_csv(sim / "registro.csv")
dias = sorted(x.name for x in sim.iterdir() if x.is_dir() and x.name.startswith("2025-"))
c.caso("181 carpetas, una por día", len(dias) == 181, f"hay {len(dias)}")
c.caso("181 filas en el registro", len(registro) == 181, f"hay {len(registro)}")
c.caso("ningún día falta (aviso por ausencia)", informe["ventana"]["faltan"] == [])
c.caso("los tres productos con la regla del sistema",
       informe["reglas"] == {p: ref["regla_del_sistema"] for p in informe["reglas"]}, str(informe["reglas"]))
# Segunda vía de la cifra de la portada: el proceso día a día, con el sorteo 0, cuesta lo que la prueba final da al
# sistema en ese mismo sorteo
pf = json.loads((RAIZ / "informes" / "07_prueba_final.json").read_text(encoding="utf-8"))
c.caso("el coste del proceso día a día es el de la prueba final en el sorteo 0",
       abs(registro["coste_acumulado"].iloc[-1] - pf["sistema"]["coste_sorteo_0"]) <= ref["tolerancia_euros"],
       f"proceso {registro['coste_acumulado'].iloc[-1]} · prueba final {pf['sistema'].get('coste_sorteo_0')}")
p = informe["prueba_de_principio_a_fin"]
c.caso("el proceso da lo mismo que el simulador de la prueba final",
       p["ok"] and all(v["dias_iguales"] == v["dias"] == 181 for v in p["por_producto"].values()), str(p))
c.caso("ROJO: el coste con la regla del sistema no es el real (si lo fuera, la comparación no diría nada)",
       abs(registro["coste_acumulado"].iloc[-1] - ref["coste_real_semestre"]) > 1000)

# Rojo del revisor: las salidas y el modelo del proceso diario siguen ahí
c.caso("ROJO del revisor: la simulación no borra las salidas ni los modelos del proceso diario",
       all(t.is_file() for t in testigos), str([t.is_file() for t in testigos]))
for t in testigos:
    shutil.rmtree(t.parent) if t.parent.name == "_testigo_simulacion" else t.unlink()

c.fin()
