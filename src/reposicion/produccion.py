"""Piezas del proceso diario: configuración, modelos vigente y candidato, contrato de entrada, decisión de cada
producto, salida de cada día y registro de ejecuciones."""

import csv
import json
import shutil
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from . import config as cfg
from . import modelo, salidas
from .datos import transformar_pedidos

CONFIG = cfg.RAIZ / "produccion" / "config.json"

# El contrato de entrada (produccion/contrato_entrada.md): columnas y tipo de cada tabla
COLUMNAS_INVENTARIO = {"fecha": "fecha", "producto": "texto", "stock_inicial": "entero", "unidades_recibidas": "entero",
                       "ventas": "entero", "ventas_perdidas": "entero", "stock_final": "entero"}
COLUMNAS_PEDIDOS = {"id_pedido": "texto", "producto": "texto", "fecha_pedido": "fecha", "fecha_llegada": "fecha",
                    "cantidad": "entero", "estado": "texto"}
CAMPOS_EJECUCIONES = ["dia", "momento", "estado", "duracion_s", "pedidos", "motivo"]
COLUMNAS_DECISION = ["fecha", "producto", "regla", "prevision_plazo", "stock_seguridad", "punto_pedido", "stock",
                     "en_camino", "posicion", "pedir", "cantidad"]


class EntradaIncorrecta(Exception):
    """Los datos del día no cumplen el contrato de entrada: la ejecución para sin dejar decisión."""


# =====================================================================================================================
# 1. Configuración
# =====================================================================================================================

def config():
    """La configuración del proceso, con las rutas ya resueltas desde la raíz del repositorio."""
    c = json.loads(CONFIG.read_text(encoding="utf-8"))
    for k in ("datos_historia", "datos_nuevos", "entrada", "modelos", "salidas", "informe_despliegue"):
        c[k] = cfg.RAIZ / c[k]
    for k in ("salidas", "modelos"):
        c["simulacion"][k] = cfg.RAIZ / c["simulacion"][k]
    return c


def carpetas_modelos(c=None):
    """Vigente, candidato y anteriores, dentro de la carpeta de modelos."""
    raiz = (c or config())["modelos"]
    return raiz / "vigente", raiz / "candidato", raiz / "anteriores"


# =====================================================================================================================
# 2. Modelos: guardar, cargar, promover y volver atrás
# =====================================================================================================================

def guardar_modelos(modelos, validacion, hasta, huellas, carpeta):
    """Un fichero joblib por producto y un manifiesto con la fecha, las versiones, las huellas y la validación."""
    if carpeta.exists():
        shutil.rmtree(carpeta)
    carpeta.mkdir(parents=True)
    ficheros = {}
    for p, m in modelos.items():
        joblib.dump(m, carpeta / f"{p}.joblib")
        ficheros[p] = f"{p}.joblib"
    manifiesto = {"entrenado_hasta": hasta, "fecha": datetime.now().isoformat(timespec="seconds"),
                  "versiones": salidas.entorno(), "datos": huellas, "modelos": ficheros, "validacion": validacion}
    (carpeta / "manifiesto.json").write_text(json.dumps(salidas.limpio(manifiesto), ensure_ascii=False, indent=2),
                                             encoding="utf-8")
    return manifiesto


def cargar_modelos(carpeta=None, c=None):
    """Los modelos de una carpeta (por defecto, los vigentes); para si las librerías no son las del entrenamiento."""
    carpeta = carpeta or carpetas_modelos(c)[0]
    if not (carpeta / "manifiesto.json").exists():
        raise RuntimeError(f"no hay modelo en {salidas.relativa(carpeta)}: ejecuta antes produccion/reentrenar.py")
    manifiesto = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    ahora = salidas.entorno()
    for lib in ("scikit-learn", "pandas"):
        if manifiesto["versiones"][lib] != ahora[lib]:
            raise RuntimeError(f"los modelos se entrenaron con {lib} {manifiesto['versiones'][lib]} y ahora hay "
                               f"{ahora[lib]}: hay que reentrenar")
    return {p: joblib.load(carpeta / f) for p, f in manifiesto["modelos"].items()}, manifiesto


def error_frente_a_referencia(manifiesto):
    """El error de validación dividido por el de la media de 30 días en los mismos días: por debajo de 1, el modelo se
    equivoca menos que esa media."""
    v = manifiesto["validacion"].values()
    return sum(x["error"] for x in v) / sum(x["referencia"] for x in v)


