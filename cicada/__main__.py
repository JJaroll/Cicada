"""Punto de entrada de subcomandos: ``python -m cicada <grupo> ...``.

Por ahora solo el grupo ``ipod`` (ver cicada/ipod/cli.py).
"""
from __future__ import annotations

import sys
from typing import Optional, Sequence


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "ipod":
        from cicada.ipod.cli import main as ipod_main
        return ipod_main(argv[1:])
    print("uso: python -m cicada ipod <backup|restore|list-backups> ...", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
