"""Punto de entrada principal para la ejecución de Cicada."""
import runpy

if __name__ == "__main__":
    # Inicia la aplicación ejecutando el módulo principal.
    runpy.run_module("cicada.core.main", run_name="__main__")
