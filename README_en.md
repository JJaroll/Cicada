# 🪲 Cicada (Smart Music Organizer)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey) ![License](https://img.shields.io/badge/License-GPLv3-blue) ![Version](https://img.shields.io/badge/Version-1.1.1-blue)

*🌍 [Español](README.md) | **English** | [日本語](README_ja.md)*

**Cicada** is a local music organization and high-fidelity automatic metadata synchronization tool.

Cicada identifies your songs, applies comprehensive metadata (title, artist, album, cover art, ISRC, BPM, original release date...), organizes them on disk, and allows you to recreate your Spotify playlists by downloading audio from YouTube — all from a local web interface, without relying on cloud services.

## ✨ Main Features

* **🧠 Waterfall Identification:**
    * **Shazam:** Main engine using acoustic fingerprinting.
    * **AcoustID:** Contingency plan for niche songs or rare remixes.
    * **iTunes:** Metadata enrichment (HD covers, genres, track numbers).
* **🏷️ Universal Tagging:** Writes ID3v2.3 and native tags (mp3, m4a, flac, wav), embeds covers, and automatically organizes your files by `Artist/Album/NN - Title.ext`.
* **📥 Spotify Integration:** Resolves playlists, albums, or tracks from your account (via OAuth2) and downloads audio directly at maximum quality with `yt-dlp`.
* **🔄 Smart Synchronization:** Generates `.m3u8` playlists by reusing your existing local library through *fuzzy matching*, preventing duplicate downloads.
* **🎵 Built-in Player:** Listen to your local tracks directly on the web with HTTP Range support for seeking and grouping by artist or album.
* **🎨 Modern Interface:** Interface with Light Mode (Aluminum) and Dark Mode (Graphite), inspired by the retro-modern aesthetic of classic players.
* **🛡️ Resumable:** Saves the progress of each session in real time so you can resume work after interruptions.

---

## 📥 Downloads

You can download the latest version (v1.1.1) according to your operating system:

*   **Windows:** [Cicada_Setup_Windows.exe](https://github.com/JJaroll/Cicada/releases/download/v1.1.1/Cicada_Setup_Windows.exe)
*   **macOS (Apple Silicon):** [Cicada_macOS_ARM64.dmg](https://github.com/JJaroll/Cicada/releases/download/v1.1.1/Cicada_macOS_ARM64.dmg)
*   **macOS (Intel):** [Cicada_macOS_Intel.dmg](https://github.com/JJaroll/Cicada/releases/download/v1.1.1/Cicada_macOS_Intel.dmg)
*   **Linux:** [Cicada_Linux.AppImage](https://github.com/JJaroll/Cicada/releases/download/v1.1.1/Cicada_Linux.AppImage)

> **⚠️ Note for macOS users:**
> Being an open-source application, macOS might prevent its initial execution for security reasons (Gatekeeper). If the system blocks the app, simply go to **System Settings > Privacy & Security**, scroll down to the security section, and click the **"Open Anyway"** button to authorize the execution.

---

## 🔑 API Keys Configuration

To enable Spotify integration features and track identification via AcoustID, you need to configure the corresponding credentials. Follow the steps described below.

### 1. Spotify (Playlist Management)
This integration allows Cicada to authenticate your account to read playlists and synchronize metadata.

1. Access the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in with your Spotify account.
2. Select the **"Create App"** option.
3. Once created, locate the **"Edit Settings"** button.
4. In the **Redirect URI** field, enter the exact following address:
   `http://127.0.0.1:8000/api/auth/callback`
5. Save the changes. The system will generate a **Client ID** and a **Client Secret**. Keep them for the next step.
6. **Important (Development Mode):** Since the application is in development phase, you must explicitly authorize your account. In the same panel of your project on Spotify, go to the **"Users and Access"** section and add the email associated with your Spotify account. Without this step, the application will not be able to connect.

### 2. AcoustID (Track Identification)
This service allows the application to identify audio files based on their acoustic fingerprint.

1. Sign up or log in at [AcoustID](https://acoustid.org/login).
2. Register a new application to get an **API Key**.
3. Upon completion, you will get a unique identification key that you must configure in Cicada.

---

### Configuration in Cicada

You can manage these credentials directly from the application interface:

1. Launch **Cicada**.
2. Go to the **Settings** section (gear icon ⚙️) at the bottom of the sidebar.
3. Enter the **Client ID**, **Client Secret**, and the **AcoustID API Key** in the corresponding fields.
4. Click **Save**.

> **Note:** The application also allows managing these keys locally via a `.env` file in the installation folder, replacing the `env.example` file. However, the Settings panel is the recommended method for quick management.
---

### 🧩 Getting Started

Once you have configured your API keys in the Settings (⚙️), the linking process is automatic:

1. **Connection:** Click the **"Connect with Spotify"** button within the **Settings** modal.
2. **Authorization:** Your default browser will open. Log in to Spotify if prompted and accept the access permissions.
3. **Synchronization:** Once accepted, the browser will return you to the application. Cicada will securely save your credentials, and you will be ready to import your lists.

*Note: You only need to do this process the first time. The application will securely remember your session for future runs.*
---

## 📥 Download and Installation via Terminal

### Prerequisites
* Python 3.10 or higher.
* [`ffmpeg`](https://ffmpeg.org/) installed on the system (required for downloads).
* `chromaprint` (`fpcalc` binary) installed on the system for AcoustID identification (Optional):
  * **macOS:** `brew install chromaprint`
  * **Debian/Ubuntu:** `apt-get install libchromaprint-tools`

### Installation Steps
1. **Clone the repository:**
   ```bash
   git clone https://github.com/JJaroll/Cicada.git
   cd Cicada
   ```

2. **Create a virtual environment (Recommended):**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   
---

## 🚀 Usage

Run the main file:

```bash
python main.py
```
*(On macOS, you can simply double-click the `start.command` file)*

This will open the application in your web browser at `http://127.0.0.1:8000`.

---

## 📁 Project Structure

| File | Responsibility |
|---|---|
| `main.py` | FastAPI server, REST/WebSocket endpoints, and interface (HTML/CSS/JS). |
| `metadata_manager.py` | Orchestrates waterfall identification (Shazam → AcoustID → iTunes). |
| `acoustid_fallback.py` | Secondary identification by acoustic fingerprint. |
| `audio_processor.py` | Tagging and saving files to the hard drive. |
| `download_manager.py` | Spotify connection and downloads via `yt-dlp`. |
| `playlist_manager.py` | Local library indexing and *fuzzy matching*. |
| `dev_scripts.py` | Diagnostic scripts to run functions outside the web. |

---

## 🔒 Privacy & Security
**Your data stays on your machine.** 

Cicada is a local-first application. Unlike cloud-based music managers, Cicada does not track your listening habits, collect your personal information, or send your music library metadata to any remote server. 

* **Local Keys**: Your Spotify and AcoustID API keys are stored securely on your own device.
* **No Telemetry**: There is no tracking, no analytics, and no data harvesting.
* **Direct Connection**: When you connect to Spotify or AcoustID, the application communicates directly with those services. The developer has no access to your account, your playlists, or your API keys.

---

## 🤝 Contributing

Contributions are welcome!

1. **Fork** the project.
2. Create a branch (`git checkout -b feature/NewFeature`).
3. Commit your changes.
4. Push to the branch (`git push origin feature/NewFeature`).
5. Open a **Pull Request**.

## 📄 License

This project is licensed under the GNU GPLv3 License.
*📝 Please read the [Terms and Conditions](TERMS.md).*

Created with ❤️ by **JJaroll**
