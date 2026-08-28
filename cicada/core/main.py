"""
Cicada
-----------
Herramienta local de organización musical y sincronización automática de metadatos de alta fidelidad.

Desarrollado por: JJaroll
GitHub: https://github.com/JJaroll
Fecha: 10/07/2026
Licencia: GNU GPLv3
"""

__author__ = "JJaroll"
__version__ = "1.1.1"
__maintainer__ = "JJaroll"
__status__ = "Production"

import sys
import os

if getattr(sys, 'frozen', False):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

import logging
import threading
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

app = FastAPI()

try:
    from cicada.ipod.api import router as ipod_router
    IPOD_AVAILABLE = True
except ModuleNotFoundError as exc:
    ipod_router = None
    IPOD_AVAILABLE = False
    logger.warning(
        "Módulo iPod no disponible (falta la dependencia '%s'). "
        "La app funciona normalmente, sin esa sección. "
        "Para habilitarla: pip install cicada[ipod]",
        exc.name,
    )
from cicada.core.routes.settings import router as settings_router
from cicada.core.routes.system import router as system_router
from cicada.core.routes.library import router as library_router
from cicada.core.routes.spotify import router as spotify_router
from cicada.core.routes.process import router as process_router
from cicada.core.routes.podcasts import router as podcasts_router
if IPOD_AVAILABLE:
    app.include_router(ipod_router)
app.include_router(settings_router)
app.include_router(system_router)
app.include_router(library_router)
app.include_router(spotify_router)
app.include_router(process_router)
app.include_router(podcasts_router)

