# -*- mode: python ; coding: utf-8 -*-

import sys

block_cipher = None

# --- Icono según plataforma -------------------------------------------------
if sys.platform == "win32":
    APP_ICON = "static/logos/cicada_logo.ico"
elif sys.platform == "darwin":
    APP_ICON = "static/logos/cicada_logo.icns"
else:
    APP_ICON = "static/logos/cicada_logo.png"

# --- Hidden imports ----------------------------------------------------------
HIDDEN_IMPORTS = [
    "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    "fastapi", "fastapi.staticfiles", "starlette", "pydantic",
    "mutagen", "mutagen.easyid3", "mutagen.id3", "mutagen.flac",
    "mutagen.mp4", "mutagen.oggvorbis",
    "yt_dlp", "yt_dlp.extractor",
    "pystray",
    "pystray._win32" if sys.platform == "win32" else "pystray._dummy",
    "PIL", "PIL.Image",
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
    datas=[("static", "static")],
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

# --- CONFIGURACIÓN DIVIDIDA SEGÚN SISTEMA OPERATIVO ---

if sys.platform == "darwin":
    # 🍏 MODO ONEDIR PARA MAC (Evita el cuelgue "usleep" del bootloader)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="Cicada",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=APP_ICON,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="Cicada"
    )
    app = BUNDLE(
        coll, # <-- Se empaqueta el directorio recolectado, no el binario crudo
        name="Cicada.app",
        icon=APP_ICON,
        bundle_identifier="com.jjaroll.cicada",
        info_plist={
            "CFBundleShortVersionString": "1.0.2",
            "NSHighResolutionCapable": True,
            "LSUIElement": False,
        },
    )
else:
    # 🪟🐧 MODO ONEFILE PARA WINDOWS / LINUX
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