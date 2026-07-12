# 🪲 Cicada (Organizador Musical Inteligente)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey) ![License](https://img.shields.io/badge/License-GPLv3-blue) ![Version](https://img.shields.io/badge/Version-1.0.1-blue)

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

## 📥 Descarga e Instalación

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

## 🔑 Obtener Claves API

Para sacar el máximo provecho a Cicada, necesitas configurar un par de claves gratuitas en tu archivo `.env` o desde los Ajustes de la app.

### 1️⃣ Spotify (Para leer playlists y metadatos extendidos)
1. Ve al [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) e inicia sesión.
2. Haz clic en "Create app".
3. En la configuración de la app, como **Redirect URI**, debes agregar exactamente: `http://127.0.0.1:8000/api/auth/callback`
4. Guarda los cambios y copia tu **Client ID** y **Client Secret**.

### 2️⃣ AcoustID (Para identificar canciones difíciles)
1. Ve a [AcoustID New Application](https://acoustid.org/new-application) e inicia sesión.
2. Registra una nueva aplicación para obtener tu **Client Key** gratuita.

> **Configuración:** Renombra el archivo `.env.example` a `.env` y pega tus claves allí. ¡También puedes introducirlas directamente en la interfaz de Cicada, abriendo la sección de Ajustes (⚙️)! Los cambios se aplican en caliente.

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