STATIC_DIR = (
    Path(sys._MEIPASS)
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[2]
) / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def get():
    html_content = """
    <!DOCTYPE html>
    <html class="dark" lang="es" data-theme="grafito" data-color="azul">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cicada</title>
        <link id="favicon-link" rel="icon" type="image/svg+xml" href="/static/logos/cicada_blue.svg">
        <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/fontsource/css/opendyslexic@latest/index.css" rel="stylesheet">
        <!-- Configuración de Tailwind: variables CSS por tema/color de acento -->
        <script id="tailwind-config">
          tailwind.config = {
            darkMode: "class",
            theme: {
              extend: {
                colors: {
                  app: 'var(--bg-app)',
                  main: 'var(--bg-main)',
                  card: 'var(--bg-card)',
                  sidebar: 'var(--bg-sidebar)',
                  input: 'var(--input-bg)',
                  btn: 'var(--btn-bg)',
                  'btn-hover': 'var(--btn-hover)',
                  accent: {
                    DEFAULT: 'var(--accent)',
                    hover: 'var(--accent-hover)',
                    light: 'var(--accent-light)',
                  },
                },
                textColor: {
                  main: 'var(--text-main)',
                  muted: 'var(--text-muted)',
                  sidebar: 'var(--text-sidebar)',
                  'sidebar-muted': 'var(--text-sidebar-muted)',
                },
                borderColor: {
                  theme: 'var(--border-color)',
                },
                fontFamily: {
                  "body-sm": ["Outfit"],
                  "label-caps": ["JetBrains Mono"],
                  "headline-sm": ["Outfit"],
                  "data-lg": ["JetBrains Mono"],
                  "body-md": ["Outfit"],
                  "display-lg": ["Outfit"],
                  "headline-md": ["Outfit"],
                  "data-sm": ["JetBrains Mono"]
                },
              }
            }
          }
        </script>
        <link rel="stylesheet" href="/static/css/app.css?v=2.2.4">
    </head>
    <body class="bg-app text-main font-body-md text-body-md h-screen flex justify-center p-4">
        <div class="app-shell w-full h-full max-w-[1920px] mx-auto flex gap-4">
        <!-- Barra de navegación lateral -->
        <aside class="h-full w-[100px] bg-sidebar rounded-[20px] flex flex-col items-center py-8 z-50 text-sidebar">
            <div class="mb-12">
                <div class="relative w-14 h-14 rounded-2xl overflow-hidden cursor-pointer hover:opacity-70 transition-opacity" onclick="openAbout()" title="Sobre Cicada" data-i18n-title="about_tooltip">
                    <img src="/static/logos/cicada_blue.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="azul" alt="Cicada">
                    <img src="/static/logos/cicada_green.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="verde" alt="Cicada">
                    <img src="/static/logos/cicada_purple.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="morado" alt="Cicada">
                    <img src="/static/logos/cicada_orange.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="naranja" alt="Cicada">
                    <img src="/static/logos/cicada_pink.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="rosa" alt="Cicada">
                </div>
            </div>
            <nav class="flex-1 w-full flex flex-col items-stretch gap-4">
                <button type="button" class="nav-item nav-item-active flex flex-col items-center py-4 transition-all w-full" data-view="process" onclick="showView('process')">
                    <span class="material-symbols-outlined text-[24px] mb-1" style="font-variation-settings: 'FILL' 1;">terminal</span>
                    <span class="font-label-caps text-[11px]" data-i18n="nav_metadata">Metadatos</span>
                </button>
                <button type="button" class="nav-item nav-item-inactive flex flex-col items-center py-4 transition-all w-full" data-view="spotify" onclick="showView('spotify')">
                    <span class="material-symbols-outlined text-[24px] mb-1">queue_music</span>
                    <span class="font-label-caps text-[11px]" data-i18n="nav_download">Descarga</span>
                </button>
                <button type="button" class="nav-item nav-item-inactive flex flex-col items-center py-4 transition-all w-full" data-view="playlists" onclick="showView('playlists'); loadSpotifyPlaylists();">
                    <span class="material-symbols-outlined text-[24px] mb-1">playlist_play</span>
                    <span class="font-label-caps text-[11px]" data-i18n="nav_playlist">Playlist</span>
                </button>
                <button type="button" class="nav-item nav-item-inactive flex flex-col items-center py-4 transition-all w-full" data-view="library" onclick="showView('library')">
                    <span class="material-symbols-outlined text-[24px] mb-1">library_music</span>
                    <span class="font-label-caps text-[11px]" data-i18n="nav_library">Biblioteca</span>
                </button>
                <button type="button" class="nav-item nav-item-inactive flex flex-col items-center py-4 transition-all w-full" data-view="ipod" onclick="showView('ipod')">
                    <span class="material-symbols-outlined text-[24px] mb-1">developer_board</span>
                    <span class="font-label-caps text-[11px]" data-i18n="nav_ipod">iPod</span>
                </button>
            </nav>
            <div class="mt-auto flex flex-col items-center gap-6">
                <button type="button" onclick="openSettings()" class="material-symbols-outlined text-sidebar/60 hover:text-sidebar transition-colors" data-i18n-title="settings_tooltip" title="Ajustes">settings</button>
                <button type="button" onclick="openServerStatusModal()" class="relative w-10 h-10 rounded-xl bg-black/10 dark:bg-black/20 flex items-center justify-center border-2 border-transparent" data-i18n-title="connection_tooltip" title="Estado de conexión">
                    <span class="material-symbols-outlined text-[22px] text-sidebar/60">graphic_eq</span>
                    <span id="ws-status-dot" class="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-gray-400 border-2 border-sidebar"></span>
                </button>
            </div>
        </aside>

        <!-- Modal de Ajustes -->
        <div id="settings-modal" class="hidden fixed inset-0 z-[100] items-center justify-center bg-black/60 backdrop-blur-sm" onclick="if(event.target === this) closeSettings()">
            <div class="w-full max-w-3xl h-[80vh] max-h-[85vh] mx-4 flex rounded-2xl border border-theme bg-card overflow-hidden">

                <!-- Sidebar de categorías -->
                <div class="w-48 shrink-0 bg-black/10 border-r border-theme flex flex-col p-3 gap-1 overflow-y-auto custom-scrollbar">
                    <div class="flex items-center gap-2 px-2 py-2 mb-2">
                        <span class="material-symbols-outlined text-accent text-[20px]">settings</span>
                        <span class="font-label-caps text-[12px] tracking-widest text-main" data-i18n="settings_title">Ajustes</span>
                    </div>
                    <button type="button" class="settings-nav-btn bg-accent text-white w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg font-label-caps text-[12px] font-bold text-left transition-colors hover:bg-btn-hover" data-settings-tab="general" onclick="switchSettingsTab('general')">
                        <span class="material-symbols-outlined text-[18px]">language</span> <span data-i18n="settings_tab_general">General</span>
                    </button>
                    <button type="button" class="settings-nav-btn text-muted w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg font-label-caps text-[12px] font-bold text-left transition-colors hover:bg-btn-hover" data-settings-tab="apariencia" onclick="switchSettingsTab('apariencia')">
                        <span class="material-symbols-outlined text-[18px]">palette</span> <span data-i18n="settings_tab_apariencia">Apariencia</span>
                    </button>
                    <button type="button" class="settings-nav-btn text-muted w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg font-label-caps text-[12px] font-bold text-left transition-colors hover:bg-btn-hover" data-settings-tab="integraciones" onclick="switchSettingsTab('integraciones')">
                        <span class="material-symbols-outlined text-[18px]">link</span> <span data-i18n="settings_tab_integraciones">Integraciones</span>
                    </button>
                    <button type="button" class="settings-nav-btn text-muted w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg font-label-caps text-[12px] font-bold text-left transition-colors hover:bg-btn-hover" data-settings-tab="ipod" onclick="switchSettingsTab('ipod')">
                        <span class="material-symbols-outlined text-[18px]">developer_board</span> <span data-i18n="settings_tab_ipod">Módulo iPod</span>
                    </button>
                </div>

                <!-- Panel de contenido -->
                <div class="flex-1 flex flex-col min-w-0">
                    <div class="flex items-center justify-between px-6 py-4 border-b border-theme shrink-0">
                        <span id="settingsTabTitle" class="font-label-caps text-[14px] tracking-widest text-main" data-i18n="settings_tab_general">General</span>
                        <button type="button" onclick="closeSettings()" class="material-symbols-outlined text-muted/60 hover:text-main transition-colors">close</button>
                    </div>

                    <div class="flex-1 overflow-y-auto custom-scrollbar p-6">

                        <!-- GENERAL -->
                        <div id="settingsTab-general" class="settings-tab-content flex flex-col gap-5">
                            <div class="flex flex-col gap-2">
                                <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_language_title">Idioma</span>
                                <div class="flex gap-2">
                                    <button type="button" class="lang-btn flex-1 py-2 rounded-lg font-label-caps text-[11px] transition-colors" data-lang="es" onclick="applyLanguage('es')">Español</button>
                                    <button type="button" class="lang-btn flex-1 py-2 rounded-lg font-label-caps text-[11px] transition-colors" data-lang="en" onclick="applyLanguage('en')">English</button>
                                    <button type="button" class="lang-btn flex-1 py-2 rounded-lg font-label-caps text-[11px] transition-colors" data-lang="ja" onclick="applyLanguage('ja')">日本語</button>
                                </div>
                            </div>

                            <div class="flex flex-col gap-2">
                                <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_folders_title">Carpetas Predeterminadas</span>

                                <label class="font-label-caps text-[10px] text-muted/50" data-i18n="settings_library_dir_label">Carpeta de tu Biblioteca</label>
                                <div class="flex gap-2">
                                    <input type="text" id="settings_library_dir" placeholder="/Users/usuario/Musica/Organizada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                                    <button type="button" onclick="pickFolder('settings_library_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                                </div>

                                <label class="font-label-caps text-[10px] text-muted/50" data-i18n="settings_input_dir_label">Carpeta de Origen (Metadatos)</label>
                                <div class="flex gap-2">
                                    <input type="text" id="settings_process_input_dir" placeholder="/Users/usuario/Musica/Entrada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                                    <button type="button" onclick="pickFolder('settings_process_input_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                                </div>

                                <label class="font-label-caps text-[10px] text-muted/50" data-i18n="settings_output_dir_label">Carpeta de Destino (Metadatos)</label>
                                <div class="flex gap-2">
                                    <input type="text" id="settings_process_output_dir" placeholder="/Users/usuario/Musica/Organizada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                                    <button type="button" onclick="pickFolder('settings_process_output_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                                </div>
                            </div>
                        </div>

                        <!-- APARIENCIA -->
                        <div id="settingsTab-apariencia" class="settings-tab-content hidden flex-col gap-5">
                            <div class="flex flex-col gap-2">
                                <span class="font-label-caps text-[12px] text-muted tracking-widest font-bold" data-i18n="settings_theme_title">TEMA</span>
                                <div class="flex gap-3">
                                    <button type="button" class="theme-btn flex-1 py-3 rounded-xl border-2 font-label-caps text-[13px] font-bold transition-all" data-theme-val="grafito" onclick="selectThemeUI('grafito')" data-i18n="settings_theme_dark">Grafito</button>
                                    <button type="button" class="theme-btn flex-1 py-3 rounded-xl border-2 font-label-caps text-[13px] font-bold transition-all" data-theme-val="aluminio" onclick="selectThemeUI('aluminio')" data-i18n="settings_theme_light">Aluminio</button>
                                </div>
                                <input type="hidden" id="settings_theme" value="grafito">
                            </div>

                            <div class="flex flex-col gap-2">
                                <span class="font-label-caps text-[12px] text-muted tracking-widest font-bold" data-i18n="settings_color_title">COLOR NANO</span>
                                <div class="flex gap-4 items-center">
                                    <button type="button" class="color-btn w-8 h-8 rounded-full transition-all flex items-center justify-center relative" style="background-color: #0099FF;" data-color-val="azul" onclick="selectColorUI('azul')"></button>
                                    <button type="button" class="color-btn w-8 h-8 rounded-full transition-all flex items-center justify-center relative" style="background-color: #77C800;" data-color-val="verde" onclick="selectColorUI('verde')"></button>
                                    <button type="button" class="color-btn w-8 h-8 rounded-full transition-all flex items-center justify-center relative" style="background-color: #8A2BE2;" data-color-val="morado" onclick="selectColorUI('morado')"></button>
                                    <button type="button" class="color-btn w-8 h-8 rounded-full transition-all flex items-center justify-center relative" style="background-color: #FF8800;" data-color-val="naranja" onclick="selectColorUI('naranja')"></button>
                                    <button type="button" class="color-btn w-8 h-8 rounded-full transition-all flex items-center justify-center relative" style="background-color: #E62E6B;" data-color-val="rosa" onclick="selectColorUI('rosa')"></button>
                                </div>
                                <input type="hidden" id="settings_color" value="azul">
                            </div>

                            <div class="flex flex-col gap-2 border-t border-theme pt-4">
                                <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_accessibility_title">Accesibilidad</span>
                                <label class="flex items-center gap-2 cursor-pointer">
                                    <input type="checkbox" id="settings_dyslexic_font" class="cicada-checkbox" onchange="selectFontUI(this.checked ? 'dyslexic' : 'standard')"/>
                                    <span class="font-data-sm text-[13px] text-muted/70" data-i18n="settings_dyslexic_font_label">Fuente para dislexia</span>
                                </label>
                                <p class="font-data-sm text-[11px] text-muted/40 pl-6" data-i18n="settings_dyslexic_font_hint">Reemplaza la tipografía de toda la interfaz por OpenDyslexic. Funciona sin recargar la página.</p>

                                <label class="flex items-center gap-2 cursor-pointer mt-1">
                                    <input type="checkbox" id="settings_colorblind_mode" class="cicada-checkbox" onchange="selectColorblindModeUI(this.checked)"/>
                                    <span class="font-data-sm text-[13px] text-muted/70" data-i18n="settings_colorblind_mode_label">Modo daltónico</span>
                                </label>
                                <p class="font-data-sm text-[11px] text-muted/40 pl-6" data-i18n="settings_colorblind_mode_hint">Cambia los colores de estado (procesando/saltado/error/cancelado) a una paleta distinguible para daltonismo rojo-verde. Se puede usar junto a cualquier tema.</p>
                            </div>
                        </div>

                        <!-- INTEGRACIONES -->
                        <div id="settingsTab-integraciones" class="settings-tab-content hidden flex-col gap-5">
                            <div class="flex flex-col gap-2">
                                <span class="font-label-caps text-[12px] text-muted tracking-widest font-bold" data-i18n="settings_external_services_title">SERVICIOS EXTERNOS</span>

                                <div class="flex items-center justify-between gap-2 mt-1">
                                    <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_spotify_title">Cuenta de Spotify</span>
                                </div>
                                <div class="flex items-center justify-between gap-2">
                                    <span id="settings-spotify-status" class="font-data-sm text-[13px] text-muted/60" data-i18n="settings_spotify_not_connected">No conectado a Spotify</span>
                                    <button type="button" onclick="window.location.href='/api/auth/login'" id="settings-spotify-connect-btn" class="px-3 py-2 rounded-lg bg-accent text-white font-label-caps text-[11px] hover:brightness-110 transition-all whitespace-nowrap" data-i18n="settings_spotify_connect_btn">Conectar con Spotify</button>
                                </div>

                                <div class="flex items-center gap-1.5 mt-2">
                                    <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_credentials_title">Claves de Acceso</span>
                                    <button type="button" onclick="window.open('https://github.com/JJaroll/Cicada/blob/main/README.md#-configuraci%C3%B3n-de-claves-api', '_blank')" data-i18n-title="settings_credentials_help_tooltip" title="¿Cómo obtener las claves?" class="material-symbols-outlined text-[15px] text-muted/50 hover:text-accent transition-colors leading-none">help</button>
                                </div>

                                <label class="font-label-caps text-[10px] text-muted/50" data-i18n="settings_acoustid_label">Clave de AcoustID</label>
                                <div class="flex gap-2">
                                    <input type="password" id="settings_acoustid_key" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]" placeholder="Client key de AcoustID"/>
                                    <button type="button" onclick="toggleSecretVisibility('settings_acoustid_key', this)" class="material-symbols-outlined text-[18px] text-muted/50 hover:text-accent px-2">visibility</button>
                                </div>

                                <label class="font-label-caps text-[10px] text-muted/50" data-i18n="settings_spotify_id_label">ID de Cliente de Spotify</label>
                                <div class="flex gap-2">
                                    <input type="password" id="settings_spotify_id" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]" placeholder="Client ID de Spotify"/>
                                    <button type="button" onclick="toggleSecretVisibility('settings_spotify_id', this)" class="material-symbols-outlined text-[18px] text-muted/50 hover:text-accent px-2">visibility</button>
                                </div>

                                <label class="font-label-caps text-[10px] text-muted/50" data-i18n="settings_spotify_secret_label">Clave Secreta de Spotify</label>
                                <div class="flex gap-2">
                                    <input type="password" id="settings_spotify_secret" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]" placeholder="Client Secret de Spotify"/>
                                    <button type="button" onclick="toggleSecretVisibility('settings_spotify_secret', this)" class="material-symbols-outlined text-[18px] text-muted/50 hover:text-accent px-2">visibility</button>
                                </div>
                            </div>

                            <div class="flex flex-col gap-2 border-t border-theme pt-4">
                                <span class="font-label-caps text-[12px] text-muted tracking-widest font-bold" data-i18n="settings_identification_behavior_title">COMPORTAMIENTO DE IDENTIFICACIÓN</span>
                                <span class="font-label-caps text-[11px] text-accent/70 mt-1" data-i18n="settings_identification_title">Identificación de Canciones</span>
                                <label class="flex items-center gap-2 cursor-pointer">
                                    <input type="checkbox" id="settings_plan_c_enabled" class="cicada-checkbox"/>
                                    <span class="font-data-sm text-[13px] text-muted/70" data-i18n="settings_plan_c_label">Adivinar por el nombre del archivo cuando no se reconoce la canción</span>
                                </label>
                                <p class="font-data-sm text-[11px] text-muted/40 pl-6" data-i18n="settings_plan_c_hint">Apagado por defecto: suele ser poco preciso. Si está apagado, esos archivos se reportan como error en vez de adivinar el título/artista.</p>
                            </div>
                        </div>

                        <!-- MÓDULO IPOD -->
                        <div id="settingsTab-ipod" class="settings-tab-content hidden flex-col gap-5">
                            <div class="flex flex-col gap-2">
                                <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_ipod_section_title">Módulo iPod</span>
                                <label class="flex items-center gap-2 cursor-pointer">
                                    <input type="checkbox" id="settings_ipod_ui_enabled" class="cicada-checkbox"/>
                                    <span class="font-data-sm text-[13px] text-muted/70" data-i18n="settings_ipod_ui_label">Mostrar la sección iPod en la interfaz</span>
                                </label>
                                <p class="font-data-sm text-[11px] text-muted/40 pl-6" data-i18n="settings_ipod_ui_hint">Oculta la sección iPod de la interfaz. No reduce el tamaño de instalación ni elimina dependencias — el módulo sigue instalado, solo se deja de mostrar.</p>
                            </div>
                        </div>

                    </div>

                    <div class="flex gap-2 justify-end items-center px-6 py-4 border-t border-theme shrink-0">
                        <span id="settings-status" class="font-data-sm text-[12px] text-secondary mr-auto"></span>
                        <button type="button" onclick="closeSettings()" class="px-4 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[12px] transition-colors" data-i18n="common_cancel">Cancelar</button>
                        <button type="button" id="settingsSaveBtn" onclick="saveSettings()" class="px-4 py-2 rounded-lg bg-accent text-white font-label-caps text-[12px] hover:brightness-110 transition-all" data-i18n="common_save">Guardar</button>
                    </div>
                </div>

            </div>
        </div>

        <!-- Modal de Sobre / About -->
        <div id="about-modal" class="hidden fixed inset-0 z-[100] items-center justify-center bg-black/60 backdrop-blur-sm">
            <div class="w-full max-w-sm mx-4 p-6 flex flex-col items-center gap-3 rounded-2xl border border-theme bg-card text-center">
                <button type="button" onclick="closeAbout()" class="material-symbols-outlined text-muted/60 hover:text-main transition-colors self-end -mb-2 -mt-2 -mr-2">close</button>

                <div class="relative w-16 h-16 rounded-2xl bg-sidebar flex items-center justify-center overflow-hidden">
                    <img src="/static/logos/cicada_blue.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="azul" alt="Cicada">
                    <img src="/static/logos/cicada_green.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="verde" alt="Cicada">
                    <img src="/static/logos/cicada_purple.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="morado" alt="Cicada">
                    <img src="/static/logos/cicada_orange.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="naranja" alt="Cicada">
                    <img src="/static/logos/cicada_pink.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="rosa" alt="Cicada">
                </div>

                <span class="font-display-lg text-[20px] font-bold tracking-tighter text-main">Cicada</span>
                <span class="font-label-caps text-[11px] text-secondary" id="about-version" data-i18n="about_version">Versión __CICADA_VERSION__</span>

                <p class="font-data-sm text-[13px] text-muted/70" data-i18n="about_description">Herramienta local de organización musical y sincronización automática de metadatos de alta fidelidad.</p>

                <div class="w-full border-t border-theme my-1"></div>

                <p class="font-data-sm text-[13px] text-muted/70"><span data-i18n="about_author_label">Desarrollado por</span> <b>JJaroll</b></p>
                <p class="font-data-sm text-[11px] text-muted/40" data-i18n="about_license">Distribuido bajo Licencia GNU GPLv3</p>
                <p class="font-data-sm text-[11px] text-muted/40 mt-1"><a href="https://github.com/JJaroll/Cicada/blob/main/TERMS.md" target="_blank" class="hover:text-main underline decoration-dashed underline-offset-2 transition-colors" data-i18n="about_terms">Términos y Condiciones</a></p>

                <button type="button" onclick="window.open('https://github.com/JJaroll/Cicada', '_blank')" class="mt-2 w-full px-4 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors inline-flex items-center justify-center gap-1.5">
                    <span class="material-symbols-outlined text-[16px]">code</span>
                    <span data-i18n="about_github_btn">Ver en GitHub</span>
                </button>
                <button type="button" onclick="window.open('https://ko-fi.com/jjaroll', '_blank')" class="w-full px-4 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors inline-flex items-center justify-center gap-1.5">
                    <span class="material-symbols-outlined text-[16px]">favorite</span>
                    <span data-i18n="about_contribute_btn">Contribuir</span>
                </button>
            </div>
        </div>

        <!-- Modal de Estado del Servidor -->
        <div id="server-status-modal" class="hidden fixed inset-0 z-[100] items-center justify-center bg-black/60 backdrop-blur-sm" onclick="if(event.target === this) closeServerStatusModal()">
            <div class="w-full max-w-sm mx-4 p-6 flex flex-col gap-4 rounded-2xl border border-theme bg-card">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-accent text-[20px]">graphic_eq</span>
                        <span class="font-label-caps text-[14px] tracking-widest text-main" data-i18n="server_status_title">Estado del Servidor</span>
                    </div>
                    <button type="button" onclick="closeServerStatusModal()" class="material-symbols-outlined text-muted/60 hover:text-main transition-colors">close</button>
                </div>
                <div id="server-status-body" class="flex flex-col gap-3">
                    <p class="font-data-sm text-[13px] text-muted/60" data-i18n="server_status_checking">Consultando...</p>
                </div>
            </div>
        </div>

        <!-- Modal de apoyo (Ko-fi): aparece tras completar un proceso de más de 250 canciones -->
        <div id="kofi-modal" class="hidden fixed inset-0 z-[100] items-center justify-center bg-black/60 backdrop-blur-sm">
            <div class="w-full max-w-sm mx-4 p-6 flex flex-col items-center gap-3 rounded-2xl border border-theme bg-card text-center">
                <button type="button" onclick="closeKofiSupport()" class="material-symbols-outlined text-muted/60 hover:text-main transition-colors self-end -mb-2 -mt-2 -mr-2">close</button>

                <span class="material-symbols-outlined text-accent text-[40px]">volunteer_activism</span>

                <span class="font-display-lg text-[18px] font-bold tracking-tighter text-main" data-i18n="kofi_support_title">¡Gran trabajo!</span>

                <p class="font-data-sm text-[13px] text-muted/70" id="kofi-support-message"></p>

                <button type="button" onclick="window.open('https://ko-fi.com/jjaroll', '_blank')" class="mt-2 w-full px-4 py-2 rounded-lg bg-accent text-white font-label-caps text-[11px] hover:brightness-110 transition-all inline-flex items-center justify-center gap-1.5">
                    <span class="material-symbols-outlined text-[16px]">favorite</span>
                    <span data-i18n="about_contribute_btn">Contribuir</span>
                </button>
            </div>
        </div>

        <!-- Aviso de actualización: mensaje pequeño no bloqueante cuando hay un nuevo release estable en GitHub -->
        <div id="update-banner" class="hidden fixed top-4 right-4 z-[200] max-w-xs p-3 rounded-xl border-2 border-yellow-400 bg-card shadow-lg items-start gap-2">
            <span class="material-symbols-outlined text-accent text-[20px]">new_releases</span>
            <div class="flex-1 flex flex-col gap-1">
                <p class="font-data-sm text-[12px] text-main" id="update-banner-text"></p>
                <a href="#" id="update-banner-link" target="_blank" rel="noopener" class="font-label-caps text-[11px] text-accent hover:underline" data-i18n="update_available_link">Ver última versión</a>
            </div>
            <button type="button" onclick="dismissUpdateBanner()" class="material-symbols-outlined text-muted/60 hover:text-main transition-colors text-[16px]">close</button>
        </div>

        <!-- Context Menu de Biblioteca -->
        <div id="library-context-menu">
            <div class="context-menu-item" onclick="contextShowInFolder()">
                <span class="material-symbols-outlined text-[18px]">folder_open</span>
                <span data-i18n="ctx_show_in_folder">Mostrar en la biblioteca</span>
            </div>
            <div class="context-menu-item" onclick="contextGetInfo()">
                <span class="material-symbols-outlined text-[18px]">info</span>
                <span data-i18n="ctx_get_info">Obtener información</span>
            </div>
            <div class="context-menu-item danger" onclick="contextDeleteTrack()">
                <span class="material-symbols-outlined text-[18px]">delete</span>
                <span data-i18n="ctx_delete_track">Eliminar de biblioteca</span>
            </div>
        </div>

        <!-- Context Menu de canciones del iPod -->
        <div id="ipod-context-menu">
            <div class="context-menu-item has-submenu" onmouseenter="showIpodPlaylistSubmenu(event)">
                <span class="material-symbols-outlined text-[18px]">playlist_add</span>
                <span data-i18n="ctx_ipod_add_to_playlist">Agregar a Playlist</span>
                <span class="material-symbols-outlined text-[16px] submenu-arrow">chevron_right</span>
            </div>
            <div class="context-menu-item has-submenu" onmouseenter="showIpodRatingSubmenu(event)">
                <span class="material-symbols-outlined text-[18px]">star</span>
                <span data-i18n="ctx_ipod_rate">Calificar</span>
                <span class="material-symbols-outlined text-[16px] submenu-arrow">chevron_right</span>
            </div>
            <div class="context-menu-item danger" onclick="contextRemoveFromIpod()">
                <span class="material-symbols-outlined text-[18px]">delete</span>
                <span data-i18n="ctx_ipod_remove">Eliminar del iPod</span>
            </div>
        </div>
        <div id="ipod-playlist-submenu"></div>
        <div id="ipod-rating-submenu"></div>

        <!-- Modal de Obtener Información -->
        <div id="track-info-modal" class="hidden fixed inset-0 z-[100] items-center justify-center bg-black/60 backdrop-blur-sm">
            <div class="w-full max-w-lg mx-4 p-6 flex flex-col gap-4 max-h-[85vh] overflow-y-auto custom-scrollbar rounded-2xl border border-theme bg-card">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-accent text-[22px]">info</span>
                        <span class="font-label-caps text-[14px] tracking-widest text-main" data-i18n="track_info_title">Información de la pista</span>
                    </div>
                    <button type="button" onclick="closeTrackInfoModal()" class="material-symbols-outlined text-muted/60 hover:text-main transition-colors">close</button>
                </div>

                <div class="flex gap-4 border-b border-theme pb-2">
                    <button type="button" class="font-label-caps text-[12px] text-accent border-b-2 border-accent pb-1" id="tab-info-details" onclick="switchTrackInfoTab('details')" data-i18n="track_info_tab_details">Detalles</button>
                    <button type="button" class="font-label-caps text-[12px] text-muted/60 hover:text-main pb-1" id="tab-info-artwork" onclick="switchTrackInfoTab('artwork')" data-i18n="track_info_tab_artwork">Carátula</button>
                </div>

                <div id="track-info-details-panel" class="flex flex-col gap-3">
                    <div class="flex gap-2">
                        <div class="flex-1 flex flex-col gap-1">
                            <label class="font-label-caps text-[10px] text-muted/50">Título</label>
                            <input type="text" id="info_title" class="cicada-input rounded-lg px-3 py-2 text-[13px]"/>
                        </div>
                        <div class="flex-1 flex flex-col gap-1">
                            <label class="font-label-caps text-[10px] text-muted/50">Artista</label>
                            <input type="text" id="info_artist" class="cicada-input rounded-lg px-3 py-2 text-[13px]"/>
                        </div>
                    </div>

                    <div class="flex gap-2">
                        <div class="flex-1 flex flex-col gap-1">
                            <label class="font-label-caps text-[10px] text-muted/50">Álbum</label>
                            <input type="text" id="info_album" class="cicada-input rounded-lg px-3 py-2 text-[13px]"/>
                        </div>
                        <div class="flex-1 flex flex-col gap-1">
                            <label class="font-label-caps text-[10px] text-muted/50">Artista del álbum</label>
                            <input type="text" id="info_album_artist" class="cicada-input rounded-lg px-3 py-2 text-[13px]"/>
                        </div>
                    </div>

                    <div class="flex gap-2">
                        <div class="flex-1 flex flex-col gap-1">
                            <label class="font-label-caps text-[10px] text-muted/50">Compositor</label>
                            <input type="text" id="info_composer" class="cicada-input rounded-lg px-3 py-2 text-[13px]"/>
                        </div>
                        <div class="flex-1 flex flex-col gap-1">
                            <label class="font-label-caps text-[10px] text-muted/50">Agrupación</label>
                            <input type="text" id="info_grouping" class="cicada-input rounded-lg px-3 py-2 text-[13px]"/>
                        </div>
                    </div>

                    <div class="flex gap-2">
                        <div class="flex-1 flex flex-col gap-1">
                            <label class="font-label-caps text-[10px] text-muted/50">Género</label>
                            <input type="text" id="info_genre" class="cicada-input rounded-lg px-3 py-2 text-[13px]"/>
                        </div>
                        <div class="w-20 flex flex-col gap-1">
                            <label class="font-label-caps text-[10px] text-muted/50">Año</label>
                            <input type="text" id="info_year" class="cicada-input rounded-lg px-3 py-2 text-[13px]"/>
                        </div>
                        <div class="w-16 flex flex-col gap-1">
                            <label class="font-label-caps text-[10px] text-muted/50">BPM</label>
                            <input type="text" id="info_bpm" class="cicada-input rounded-lg px-3 py-2 text-[13px]"/>
                        </div>
                    </div>

                    <div class="flex gap-2 items-center">
                        <div class="flex flex-col gap-1">
                            <label class="font-label-caps text-[10px] text-muted/50">Pista</label>
                            <div class="flex items-center gap-1">
                                <input type="text" id="info_track_number" class="cicada-input rounded-lg px-2 py-1 text-[13px] w-12 text-center"/>
                                <span class="text-muted/50 text-[12px]">de</span>
                                <input type="text" id="info_track_count" class="cicada-input rounded-lg px-2 py-1 text-[13px] w-12 text-center"/>
                            </div>
                        </div>
                        <div class="flex flex-col gap-1 ml-4">
                            <label class="font-label-caps text-[10px] text-muted/50">Disco</label>
                            <div class="flex items-center gap-1">
                                <input type="text" id="info_disc_number" class="cicada-input rounded-lg px-2 py-1 text-[13px] w-12 text-center"/>
                                <span class="text-muted/50 text-[12px]">de</span>
                                <input type="text" id="info_disc_count" class="cicada-input rounded-lg px-2 py-1 text-[13px] w-12 text-center"/>
                            </div>
                        </div>
                        <div class="flex items-center gap-2 ml-auto mt-4">
                            <input type="checkbox" id="info_compilation" class="cicada-checkbox"/>
                            <label for="info_compilation" class="font-data-sm text-[12px] text-muted/70">Es compilación</label>
                        </div>
                    </div>

                    <div class="flex flex-col gap-1 mt-1">
                        <label class="font-label-caps text-[10px] text-muted/50">Comentarios</label>
                        <textarea id="info_comments" class="cicada-input rounded-lg px-3 py-2 text-[13px] h-16 resize-none"></textarea>
                    </div>
                </div>

                <div id="track-info-artwork-panel" class="hidden flex-col items-center gap-4 py-4">
                    <div class="relative w-48 h-48 rounded-lg bg-btn overflow-hidden flex items-center justify-center border border-theme">
                        <span class="material-symbols-outlined text-[48px] text-muted/30">music_note</span>
                        <img id="info_artwork_img" class="absolute inset-0 w-full h-full object-cover hidden" alt="">
                    </div>
                    <label class="px-4 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[12px] cursor-pointer transition-colors">
                        <span data-i18n="track_info_change_artwork">Cambiar Carátula</span>
                        <input type="file" id="info_artwork_input" class="hidden" accept="image/jpeg, image/png, image/webp" onchange="handleArtworkSelection(event)"/>
                    </label>
                </div>

                <div class="flex justify-end gap-3 mt-2">
                    <button type="button" onclick="closeTrackInfoModal()" class="px-5 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[12px] transition-colors" data-i18n="common_cancel">Cancelar</button>
                    <button type="button" onclick="saveTrackInfo()" class="px-5 py-2 rounded-lg bg-accent text-white font-label-caps text-[12px] hover:brightness-110 transition-all" data-i18n="common_save">Guardar</button>
                </div>
            </div>
        </div>

        <!-- Main Canvas: contenido por pestaña (izquierda) + módulo de proceso persistente (derecha) -->
        <main class="flex-1 h-full overflow-hidden flex gap-4">
            <div class="flex-1 h-full overflow-hidden">

                <!-- Vista: Metadatos -->
                <div id="view-process" class="view active grid-cols-9 grid-rows-6 gap-4 h-full overflow-hidden">
                    <div class="col-start-1 col-span-3 row-start-1 row-span-3 glass-card p-5 flex flex-col gap-3 overflow-y-auto custom-scrollbar">
                        <div class="flex items-center gap-2 mb-1">
                            <span class="material-symbols-outlined text-accent text-[20px]">settings_input_component</span>
                            <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="process_folders_title">Carpetas de Trabajo</span>
                        </div>

                        <div class="flex flex-col gap-1.5">
                            <label for="input_dir" class="font-label-caps text-[10px] text-accent/70" data-i18n="process_source_label">Carpeta de Origen</label>
                            <div class="flex gap-2">
                                <input type="text" id="input_dir" placeholder="/Users/usuario/Musica/Entrada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                                <button type="button" onclick="pickFolder('input_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                            </div>
                        </div>

                        <div class="flex flex-col gap-1.5">
                            <label for="output_dir" class="font-label-caps text-[10px] text-accent/70" data-i18n="process_dest_label">Carpeta de Destino</label>
                            <div class="flex gap-2">
                                <input type="text" id="output_dir" placeholder="/Users/usuario/Musica/Organizada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                                <button type="button" onclick="pickFolder('output_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                            </div>
                        </div>

                        <div class="flex gap-2 mt-1">
                            <button id="startBtn" type="button" onclick="startProcess()" class="flex-1 py-3 bg-accent text-white rounded-xl font-label-caps text-[12px] tracking-widest hover:brightness-110 transition-all inline-flex items-center justify-center gap-1.5">
                                <span class="material-symbols-outlined text-[18px]">play_arrow</span> <span data-i18n="process_start_btn">Iniciar</span>
                            </button>
                            <button id="cancelBtnSource" type="button" onclick="cancelProcess()" class="cancel-action hidden py-3 px-3 bg-red-600 text-white rounded-xl font-label-caps text-[12px] tracking-widest hover:brightness-110 transition-all inline-flex items-center justify-center gap-1.5">
                                <span class="material-symbols-outlined text-[18px]">stop</span> <span data-i18n="process_cancel_btn">Cancelar</span>
                            </button>
                        </div>
                    </div>

                    <!-- Actividad Reciente -->
                    <div class="col-start-1 col-span-3 row-start-4 row-span-3 glass-card p-5 flex flex-col">
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-accent text-[20px]">inventory_2</span>
                                <span class="font-label-caps text-[11px] tracking-widest text-muted/60" data-i18n="process_recent_activity_title">Actividad Reciente</span>
                            </div>
                            <span class="font-label-caps text-[10px] text-secondary cursor-pointer" onclick="showView('library')" data-i18n="process_view_more">Ver más</span>
                        </div>
                        <div class="flex flex-col gap-2 overflow-y-auto custom-scrollbar flex-1" id="process-file-grid">
                            <p class="font-data-sm text-[13px] text-muted/40" data-i18n="process_no_files_yet">Todavía no se procesó ningún archivo en esta sesión.</p>
                        </div>
                    </div>

                    <!-- Estadísticas en vivo -->
                    <div class="col-start-4 col-span-3 row-start-1 row-span-1 glass-card p-6 flex flex-col justify-center">
                        <span class="font-label-caps text-label-caps text-muted/60" data-i18n="process_progress_title">Progreso</span>
                        <div class="flex items-baseline gap-2 mt-1">
                            <span class="font-data-lg text-[28px] text-main" id="stat-progress-count">0/0</span>
                            <span class="font-data-sm text-secondary text-[12px] uppercase" id="stat-progress-pct">0%</span>
                        </div>
                    </div>
                    <div class="col-start-7 col-span-3 row-start-1 row-span-1 glass-card p-6 flex flex-col justify-center">
                        <span class="font-label-caps text-label-caps text-muted/60" data-i18n="process_connection_title">Conexión</span>
                        <div class="flex items-center justify-between mt-1">
                            <span class="font-data-lg text-[22px] text-accent" id="stat-ws-status" data-i18n="ws_connecting_short">Conectando</span>
                        </div>
                    </div>

                    <!-- Centro: registro de actividad en vivo -->
                    <div class="col-start-4 col-span-6 row-start-2 row-span-5 glass-card relative overflow-hidden scanline-effect">
                        <div class="absolute top-0 left-0 right-0 p-5 flex justify-between items-center z-10 bg-gradient-to-b from-black/40 to-transparent">
                            <div class="flex items-center gap-3">
                                <span class="material-symbols-outlined text-secondary text-[22px]">analytics</span>
                                <span class="font-label-caps text-[13px] tracking-[0.2em] text-main" data-i18n="process_activity_log_title">Registro de Actividad</span>
                            </div>
                            <span class="font-data-sm text-[12px] text-secondary/60" id="ws-status-label" data-i18n="ws_connecting_dots">Conectando...</span>
                        </div>
                        <div class="absolute inset-0 p-6 pt-16 font-data-sm text-[13px] leading-relaxed custom-scrollbar overflow-y-auto" id="log-container">
                            <p class="text-secondary/60">&gt; <span data-i18n="process_log_ready">Listo. Esperando instrucciones...</span></p>
                        </div>
                    </div>
                </div>

                <!-- Vista: Descarga -->
                <div id="view-spotify" class="view h-full flex-col gap-4 overflow-hidden">
                    <div class="glass-card p-5 flex flex-col gap-3">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-accent text-[20px]">link</span>
                            <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="spotify_link_title">Enlace de Spotify</span>
                        </div>
                        <div class="flex gap-2">
                            <input type="text" id="spotify_url" placeholder="https://open.spotify.com/track|album|playlist/..." class="cicada-input flex-1 rounded-lg px-3 py-3 text-[15px]"/>
                            <button type="button" id="resolveBtn" onclick="resolveSpotifyUrl()" class="px-5 rounded-lg bg-accent text-white font-label-caps text-[12px] hover:brightness-110 transition-all inline-flex items-center gap-1.5">
                                <span class="material-symbols-outlined text-[18px]">search</span> <span data-i18n="spotify_analyze_btn">Analizar</span>
                            </button>
                        </div>
                        <p id="spotify-resolve-status" class="font-data-sm text-[12px] text-[#f43f5e]"></p>
                    </div>

                    <div class="glass-card p-5 flex flex-col gap-2">
                        <label for="spotify_output_dir" class="font-label-caps text-[11px] text-accent/70" data-i18n="process_dest_label">Carpeta de Destino</label>
                        <div class="flex gap-2">
                            <input type="text" id="spotify_output_dir" placeholder="/Users/usuario/Musica/Organizada" class="cicada-input flex-1 rounded-lg px-3 py-3 text-[15px]"/>
                            <button type="button" onclick="pickFolder('spotify_output_dir')" class="px-4 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[12px] transition-colors" data-i18n="common_choose">Elegir</button>
                        </div>
                    </div>

                    <div class="glass-card p-5 flex flex-col flex-1 overflow-hidden">
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-accent text-[20px]">queue_music</span>
                                <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="spotify_tracks_found_title">Canciones Encontradas</span>
                                <span class="font-data-sm text-[12px] text-muted/40" id="spotify-track-count"></span>
                            </div>
                            <label class="flex items-center gap-2 font-label-caps text-[11px] text-muted/60 cursor-pointer">
                                <input type="checkbox" id="spotify-select-all" onchange="toggleSelectAllTracks(this.checked)" class="cicada-checkbox"/>
                                <span data-i18n="spotify_select_all">Seleccionar Todas</span>
                            </label>
                        </div>
                        <div class="flex flex-col gap-2 overflow-y-auto custom-scrollbar flex-1" id="spotify-track-list">
                            <p class="font-data-sm text-[13px] text-muted/40" data-i18n="spotify_hint_paste_link">Pega un link de Spotify (canción, álbum o playlist) y presiona Analizar para ver las canciones.</p>
                        </div>
                        <button type="button" id="spotifyDownloadBtn" onclick="startSpotifyDownload()" disabled class="mt-3 w-full py-3 bg-accent text-white rounded-xl font-label-caps text-[13px] tracking-widest hover:brightness-110 transition-all inline-flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed">
                            <span class="material-symbols-outlined text-[18px]">download</span> <span data-i18n="spotify_download_selected_btn">Descargar Seleccionadas</span> (<span id="spotify-selected-count">0</span>)
                        </button>
                    </div>
                </div>

                <!-- Vista: Playlists -->
                <div id="view-playlists" class="view grid-cols-12 grid-rows-6 gap-4 h-full overflow-hidden">
                    <!-- Izquierda: playlists del usuario -->
                    <div class="col-start-1 col-span-3 row-start-1 row-span-6 glass-card p-5 flex flex-col gap-3 overflow-hidden">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-accent text-[20px]">playlist_play</span>
                                <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="playlists_my_playlists_title">Mis Playlists</span>
                            </div>
                            <button type="button" onclick="loadSpotifyPlaylists()" data-i18n-title="process_view_more" title="Recargar" class="material-symbols-outlined text-[18px] text-muted/50 hover:text-accent transition-colors">refresh</button>
                        </div>
                        <div class="flex flex-col gap-2 overflow-y-auto custom-scrollbar flex-1" id="playlists-list">
                            <p class="font-data-sm text-[13px] text-muted/40" data-i18n="playlists_loading">Cargando tus playlists...</p>
                        </div>
                    </div>

                    <!-- Centro: canciones de la playlist seleccionada + configuración para replicar -->
                    <div class="col-start-4 col-span-3 row-start-1 row-span-6 glass-card p-5 flex flex-col gap-3 overflow-hidden">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-accent text-[20px]">queue_music</span>
                            <span class="font-label-caps text-[12px] tracking-widest text-muted/60" id="playlist-detail-title" data-i18n="playlists_choose_title">Elige una playlist</span>
                        </div>

                        <div class="flex-col gap-2" id="replicate-controls" style="display:none">
                            <label for="library_dir" class="font-label-caps text-[10px] text-accent/70" data-i18n="playlists_local_library_label">Tu Biblioteca Local</label>
                            <div class="flex gap-2">
                                <input type="text" id="library_dir" placeholder="/Users/usuario/Musica/Organizada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                                <button type="button" onclick="pickFolder('library_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                            </div>
                            <button type="button" id="replicateBtn" onclick="replicatePlaylist()" class="w-full py-2 bg-accent text-white rounded-lg font-label-caps text-[11px] hover:brightness-110 transition-all inline-flex items-center justify-center gap-1.5">
                                <span class="material-symbols-outlined text-[18px]">content_copy</span> <span data-i18n="playlists_replicate_btn">Replicar Playlist</span>
                            </button>
                        </div>

                        <div class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-2" id="playlist-track-list">
                            <p class="font-data-sm text-[13px] text-muted/40" data-i18n="playlists_choose_hint">Elige una playlist de la izquierda para ver sus canciones.</p>
                        </div>
                    </div>

                    <!-- Vista Previa de la Playlist -->
                    <div class="col-start-7 col-span-6 row-start-1 row-span-6 glass-card p-5 flex flex-col gap-2 overflow-hidden">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-accent text-[20px]">save</span>
                                <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="playlists_preview_title">Vista Previa de la Playlist</span>
                            </div>
                            <span class="font-data-sm text-[12px] text-muted/40" id="replicate-match-summary"></span>
                        </div>
                        <p class="font-data-sm text-[12px] text-muted/40" id="replicate-empty-hint" data-i18n="playlists_preview_hint">Elige una playlist y presiona Replicar Playlist para armar aquí la vista previa. Vas a poder arrastrar las canciones para reordenarlas y destildar las que no quieras incluir.</p>
                        <div class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-2" id="replicate-track-list"></div>
                        <div class="hidden gap-2 items-center mt-1" id="generate-m3u8-controls">
                            <input type="text" id="m3u8_name" placeholder="Nombre de la playlist" data-i18n-placeholder="playlists_m3u8_name_placeholder" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                            <button type="button" id="generateM3u8Btn" onclick="generatePlaylistM3u8()" class="px-4 py-2 bg-gray-600 text-white rounded-lg font-label-caps text-[12px] hover:brightness-110 transition-all inline-flex items-center gap-1.5">
                                <span class="material-symbols-outlined text-[18px]">save</span> <span data-i18n="playlists_generate_btn">Generar Playlist</span>
                            </button>
                            <button type="button" id="send-playlist-ipod-btn" onclick="sendPlaylistToIpod()" class="hidden px-4 py-2 bg-secondary text-white rounded-lg font-label-caps text-[12px] hover:brightness-110 transition-all items-center gap-1.5">
                                <span class="material-symbols-outlined text-[18px]">add_to_queue</span> <span data-i18n="playlists_send_to_ipod">Enviar a iPod</span>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Vista: Biblioteca -->
                <div id="view-library" class="view h-full flex-col gap-4">
                    <div class="glass-card p-5 flex flex-col gap-3">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-accent text-[20px]">library_music</span>
                            <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="library_my_library_title">Mi Biblioteca</span>
                        </div>
                        <div class="flex gap-2">
                            <input type="text" id="library_browse_dir" placeholder="/Users/usuario/Musica/Organizada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                            <button type="button" onclick="pickFolder('library_browse_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                            <button type="button" onclick="saveLibraryDirAndScan()" class="px-4 rounded-lg bg-accent text-white font-label-caps text-[11px] hover:brightness-110 transition-all" data-i18n="library_save_scan_btn">Guardar y Buscar Canciones</button>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-[18px] text-muted/40">search</span>
                            <input type="text" id="library_search" placeholder="Buscar por título, artista o álbum..." data-i18n-placeholder="library_search_placeholder" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[13px]" oninput="filterLibrary()"/>
                        </div>
                        <div class="flex items-center gap-2 flex-wrap">
                            <span class="font-label-caps text-[11px] text-muted/50" data-i18n="library_group_by_label">Agrupar por</span>
                            <button type="button" class="library-group-btn active px-3 py-1 rounded-full font-label-caps text-[11px] transition-colors" data-group="all" onclick="setLibraryGrouping('all')" data-i18n="library_group_all">Todas</button>
                            <button type="button" class="library-group-btn px-3 py-1 rounded-full font-label-caps text-[11px] transition-colors" data-group="artist" onclick="setLibraryGrouping('artist')" data-i18n="library_group_artist">Artista</button>
                            <button type="button" class="library-group-btn px-3 py-1 rounded-full font-label-caps text-[11px] transition-colors" data-group="album" onclick="setLibraryGrouping('album')" data-i18n="library_group_album">Álbum</button>
                            <button type="button" class="library-group-btn px-3 py-1 rounded-full font-label-caps text-[11px] transition-colors" data-group="playlist" onclick="setLibraryGrouping('playlist')" data-i18n="library_group_playlist">Playlist</button>

                            <span class="w-px h-4 bg-theme mx-1"></span>

                            <button type="button" id="library-sort-btn" class="library-group-btn active px-3 py-1 rounded-full font-label-caps text-[11px] transition-colors inline-flex items-center gap-1" onclick="toggleLibrarySort()" data-i18n-title="library_sort_tooltip" title="Orden alfabético">
                                <span class="material-symbols-outlined text-[14px]">sort_by_alpha</span>
                                <span data-i18n="library_sort_alpha">A-Z</span>
                            </button>

                            <div class="flex items-center rounded-full bg-btn p-0.5 gap-0.5">
                                <button type="button" id="library-view-list-btn" class="library-view-btn active p-1.5 rounded-full transition-colors inline-flex items-center" onclick="setLibraryViewMode('list')" data-i18n-title="library_view_list" title="Lista">
                                    <span class="material-symbols-outlined text-[16px]">view_list</span>
                                </button>
                                <button type="button" id="library-view-grid-btn" class="library-view-btn p-1.5 rounded-full transition-colors inline-flex items-center" onclick="setLibraryViewMode('grid')" data-i18n-title="library_view_grid" title="Grilla">
                                    <span class="material-symbols-outlined text-[16px]">grid_view</span>
                                </button>
                            </div>

                            <!-- Agregar a iPod (solo con iPod conectado) -->
                            <button type="button" id="library-add-ipod-btn" onclick="onLibraryIpodButton()" class="hidden items-center gap-1 px-3 py-1 rounded-full bg-secondary/15 text-secondary font-label-caps text-[11px] hover:bg-secondary/25 transition-colors">
                                <span class="material-symbols-outlined text-[15px]">add_to_queue</span>
                                <span id="library-add-ipod-label" data-i18n="library_add_to_ipod">Agregar a iPod</span>
                            </button>
                            <button type="button" id="library-select-cancel-btn" onclick="exitLibrarySelectMode()" class="hidden items-center px-3 py-1 rounded-full bg-btn text-muted font-label-caps text-[11px] hover:bg-btn-hover transition-colors" data-i18n="common_cancel">Cancelar</button>

                            <span class="ml-auto font-data-sm text-[12px] text-muted/40" id="library-track-count"></span>
                        </div>
                    </div>
                    <div class="glass-card p-5 flex-1 overflow-y-auto custom-scrollbar">
                        <div class="flex flex-col gap-1" id="library-browser">
                            <p class="font-data-sm text-[13px] text-muted/40" data-i18n="library_configure_hint">Configura la carpeta de tu biblioteca arriba para verla aquí.</p>
                        </div>
                    </div>
                </div>

                <!-- Vista: Sincronizar iPod -->
                <div id="view-ipod" class="view h-full flex-col gap-4 overflow-hidden">

                    <!-- Top section: Device Info & Storage Bar & Quick Actions -->
                    <div class="glass-card p-5 flex flex-col gap-4 flex-shrink-0">
                        <div class="flex justify-between items-center border-b border-theme pb-3">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-accent text-[20px]">devices</span>
                                <h2 class="font-label-caps tracking-widest text-[14px] text-main">Dispositivo iPod</h2>
                            </div>
                            <button onclick="scanIpod()" id="btn-scan-always" class="bg-accent text-white px-4 py-1.5 rounded-full font-label-caps text-[12px] hover:scale-105 transition-transform flex items-center gap-1.5 shadow-sm">
                                <span class="material-symbols-outlined text-[16px]">search</span>
                                <span data-i18n="ipod_btn_scan">Escanear</span>
                            </button>
                        </div>

                        <!-- Estado: Sin Dispositivo -->
                        <div id="ipod-no-device" class="text-center py-6 text-muted font-data-sm text-[13px] flex flex-col items-center gap-3">
                            <span class="material-symbols-outlined text-[44px] text-muted/40">device_unknown</span>
                            <p data-i18n="ipod_no_device">No se ha detectado ningún iPod. Asegúrate de que esté conectado y montado.</p>
                            <button onclick="scanIpod()" class="px-5 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[12px] text-accent transition-colors flex items-center gap-2 mt-1">
                                <span class="material-symbols-outlined text-[16px]">refresh</span>
                                <span>Buscar iPod conectado</span>
                            </button>
                        </div>
                        <div id="ipod-no-control" class="text-center py-6 text-[#f59e0b] font-data-sm text-[13px] hidden">
                            <span class="material-symbols-outlined text-[40px] text-[#f59e0b]/60 mb-2 block">warning</span>
                            <p data-i18n="ipod_no_control">Se detectó un volumen pero falta la carpeta iPod_Control.</p>
                            <button onclick="scanIpod()" class="px-5 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[12px] text-[#f59e0b] transition-colors inline-flex items-center gap-2 mt-2">
                                <span class="material-symbols-outlined text-[16px]">refresh</span>
                                <span>Reintentar escaneo</span>
                            </button>
                        </div>

                        <!-- Info del Dispositivo Conectado -->
                        <div id="ipod-info-container" class="flex flex-col gap-3 hidden">
                            <div class="flex items-center gap-5 justify-between">
                                <!-- Imagen del iPod -->
                                <div class="w-20 h-24 flex-shrink-0 flex items-center justify-center bg-black/10 dark:bg-white/5 rounded-xl p-1 border border-theme">
                                    <img id="ipod-device-img" src="/static/ipod_images/iPodGeneric.png" alt="iPod" class="max-h-22 max-w-18 object-contain drop-shadow-md"/>
                                </div>

                                <!-- Detalles del Dispositivo y Almacenamiento -->
                                <div class="flex-1 min-w-0 flex flex-col gap-2">
                                    <div class="flex items-center justify-between gap-2 flex-wrap">
                                        <div class="flex items-baseline gap-2">
                                            <h3 id="ipod-name" class="font-headline-sm text-[17px] text-main font-semibold truncate">iPod</h3>
                                            <span id="ipod-model" class="font-data-sm text-[12px] text-muted truncate">Modelo: --</span>
                                        </div>
                                        <div class="flex items-center gap-3 font-data-sm text-[11px] text-muted/70">
                                            <span id="ipod-capacity">Capacidad: --</span>
                                            <span class="text-muted/30">|</span>
                                            <span id="ipod-format">Firma: --</span>
                                        </div>
                                    </div>

                                    <!-- Barra de Almacenamiento -->
                                    <div class="flex flex-col gap-1 mt-0.5">
                                        <div class="ipod-storage-bar" id="ipod-storage-bar">
                                            <div id="storage-seg-audio" class="storage-seg storage-seg-audio" style="width: 0%" title="Audio"></div>
                                            <div id="storage-seg-video" class="storage-seg storage-seg-video" style="width: 0%" title="Video"></div>
                                            <div id="storage-seg-photos" class="storage-seg storage-seg-photos" style="width: 0%" title="Fotos"></div>
                                            <div id="storage-seg-podcasts" class="storage-seg storage-seg-podcasts" style="width: 0%" title="Podcasts/Audiolibros"></div>
                                            <div id="storage-seg-other" class="storage-seg storage-seg-other" style="width: 0%" title="Otro"></div>
                                        </div>
                                        <div class="flex items-center justify-between text-[11px] font-data-sm text-muted/70 flex-wrap gap-2">
                                            <div class="flex items-center gap-3">
                                                <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-[#10b981]"></span> <span id="storage-legend-audio" data-i18n="ipod_storage_audio">Audio</span></span>
                                                <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-[#8b5cf6]"></span> <span id="storage-legend-video" data-i18n="ipod_storage_video">Video</span></span>
                                                <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-[#f59e0b]"></span> <span id="storage-legend-photos" data-i18n="ipod_storage_photos">Fotos</span></span>
                                                <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-[#64748b]"></span> <span id="storage-legend-other" data-i18n="ipod_storage_other">Otro</span></span>
                                            </div>
                                            <div id="ipod-storage-text" class="font-semibold text-main">-- usados · -- libres</div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Botonera de Acciones Rápidas -->
                                <div class="flex flex-col gap-1.5 flex-shrink-0 pl-2 border-l border-theme">
                                    <div class="flex gap-1.5">
                                        <button onclick="scanIpod()" id="btn-scan-ipod" class="p-2 rounded-lg bg-btn hover:bg-btn-hover text-muted hover:text-main font-label-caps text-[11px] transition-colors inline-flex items-center gap-1" data-i18n-title="ipod_btn_scan" title="Escanear">
                                            <span class="material-symbols-outlined text-[17px]">search</span>
                                        </button>
                                        <button onclick="ejectIpod()" id="btn-eject-ipod" class="p-2 rounded-lg bg-btn hover:bg-red-500/20 text-muted hover:text-red-400 font-label-caps text-[11px] transition-colors inline-flex items-center gap-1" data-i18n-title="ipod_btn_eject" title="Eyectar iPod">
                                            <span class="material-symbols-outlined text-[17px]">eject</span>
                                        </button>
                                    </div>
                                    <button onclick="syncIpod()" id="btn-sync-ipod" data-i18n-title="ipod_btn_sync_title" title="Reescribe la base de datos del iPod (preservando sus playlists). No agrega música nueva." class="bg-accent text-white px-3 py-1.5 rounded-lg font-label-caps text-[11px] hover:scale-102 transition-transform flex items-center justify-center gap-1 shadow-sm opacity-50 cursor-not-allowed" disabled>
                                        <span class="material-symbols-outlined text-[15px]">build</span>
                                        <span data-i18n="ipod_btn_sync">Reparar</span>
                                    </button>
                                    <button onclick="backupIpod()" id="btn-backup-ipod" class="border border-secondary text-secondary px-3 py-1.5 rounded-lg font-label-caps text-[11px] hover:bg-secondary hover:text-white transition-colors flex items-center justify-center gap-1 opacity-50 cursor-not-allowed" disabled>
                                        <span class="material-symbols-outlined text-[15px]">save</span>
                                        <span data-i18n="ipod_btn_backup">Backup</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Main Section: Sub-Sidebar Categories + Content Browser -->
                    <div id="ipod-main-browser" class="glass-card p-4 flex gap-4 flex-1 overflow-hidden hidden">
                        <!-- Sub-Sidebar: Categorías -->
                        <div class="w-44 flex-shrink-0 flex flex-col gap-1 border-r border-theme pr-3">
                            <span class="font-label-caps text-[10px] text-muted/50 px-3 py-1 uppercase tracking-wider">Biblioteca</span>
                            <button type="button" class="ipod-cat-btn active" data-cat="songs" onclick="switchIpodCategory('songs')">
                                <span class="material-symbols-outlined text-[18px]">music_note</span>
                                <span class="flex-1 truncate" data-i18n="ipod_cat_songs">Canciones</span>
                                <span id="ipod-count-songs" class="font-data-sm text-[11px] text-muted/60">0</span>
                            </button>
                            <button type="button" class="ipod-cat-btn" data-cat="playlists" onclick="switchIpodCategory('playlists')">
                                <span class="material-symbols-outlined text-[18px]">playlist_play</span>
                                <span class="flex-1 truncate" data-i18n="ipod_cat_playlists">Playlist</span>
                                <span id="ipod-count-playlists" class="font-data-sm text-[11px] text-muted/60">0</span>
                            </button>
                            <button type="button" class="ipod-cat-btn" data-cat="videos" onclick="switchIpodCategory('videos')">
                                <span class="material-symbols-outlined text-[18px]">movie</span>
                                <span class="flex-1 truncate" data-i18n="ipod_cat_videos">Videos</span>
                                <span id="ipod-count-videos" class="font-data-sm text-[11px] text-muted/60">0</span>
                            </button>
                            <button type="button" class="ipod-cat-btn" data-cat="podcasts" onclick="switchIpodCategory('podcasts')">
                                <span class="material-symbols-outlined text-[18px]">podcasts</span>
                                <span class="flex-1 truncate" data-i18n="ipod_cat_podcasts">Podcast</span>
                                <span id="ipod-count-podcasts" class="font-data-sm text-[11px] text-muted/60">0</span>
                            </button>
                            <button type="button" class="ipod-cat-btn" data-cat="audiobooks" onclick="switchIpodCategory('audiobooks')">
                                <span class="material-symbols-outlined text-[18px]">menu_book</span>
                                <span class="flex-1 truncate" data-i18n="ipod_cat_audiobooks">Audiolibros</span>
                                <span id="ipod-count-audiobooks" class="font-data-sm text-[11px] text-muted/60">0</span>
                            </button>
                            <!-- Solo visible si el dispositivo ya tiene fotos (photos_bytes > 0). Solo lectura: sin escritura, ver docs/VENDORED.md. -->
                            <button type="button" id="ipod-cat-photos-btn" class="ipod-cat-btn hidden" data-cat="photos" onclick="switchIpodCategory('photos')">
                                <span class="material-symbols-outlined text-[18px]">photo_library</span>
                                <span class="flex-1 truncate" data-i18n="ipod_cat_photos">Fotos</span>
                            </button>
                            <!-- Separador + carrito de sincronización (pendientes de inyectar) -->
                            <div class="border-t border-theme my-2"></div>
                            <button type="button" class="ipod-cat-btn" data-cat="sync" onclick="switchIpodCategory('sync')">
                                <span class="material-symbols-outlined text-[18px]">sync</span>
                                <span class="flex-1 truncate" data-i18n="ipod_cat_sync">Sincronizar con Cicada</span>
                                <span id="ipod-count-sync" class="font-data-sm text-[11px] text-secondary font-bold">0</span>
                            </button>
                            <button type="button" class="ipod-cat-btn" data-cat="conflicts" onclick="switchIpodCategory('conflicts')">
                                <span class="material-symbols-outlined text-[18px]">warning</span>
                                <span class="flex-1 truncate" data-i18n="ipod_cat_conflicts">Conflictos</span>
                                <span id="ipod-count-conflicts" class="hidden font-data-sm text-[11px] text-white bg-[#f43f5e] rounded-full px-1.5 font-bold">0</span>
                            </button>
                        </div>

                        <!-- Contenedor Principal de la Categoría -->
                        <div class="flex-1 flex flex-col gap-3 overflow-hidden min-w-0">
                            <!-- Toolbar de Búsqueda, Filtros y Switch de Vista -->
                            <div class="flex items-center justify-between gap-3 pb-2 border-b border-theme flex-shrink-0">
                                <!-- Búsqueda -->
                                <div class="flex items-center gap-2 flex-1 max-w-md">
                                    <div class="relative w-full">
                                        <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-muted/40 pointer-events-none">search</span>
                                        <input type="text" id="ipod-search-input" placeholder="Buscar canciones, artistas, álbumes..." data-i18n-placeholder="ipod_search_placeholder" class="cicada-input w-full pl-9 pr-3 py-1.5 text-[13px] rounded-lg" oninput="handleIpodSearch(this.value)"/>
                                    </div>
                                </div>

                                <!-- Filtros, Vistas y Agregar -->
                                <div class="flex items-center gap-2">
                                    <!-- Botón de Filtros -->
                                    <button type="button" id="ipod-filter-btn" onclick="toggleIpodFilters()" class="px-3 py-1.5 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors inline-flex items-center gap-1.5 text-muted hover:text-main">
                                        <span class="material-symbols-outlined text-[16px]">tune</span>
                                        <span data-i18n="ipod_filter_label">Filtros</span>
                                        <span id="ipod-active-filters-badge" class="hidden w-2 h-2 rounded-full bg-accent"></span>
                                    </button>

                                    <!-- Switch de Vista: Lista vs Cuadros -->
                                    <div class="flex items-center rounded-full bg-btn p-0.5 gap-0.5" id="ipod-viewmode-switch">
                                        <button type="button" id="ipod-viewmode-list-btn" class="library-view-btn active p-1.5 rounded-full transition-colors inline-flex items-center" onclick="setIpodViewMode('list')" data-i18n-title="ipod_view_list" title="Lista">
                                            <span class="material-symbols-outlined text-[16px]">view_list</span>
                                        </button>
                                        <button type="button" id="ipod-viewmode-grid-btn" class="library-view-btn p-1.5 rounded-full transition-colors inline-flex items-center" onclick="setIpodViewMode('grid')" data-i18n-title="ipod_view_grid" title="Cuadros">
                                            <span class="material-symbols-outlined text-[16px]">grid_view</span>
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <!-- Panel Desplegable de Filtros -->
                            <div id="ipod-filters-panel" class="hidden flex-wrap items-center gap-3 p-3 bg-card/60 rounded-xl border border-theme flex-shrink-0">
                                <div class="flex items-center gap-1.5">
                                    <label for="ipod-filter-genre" class="font-label-caps text-[10px] text-muted/60" data-i18n="ipod_filter_genre">Género</label>
                                    <select id="ipod-filter-genre" onchange="applyIpodFilter('genre', this.value)" class="cicada-input px-2 py-1 text-[12px] rounded-lg">
                                        <option value="" data-i18n="ipod_filter_all">Todos</option>
                                    </select>
                                </div>
                                <div class="flex items-center gap-1.5">
                                    <label for="ipod-filter-year" class="font-label-caps text-[10px] text-muted/60" data-i18n="ipod_filter_year">Año</label>
                                    <select id="ipod-filter-year" onchange="applyIpodFilter('year', this.value)" class="cicada-input px-2 py-1 text-[12px] rounded-lg">
                                        <option value="" data-i18n="ipod_filter_all">Todos</option>
                                    </select>
                                </div>
                                <div class="flex items-center gap-1.5">
                                    <label for="ipod-filter-artist" class="font-label-caps text-[10px] text-muted/60" data-i18n="ipod_filter_artist">Artista</label>
                                    <select id="ipod-filter-artist" onchange="applyIpodFilter('artist', this.value)" class="cicada-input px-2 py-1 text-[12px] rounded-lg">
                                        <option value="" data-i18n="ipod_filter_all">Todos</option>
                                    </select>
                                </div>
                                <div class="flex items-center gap-1.5">
                                    <label for="ipod-filter-album" class="font-label-caps text-[10px] text-muted/60" data-i18n="ipod_filter_album">Álbum</label>
                                    <select id="ipod-filter-album" onchange="applyIpodFilter('album', this.value)" class="cicada-input px-2 py-1 text-[12px] rounded-lg">
                                        <option value="" data-i18n="ipod_filter_all">Todos</option>
                                    </select>
                                </div>
                                <button type="button" onclick="resetIpodFilters()" class="text-secondary font-label-caps text-[10px] hover:underline ml-auto">Limpiar Filtros</button>
                            </div>

                            <!-- VISTA 1: CANCIONES (Lista o Cuadros) -->
                            <div id="ipod-view-songs" class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-2">
                                <!-- Modo Lista -->
                                <div id="ipod-songs-list" class="flex flex-col gap-1"></div>
                                <!-- Modo Cuadros / Grid -->
                                <div id="ipod-songs-grid" class="hidden grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 p-1"></div>
                            </div>

                            <!-- VISTA 2: PLAYLISTS (2 Columnas: Playlists + Canciones) -->
                            <div id="ipod-view-playlists" class="hidden flex gap-4 flex-1 overflow-hidden">
                                <!-- Columna Izquierda: Lista de Playlists + Acciones al pie -->
                                <div class="w-[240px] flex-shrink-0 flex flex-col gap-2 border-r border-theme pr-3 overflow-hidden">
                                    <h4 class="font-label-caps text-[11px] text-secondary uppercase tracking-wider" data-i18n="ipod_playlists_label">Playlists</h4>
                                    <div id="ipod-playlists-list" class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-1"></div>
                                    <!-- Botones de Acción al pie de la lista -->
                                    <div class="flex flex-col gap-1.5 pt-2 border-t border-theme mt-auto">
                                        <button type="button" onclick="openCreatePlaylistModal()" class="w-full py-2 bg-accent text-white rounded-lg font-label-caps text-[11px] hover:brightness-110 transition-all flex items-center justify-center gap-1">
                                            <span class="material-symbols-outlined text-[16px]">add</span>
                                            <span data-i18n="ipod_create_playlist">Crear Playlist</span>
                                        </button>
                                        <button type="button" onclick="openImportPlaylistModal()" class="w-full py-1.5 bg-btn hover:bg-btn-hover text-muted hover:text-main rounded-lg font-label-caps text-[11px] transition-colors flex items-center justify-center gap-1">
                                            <span class="material-symbols-outlined text-[16px]">download</span>
                                            <span data-i18n="ipod_import_playlist">Importar Playlist</span>
                                        </button>
                                    </div>
                                </div>

                                <!-- Columna Derecha: Canciones de la Playlist Seleccionada -->
                                <div class="flex-1 flex flex-col gap-2 overflow-hidden min-w-0">
                                    <div class="flex items-center justify-between pb-1 gap-2">
                                        <h4 id="ipod-playlist-title" class="font-label-caps text-[13px] text-main font-semibold truncate">Todas las Canciones</h4>
                                        <div class="flex items-center gap-2 flex-shrink-0">
                                            <button type="button" id="ipod-playlist-add-btn" onclick="openIpodPlaylistAddPicker()" class="hidden items-center gap-1 px-3 py-1 rounded-full bg-btn hover:bg-btn-hover text-main font-label-caps text-[11px] transition-all">
                                                <span class="material-symbols-outlined text-[14px]">add</span>
                                                <span data-i18n="ipod_playlist_add_songs">Agregar</span>
                                            </button>
                                            <button type="button" id="ipod-playlist-save-order-btn" onclick="saveIpodPlaylistOrder()" class="hidden items-center gap-1 px-3 py-1 rounded-full bg-secondary text-white font-label-caps text-[11px] hover:brightness-110 transition-all">
                                                <span class="material-symbols-outlined text-[14px]">save</span>
                                                <span data-i18n="ipod_playlist_save_order">Guardar cambios</span>
                                            </button>
                                            <span id="ipod-playlist-count" class="font-data-sm text-[12px] text-muted/60">0 canciones</span>
                                        </div>
                                    </div>
                                    <div id="ipod-playlist-tracks-list" class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-1"></div>
                                </div>
                            </div>

                            <!-- VISTA 4: VIDEOS (Grilla de Cuadros con Hover Delete) -->
                            <div id="ipod-view-videos" class="hidden flex-1 overflow-y-auto custom-scrollbar">
                                <div id="ipod-videos-grid" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 p-1"></div>
                                <div id="ipod-videos-empty" class="hidden text-center py-12 text-muted font-data-sm text-[13px] flex flex-col items-center gap-2">
                                    <span class="material-symbols-outlined text-[40px] text-muted/40">movie</span>
                                    <p data-i18n="ipod_no_items">No hay videos en el iPod.</p>
                                    <button type="button" onclick="handleIpodAddAction()" class="mt-2 px-4 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] text-accent transition-colors">Agregar Videos</button>
                                </div>
                            </div>

                            <!-- VISTA 5: PODCASTS (2 Columnas: Podcasts + Episodios) -->
                            <div id="ipod-view-podcasts" class="hidden flex-col gap-4 flex-1 overflow-y-auto custom-scrollbar">
                                <div class="flex gap-4" style="min-height: 260px;">
                                    <div class="w-[240px] flex-shrink-0 flex flex-col gap-2 border-r border-theme pr-3 overflow-hidden">
                                        <h4 class="font-label-caps text-[11px] text-secondary uppercase tracking-wider">Podcasts</h4>
                                        <div id="ipod-podcasts-list" class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-1"></div>
                                        <div class="flex flex-col gap-1.5 pt-2 border-t border-theme mt-auto">
                                            <button type="button" onclick="handleIpodAddAction()" class="w-full py-2 bg-accent text-white rounded-lg font-label-caps text-[11px] hover:brightness-110 transition-all flex items-center justify-center gap-1">
                                                <span class="material-symbols-outlined text-[16px]">add</span>
                                                <span>Suscribir Podcast</span>
                                            </button>
                                        </div>
                                    </div>
                                    <div class="flex-1 flex flex-col gap-2 overflow-hidden min-w-0">
                                        <div class="flex items-center justify-between pb-1">
                                            <h4 id="ipod-podcast-title" class="font-label-caps text-[13px] text-main font-semibold truncate">Episodios</h4>
                                            <span id="ipod-podcast-count" class="font-data-sm text-[12px] text-muted/60">0 episodios</span>
                                        </div>
                                        <div id="ipod-podcast-episodes-list" class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-1"></div>
                                    </div>
                                </div>

                                <!-- Agregar más: suscribir/descargar/agregar al carrito (movido de Biblioteca) -->
                                <div class="glass-card p-5 flex flex-col gap-3 border-t border-theme pt-4">
                                    <div class="flex items-center gap-2">
                                        <span class="material-symbols-outlined text-accent text-[20px]">podcasts</span>
                                        <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="podcasts_title">Podcasts</span>
                                    </div>
                                    <div class="flex gap-2">
                                        <input type="text" id="podcast_feed_url" placeholder="https://ejemplo.com/feed.xml" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                                        <button type="button" onclick="subscribePodcastFeed()" class="px-4 rounded-lg bg-accent text-white font-label-caps text-[11px] hover:brightness-110 transition-all" data-i18n="podcasts_subscribe_btn">Suscribirse</button>
                                    </div>
                                    <div class="grid grid-cols-2 gap-3">
                                        <div class="flex flex-col gap-1 max-h-48 overflow-y-auto custom-scrollbar" id="podcast-feeds-list">
                                            <p class="font-data-sm text-[13px] text-muted/40 p-2" data-i18n="podcasts_no_subscriptions">Todavía no hay podcasts suscriptos.</p>
                                        </div>
                                        <div class="flex flex-col gap-2">
                                            <div class="flex items-center gap-2 flex-wrap">
                                                <span class="font-data-sm text-[13px] text-main truncate" id="podcast-episodes-title"></span>
                                                <button type="button" id="podcast-add-ipod-btn" onclick="onPodcastIpodButton()" class="hidden ml-auto items-center gap-1 px-3 py-1 rounded-full bg-secondary/15 text-secondary font-label-caps text-[11px] hover:bg-secondary/25 transition-colors">
                                                    <span class="material-symbols-outlined text-[15px]">add_to_queue</span>
                                                    <span id="podcast-add-ipod-label" data-i18n="library_add_to_ipod">Agregar a iPod</span>
                                                </button>
                                                <button type="button" id="podcast-select-cancel-btn" onclick="exitPodcastSelectMode()" class="hidden items-center px-3 py-1 rounded-full bg-btn text-muted font-label-caps text-[11px] hover:bg-btn-hover transition-colors" data-i18n="common_cancel">Cancelar</button>
                                            </div>
                                            <div class="flex flex-col gap-1 max-h-48 overflow-y-auto custom-scrollbar" id="podcast-episodes-list">
                                                <p class="font-data-sm text-[13px] text-muted/40 p-2" data-i18n="podcasts_pick_feed_hint">Suscribite a un feed para ver sus episodios.</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- VISTA 6: AUDIOLIBROS (2 Columnas: Libros + Capítulos) -->
                            <div id="ipod-view-audiobooks" class="hidden flex-col gap-4 flex-1 overflow-y-auto custom-scrollbar">
                                <div class="flex gap-4" style="min-height: 260px;">
                                    <div class="w-[240px] flex-shrink-0 flex flex-col gap-2 border-r border-theme pr-3 overflow-hidden">
                                        <h4 class="font-label-caps text-[11px] text-secondary uppercase tracking-wider">Audiolibros</h4>
                                        <div id="ipod-audiobooks-list" class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-1"></div>
                                        <div class="flex flex-col gap-1.5 pt-2 border-t border-theme mt-auto">
                                            <button type="button" onclick="handleIpodAddAction()" class="w-full py-2 bg-accent text-white rounded-lg font-label-caps text-[11px] hover:brightness-110 transition-all flex items-center justify-center gap-1">
                                                <span class="material-symbols-outlined text-[16px]">add</span>
                                                <span>Agregar Audiolibro</span>
                                            </button>
                                        </div>
                                    </div>
                                    <div class="flex-1 flex flex-col gap-2 overflow-hidden min-w-0">
                                        <div class="flex items-center justify-between pb-1">
                                            <h4 id="ipod-audiobook-title" class="font-label-caps text-[13px] text-main font-semibold truncate">Capítulos</h4>
                                            <span id="ipod-audiobook-count" class="font-data-sm text-[12px] text-muted/60">0 pistas</span>
                                        </div>
                                        <div id="ipod-audiobook-chapters-list" class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-1"></div>
                                    </div>
                                </div>

                                <!-- Agregar más: explorar carpeta/agregar al carrito (movido de Biblioteca) -->
                                <div class="glass-card p-5 flex flex-col gap-3 border-t border-theme pt-4">
                                    <div class="flex items-center gap-2">
                                        <span class="material-symbols-outlined text-accent text-[20px]">menu_book</span>
                                        <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="audiobooks_title">Audiolibros</span>
                                    </div>
                                    <div class="flex gap-2">
                                        <input type="text" id="audiobook_browse_dir" placeholder="/Users/usuario/Audiolibros" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                                        <button type="button" onclick="pickFolder('audiobook_browse_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                                        <button type="button" onclick="scanAudiobookFolder()" class="px-4 rounded-lg bg-accent text-white font-label-caps text-[11px] hover:brightness-110 transition-all" data-i18n="audiobooks_scan_btn">Buscar Audiolibros</button>
                                    </div>
                                    <div class="flex items-center gap-2 flex-wrap">
                                        <button type="button" id="audiobook-add-ipod-btn" onclick="onAudiobookIpodButton()" class="hidden items-center gap-1 px-3 py-1 rounded-full bg-secondary/15 text-secondary font-label-caps text-[11px] hover:bg-secondary/25 transition-colors">
                                            <span class="material-symbols-outlined text-[15px]">add_to_queue</span>
                                            <span id="audiobook-add-ipod-label" data-i18n="library_add_to_ipod">Agregar a iPod</span>
                                        </button>
                                        <button type="button" id="audiobook-select-cancel-btn" onclick="exitAudiobookSelectMode()" class="hidden items-center px-3 py-1 rounded-full bg-btn text-muted font-label-caps text-[11px] hover:bg-btn-hover transition-colors" data-i18n="common_cancel">Cancelar</button>
                                        <span class="ml-auto font-data-sm text-[12px] text-muted/40" id="audiobook-count"></span>
                                    </div>
                                    <div class="flex flex-col gap-1" id="audiobook-browser">
                                        <p class="font-data-sm text-[13px] text-muted/40" data-i18n="audiobooks_hint">Elegí una carpeta para buscar archivos .m4b, .m4a, .mp3 o .aac.</p>
                                    </div>
                                </div>
                            </div>

                            <!-- VISTA: FOTOS (solo indicador, sin listado — ver docs/VENDORED.md sobre por qué no hay escritura ni lectura detallada) -->
                            <div id="ipod-view-photos" class="hidden flex-1 flex flex-col items-center justify-center gap-3 text-center px-8">
                                <span class="material-symbols-outlined text-[40px] text-muted/40">photo_library</span>
                                <p class="font-data-sm text-[14px] text-main" id="ipod-photos-summary" data-i18n="ipod_photos_summary">El iPod tiene fotos.</p>
                                <p class="font-data-sm text-[12px] text-muted/50 max-w-sm" data-i18n="ipod_photos_readonly_hint">Cicada no gestiona fotos del iPod — esto es solo informativo.</p>
                            </div>

                            <!-- VISTA 7: SINCRONIZAR CON CICADA (elementos pendientes de inyectar) -->
                            <div id="ipod-view-sync" class="hidden flex-1 flex flex-col gap-3 overflow-hidden">
                                <div class="flex items-center justify-between pb-2 border-b border-theme">
                                    <div class="flex flex-col min-w-0">
                                        <h4 class="font-label-caps text-[13px] text-main font-semibold" data-i18n="ipod_sync_pending_title">Pendientes de sincronizar</h4>
                                        <span class="font-data-sm text-[12px] text-muted/60" data-i18n="ipod_sync_pending_hint">Elementos seleccionados que aún no se han enviado al iPod.</span>
                                    </div>
                                    <button type="button" id="ipod-sync-now-btn" onclick="syncBasketToIpod()" class="flex-shrink-0 px-5 py-2 bg-secondary text-white rounded-full font-label-caps text-[12px] hover:brightness-110 transition-all flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed" disabled>
                                        <span class="material-symbols-outlined text-[16px]">sync</span>
                                        <span id="ipod-sync-now-label" data-i18n="ipod_sync_now">Sincronizar</span>
                                    </button>
                                </div>
                                <div id="ipod-sync-basket-list" class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-1"></div>
                            </div>

                            <!-- VISTA 8: CONFLICTOS DE RATING -->
                            <div id="ipod-view-conflicts" class="hidden flex-1 flex flex-col gap-3 overflow-hidden">
                                <div class="flex items-center justify-between pb-2 border-b border-theme">
                                    <div class="flex flex-col min-w-0">
                                        <h4 class="font-label-caps text-[13px] text-main font-semibold" data-i18n="ipod_conflicts_title">Conflictos de calificación</h4>
                                        <span class="font-data-sm text-[12px] text-muted/60" data-i18n="ipod_conflicts_hint">Cambiaron en Cicada y en el iPod desde la última sincronización — elige cuál vale.</span>
                                    </div>
                                    <div id="ipod-conflicts-batch-actions" class="hidden flex-shrink-0 flex items-center gap-2">
                                        <button type="button" onclick="resolveAllIpodConflicts('local')" class="px-3 py-1.5 rounded-full bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="ipod_conflicts_use_local_all">Usar Local en todos</button>
                                        <button type="button" onclick="resolveAllIpodConflicts('device')" class="px-3 py-1.5 rounded-full bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="ipod_conflicts_use_device_all">Usar Dispositivo en todos</button>
                                    </div>
                                </div>
                                <div id="ipod-conflicts-list" class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-2"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Modal Crear Playlist -->
                <div id="ipod-create-playlist-modal" class="hidden fixed inset-0 z-[100] items-center justify-center bg-black/60 backdrop-blur-sm">
                    <div class="w-full max-w-md mx-4 p-6 flex flex-col gap-4 rounded-2xl border border-theme bg-card shadow-2xl">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-accent text-[22px]">playlist_add</span>
                                <h3 class="font-label-caps text-[14px] tracking-widest text-main" data-i18n="ipod_create_playlist">Crear Nueva Playlist</h3>
                            </div>
                            <button type="button" onclick="closeCreatePlaylistModal()" class="material-symbols-outlined text-muted/60 hover:text-main transition-colors">close</button>
                        </div>
                        <div class="flex flex-col gap-2">
                            <label for="new_playlist_name" class="font-label-caps text-[11px] text-accent/70">Nombre de la Playlist</label>
                            <input type="text" id="new_playlist_name" placeholder="Mi Nueva Playlist" class="cicada-input rounded-lg px-3 py-2.5 text-[14px]"/>
                        </div>
                        <div class="flex justify-end gap-3 mt-2">
                            <button type="button" onclick="closeCreatePlaylistModal()" class="px-4 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_cancel">Cancelar</button>
                            <button type="button" onclick="submitCreatePlaylist()" class="px-5 py-2 rounded-lg bg-accent text-white font-label-caps text-[11px] hover:brightness-110 transition-all" data-i18n="common_save">Crear</button>
                        </div>
                    </div>
                </div>

                <!-- Modal Importar Playlist -->
                <div id="ipod-import-playlist-modal" class="hidden fixed inset-0 z-[100] items-center justify-center bg-black/60 backdrop-blur-sm">
                    <div class="w-full max-w-md mx-4 p-6 flex flex-col gap-4 rounded-2xl border border-theme bg-card shadow-2xl">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-accent text-[22px]">download</span>
                                <h3 class="font-label-caps text-[14px] tracking-widest text-main" data-i18n="ipod_import_playlist">Importar Playlist a iPod</h3>
                            </div>
                            <button type="button" onclick="closeImportPlaylistModal()" class="material-symbols-outlined text-muted/60 hover:text-main transition-colors">close</button>
                        </div>
                        <p class="font-data-sm text-[12px] text-muted/70">Selecciona una playlist de tu biblioteca local o Spotify para sincronizarla en el iPod.</p>
                        <div id="ipod-import-playlist-options" class="flex flex-col gap-1.5 max-h-48 overflow-y-auto custom-scrollbar">
                            <p class="font-data-sm text-[12px] text-muted/40">Cargando playlists disponibles...</p>
                        </div>
                        <div class="flex justify-end gap-3 mt-2">
                            <button type="button" onclick="closeImportPlaylistModal()" class="px-4 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_cancel">Cancelar</button>
                        </div>
                    </div>
                </div>

                <!-- Modal Agregar canciones de la biblioteca a una playlist del iPod -->
                <div id="ipod-playlist-add-modal" class="hidden fixed inset-0 z-[100] items-center justify-center bg-black/60 backdrop-blur-sm">
                    <div class="w-full max-w-lg mx-4 p-6 flex flex-col gap-4 rounded-2xl border border-theme bg-card shadow-2xl max-h-[80vh]">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-accent text-[22px]">library_add</span>
                                <h3 class="font-label-caps text-[14px] tracking-widest text-main" data-i18n="ipod_playlist_add_songs">Agregar canciones</h3>
                            </div>
                            <button type="button" onclick="closeIpodPlaylistAddModal()" class="material-symbols-outlined text-muted/60 hover:text-main transition-colors">close</button>
                        </div>
                        <input type="text" id="ipod-playlist-add-search" oninput="renderIpodAddPickerList(this.value)" data-i18n-placeholder="ipod_playlist_add_search" placeholder="Buscar en la biblioteca..." class="cicada-input rounded-lg px-3 py-2.5 text-[14px]"/>
                        <div id="ipod-playlist-add-list" class="flex flex-col gap-1 overflow-y-auto custom-scrollbar min-h-[10rem]"></div>
                        <div class="flex justify-end gap-3 mt-1">
                            <button type="button" onclick="closeIpodPlaylistAddModal()" class="px-4 py-2 rounded-lg bg-accent text-white font-label-caps text-[11px] hover:brightness-110 transition-all" data-i18n="common_done">Listo</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Módulo derecho: Progreso (Metadatos/Descarga) o Reproductor (Biblioteca). Oculto en Playlist. -->
            <div id="process-module" class="w-[320px] flex-shrink-0 h-full bg-sidebar rounded-[24px] p-6 flex flex-col gap-6 text-sidebar">
                <div id="progress-panel" class="flex flex-col gap-6 h-full">
                    <div class="flex justify-between items-center">
                        <span id="status-pill" class="bg-accent-light text-accent px-3 py-1 rounded-full font-label-caps text-[12px]">En espera</span>
                        <span class="font-data-sm text-[12px] text-sidebar/40" data-i18n="player_cicada_label">Cicada</span>
                    </div>
                    <div class="flex-1 flex flex-col justify-center items-center text-center">
                        <div class="w-full aspect-square rounded-[20px] overflow-hidden shadow-2xl mb-8 relative border-4 border-transparent bg-black/5 dark:bg-black/10 flex items-center justify-center">
                            <div class="flex flex-col items-center gap-2 text-sidebar/30" id="coverPlaceholder">
                                <span class="material-symbols-outlined text-[40px]">music_note</span>
                                <span class="font-label-caps text-[11px]" data-i18n="player_no_cover">Sin carátula</span>
                            </div>
                            <img alt="Album Art" class="w-full h-full object-cover absolute inset-0 hidden" id="currentCover" src=""/>
                        </div>
                        <h2 class="font-headline-sm text-[20px] leading-tight mb-1 truncate w-full" id="track-title">En espera...</h2>
                        <p class="font-body-sm text-sidebar/60 mb-8 truncate w-full" id="track-subtitle">Configura una fuente para comenzar</p>
                        <div class="w-full space-y-4">
                            <div class="w-full h-[54px] bg-black/5 dark:bg-black/10 rounded-xl p-3 flex items-center justify-between">
                                <span class="font-label-caps text-[11px] text-sidebar/40 uppercase" data-i18n="player_remaining_time_label">Tiempo Restante</span>
                                <span class="font-data-lg text-accent text-[16px]" id="eta_display">&#45;&#45;</span>
                            </div>
                            <div class="relative w-full h-1.5 bg-black/10 dark:bg-black/20 rounded-full overflow-hidden">
                                <div class="absolute inset-y-0 left-0 bg-accent w-0 transition-all duration-500" id="bar"></div>
                            </div>
                            <div class="flex justify-between font-data-sm text-[12px] text-sidebar/40">
                                <span data-i18n="player_progress_label">Avance</span>
                                <span id="progress_label">0%</span>
                            </div>
                        </div>
                    </div>
                    <button id="cancelBtnProcess" type="button" onclick="cancelProcess()" class="cancel-action hidden w-full py-4 bg-card text-main rounded-xl font-label-caps tracking-widest hover:bg-black transition-colors items-center justify-center gap-2">
                        <span class="material-symbols-outlined text-sm">stop_circle</span> <span data-i18n="player_cancel_process_btn">Cancelar Proceso</span>
                    </button>
                </div>

                <div id="player-panel" class="hidden flex flex-col gap-6 h-full">
                    <div class="flex justify-between items-center">
                        <div class="flex items-center gap-2">
                            <button type="button" id="player-collapse-btn" onclick="togglePlayerPanel(false)" class="p-1 rounded-lg hover:bg-black/10 dark:hover:bg-white/10 text-sidebar/50 hover:text-sidebar transition-all duration-200 flex items-center justify-center cursor-pointer" data-i18n-title="player_hide" title="Ocultar reproductor">
                                <span class="material-symbols-outlined text-[18px]">chevron_right</span>
                            </button>
                            <span class="font-label-caps text-[12px] text-sidebar/40" data-i18n="player_title">Reproductor</span>
                        </div>
                        <span class="font-data-sm text-[12px] text-sidebar/40" data-i18n="player_cicada_label">Cicada</span>
                    </div>
                    <div class="flex-1 flex flex-col justify-center items-center text-center">
                        <div class="w-full aspect-square rounded-[20px] overflow-hidden shadow-2xl mb-8 relative border-4 border-transparent bg-black/5 dark:bg-black/10 flex items-center justify-center">
                            <div class="flex flex-col items-center gap-2 text-sidebar/30" id="playerCoverPlaceholder">
                                <span class="material-symbols-outlined text-[40px]">music_note</span>
                                <span class="font-label-caps text-[11px]" data-i18n="player_no_cover">Sin carátula</span>
                            </div>
                            <img alt="Cover" class="w-full h-full object-cover absolute inset-0 hidden" id="playerCover" src=""/>
                        </div>
                        <h2 class="font-headline-sm text-[20px] leading-tight mb-1 truncate w-full" id="playerTrackTitle">Nada sonando</h2>
                        <p class="font-body-sm text-sidebar/60 mb-8 truncate w-full" id="playerTrackArtist">Elige una canción de tu biblioteca</p>
                        <div class="w-full space-y-3">
                            <div class="relative w-full h-1.5 bg-black/10 dark:bg-black/20 rounded-full overflow-hidden cursor-pointer" id="playerSeekTrack" onclick="seekPlayer(event)">
                                <div class="absolute inset-y-0 left-0 bg-accent w-0" id="playerSeekFill"></div>
                            </div>
                            <div class="flex justify-between font-data-sm text-[12px] text-sidebar/40">
                                <span id="playerCurrentTime">0:00</span>
                                <span id="playerDuration">0:00</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center justify-center gap-4">
                        <button type="button" id="btnShuffle" onclick="toggleShuffle()" class="material-symbols-outlined text-[20px] text-sidebar/40 hover:text-sidebar transition-colors">shuffle</button>
                        <button type="button" onclick="playPrevTrack()" class="material-symbols-outlined text-[24px] text-sidebar/70 hover:text-sidebar">skip_previous</button>
                        <button type="button" id="playerPlayPauseBtn" onclick="togglePlayPause()" class="w-14 h-14 rounded-full bg-card text-main flex items-center justify-center hover:bg-black hover:text-white transition-colors">
                            <span class="material-symbols-outlined text-[28px]" id="playerPlayPauseIcon">play_arrow</span>
                        </button>
                        <button type="button" onclick="playNextTrack()" class="material-symbols-outlined text-[24px] text-sidebar/70 hover:text-sidebar">skip_next</button>
                        <button type="button" id="btnRepeat" onclick="toggleRepeat()" class="material-symbols-outlined text-[20px] text-sidebar/40 hover:text-sidebar transition-colors">repeat</button>
                    </div>

                    <div class="flex items-center justify-center gap-3 mt-6 w-full px-4">
                        <span class="material-symbols-outlined text-[16px] text-sidebar/50 hover:text-sidebar cursor-pointer" onclick="setVolume(0)">volume_mute</span>
                        <div class="relative w-full h-1.5 bg-black/10 dark:bg-black/20 rounded-full overflow-hidden cursor-pointer" id="playerVolumeTrack" onclick="setVolumeFromClick(event)">
                            <div class="absolute inset-y-0 left-0 bg-accent w-full" id="playerVolumeFill"></div>
                        </div>
                        <span class="material-symbols-outlined text-[16px] text-sidebar/50 hover:text-sidebar cursor-pointer" onclick="setVolume(1)">volume_up</span>
                    </div>
                </div>
            </div>
        </main>

        <!-- Botón flotante para reabrir el reproductor (Caelestia Shell style) -->
        <button id="player-expand-btn" type="button" onclick="togglePlayerPanel(true)" class="hidden fixed right-0 top-1/2 -translate-y-1/2 z-40 flex items-center gap-1.5 pl-2.5 pr-3 py-3 rounded-l-2xl bg-sidebar/90 dark:bg-card/90 backdrop-blur-xl border-l border-y border-theme shadow-2xl text-sidebar hover:text-accent hover:pl-3.5 transition-all duration-300 group cursor-pointer" data-i18n-title="player_show" title="Mostrar reproductor">
            <span class="material-symbols-outlined text-[20px] transition-transform duration-300 group-hover:-translate-x-0.5">chevron_left</span>
            <span class="material-symbols-outlined text-[16px] text-accent opacity-75 group-hover:opacity-100 transition-opacity" id="player-mini-indicator">music_note</span>
        </button>
        </div>

        <audio id="library-audio" preload="none"></audio>

        <script>window.CICADA_VERSION = "__CICADA_VERSION__";</script>
        <script src="/static/js/i18n.js?v=2.2.7"></script>
        <script src="/static/js/common.js?v=2.2.10"></script>
        <script src="/static/js/metadata.js?v=2.2.0"></script>
        <script src="/static/js/download.js?v=2.2.0"></script>
        <script src="/static/js/playlist.js?v=2.2.1"></script>
        <script src="/static/js/library.js?v=2.2.1"></script>
        <script src="/static/js/library_audiobooks.js?v=1.0.0"></script>
        <script src="/static/js/library_podcasts.js?v=1.0.0"></script>
        <script src="/static/js/player.js?v=2.2.1"></script>
        <script src="/static/js/ipod/api.js?v=2.2.2"></script>
        <script src="/static/js/ipod/render.js?v=2.2.4"></script>
        <script src="/static/js/ipod/ui.js?v=2.2.8"></script>
        <script>
            // Inicialización de la UI
            applyLanguage(currentLang);
            showView('process');
            loadLibraryConfig();
            loadPodcastFeeds();
            prefillProcessDirsFromSettings();

            // Cargar y aplicar tema inicial
            fetch('/api/settings').then(r => r.json()).then(data => {
            document.documentElement.setAttribute('data-theme', data.theme || "grafito");
            setAccentColor(data.color_accent || "azul");
            ipodUiEnabled = data.ipod_ui_enabled !== false;
            applyIpodUiVisibility();
            }).catch(e => console.error("Error loading theme", e));

            // Accesibilidad: preferencias 100% client-side, no dependen del backend
            selectFontUI(localStorage.getItem('cicada_font') || 'standard');
            selectColorblindModeUI(localStorage.getItem('cicada_colorblind') === 'true');
            handleSpotifyAuthRedirect();
            checkForUpdates();
        </script>
    </body>
    </html>
    """
    html_content = html_content.replace("__CICADA_VERSION__", __version__)
    return HTMLResponse(
        content=html_content,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    )

