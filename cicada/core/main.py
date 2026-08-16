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

import threading
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

from cicada.ipod.api import router as ipod_router
from cicada.core.routes.settings import router as settings_router
from cicada.core.routes.system import router as system_router
from cicada.core.routes.library import router as library_router
from cicada.core.routes.spotify import router as spotify_router
from cicada.core.routes.process import router as process_router
app.include_router(ipod_router)
app.include_router(settings_router)
app.include_router(system_router)
app.include_router(library_router)
app.include_router(spotify_router)
app.include_router(process_router)

STATIC_DIR = (
    Path(sys._MEIPASS)  # type: ignore[attr-defined]
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[2]
) / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")























# --- IPOD ENDPOINTS ---



































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
        
        <link rel="stylesheet" href="/static/css/app.css">
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
                <div class="relative w-10 h-10 rounded-xl bg-black/10 dark:bg-black/20 flex items-center justify-center border-2 border-transparent" data-i18n-title="connection_tooltip" title="Estado de conexión">
                    <span class="material-symbols-outlined text-[22px] text-sidebar/60">graphic_eq</span>
                    <span id="ws-status-dot" class="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-gray-400 border-2 border-sidebar"></span>
                </div>
            </div>
        </aside>

        <!-- Modal de Ajustes -->
        <div id="settings-modal" class="hidden fixed inset-0 z-[100] items-center justify-center bg-black/60 backdrop-blur-sm">
            <div class="w-full max-w-lg mx-4 p-6 flex flex-col gap-4 max-h-[85vh] overflow-y-auto custom-scrollbar rounded-2xl border border-theme bg-card">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-accent text-[22px]">settings</span>
                        <span class="font-label-caps text-[14px] tracking-widest text-main" data-i18n="settings_title">Ajustes</span>
                    </div>
                    <button type="button" onclick="closeSettings()" class="material-symbols-outlined text-muted/60 hover:text-main transition-colors">close</button>
                </div>

                <div class="flex flex-col gap-2">
                    <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_language_title">Idioma</span>
                    <div class="flex gap-2">
                        <button type="button" class="lang-btn flex-1 py-2 rounded-lg font-label-caps text-[11px] transition-colors" data-lang="es" onclick="applyLanguage('es')">Español</button>
                        <button type="button" class="lang-btn flex-1 py-2 rounded-lg font-label-caps text-[11px] transition-colors" data-lang="en" onclick="applyLanguage('en')">English</button>
                        <button type="button" class="lang-btn flex-1 py-2 rounded-lg font-label-caps text-[11px] transition-colors" data-lang="ja" onclick="applyLanguage('ja')">日本語</button>
                    </div>
                </div>

                <div class="flex flex-col gap-2 border-t border-theme pt-3">
                    <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_spotify_title">Cuenta de Spotify</span>
                    <div class="flex items-center justify-between gap-2">
                        <span id="settings-spotify-status" class="font-data-sm text-[13px] text-muted/60" data-i18n="settings_spotify_not_connected">No conectado a Spotify</span>
                        <button type="button" onclick="window.location.href='/api/auth/login'" id="settings-spotify-connect-btn" class="px-3 py-2 rounded-lg bg-accent text-white font-label-caps text-[11px] hover:brightness-110 transition-all whitespace-nowrap" data-i18n="settings_spotify_connect_btn">Conectar con Spotify</button>
                    </div>
                </div>

                <div class="flex flex-col gap-2 border-t border-theme pt-3">
                    <div class="flex items-center gap-1.5">
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

                <div class="flex flex-col gap-2 border-t border-theme pt-3">
                    <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_identification_title">Identificación de Canciones</span>
                    <label class="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" id="settings_plan_c_enabled" class="cicada-checkbox"/>
                        <span class="font-data-sm text-[13px] text-muted/70" data-i18n="settings_plan_c_label">Adivinar por el nombre del archivo cuando no se reconoce la canción</span>
                    </label>
                    <p class="font-data-sm text-[11px] text-muted/40 pl-6" data-i18n="settings_plan_c_hint">Apagado por defecto: suele ser poco preciso. Si está apagado, esos archivos se reportan como error en vez de adivinar el título/artista.</p>
                </div>

                
                                <div class="flex flex-col gap-4 border-t border-theme pt-5">
                    <!-- TEMA -->
                    <div class="flex flex-col gap-2">
                        <span class="font-label-caps text-[12px] text-muted tracking-widest font-bold" data-i18n="settings_theme_title">TEMA</span>
                        <div class="flex gap-3">
                            <button type="button" class="theme-btn flex-1 py-3 rounded-xl border-2 font-label-caps text-[13px] font-bold transition-all" data-theme-val="grafito" onclick="selectThemeUI('grafito')" data-i18n="settings_theme_dark">Grafito</button>
                            <button type="button" class="theme-btn flex-1 py-3 rounded-xl border-2 font-label-caps text-[13px] font-bold transition-all" data-theme-val="aluminio" onclick="selectThemeUI('aluminio')" data-i18n="settings_theme_light">Aluminio</button>
                        </div>
                        <input type="hidden" id="settings_theme" value="grafito">
                    </div>

                    <!-- COLOR NANO -->
                    <div class="flex flex-col gap-2 mt-2">
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
                </div>

