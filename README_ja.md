# 🪲 Cicada (スマート音楽オーガナイザー)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey) ![License](https://img.shields.io/badge/License-GPLv3-blue) ![Version](https://img.shields.io/badge/Version-1.1.1-blue)

*🌍 [Español](README.md) | [English](README_en.md) | **日本語***

**Cicada**は、ローカルの音楽整理と高音質なメタデータの自動同期ツールです。

Cicadaは曲を識別し、完全なメタデータ（タイトル、アーティスト、アルバム、カバーアート、ISRC、BPM、オリジナルリリース日など）を適用してディスク上で整理します。また、クラウドサービスに依存することなく、YouTubeからオーディオをダウンロードしてSpotifyのプレイリストを再構築することができます。すべてローカルのウェブインターフェースから実行可能です。

## ✨ 主な機能

* **🧠 ウォーターフォール識別:**
    * **Shazam:** 音響指紋を利用したメインエンジン。
    * **AcoustID:** ニッチな曲や珍しいリミックスのためのフォールバック。
    * **iTunes:** メタデータの強化（HDカバー、ジャンル、トラック番号）。
* **🏷️ ユニバーサルタグ付け:** ID3v2.3およびネイティブタグ（mp3, m4a, flac, wav）の書き込み、カバーの埋め込み、`アーティスト/アルバム/NN - タイトル.ext`によるファイルの自動整理。
* **📥 Spotify統合:** アカウント（OAuth2経由）からプレイリスト、アルバム、またはトラックを解決し、`yt-dlp`を使用して最高音質で直接オーディオをダウンロードします。
* **🔄 スマート同期:** ファジーマッチングによって既存のローカルライブラリを再利用し、重複ダウンロードを防ぎながら`.m3u8`プレイリストを生成します。
* **🎵 内蔵プレーヤー:** ウェブ上でローカルのトラックを直接聴くことができます。シーク機能（HTTP Range）やアーティスト/アルバムごとのグループ化に対応しています。
* **🎨 モダンなインターフェース:** クラシックなプレーヤーのレトロモダンな美学にインスパイアされた、ライトモード（アルミニウム）とダークモード（グラファイト）のインターフェース。
* **🛡️ レジューム機能:** 中断後に作業を再開できるよう、各セッションの進行状況をリアルタイムで保存します。

---

## 📥 ダウンロード

お使いのオペレーティングシステムに合わせて最新バージョン（v1.1.1）をダウンロードできます：

