# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para Cicada.
Compila main.py como aplicación "windowed" (sin consola), incluyendo la
carpeta static/ completa y las dependencias ocultas que PyInstaller no
detecta automáticamente (uvicorn/fastapi usan carga dinámica de módulos,
mutagen y yt_dlp registran plugins por introspección).

Uso:
    pyinstaller Cicada.spec
"""

import sys

block_cipher = None

# --- Icono según plataforma -------------------------------------------------
if sys.platform == "win32":
    APP_ICON = "static/logos/cicada_logo.ico"
elif sys.platform == "darwin":
    APP_ICON = "static/logos/cicada_logo.icns"
else:
    # Linux no soporta iconos embebidos en el binario ELF; PyInstaller
    # simplemente ignora el icono en este caso (se maneja vía .desktop).
    APP_ICON = "static/logos/cicada_logo.png"

# --- Hidden imports ----------------------------------------------------------
HIDDEN_IMPORTS = [
    # uvicorn carga sus loops/protocolos dinámicamente
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # fastapi / starlette y su stack de validación
    "fastapi",
    "fastapi.staticfiles",
    "starlette",
    "pydantic",
    # metadatos de audio
    "mutagen",
    "mutagen.easyid3",
    "mutagen.id3",
    "mutagen.flac",
    "mutagen.mp4",
    "mutagen.oggvorbis",
    # descarga de audio
    "yt_dlp",
    "yt_dlp.extractor",
    # tray icon
    "pystray",
    "pystray._win32" if sys.platform == "win32" else "pystray._dummy",
    "PIL",
    "PIL.Image",
]

if sys.platform == "darwin":
    HIDDEN_IMPORTS.append("pystray._darwin")
elif sys.platform.startswith("linux"):
    HIDDEN_IMPORTS.append("pystray._xorg")
    HIDDEN_IMPORTS.append("Xlib")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("static", "static"),
    ],
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Cicada",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
)

# En macOS, además del binario, se genera el bundle .app con el icono correcto.
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Cicada.app",
        icon=APP_ICON,
        bundle_identifier="com.jjaroll.cicada",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSUIElement": False,
        },
    )
