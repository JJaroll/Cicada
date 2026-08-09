"""
Punto de entrada de Cicada.

La aplicación vive en cicada/core/main.py. Este shim ejecuta ese módulo como
paquete para que los imports absolutos (cicada.core.*, cicada.ipod.*) resuelvan
correctamente, tanto en desarrollo (`python run.py`) como empaquetado con
PyInstaller.
"""
import runpy

if __name__ == "__main__":
    runpy.run_module("cicada.core.main", run_name="__main__")
