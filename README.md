# 🪲 Cicada (Organizador Musical Inteligente)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey) ![License](https://img.shields.io/badge/License-GPLv3-blue) ![Version](https://img.shields.io/badge/Version-1.0.0-blue)

**Cicada** es una herramienta local de organización musical y sincronización automática de metadatos de alta fidelidad.

Cicada identifica tus canciones, les aplica metadatos completos (título, artista, álbum, portada, ISRC, BPM, fecha de lanzamiento original...), las organiza en disco y te permite recrear tus playlists de Spotify descargando el audio desde YouTube — todo desde una interfaz web local, sin depender de servicios en la nube.

## ✨ Características Principales

* **🧠 Identificación en Cascada:**
    * **Shazam:** Motor principal por huella acústica.
    * **AcoustID:** Plan de contingencia para canciones de nicho o remixes raros.
    * **iTunes:** Enriquecimiento de metadatos (portadas HD, géneros, números de pista).
* **🏷️ Etiquetado Universal:** Escribe tags ID3v2.3 y nativos (mp3, m4a, flac, wav), incrusta portadas y organiza tus archivos automáticamente por `Artista/Álbum/NN - Título.ext`.
* **📥 Integración con Spotify:** Resuelve playlists, álbumes o tracks desde tu cuenta (vía OAuth2) y descarga el audio directamente a máxima calidad con `yt-dlp`.
* **🔄 Sincronización Inteligente:** Genera playlists `.m3u8` reutilizando tu biblioteca local existente mediante *fuzzy matching*, evitando que descargues archivos duplicados.
* **🎵 Reproductor Integrado:** Escucha tus pistas locales directamente en la web con soporte de salto de tiempo (HTTP Range) y agrupación por artista o álbum.
* **🎨 Interfaz Moderna:** Interfaz con Modo Claro (Aluminio) y Oscuro (Grafito), inspirada en la estética retro-moderna de los reproductores clásicos.
* **🛡️ Reanudable:** Guarda el progreso de cada sesión en tiempo real para que puedas retomar el trabajo tras interrupciones.

---

## 📥 Descargas

Puedes descargar la versión más reciente (v1.0.0) según tu sistema operativo:

*   **Windows:** [Cicada_Setup_Windows.exe](https://github.com/JJaroll/Cicada/releases/download/v1.0.0/Cicada_Setup_Windows.exe)
*   **macOS (Apple Silicon):** [Cicada_macOS_ARM64.dmg](https://github.com/JJaroll/Cicada/releases/download/v1.0.0/Cicada_macOS_ARM64.dmg)
*   **macOS (Intel):** [Cicada_macOS_Intel.dmg](https://github.com/JJaroll/Cicada/releases/download/v1.0.0/Cicada_macOS_Intel.dmg)
*   **Linux:** [Cicada_Linux.AppImage](https://github.com/JJaroll/Cicada/releases/download/v1.0.0/Cicada_Linux.AppImage)

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
   
---

## 🚀 Uso

Ejecuta el archivo principal:

```bash
python main.py
```
*(En macOS, puedes simplemente hacer doble clic en el archivo `start.command`)*

Esto abrirá la aplicación en tu navegador web en la dirección `http://127.0.0.1:8000`.

---

## 📁 Estructura del Proyecto

| Archivo | Responsabilidad |
|---|---|
| `main.py` | Servidor FastAPI, endpoints REST/WebSocket e interfaz (HTML/CSS/JS). |
| `metadata_manager.py` | Orquesta la identificación en cascada (Shazam → AcoustID → iTunes). |
| `acoustid_fallback.py` | Identificación secundaria por huella acústica. |
| `audio_processor.py` | Etiquetado y guardado de archivos en el disco duro. |
| `download_manager.py` | Conexión con Spotify y descargas vía `yt-dlp`. |
| `playlist_manager.py` | Indexado de biblioteca local y *fuzzy matching*. |
| `dev_scripts.py` | Scripts de diagnóstico para ejecutar funciones fuera de la web. |

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

Creado con ❤️ por **JJaroll**