*   **Windows:** [Cicada_Setup_Windows.exe](https://github.com/JJaroll/Cicada/releases/download/v1.1.1/Cicada_Setup_Windows.exe)
*   **macOS (Apple Silicon):** [Cicada_macOS_ARM64.dmg](https://github.com/JJaroll/Cicada/releases/download/v1.1.1/Cicada_macOS_ARM64.dmg)
*   **macOS (Intel):** [Cicada_macOS_Intel.dmg](https://github.com/JJaroll/Cicada/releases/download/v1.1.1/Cicada_macOS_Intel.dmg)
*   **Linux:** [Cicada_Linux.AppImage](https://github.com/JJaroll/Cicada/releases/download/v1.1.1/Cicada_Linux.AppImage)

> **⚠️ macOSユーザーへの注意:**
> オープンソースアプリケーションであるため、macOSはセキュリティ上の理由（Gatekeeper）で初回の実行をブロックする場合があります。アプリがブロックされた場合は、**システム設定 > プライバシーとセキュリティ**に移動し、セキュリティセクションまでスクロールして、**「このまま開く」**ボタンをクリックして実行を許可してください。

---

## 🔑 APIキーの設定

Spotifyの統合機能やAcoustIDによるトラック識別を有効にするには、対応する認証情報を設定する必要があります。以下の手順に従ってください。

### 1. Spotify (プレイリスト管理)
この統合により、Cicadaはアカウントを認証し、プレイリストを読み取ってメタデータを同期できるようになります。

1. [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)にアクセスし、Spotifyアカウントでログインします。
2. **「Create App」**オプションを選択します。
3. 作成したら、**「Edit Settings」**ボタンを見つけます。
4. **Redirect URI**フィールドに、正確に以下のアドレスを入力します：
   `http://127.0.0.1:8000/api/auth/callback`
5. 変更を保存します。システムが**Client ID**と**Client Secret**を生成します。次のステップのためにこれらを保存してください。
6. **重要（開発モード）:** アプリケーションが開発段階にあるため、アカウントを明示的に承認する必要があります。Spotifyのプロジェクトの同じパネルで、**「Users and Access」**セクションに移動し、Spotifyアカウントに関連付けられたメールアドレスを追加します。このステップがないと、アプリケーションは接続できません。

### 2. AcoustID (トラック識別)
このサービスにより、アプリケーションは音響指紋に基づいてオーディオファイルを識別できます。

1. [AcoustID](https://acoustid.org/login)で登録またはログインします。
2. 新しいアプリケーションを登録して**API Key**を取得します。
3. 完了すると、Cicadaで設定する必要がある一意の識別キーが取得できます。

---

### Cicadaでの設定

これらの認証情報は、アプリケーションのインターフェースから直接管理できます：

1. **Cicada**を起動します。
2. サイドバー下部の**設定**セクション（歯車アイコン ⚙️）に移動します。
3. 対応するフィールドに**Client ID**、**Client Secret**、および**AcoustID API Key**を入力します。
4. **保存**をクリックします。

> **注:** アプリケーションでは、インストールフォルダにある`.env`ファイル（`env.example`ファイルを置き換える）を介してこれらのキーをローカルで管理することもできます。ただし、すばやく管理するには設定パネルをお勧めします。
---

### 🧩 はじめに

設定（⚙️）でAPIキーを構成すると、リンクプロセスは自動的に行われます：

1. **接続:** **設定**モーダル内の**「Conectar con Spotify」**ボタンをクリックします。
2. **承認:** デフォルトのブラウザが開きます。プロンプトが表示されたらSpotifyにログインし、アクセス許可を受け入れます。
3. **同期:** 受け入れると、ブラウザからアプリケーションに戻ります。Cicadaは認証情報を安全に保存し、リストをインポートする準備が整います。

*注：このプロセスは最初の一度だけ行う必要があります。アプリケーションは将来の実行のためにセッションを安全に記憶します。*
---

## 📥 ターミナルからのダウンロードとインストール

### 前提条件
* Python 3.10以上。
* システムに[`ffmpeg`](https://ffmpeg.org/)がインストールされていること（ダウンロードに必要）。
* AcoustID識別用にシステムに`chromaprint`（`fpcalc`バイナリ）がインストールされていること（オプション）：
  * **macOS:** `brew install chromaprint`
  * **Debian/Ubuntu:** `apt-get install libchromaprint-tools`

### インストール手順
1. **リポジトリのクローン:**
   ```bash
   git clone https://github.com/JJaroll/Cicada.git
   cd Cicada
   ```

2. **仮想環境の作成 (推奨):**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **依存関係のインストール:**
   ```bash
   pip install -r requirements.txt
   ```
   
---

## 🚀 使い方

メインファイルを実行します：

```bash
python main.py
```
*(macOSでは、`start.command`ファイルをダブルクリックするだけでも実行できます)*

これにより、ウェブブラウザでアプリケーションが`http://127.0.0.1:8000`で開きます。

---

## 📁 プロジェクト構造

| ファイル | 責任 |
|---|---|
| `main.py` | FastAPIサーバー、REST/WebSocketエンドポイント、インターフェース（HTML/CSS/JS）。 |
| `metadata_manager.py` | ウォーターフォール識別（Shazam → AcoustID → iTunes）をオーケストレーションします。 |
| `acoustid_fallback.py` | 音響指紋による二次識別。 |
| `audio_processor.py` | タグ付けとハードドライブへのファイルの保存。 |
| `download_manager.py` | Spotify接続と`yt-dlp`経由のダウンロード。 |
| `playlist_manager.py` | ローカルライブラリのインデックス作成とファジーマッチング。 |
| `dev_scripts.py` | ウェブ外で機能を実行するための診断スクリプト。 |

---

## 🔒 プライバシーとセキュリティ
**あなたのデータはあなたのデバイス上に留まります。**

Cicadaはローカルファーストのアプリケーションです。クラウドベースの音楽マネージャーとは異なり、Cicadaはあなたのリスニング習慣を追跡したり、個人情報を収集したり、音楽ライブラリのメタデータをリモートサーバーに送信したりすることはありません。

* **ローカルキー**: SpotifyおよびAcoustIDのAPIキーは、ご自身のデバイスに安全に保存されます。
* **テレメトリなし**: 追跡、分析、データ収集は一切行われません。
* **直接接続**: SpotifyやAcoustIDに接続する際、アプリケーションはそれらのサービスと直接通信します。開発者があなたのアカウント、プレイリスト、またはAPIキーにアクセスすることはありません。

---

## 🤝 貢献

貢献は大歓迎です！

1. プロジェクトを**Fork**します。
2. ブランチを作成します (`git checkout -b feature/NewFeature`)。
3. 変更をコミットします。
4. ブランチにプッシュします (`git push origin feature/NewFeature`)。
5. **Pull Request**を開きます。

## 📄 ライセンス

このプロジェクトはGNU GPLv3ライセンスの下で公開されています。
*📝 [利用規約](TERMS.md)をご確認ください。*

Created with ❤️ by **JJaroll**