def _identidad(manifiesto):
    """Lo que identifica un modelo: hasta qué día se entrenó y con qué datos."""
    return {"entrenado_hasta": manifiesto["entrenado_hasta"], "datos": manifiesto.get("datos", {})}


def _retirados(c):
    """La lista de modelos que retiró una vuelta atrás, que no vuelven a entrar."""
    ruta = c["modelos"] / "retirados.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else []


def motivo_para_no_promover(nuevo, actual, retirados):
    """Por qué el candidato no pasa a vigente, o None si pasa.

    No pasa si tiene menos historia que el vigente, si es un modelo que retiró una vuelta atrás, si no se equivoca menos
    que la media de 30 días o si, medido en los mismos días, se equivoca más que el vigente.
    """
    if actual is not None and nuevo["entrenado_hasta"] < actual["entrenado_hasta"]:
        return "el candidato tiene menos historia que el vigente"
    if _identidad(nuevo) in retirados:
        return "es el modelo que retiró una vuelta atrás"
    if error_frente_a_referencia(nuevo) >= 1:
        return "el candidato no se equivoca menos que la media de 30 días"
    v = list(nuevo["validacion"].values())
    if actual is not None and all(x.get("error_vigente") is not None for x in v):
        if sum(x["error"] for x in v) > sum(x["error_vigente"] for x in v):
            return "medido en los mismos días, el candidato se equivoca más que el vigente"
    return None


def promover(c=None):
    """Pone el candidato en uso si nada lo impide (`motivo_para_no_promover`); el vigente pasa a anteriores.

    Si la promoción falla a mitad, devuelve el vigente a su sitio antes de lanzar el error. Devuelve la decisión.
    """
    c = c or config()
    vigente, candidato, anteriores = carpetas_modelos(c)
    nuevo = json.loads((candidato / "manifiesto.json").read_text(encoding="utf-8"))
    actual = (json.loads((vigente / "manifiesto.json").read_text(encoding="utf-8"))
              if (vigente / "manifiesto.json").exists() else None)
    decision = {"nuevo": error_frente_a_referencia(nuevo),
                "vigente": None if actual is None else error_frente_a_referencia(actual)}
    motivo = motivo_para_no_promover(nuevo, actual, _retirados(c))
    if motivo:
        return {"promovido": False, **decision, "motivo": f"{motivo}; el vigente sigue en uso"}
    destino = None
    if actual is not None:
        destino = anteriores / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(vigente), str(destino))
    try:
        shutil.move(str(candidato), str(vigente))
    except Exception:
        # El vigente vuelve a su sitio: el proceso nunca se queda sin modelo por una promoción a medias
        if destino is not None and not vigente.exists():
            shutil.move(str(destino), str(vigente))
        raise
    return {"promovido": True, **decision,
            "motivo": "no había modelo vigente" if actual is None else "el candidato mejora al vigente"}


