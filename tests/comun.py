"""Lo común de las pruebas: el contador de casos y la ruta del paquete."""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "produccion"))


class Casos:
    """Cuenta los casos que pasan y los que fallan, y sale con 0 o 1."""

    def __init__(self):
        """Empieza sin casos."""
        self.fallos = []
        self.total = 0

    def caso(self, nombre, ok, detalle=""):
        """Apunta un caso y lo imprime."""
        self.total += 1
        print(("OK    " if ok else "FALLA ") + nombre + (f"  ({detalle})" if detalle and not ok else ""))
        if not ok:
            self.fallos.append(nombre)

    def lanza(self, nombre, funcion, excepcion):
        """Un caso que pasa si `funcion()` lanza `excepcion`."""
        try:
            funcion()
        except excepcion as e:
            self.caso(nombre, True)
            return str(e)
        self.caso(nombre, False, f"no lanzó {excepcion.__name__}")
        return None

    def fin(self):
        """Resume y sale con 1 si algo falla."""
        print(f"\n{self.total - len(self.fallos)} de {self.total} casos pasan" +
              (f"; fallan: {', '.join(self.fallos)}" if self.fallos else ""))
        raise SystemExit(1 if self.fallos else 0)
