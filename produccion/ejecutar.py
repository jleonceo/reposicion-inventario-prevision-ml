"""La ejecución de un día: al cierre de `--dia`, decide para cada producto si se pide o no.

Lee de la carpeta de entrada el inventario por día y los pedidos (el contrato está en `produccion/contrato_entrada.md`),
quita todo lo posterior a `--dia`, para que no se pueda usar, y comprueba la entrada. Si algo falla, sea la entrada, la
fecha o el modelo, para sin dejar decisión, anota el motivo en el registro de ejecuciones y termina con error. Si falta
la decisión del día anterior, decide igual y lo anota como aviso por ausencia.

Deja en `<salidas>/<dia>/` la línea de cada producto (`decision.csv`: previsión del plazo, punto de pedido, stock, en
camino, posición, pedir o no y cantidad) y su resumen. Si ese día ya se había ejecutado, la carpeta anterior se archiva.

Uso:  python produccion/ejecutar.py --dia 2025-01-15 [--entrada carpeta]
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from reposicion.produccion import (EntradaIncorrecta, anotar_ejecucion, cargar_modelos, comprobar_dia,  # noqa: E402
                                   config, decidir, hasta_el_dia, leer_entrada, preparar_salida)


def falta_la_vispera(c, dia):
    """Aviso por ausencia: el registro tiene ejecuciones anteriores y la del día anterior no dejó decisión."""
    registro = c["salidas"] / "ejecuciones.csv"
    vispera = (datetime.strptime(dia, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    return registro.exists() and not (c["salidas"] / vispera / "decision.csv").exists()


def ejecutar(dia, entrada=None, c=None, modelos=None, manifiesto=None):
    """Decide al cierre de `dia` y guarda la decisión y su resumen; devuelve la decisión.

    Si algo falla, anota el error y lanza `EntradaIncorrecta` sin dejar decisión.
    """
    c = c or config()
    entrada = Path(entrada) if entrada else c["entrada"]
    inicio = time.perf_counter()
    momento = datetime.now().isoformat(timespec="seconds")
    try:
        # La fecha, escrita exactamente como AAAA-MM-DD: con otra forma, la carpeta del día no sería la misma
        try:
            if datetime.strptime(dia, "%Y-%m-%d").strftime("%Y-%m-%d") != dia:
                raise ValueError
        except ValueError:
            raise EntradaIncorrecta(f"la fecha «{dia}» no es un día AAAA-MM-DD") from None
        inv, ped = leer_entrada(entrada)
        inv, ped = hasta_el_dia(inv, ped, dia)
        comprobar_dia(inv, ped, dia, c["productos"])
        if modelos is None:
            try:
                modelos, manifiesto = cargar_modelos(c=c)
            except RuntimeError as e:
                raise EntradaIncorrecta(str(e)) from e
        aviso = "falta la decisión del día anterior (aviso por ausencia)" if falta_la_vispera(c, dia) else ""
        decision = decidir(inv, ped, dia, c, modelos)
    except EntradaIncorrecta as e:
        anotar_ejecucion(c["salidas"], {"dia": dia, "momento": momento, "estado": "ERROR",
                                        "duracion_s": round(time.perf_counter() - inicio, 3), "pedidos": 0,
                                        "motivo": str(e)})
        raise
    except Exception as e:
        # Cualquier otro fallo también se anota, con su tipo, antes de pararlo como error de la ejecución
        anotar_ejecucion(c["salidas"], {"dia": dia, "momento": momento, "estado": "ERROR",
                                        "duracion_s": round(time.perf_counter() - inicio, 3), "pedidos": 0,
                                        "motivo": f"{type(e).__name__}: {e}"})
        raise EntradaIncorrecta(f"{type(e).__name__}: {e}") from e
    carpeta = preparar_salida(c["salidas"] / dia)
    decision.to_csv(carpeta / "decision.csv", index=False, encoding="utf-8")
    duracion = round(time.perf_counter() - inicio, 3)
    resumen = {"dia": dia, "momento": momento, "estado": "OK", "duracion_s": duracion, "aviso": aviso or None,
               "filas_entrada": int(len(inv)), "pedidos_a_lanzar": decision.loc[decision["pedir"], "producto"].tolist(),
               "modelo": {"entrenado_hasta": manifiesto["entrenado_hasta"], "fecha": manifiesto["fecha"]}}
    (carpeta / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    anotar_ejecucion(c["salidas"], {"dia": dia, "momento": momento, "estado": "OK", "duracion_s": duracion,
                                    "pedidos": int(decision["pedir"].sum()), "motivo": aviso})
    return decision


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--dia", required=True, help="el día a cuyo cierre se decide, AAAA-MM-DD")
    argumentos.add_argument("--entrada", default=None, help="carpeta con inventario_diario.csv y pedidos.csv")
    a = argumentos.parse_args()
    try:
        d = ejecutar(a.dia, a.entrada)
    except EntradaIncorrecta as e:
        sys.exit(f"ERROR: la ejecución del {a.dia} se para: {e}")
    for f in d.itertuples(index=False):
        print(f"{f.producto}: posición {f.posicion}, punto de pedido {f.punto_pedido:.1f} -> "
              f"{'PEDIR ' + str(f.cantidad) if f.pedir else 'no pedir'}")