<div class="flex flex-col gap-2 border-t border-theme pt-3">
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

                <div class="flex gap-2 justify-end items-center pt-2">
                    <span id="settings-status" class="font-data-sm text-[12px] text-secondary mr-auto"></span>
                    <button type="button" onclick="closeSettings()" class="px-4 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[12px] transition-colors" data-i18n="common_cancel">Cancelar</button>
                    <button type="button" id="settingsSaveBtn" onclick="saveSettings()" class="px-4 py-2 rounded-lg bg-accent text-white font-label-caps text-[12px] hover:brightness-110 transition-all" data-i18n="common_save">Guardar</button>
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
                <span class="font-label-caps text-[11px] text-secondary" id="about-version" data-i18n="about_version">Versión 1.1.1</span>

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
                <div id="view-ipod" class="view h-full flex-col gap-4 overflow-hidden hidden">
                    
                    <!-- Top section: Device Info -->
                    <div class="glass-card p-6 flex flex-col gap-4">
                        <div class="flex justify-between items-center border-b border-theme pb-4">
                            <h2 class="font-label-caps tracking-widest text-[16px] text-main">Dispositivo Conectado</h2>
                            <button onclick="scanIpod()" class="bg-accent text-white px-4 py-2 rounded-full font-label-caps text-[12px] hover:scale-105 transition-transform flex items-center gap-2">
                                <span class="material-symbols-outlined text-[16px]">search</span>
                                Escanear
                            </button>
                        </div>
                        
                        <div id="ipod-info-container" class="flex items-center gap-6 hidden">
                            <!-- Placeholder for an iPod image or generic icon -->
                            <div class="w-24 h-32 bg-black/10 dark:bg-white/10 rounded-lg flex items-center justify-center">
                                <span class="material-symbols-outlined text-[48px] text-muted">mp3</span>
                            </div>
                            <div class="flex-1 flex flex-col gap-2">
                                <h3 id="ipod-name" class="font-label-caps text-[18px] text-main">--</h3>
                                <p id="ipod-model" class="font-data-sm text-[13px] text-muted">Modelo: --</p>
                                <p id="ipod-capacity" class="font-data-sm text-[13px] text-muted">Capacidad: --</p>
                                <p id="ipod-format" class="font-data-sm text-[13px] text-muted">Formato: --</p>
                            </div>
                        </div>
                        <div id="ipod-no-device" class="text-center py-6 text-muted font-data-sm text-[13px]" data-i18n="ipod_no_device">
                            No se ha detectado ningún iPod. Asegúrate de que esté conectado y montado.
                        </div>
                        <div id="ipod-no-control" class="text-center py-6 text-[#f59e0b] font-data-sm text-[13px] hidden" data-i18n="ipod_no_control"></div>
                    </div>

                    <!-- Middle section: Sync & Backup (side by side) -->
                    <div class="flex gap-4 h-full">
                        <!-- Sync -->
                        <div class="glass-card p-6 flex-1 flex flex-col gap-4 relative">
                            <h2 class="font-label-caps tracking-widest text-[16px] text-main border-b border-theme pb-4">Sincronización</h2>
                            <p class="font-data-sm text-[13px] text-muted mb-4">
                                Reescribe la base de datos del iPod con las pistas actuales, en el formato de Cicada. Se hace un backup automático antes de escribir; ante cualquier error se restaura. La primera escritura vuelve el iPod incompatible con Music.app (se pedirá confirmación).
                            </p>
                            <div class="mt-auto flex justify-end">
                                <button onclick="syncIpod()" id="btn-sync-ipod" class="bg-secondary text-white px-6 py-2 rounded-full font-label-caps text-[12px] hover:scale-105 transition-transform opacity-50 cursor-not-allowed" disabled>
                                    Escribir en el iPod
                                </button>
                            </div>
                        </div>

                        <!-- Backup -->
                        <div class="glass-card p-6 flex-1 flex flex-col gap-4 relative">
                            <h2 class="font-label-caps tracking-widest text-[16px] text-main border-b border-theme pb-4">Respaldos</h2>
                            <p class="font-data-sm text-[13px] text-muted mb-4">
                                Crea una copia de seguridad manual de los archivos internos del iPod.
                            </p>
                            <div class="mt-auto flex justify-end">
                                <button onclick="backupIpod()" id="btn-backup-ipod" class="border border-secondary text-secondary px-6 py-2 rounded-full font-label-caps text-[12px] hover:bg-secondary hover:text-white transition-colors opacity-50 cursor-not-allowed" disabled>
                                    Crear Backup Manual
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Biblioteca del dispositivo (Fase 1: lectura) -->
                    <div id="ipod-library" class="glass-card p-6 flex flex-col gap-4 flex-1 overflow-hidden hidden">
                        <div class="flex justify-between items-center border-b border-theme pb-4">
                            <h2 class="font-label-caps tracking-widest text-[16px] text-main" data-i18n="ipod_library_title">Biblioteca del iPod</h2>
                            <span id="ipod-library-counts" class="font-data-sm text-[13px] text-muted"></span>
                        </div>
                        <div class="flex gap-4 flex-1 overflow-hidden">
                            <div class="w-[220px] flex-shrink-0 flex flex-col gap-2 overflow-y-auto">
                                <h3 class="font-label-caps text-[12px] text-secondary uppercase" data-i18n="ipod_playlists_label">Playlists</h3>
                                <div id="ipod-playlists-list" class="flex flex-col gap-1"></div>
                            </div>
                            <div class="flex-1 flex flex-col gap-1 overflow-y-auto">
                                <h3 class="font-label-caps text-[12px] text-secondary uppercase" data-i18n="ipod_tracks_label">Canciones</h3>
                                <div id="ipod-tracks-list" class="flex flex-col gap-1"></div>
                            </div>
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
                        <span class="font-label-caps text-[12px] text-sidebar/40" data-i18n="player_title">Reproductor</span>
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
        </div>

        <audio id="library-audio" preload="none"></audio>

        <script src="/static/js/i18n.js"></script>
        <script src="/static/js/common.js"></script>
        <script src="/static/js/metadata.js"></script>
        <script src="/static/js/download.js"></script>
        <script src="/static/js/playlist.js"></script>
        <script src="/static/js/library.js"></script>
        <script src="/static/js/player.js"></script>
        <script src="/static/js/ipod.js"></script>
        <script>
            // Inicialización de la UI
            applyLanguage(currentLang);
            showView('process');
            loadLibraryConfig();
            prefillProcessDirsFromSettings();

            // Cargar y aplicar tema inicial
            fetch('/api/settings').then(r => r.json()).then(data => {
            document.documentElement.setAttribute('data-theme', data.theme || "grafito");
            setAccentColor(data.color_accent || "azul");
            }).catch(e => console.error("Error loading theme", e));
            handleSpotifyAuthRedirect();
            checkForUpdates();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

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
        # Si la consola de Windows no soporta los caracteres, simplemente lo ignoramos
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