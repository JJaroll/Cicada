"""Punto de entrada principal para la ejecución de Cicada."""
# Import estático (no runpy.run_module): en el ejecutable congelado de
# PyInstaller, un import dinámico por string no resuelve el paquete padre
# aunque esté empaquetado — ver Cicada.spec para el detalle. El import
# estático deja que el analizador de PyInstaller siga la dependencia real.
from cicada.core.main import main

if __name__ == "__main__":
    main()
