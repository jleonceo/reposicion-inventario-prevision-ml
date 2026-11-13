"""Pruebas de limpieza del repositorio: ningún fichero nombra el origen, un nombre interno ni una ruta de la máquina.

Recorre todos los ficheros de texto del repositorio (menos `.git/`, los datos y las salidas generadas) y busca tres
listas de palabras. Antes de dar el verde, comprueba que la búsqueda caza lo que tiene que cazar: un fichero de prueba
con cada palabra prohibida tiene que salir en rojo.

Uso: python -W error tests/probar_limpieza.py [carpeta]   (por defecto, la raíz del repositorio)
Sale con 0 si todo pasa y con 1 si algo falla.
"""

# =====================================================================================================================
# CONFIGURACIÓN
# =====================================================================================================================

import re
import sys
import tempfile
from pathlib import Path

# Raíz del repositorio, calculada desde el propio script
RAIZ = Path(__file__).resolve().parents[1]

# Palabras que delatan el origen del material
ORIGEN = [r"\bejercicio", r"\bprofesor", r"\bprofe\b", r"\bcurso\b", r"\bm[aá]ster\b", r"\blecci[oó]n",
          r"\bcuaderno", r"\bmaterial\b", r"\bminicaso", r"\bampliaci[oó]n\b", r"\baudio\b"]
# Nombres internos del trabajo
INTERNOS = [r"\bR65-\d", r"\bCP-\d", r"\bWF-\d", r"\bDEC-\d", r"\bJuan\b", r"\bClaude\b", r"\bskill",
            r"00_comun", r"reglas? §", r"\bencargo", r"\bintermedia\b", r"\bpropuesta\b", r"cl[aá]sica[ _]?de[ _]?manual",
            r"clasica_manual", r"contexto-proyecto", r"\bradiograf"]
# Rutas de la máquina: cualquier unidad de Windows con una carpeta detrás, las carpetas de usuario de Linux y macOS y
# los nombres de la máquina de trabajo
RUTAS = [r"(?<![\w])[A-Za-z]:[\\/]+[A-Za-z_]", r"/home/\w", r"/Users/\w", r"\busuario\b", r"anaconda3",
         r"PROYECTOS_GITHUB"]
# Un ejemplo que tiene que cazar cada patrón, uno a uno: si un patrón no caza el suyo, la lista no protege
MUESTRAS = {r"\bejercicio": "el ejercicio", r"\bprofesor": "el profesor", r"\bprofe\b": "la profe",
            r"\bcurso\b": "el curso", r"\bm[aá]ster\b": "el máster", r"\blecci[oó]n": "la lección",
            r"\bcuaderno": "el cuaderno", r"\bmaterial\b": "el material", r"\bminicaso": "un minicaso",
            r"\bampliaci[oó]n\b": "la ampliación", r"\baudio\b": "el audio", r"\bR65-\d": "R65-12",
            r"\bCP-\d": "CP-003", r"\bWF-\d": "WF-94", r"\bDEC-\d": "DEC-170", r"\bJuan\b": "Juan",
            r"\bClaude\b": "Claude", r"\bskill": "la skill", r"00_comun": "00_comun", r"reglas? §": "reglas §7",
            r"\bencargo": "el encargo", r"\bintermedia\b": "la intermedia", r"\bpropuesta\b": "la propuesta",
            r"cl[aá]sica[ _]?de[ _]?manual": "clásica de manual", r"clasica_manual": "clasica_manual",
            r"contexto-proyecto": "contexto-proyecto", r"\bradiograf": "la radiografía",
            r"(?<![\w])[A-Za-z]:[\\/]+[A-Za-z_]": "D:\\trabajo\\pepe", r"/home/\w": "/home/pepe/x",
            r"/Users/\w": "/Users/pepe", r"\busuario\b": "el usuario", r"anaconda3": "anaconda3",
            r"PROYECTOS_GITHUB": "PROYECTOS_GITHUB"}
# Lo que no se recorre: control de versiones, datos y salidas que genera el código
FUERA = {".git", "__pycache__", "datos", "salidas", "modelos", "salidas_pipeline", "entrada", "salidas_simulacion",
         "modelos_simulacion"}
# Esta misma prueba lleva las listas: no se busca en ella
ESTE = Path(__file__).resolve()
# La licencia lleva el nombre del titular de los derechos, que tiene que estar
LICENCIA = RAIZ / "LICENSE"


# =====================================================================================================================
# BÚSQUEDA
# =====================================================================================================================

def ficheros(carpeta):
    """Ficheros de texto de la carpeta, sin los de FUERA ni esta prueba."""
    # Los que se pueden leer como texto
    salida = []
    for f in sorted(Path(carpeta).rglob("*")):
        # Solo ficheros, fuera de las carpetas excluidas y sin esta prueba
        if not f.is_file() or FUERA & set(f.relative_to(carpeta).parts) or f.resolve() in (ESTE, LICENCIA):
            continue
        # Los binarios se saltan: no se pueden leer como UTF-8
        try:
            f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        salida.append(f)
    return salida