def print_signature():
    signature = """
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║      ██╗     ██╗  █████╗ ██████╗  ██████╗ ██╗     ██╗                ║
    ║      ██║     ██║ ██╔══██╗██╔══██╗██╔═══██╗██║     ██║                ║
    ║      ██║     ██║ ███████║██████╔╝██║   ██║██║     ██║                ║
    ║ ██╗  ██║██╗  ██║ ██╔══██║██╔══██╗██║   ██║██║     ██║                ║
    ║ ╚█████╔╝╚█████╔╝ ██║  ██║██║  ██║╚██████╔╝███████╗███████╗           ║
    ║  ╚════╝  ╚════╝  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚══════╝           ║
    ║                                                                      ║
    ║   Cicada v1.1.1 - "Dando vida a los píxeles."                        ║
    ║   github.com/JJaroll                                                 ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """
    try:
        print(signature)
    except UnicodeEncodeError:
        pass

if __name__ == "__main__":
    import threading
    import uvicorn
    import webbrowser
    from cicada.core.tray_icon import run_tray_icon
    import sys
    import os

    print_signature()

    HOST = "127.0.0.1"
    PORT = 8000
    APP_URL = f"http://{HOST}:{PORT}"

    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT))
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    def _quit_app():
        os._exit(0)

    @app.post("/api/shutdown")
    async def shutdown_app():
        threading.Timer(0.5, lambda: os._exit(0)).start()
        return {"message": "Cicada apagada correctamente"}

    threading.Timer(1.0, lambda: webbrowser.open(APP_URL)).start()

    if not run_tray_icon(APP_URL, on_quit=_quit_app):
        server_thread.join()
