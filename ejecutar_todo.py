"""Reproduce el proyecto entero desde los CSV de `datos/`.

1. Pruebas que no necesitan resultados: limpieza del repositorio y método.
2. El pipeline, del paso 1 al 7: transformación, variables, medida de 2024, stock de seguridad, comparación de 2024,
   previsión de 2025 y prueba final.
3. El proceso diario: reentreno, pruebas de la entrada del día, de la evaluación y del reentreno, y la simulación de
   los 181 días de 2025 (con la regla actual y con la regla del sistema).
4. Las pruebas de resultados: las cifras de las portadas contra lo que acaba de salir.

Con `--rapido`, el paso 5 no recorre la rejilla de objetivos de servicio (unos 10 minutos): usa los ya elegidos, que
guarda `src/reposicion/config.py`. Sin él, los vuelve a elegir y comprueba que salen esos.

Uso:  python ejecutar_todo.py [--rapido]
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ANTES = ["tests/probar_limpieza.py", "tests/probar_metodo.py"]
PIPELINE = ["pipeline/01_transformacion.py", "pipeline/02_variables.py", "pipeline/03_medida_2024.py",
            "pipeline/04_stock_de_seguridad.py", "pipeline/05_comparacion_2024.py", "pipeline/06_prevision_2025.py",
            "pipeline/07_prueba_final.py"]
PRODUCCION = ["produccion/reentrenar.py", "tests/probar_produccion.py", "tests/probar_evaluar.py",
              "tests/probar_reentreno.py",
              "tests/probar_simulacion.py"]
DESPUES = ["tests/probar_resultados.py", "tests/probar_portada.py"]


def paso(script, *argumentos):
    """Ejecuta un script con el mismo Python y para todo si falla."""
    print(f"\n=== {script} {' '.join(argumentos)}", flush=True)
    inicio = time.perf_counter()
    r = subprocess.run([sys.executable, "-W", "error", str(RAIZ / script), *argumentos], cwd=RAIZ)
    if r.returncode != 0:
        sys.exit(f"PARADO: {script} terminó con {r.returncode}")
    print(f"    ({time.perf_counter() - inicio:.0f} s)")


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--rapido", action="store_true", help="usar los objetivos de servicio ya elegidos")
    rapido = argumentos.parse_args().rapido
    for script in ANTES:
        paso(script)
    for script in PIPELINE:
        paso(script, *(["--rapido"] if rapido and script.startswith("pipeline/05") else []))
    for script in PRODUCCION:
        paso(script)
    for script in DESPUES:
        paso(script)
    print("\nOK: todo reproducido y comprobado")
