# 🪲 Cicada (Organizador Musical Inteligente)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey) ![License](https://img.shields.io/badge/License-GPLv3-blue) ![Version](https://img.shields.io/badge/Version-2.0.0-blue)

*🌍 **Español** | [English](README_en.md) | [日本語](README_ja.md)*

**Cicada** es una herramienta local de organización musical y sincronización automática de metadatos de alta fidelidad.

Cicada identifica tus canciones, les aplica metadatos completos (título, artista, álbum, portada, ISRC, BPM, fecha de lanzamiento original...), las organiza en disco y te permite recrear tus playlists de Spotify descargando el audio desde YouTube — todo desde una interfaz web local, sin depender de servicios en la nube.

## ✨ Características Principales

* **🧠 Identificación en Cascada:**
    * **Shazam:** Motor principal por huella acústica.
    * **AcoustID:** Plan de contingencia para canciones de nicho o remixes raros.
    * **iTunes:** Enriquecimiento de metadatos (portadas HD, géneros, números de pista).
* **🏷️ Etiquetado Universal:** Escribe tags ID3v2.3 y nativos (mp3, m4a, flac, wav), incrusta portadas y organiza tus archivos automáticamente por `Artista/Álbum/NN - Título.ext`.
* **📥 Descarga Multicanal de Música:** Resuelve canciones, álbumes y playlists desde enlaces de **Spotify**, **YouTube Music** y **Deezer** (incluyendo enlaces compartidos y listas públicas), y descarga el audio directamente a máxima calidad con `yt-dlp`.
* **🔄 Sincronización Inteligente:** Genera playlists `.m3u8` reutilizando tu biblioteca local existente mediante *fuzzy matching*, evitando que descargues archivos duplicados.
* **🎵 Reproductor Integrado:** Escucha tus pistas locales directamente en la web con soporte de salto de tiempo (HTTP Range) y agrupación por artista o álbum.
* **🎨 Interfaz Moderna:** Interfaz con Modo Claro (Aluminio) y Oscuro (Grafito), inspirada en la estética retro-moderna de los reproductores clásicos.
* **🛡️ Reanudable:** Guarda el progreso de cada sesión en tiempo real para que puedas retomar el trabajo tras interrupciones.
* **🎧 Integración con iPod:** Detecta tu iPod, sincroniza música y playlists (incluyendo importación de playlists replicadas y sync bidireccional con resolución de conflictos de calificación), escribe cover art, gestiona video, podcasts y audiolibros, y ofrece visualización de fotos existentes en el dispositivo en modo de solo lectura — todo con backup automático y rollback ante errores. Ver la sección dedicada más abajo.

---

## 📥 Descargas

Puedes descargar la versión más reciente (v2.0.0) según tu sistema operativo:

