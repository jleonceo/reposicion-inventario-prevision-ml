"""Pruebas del reentreno, la promoción y la vuelta atrás, en una carpeta temporal.

- Vigente y candidato se miden en los mismos días; un candidato con más historia que valida mejor pasa.
- Un candidato con menos historia que el vigente, peor que la media de 30 días o igual a uno retirado no pasa.
- La validación usa un modelo entrenado sin los días que mide.
- Si la promoción falla a mitad, el vigente sigue en su sitio.
- Dos vueltas atrás seguidas no restauran el modelo recién retirado.

Uso: python -W error tests/probar_reentreno.py
"""

import json
import shutil
import tempfile
from pathlib import Path

import joblib

from comun import Casos
from reentrenar import reentrenar
from reposicion import produccion
from reposicion.produccion import carpetas_modelos, config, guardar_modelos, promover, volver_atras

c = Casos()


def hasta_de(carpeta):
    """La fecha de entrenamiento del manifiesto de una carpeta."""
    return json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))["entrenado_hasta"]


with tempfile.TemporaryDirectory() as tmp:
    cf = config()
    cf.update({"modelos": Path(tmp) / "modelos", "salidas": Path(tmp) / "salidas"})
    vigente, candidato, anteriores = carpetas_modelos(cf)

    d = reentrenar("2024-06-30", cf)
    c.caso("sin modelo vigente, el primero pasa a vigente", d["promovido"] and hasta_de(vigente) == "2024-06-30", str(d))

    # El caso del revisor: con más historia y medido en los mismos días que el vigente, el candidato pasa
    d = reentrenar("2024-12-31", cf)
    c.caso("ROJO del revisor: el candidato hasta el 31/12/2024 sustituye al de junio", d["promovido"], str(d))
    m = json.loads((vigente / "manifiesto.json").read_text(encoding="utf-8"))
    v = m["validacion"]["Producto_C"]
    c.caso("vigente y candidato se miden en los mismos días", v.get("error_vigente") is not None, str(v))
    c.caso("la validación usa un modelo entrenado antes del primer día que mide",
           v.get("ajustado_hasta", "9999") < v.get("medido_desde", "0000"), str(v))

    # Un candidato con menos historia que el vigente no pasa, aunque su error sea bueno
    d = reentrenar("2024-06-30", cf)
    c.caso("ROJO: un candidato con menos historia que el vigente no pasa",
           not d["promovido"] and hasta_de(vigente) == "2024-12-31", str(d))

    # Una fecha posterior a los datos para
    c.lanza("ROJO: entrenar hasta una fecha sin datos para", lambda: reentrenar("2030-01-01", cf), ValueError)

    # Un candidato peor que la media de 30 días no pasa, ni siquiera sin vigente
    modelos = {p: joblib.load(vigente / f"{p}.joblib") for p in cf["productos"]}
    sin = Path(tmp) / "sin_vigente"
    cf_sin = {**cf, "modelos": sin}
    guardar_modelos(modelos, {p: {"error": 5.0, "error_vigente": None, "referencia": 1.0} for p in cf["productos"]},
                    "2024-12-31", {}, carpetas_modelos(cf_sin)[1])
    c.caso("ROJO: un candidato cinco veces peor que la media de 30 días no pasa", not promover(cf_sin)["promovido"])

    # Si la promoción falla a mitad, el vigente sigue en su sitio
    guardar_modelos(modelos, {p: {"error": 0.1, "error_vigente": 0.5, "referencia": 1.0} for p in cf["productos"]},
                    "2025-01-31", {}, candidato)
    original, llamadas = shutil.move, []

    def mover_que_falla(origen, destino):
        """El segundo movimiento falla, como un disco lleno a mitad de la promoción."""
        llamadas.append(origen)
        if len(llamadas) == 2:
            raise OSError("fallo simulado")
        return original(origen, destino)
    produccion.shutil.move = mover_que_falla
    try:
        promover(cf)
    except OSError:
        pass
    finally:
        produccion.shutil.move = original
    c.caso("ROJO: si la promoción falla a mitad, el vigente sigue en su sitio",
           (vigente / "manifiesto.json").is_file() and hasta_de(vigente) == "2024-12-31")
    shutil.rmtree(candidato, ignore_errors=True)

    # Lo que retira una vuelta atrás no vuelve a entrar con los mismos datos
    retirado = hasta_de(vigente)
    volver_atras(cf)
    c.caso("la vuelta atrás restaura el anterior", hasta_de(vigente) == "2024-06-30")
    d = reentrenar("2024-12-31", cf)
    c.caso("ROJO: el modelo retirado no vuelve con el siguiente reentreno de los mismos datos",
           not d["promovido"] and hasta_de(vigente) == "2024-06-30", str(d))
    try:
        volver_atras(cf)
        segunda = hasta_de(vigente)
    except RuntimeError:
        segunda = None
    c.caso("ROJO: la segunda vuelta atrás no restaura el recién retirado", segunda != retirado)

c.fin()