def volver_atras(c=None):
    """Restaura el último modelo de `anteriores/` como vigente. El vigente se guarda allí como retirado y se apunta en
    `retirados.json`, para que el siguiente reentreno con los mismos datos no lo vuelva a poner."""
    c = c or config()
    vigente, _, anteriores = carpetas_modelos(c)
    # Los retirados por una vuelta atrás no cuentan: si contaran, la segunda vuelta restauraría el recién retirado
    previos = (sorted(p for p in anteriores.iterdir() if p.is_dir() and not p.name.endswith("_retirado"))
               if anteriores.exists() else [])
    if not previos:
        raise RuntimeError("no hay ningún modelo anterior al que volver")
    restaurar = previos[-1]
    if vigente.exists():
        actual = json.loads((vigente / "manifiesto.json").read_text(encoding="utf-8"))
        retirados = _retirados(c) + [_identidad(actual)]
        (c["modelos"] / "retirados.json").write_text(json.dumps(retirados, ensure_ascii=False, indent=2),
                                                    encoding="utf-8")
        shutil.move(str(vigente), str(anteriores / (datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_retirado")))
    shutil.move(str(restaurar), str(vigente))
    return restaurar.name


# =====================================================================================================================
# 3. Los datos del día
# =====================================================================================================================

def _comprobar_columnas(tabla, columnas, nombre):
    """Columnas y tipos de una tabla del contrato."""
    faltan = [c for c in columnas if c not in tabla.columns]
    if faltan:
        raise EntradaIncorrecta(f"a {nombre} le faltan columnas: {', '.join(faltan)}")
    for c, tipo in columnas.items():
        if tipo == "entero" and not pd.api.types.is_integer_dtype(tabla[c]):
            raise EntradaIncorrecta(f"la columna {c} de {nombre} tiene que ser un número entero")


def leer_entrada(carpeta):
    """Lee las dos tablas del contrato desde una carpeta; sin ellas, para."""
    rutas = {"inventario": carpeta / "inventario_diario.csv", "pedidos": carpeta / "pedidos.csv"}
    faltan = [salidas.relativa(r) for r in rutas.values() if not r.is_file()]
    if faltan:
        raise EntradaIncorrecta(f"no llega el fichero del día: falta {', '.join(faltan)}")
    try:
        inv = pd.read_csv(rutas["inventario"], encoding="utf-8", dtype={"producto": "str"})
        inv["fecha"] = pd.to_datetime(inv["fecha"], format="%Y-%m-%d")
        ped = pd.read_csv(rutas["pedidos"], encoding="utf-8",
                          dtype={"id_pedido": "str", "producto": "str", "estado": "str", "fecha_llegada": "str"})
        ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], format="%Y-%m-%d")
        ped["fecha_llegada"] = pd.to_datetime(ped["fecha_llegada"], format="%Y-%m-%d")
    except (ValueError, KeyError) as e:
        raise EntradaIncorrecta(f"el fichero del día no se puede leer como dice el contrato: {e}") from e

    # Lo que tiene que cumplir cada pedido sea cual sea el día: si no, quitar lo posterior lo escondería
    if ped["fecha_pedido"].isna().any():
        raise EntradaIncorrecta("hay pedidos sin fecha de pedido")
    if ped["id_pedido"].duplicated().any():
        raise EntradaIncorrecta(f"hay pedidos repetidos: {sorted(ped.loc[ped['id_pedido'].duplicated(), 'id_pedido'])}")
    if (ped["fecha_llegada"] < ped["fecha_pedido"]).any():
        raise EntradaIncorrecta("hay pedidos que llegan antes de pedirse")
    if not ped["estado"].isin(["recibido", "pendiente"]).all():
        raise EntradaIncorrecta(f"estados que no son recibido ni pendiente: {sorted(set(ped['estado']) - {'recibido', 'pendiente'})}")
    return inv, ped


def comprobar_dia(inv, ped, dia, productos):
    """Lo que tiene que cumplir la entrada del cierre de `dia`, ya sin lo posterior: lo de cada producto llega hasta
    ese día, sin huecos ni repetidos y con el stock cuadrado, y cada pedido trae unidades. Si algo falla, para."""
    _comprobar_columnas(inv, COLUMNAS_INVENTARIO, "inventario_diario.csv")
    _comprobar_columnas(ped, COLUMNAS_PEDIDOS, "pedidos.csv")
    dia = pd.Timestamp(dia)
    llegan = set(inv["producto"])
    if llegan != set(productos):
        faltan, sobran = sorted(set(productos) - llegan), sorted(llegan - set(productos))
        raise EntradaIncorrecta(f"productos que faltan: {faltan}; que sobran: {sobran}")
    if inv.duplicated(["producto", "fecha"]).any():
        raise EntradaIncorrecta("hay productos con el mismo día repetido")
    ultimo = inv.groupby("producto")["fecha"].max()
    if (ultimo != dia).any():
        raise EntradaIncorrecta(f"el último día de algún producto no es el {dia.date()}: "
                                f"{sorted(str(x.date()) for x in set(ultimo))}")
    for p, g in inv.sort_values("fecha").groupby("producto"):
        if not (np.diff(g["fecha"].values) == np.timedelta64(1, "D")).all():
            raise EntradaIncorrecta(f"{p}: la historia tiene huecos")
        if len(g) < cfg.VENTANA:
            raise EntradaIncorrecta(f"{p}: hacen falta {cfg.VENTANA} días de historia y llegan {len(g)}")
        # Cada día empieza con el stock con que cerró la víspera
        salto = g["stock_inicial"].to_numpy()[1:] != g["stock_final"].to_numpy()[:-1]
        if salto.any():
            raise EntradaIncorrecta(f"{p}: el stock inicial no es el final de la víspera en {int(salto.sum())} días")
    negativos = [c for c in ("stock_inicial", "unidades_recibidas", "ventas", "ventas_perdidas", "stock_final")
                 if (inv[c] < 0).any()]
    if negativos:
        raise EntradaIncorrecta(f"hay unidades negativas en {', '.join(negativos)}")
    cuadra = inv["stock_inicial"] + inv["unidades_recibidas"] - inv["ventas"] == inv["stock_final"]
    if not cuadra.all():
        raise EntradaIncorrecta(f"el stock no cuadra en {int((~cuadra).sum())} filas")
    if (ped["cantidad"] <= 0).any():
        raise EntradaIncorrecta("hay pedidos sin unidades")
    otros = sorted(set(ped["producto"]) - set(productos))
    if otros:
        raise EntradaIncorrecta(f"hay pedidos de productos que no están en la configuración: {otros}")
    if (ped["fecha_llegada"].isna() != (ped["estado"] == "pendiente")).any():
        raise EntradaIncorrecta("el estado de algún pedido no casa con su llegada: recibido sin llegada o pendiente "
                                "con llegada")


def hasta_el_dia(inv, ped, dia):
    """Las tablas tal como se conocen al cierre de `dia`: nada posterior. Un pedido lanzado después no está y uno que
    llega después sigue pendiente. Así el proceso no puede usar el futuro."""
    dia = pd.Timestamp(dia)
    ped = ped.loc[ped["fecha_pedido"] <= dia].copy()
    despues = ped["fecha_llegada"] > dia
    ped.loc[despues, "fecha_llegada"] = pd.NaT
    ped.loc[despues, "estado"] = "pendiente"
    return inv.loc[inv["fecha"] <= dia].copy(), ped


# =====================================================================================================================
# 4. La decisión de cada producto
# =====================================================================================================================

def decidir(inv, ped, dia, c, modelos):
    """La línea de cada producto al cierre de `dia`: previsión del plazo, punto de pedido, stock, en camino, posición y
    si se pide o no, con la cantidad fija."""
    dia = pd.Timestamp(dia)
    camino = transformar_pedidos(ped)
    filas = []
    for p, x in sorted(c["productos"].items()):
        g = inv.loc[inv["producto"] == p].sort_values("fecha")
        demanda = (g["ventas"] + g["ventas_perdidas"]).to_numpy(dtype=float)
        fechas = pd.DatetimeIndex(g["fecha"])
        hoy = len(g) - 1
        if x["regla"] == cfg.ACTUAL:
            prevision = float(g["ventas"].to_numpy()[-cfg.VENTANA:].sum()) / cfg.VENTANA * x["plazo"]
        elif x["regla"] == cfg.CORREGIDA:
            prevision = float(modelo.media_ventana(demanda, [hoy])[0]) * x["plazo"]
        elif x["regla"] == cfg.PREVISION:
            prevision = float(modelo.prevision_del_plazo(modelos[p], demanda, fechas, [hoy], x["plazo"])[0])
        else:
            raise ValueError(f"{p}: regla desconocida {x['regla']}")
        stock = int(g["stock_final"].iloc[-1])
        en_camino = int(camino.loc[(camino["producto"] == p) & camino["fecha_llegada"].isna(), "cantidad"].sum())
        punto = prevision + float(x["stock_seguridad"])
        filas.append({"fecha": dia.date().isoformat(), "producto": p, "regla": x["regla"], "prevision_plazo": prevision,
                      "stock_seguridad": float(x["stock_seguridad"]), "punto_pedido": punto, "stock": stock,
                      "en_camino": en_camino, "posicion": stock + en_camino,
                      "pedir": bool(stock + en_camino <= punto), "cantidad": int(x["cantidad"])})
    return pd.DataFrame(filas)[COLUMNAS_DECISION]


# =====================================================================================================================
# 5. Salida y registro de cada ejecución
# =====================================================================================================================

def preparar_salida(carpeta_dia):
    """La carpeta de un día; si ya existía, la anterior se archiva antes de escribir nada."""
    if carpeta_dia.exists():
        archivo = carpeta_dia.parent / "_archivo" / f"{carpeta_dia.name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        archivo.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(carpeta_dia), str(archivo))
    carpeta_dia.mkdir(parents=True)
    return carpeta_dia


def anotar_ejecucion(carpeta_salidas, fila):
    """Añade una fila al registro de ejecuciones: día, momento, estado, duración, pedidos lanzados y motivo."""
    registro = carpeta_salidas / "ejecuciones.csv"
    nuevo = not registro.exists()
    registro.parent.mkdir(parents=True, exist_ok=True)
    with registro.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_EJECUCIONES)
        if nuevo:
            w.writeheader()
        w.writerow({k: fila.get(k) for k in CAMPOS_EJECUCIONES})