*   **Windows:** [Cicada_Setup_Windows.exe](https://github.com/JJaroll/Cicada/releases/download/v2.0.0/Cicada_Setup_Windows.exe)
*   **macOS (Apple Silicon):** [Cicada_macOS_ARM64.dmg](https://github.com/JJaroll/Cicada/releases/download/v2.0.0/Cicada_macOS_ARM64.dmg)
*   **macOS (Intel):** [Cicada_macOS_Intel.dmg](https://github.com/JJaroll/Cicada/releases/download/v2.0.0/Cicada_macOS_Intel.dmg)
*   **Linux:** [Cicada_Linux.AppImage](https://github.com/JJaroll/Cicada/releases/download/v2.0.0/Cicada_Linux.AppImage)

> **⚠️ Nota para usuarios de macOS:**
> Al ser una aplicación de código abierto, macOS podría impedir su ejecución inicial por seguridad (Gatekeeper). Si el sistema bloquea la app, simplemente dirígete a **Ajustes del Sistema > Privacidad y seguridad**, desplázate hasta el apartado de seguridad y haz clic en el botón **"Abrir de todos modos"** para autorizar la ejecución.

---

## 🔑 Configuración de Claves API

Para habilitar las funciones de integración con Spotify y la identificación de pistas mediante AcoustID, es necesario configurar las credenciales correspondientes. Sigue los pasos descritos a continuación.

### 1. Spotify (Gestión de Playlists)
Esta integración permite a Cicada autenticar tu cuenta para leer playlists y sincronizar metadatos.

1. Accede al [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) e inicia sesión con tu cuenta de Spotify.
2. Selecciona la opción **"Create App"**.
3. Una vez creada, localiza el botón **"Edit Settings"**.
4. En el campo **Redirect URI**, ingresa la siguiente dirección exacta:
   `http://127.0.0.1:8000/api/auth/callback`
5. Guarda los cambios. El sistema generará un **Client ID** y un **Client Secret**. Consérvalos para el siguiente paso.
6. **Importante (Modo Desarrollo):** Debido a que la aplicación se encuentra en fase de desarrollo, debes autorizar tu cuenta explícitamente. En el mismo panel de tu proyecto en Spotify, ve a la sección **"Users and Access"** y añade el correo electrónico vinculado a tu cuenta de Spotify. Sin este paso, la aplicación no podrá conectarse.

### 2. AcoustID (Identificación de Pistas)
Este servicio permite a la aplicación identificar archivos de audio basándose en su huella acústica.

1. Regístrate o inicia sesión en [AcoustID](https://acoustid.org/login).
2. Registra una nueva aplicación para obtener una **API Key**.
3. Al finalizar, obtendrás una clave única de identificación que deberás configurar en Cicada.

---

### Configuración en Cicada

Puedes gestionar estas credenciales directamente desde la interfaz de la aplicación:

1. Inicia **Cicada**.
2. Dirígete a la sección de **Ajustes** (ícono de engranaje ⚙️) en la parte inferior de la barra lateral.
3. Introduce el **Client ID**, **Client Secret** y la **API Key de AcoustID** en los campos correspondientes.
4. Haz clic en **Guardar**.

> **Nota:** La aplicación también permite gestionar estas claves de forma local mediante un archivo `.env` en la carpeta de instalación, reemplazando el archivo `env.example`. Sin embargo, el panel de Ajustes es el método recomendado para una gestión rápida.
---

### 🧩 Primeros pasos

Una vez que hayas configurado tus claves API en los Ajustes (⚙️), el proceso de vinculación es automático:

1. **Conexión:** Haz clic en el botón **"Conectar con Spotify"** dentro del modal de **Ajustes**.
2. **Autorización:** Se abrirá tu navegador predeterminado. Inicia sesión en Spotify si se te solicita y acepta los permisos de acceso.
3. **Sincronización:** Una vez aceptado, el navegador te devolverá a la aplicación. Cicada guardará tus credenciales de forma segura y ya estarás listo para importar tus listas.

*Nota: Solo necesitas realizar este proceso la primera vez. La aplicación recordará tu sesión de forma segura para futuras ejecuciones.*
---

## 📥 Descarga e Instalación por Terminal

### Requisitos Previos
* Python 3.10 o superior.
* [`ffmpeg`](https://ffmpeg.org/) instalado en el sistema (necesario para las descargas).
* `chromaprint` (binario `fpcalc`) instalado en el sistema para la identificación por AcoustID (Opcional):
  * **macOS:** `brew install chromaprint`
  * **Debian/Ubuntu:** `apt-get install libchromaprint-tools`

### Pasos de Instalación
1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/JJaroll/Cicada.git
   cd Cicada
   ```

2. **Crear un entorno virtual (Recomendado):**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
   > **Nota:** esto incluye las dependencias del módulo iPod (`wasmtime`,
   > `zstandard`, `numpy`), que pesan varias decenas de MB adicionales. Hoy
   > no hay forma de omitirlas en una instalación estándar; si no tenés
   > un iPod, podés ocultar la sección desde **Ajustes** una vez dentro de
   > la app (ver más abajo), aunque las dependencias sigan instaladas.

---

## 🚀 Uso

Ejecuta el archivo principal:

```bash
python run.py
```
*(En macOS, puedes simplemente hacer doble clic en el archivo `start.command`)*

Esto abrirá la aplicación en tu navegador web en la dirección `http://127.0.0.1:8000`.

---

## 🎧 Integración con iPod

Cicada detecta tu iPod conectado y lo gestiona directamente desde la interfaz
web, sin pasar por iTunes/Music.app: lectura de biblioteca, escritura segura
(plan *dry-run* + backup automático + rollback ante cualquier error), y
expulsión segura del volumen.

### Qué funciona hoy

* **Música y playlists:** lectura y escritura de la biblioteca, creación,
  eliminación e **importación de playlists locales y replicadas** con resolución
  automática de canciones en subcarpetas.
* **Sincronización bidireccional:** reproducciones y saltos del iPod se
  reflejan de vuelta en Cicada, con resolución interactiva de conflictos de
  calificación (el único campo genuinamente conflictivo — reproducciones y
  saltos se suman en vez de pisarse).
* **Cover art (artwork):** implementado con el mismo formato de píxel
  (RGB565_LE) en las 24 device families que Cicada modela; de estas, 14
  soportan cover art según su hardware (las demás — Shuffles, Minis, algunos
  iPods de rueda de clic tempranos — no tienen esa capacidad físicamente). La
  correspondencia de capacidades está auditada contra libgpod para 12 de las
  13 families relevantes (Nano 7G, ausente de libgpod, se verificó contra
  hardware real en su lugar). Detalle completo de la auditoría en
  [`docs/IPOD_INTEGRATION.md`](docs/IPOD_INTEGRATION.md).
* **Video, podcasts y audiolibros:** gestión completa (lectura, escritura,
  metadatos específicos como capítulos embebidos).
* **Visualización de Fotos (Solo Lectura):** decodificación directa en tiempo
  real de miniaturas y fotos a resolución completa desde `Photo Database` y
  archivos binarios `.ithmb` (RGB565) del iPod, con galería y visor Lightbox
  interactivo de solo lectura (sin modificar la base de datos de fotos).
* **Visibilidad opcional:** un switch en **Ajustes** oculta toda la sección
  iPod de la interfaz para quien no tenga el dispositivo — no reduce el
  tamaño de instalación ni desinstala nada, solo la interfaz.

### Qué NO funciona

* **Modificación / Sincronización de Fotos:** La escritura o adición/eliminación
  de fotos en el iPod no está soportada (el módulo opera en modo 100% de solo
  lectura y visualización segura para preservar la integridad del firmware).
* **iPod touch** (y el "iPod Mobile" de los Motorola ROKR/SLVR/RAZR): **no
  soportado, y no está planeado como extensión incremental.** Es un
  dispositivo con SO propio (iOS) que sincroniza por un protocolo distinto,
  muy probablemente sin el par FireWireGUID/HASHAB en el que se apoya toda la
  identificación y firma de Cicada hoy. Soportarlo sería un proyecto aparte,
  no una generalización del código existente.

### Modelos verificados vs. modelados

Cicada **modela** 24 device families de iPods de rueda de clic (click-wheel)
y Nano de pantalla táctil hasta la 7ª generación — Shuffle, Classic, Nano
1G-7G, iPod Video/Photo/Color, etc. Sé honesto con el alcance real: **solo el
Nano 7G está verificado contra hardware físico real**, repetidas veces, en
esta sesión de desarrollo. El resto del código sigue el mismo modelo de datos
(vendorizado y auditado contra `itdb_device.c` de libgpod donde es posible),
pero no se probó contra el dispositivo físico correspondiente. Si usás
Cicada con otra family y encontrás un problema, es información valiosa —
reportalo.

### CLI del iPod (`cicada ipod`)

Para gestionar el iPod desde la terminal (backups, restauración, expulsión segura,
etc.) sin pasar por la app web, instala Cicada en modo editable una vez:

```bash
pip install -e .
```

Esto agrega el ejecutable `cicada` al `PATH` de tu entorno virtual, disponible
desde cualquier directorio mientras el venv esté activo:

```bash
cicada ipod status              # identidad y estado del iPod montado
cicada ipod backup              # snapshot de seguridad (--full para incluir Music/)
cicada ipod restore <archivo>   # restaura un backup
cicada ipod list-backups        # lista los backups existentes
cicada ipod consent             # consulta/otorga el consentimiento de Music.app
cicada ipod eject               # expulsa el iPod de forma segura
```

Usa `cicada ipod --help` o `cicada ipod <subcomando> --help` para ver todas las
opciones. (La instalación es editable a propósito: los archivos estáticos de la
app se resuelven en runtime relativos al checkout del repositorio, no se
empaquetan — por eso no se recomienda una instalación no-editable.)

Detalle técnico completo de toda la integración en
[`docs/IPOD_INTEGRATION.md`](docs/IPOD_INTEGRATION.md) y el registro de
vendorizado por etapa en [`docs/VENDORED.md`](docs/VENDORED.md).

---

## 📁 Estructura del Proyecto

| Archivo | Responsabilidad |
|---|---|
| `run.py` | Punto de entrada. La app vive en `cicada/core/main.py` (Servidor FastAPI, endpoints REST/WebSocket e interfaz HTML/CSS/JS). |
| `metadata_manager.py` | Orquesta la identificación en cascada (Shazam → AcoustID → iTunes). |
| `acoustid_fallback.py` | Identificación secundaria por huella acústica. |
| `audio_processor.py` | Etiquetado y guardado de archivos en el disco duro. |
| `download_manager.py` | Conexión con Spotify y descargas vía `yt-dlp`. |
| `playlist_manager.py` | Indexado de biblioteca local y *fuzzy matching*. |
| `dev_scripts.py` | Scripts de diagnóstico para ejecutar funciones fuera de la web. |

---

## 🔒 Privacidad y Seguridad
**Tus datos se quedan en tu máquina.**

Cicada es una aplicación local. A diferencia de los gestores de música basados en la nube, Cicada no rastrea tus hábitos de escucha, no recopila tu información personal ni envía los metadatos de tu biblioteca musical a ningún servidor remoto.

* **Claves Locales**: Tus claves de API de Spotify y AcoustID se almacenan de forma segura en tu propio dispositivo.
* **Sin Telemetría**: No hay rastreo, análisis de datos, ni recopilación de información.
* **Conexión Directa**: Cuando te conectas a Spotify o AcoustID, la aplicación se comunica directamente con esos servicios. El desarrollador no tiene acceso a tu cuenta, tus listas de reproducción ni a tus claves de API.

---

## 🤝 Contribuir

¡Las contribuciones son bienvenidas!

1. Haz un **Fork** del proyecto.
2. Crea una rama (`git checkout -b feature/NuevaFuncion`).
3. Haz tus cambios y commits.
4. Haz Push a tu rama (`git push origin feature/NuevaFuncion`).
5. Abre un **Pull Request**.

## 📄 Licencia

Este proyecto está bajo la Licencia GNU GPLv3.
*📝 Consulta los [Términos y Condiciones](TERMS.md).*

**Código de terceros:** el módulo de integración con iPod incorpora código
vendorizado de [iOpenPod](https://github.com/TheRealSavi/iOpenPod) (MIT) y de
[dstaley/hashab](https://github.com/dstaley/hashab) (The Unlicense/dominio
público), ambas compatibles con GPLv3 y redistribuidas bajo esos términos.
Ver [`NOTICE`](NOTICE) para las atribuciones completas y
[`docs/VENDORED.md`](docs/VENDORED.md) para el detalle de qué se vendorizó,
de dónde y en qué commit.

Creado con ❤️ por **JJaroll**