def no_caben_en_consola(carpeta, codificacion="cp1252"):
    """(fichero, línea, texto) de cada línea de código Python que la consola de Windows no puede imprimir.

    En Windows la consola usa cp1252 si no se cambia, y un carácter que no está en ella (como «−» o «→») hace caer el
    script al imprimirlo. Se mira el código, no los comentarios ni las cadenas de documentación, salvo la primera línea
    del módulo, que es la ayuda que imprime `--help`.
    """
    salida = []
    for f in ficheros(carpeta):
        if f.suffix != ".py":
            continue
        en_doc, primera = False, True
        for i, linea in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            limpia = linea.strip()
            comillas = linea.count('"""')
            if en_doc or comillas:
                # La primera línea de la documentación del módulo sí se imprime
                if primera and not en_doc and limpia.startswith('"""'):
                    revisar = limpia
                else:
                    revisar = ""
                if comillas % 2:
                    en_doc = not en_doc
                primera = False
            elif limpia.startswith("#") or not limpia:
                continue
            else:
                primera = False
                revisar = re.split(r"\s#\s", linea)[0]
            try:
                revisar.encode(codificacion)
            except UnicodeEncodeError:
                salida.append((str(f.relative_to(carpeta)), i, limpia[:80]))
    return salida


def hallazgos(carpeta, patrones):
    """(fichero, línea, palabra) de cada aparición de un patrón en los ficheros de la carpeta."""
    # Cada aparición, con su sitio
    salida = []
    for f in ficheros(carpeta):
        for i, linea in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for patron in patrones:
                for m in re.finditer(patron, linea, flags=re.I):
                    salida.append((str(f.relative_to(carpeta)), i, m.group(0)))
    return salida


# =====================================================================================================================
# CASOS
# =====================================================================================================================

def main():
    """Lanza los casos y sale con 0 o 1."""
    # Carpeta a recorrer
    carpeta = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else RAIZ
    fallos = []
    # El rojo primero: cada patrón tiene que cazar su propio ejemplo, en un fichero de prueba
    todos = ORIGEN + INTERNOS + RUTAS
    with tempfile.TemporaryDirectory() as tmp:
        sueltos = [p for p in todos if p not in MUESTRAS]
        no_cazan = []
        for patron in todos:
            if patron in MUESTRAS:
                (Path(tmp) / "canario.md").write_text(MUESTRAS[patron], encoding="utf-8")
                if not hallazgos(tmp, [patron]):
                    no_cazan.append(patron)
        ok = not sueltos and not no_cazan
        print(("OK    " if ok else "FALLA ") + f"ROJO: cada uno de los {len(todos)} patrones caza su ejemplo"
              + ("" if ok else f" (sin ejemplo: {sueltos}; no cazan: {no_cazan})"))
        if not ok:
            fallos.append("canario")
        # La consola: lo que se imprime con «→» se caza; tildes, eñes, comentarios y documentación no
        (Path(tmp) / "canario.md").unlink()
        (Path(tmp) / "malo.py").write_text('"""Uno."""\nprint("a → b")\n', encoding="utf-8")
        (Path(tmp) / "bueno.py").write_text('"""Acción del año."""\n\n\ndef f():\n    """Diferencia a − b."""\n'
                                            '    # media × plazo\n    print("señal, posición")\n',
                                            encoding="utf-8")
        cazados = no_caben_en_consola(tmp)
        ok = [(f, i) for f, i, _ in cazados] == [("malo.py", 2)]
        print(("OK    " if ok else "FALLA ") + "ROJO: la prueba de consola caza «→» al imprimir y deja pasar tildes, "
              "comentarios y documentación" + ("" if ok else f" (da {cazados})"))
        if not ok:
            fallos.append("canario de consola")
    # Lo que imprime el código cabe en la consola de Windows
    h = no_caben_en_consola(carpeta)
    print(("OK    " if not h else "FALLA ") + f"todo lo que imprime el código cabe en la consola de Windows: "
          f"{len(h)} líneas que no")
    for f, i, texto in h[:15]:
        print(f"        {f}:{i}  {texto}")
    if h:
        fallos.append("consola")
    # El repositorio, limpio
    for nombre, patrones in (("origen", ORIGEN), ("nombres internos", INTERNOS), ("rutas de la máquina", RUTAS)):
        h = hallazgos(carpeta, patrones)
        print(("OK    " if not h else "FALLA ") + f"ningún fichero con {nombre}: {len(h)} apariciones")
        for f, i, palabra in h[:15]:
            print(f"        {f}:{i}  «{palabra}»")
        if h:
            fallos.append(nombre)
    # Resultado
    print("\n" + (f"{len(fallos)} caso(s) fallan" if fallos else "Todos los casos pasan"))
    raise SystemExit(1 if fallos else 0)


if __name__ == "__main__":
    main()
