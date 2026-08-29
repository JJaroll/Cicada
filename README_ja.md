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
* **📥 マルチソース音楽ダウンロード:** **Spotify**、**YouTube Music**、**Deezer** のリンク（共有ショートリンクや公開プレイリストを含む）から楽曲、アルバム、プレイリストを解析し、`yt-dlp` を使用して最高音質で直接オーディオをダウンロードします。
* **🔄 スマート同期:** ファジーマッチングによって既存のローカルライブラリを再利用し、重複ダウンロードを防ぎながら`.m3u8`プレイリストを生成します。
* **🎵 内蔵プレーヤー:** ウェブ上でローカルのトラックを直接聴くことができます。シーク機能（HTTP Range）やアーティスト/アルバムごとのグループ化に対応しています。
* **🎨 モダンなインターフェース:** クラシックなプレーヤーのレトロモダンな美学にインスパイアされた、ライトモード（アルミニウム）とダークモード（グラファイト）のインターフェース。
* **🛡️ レジューム機能:** 中断後に作業を再開できるよう、各セッションの進行状況をリアルタイムで保存します。
* **🎧 iPod連携:** iPodを検出し、音楽とプレイリストを同期（複製されたプレイリストのインポートや評価の競合を解決する双方向同期を含む）、カバーアートを書き込み、動画・ポッドキャスト・オーディオブックを管理し、デバイス内の写真を読み取り専用で閲覧できます — すべて自動バックアップとエラー時のロールバック付き。詳細は下記の専用セクションをご覧ください。

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
   > **注:** これにはiPodモジュールの依存関係（`wasmtime`、`zstandard`、
   > `numpy`）が含まれており、数十MBの容量が追加されます。現時点では
   > 標準インストールでこれらを省略する方法はありません。iPodを持って
   > いない場合は、アプリ内の**設定**からセクションを非表示にできます
   > （後述）が、依存関係自体はインストールされたままです。

---

## 🚀 使い方

メインファイルを実行します：

```bash
python run.py
```
*(macOSでは、`start.command`ファイルをダブルクリックするだけでも実行できます)*

これにより、ウェブブラウザでアプリケーションが`http://127.0.0.1:8000`で開きます。

---

## 🎧 iPod連携

Cicadaは接続されたiPodを検出し、iTunes/Music.appを経由せずにウェブ
インターフェースから直接管理します：ライブラリの読み込み、安全な書き込み
（デバイス外での*ドライラン*計画＋自動バックアップ＋エラー時のロール
バック）、そして安全なボリュームの取り出し。

### 現在動作する機能

* **音楽とプレイリスト:** ライブラリの読み書き、プレイリストの作成、削除、
  およびサブフォルダ内の曲の自動解決を含む**ローカル/複製プレイリストの
  インポート**。
* **双方向同期:** iPod側の再生回数とスキップがCicadaに反映され、評価の
  競合は対話的に解決できます（本当に競合しうる唯一のフィールドが評価
  です — 再生回数とスキップ数は上書きではなく加算されます）。
* **カバーアート:** Cicadaがモデル化している24のデバイスファミリー全体
  で同じピクセル形式（RGB565_LE）を使って実装。そのうち14ファミリーが
  ハードウェア的にカバーアートに対応しています（残り — Shuffle、Mini、
  一部の初期クリックホイールiPod — は物理的にその機能がありません）。
  対応関係は13の関連ファミリーのうち12でlibgpodと照合して監査済みです
  （libgpodに存在しないNano 7Gは、代わりに実機で検証済み）。監査の詳細
  は[`docs/IPOD_INTEGRATION.md`](docs/IPOD_INTEGRATION.md)を参照して
  ください。
* **動画・ポッドキャスト・オーディオブック:** 完全な管理機能（読み書き、
  埋め込みチャプターなど形式固有のメタデータ）。
* **写真閲覧（読み取り専用）:** iPodの`Photo Database`およびバイナリ
  `.ithmb`ファイル（RGB565）からサムネイルと高解像度写真を直接リアル
  タイムでデコードし、写真データベースを変更することなくギャラリーと
  インタラクティブなLightboxビューアで閲覧可能。
* **表示のオン/オフ:** **設定**内のスイッチで、iPodセクション全体を
  インターフェースから非表示にできます（iPodを持っていない人向け）。
  インストールサイズの削減や何かのアンインストールは行われません —
  UIが変わるだけです。

### 動作しない機能

* **写真の変更 / 同期:** iPod上の写真の書き込み、追加、削除はサポート
  されていません（ファームウェアの整合性を保護するため、写真機能は
  100%読み取り専用として動作します）。
* **iPod touch**（およびMotorola ROKR/SLVR/RAZRの「iPod Mobile」）:
  **サポートされておらず、段階的な拡張としても予定されていません。**
  これは独自のOS（iOS）を搭載し、異なるプロトコルで同期するデバイスで
  あり、Cicadaの現在のデバイス識別と署名すべてが依存している
  FireWireGUID/HASHABのペアを持たない可能性が非常に高いです。対応する
  には既存コードの一般化ではなく、別プロジェクトが必要です。

### 検証済みモデル vs. モデル化のみ

Cicadaは、クリックホイールおよびタッチスクリーンNano（第7世代まで）の
24のデバイスファミリーを**モデル化**しています — Shuffle、Classic、
Nano 1G-7G、iPod Video/Photo/Colorなど。実際の対応範囲について正直に
言うと、**実機で検証されているのはNano 7Gのみ**です。この開発セッション
中に何度も検証されました。それ以外のコードは同じデータモデルに従って
います（可能な限りlibgpodの`itdb_device.c`と照合して監査済み）が、
対応する実機ではテストされていません。もし別のファミリーでCicadaを
使って問題を見つけた場合、それは貴重な情報です — ぜひご報告ください。

### iPod CLI (`cicada ipod`)

ウェブアプリを経由せずにターミナルからiPodを管理する（バックアップ、
復元、安全な取り出しなど）には、一度だけCicadaを編集可能モードで
インストールします：

```bash
pip install -e .
```

これにより、仮想環境の`PATH`に`cicada`実行ファイルが追加され、venvが
アクティブな間はどのディレクトリからでも利用できます：

```bash
cicada ipod status              # マウントされたiPodの識別情報と状態
cicada ipod backup              # 安全のためのスナップショット（--fullでMusic/も含む）
cicada ipod restore <ファイル>   # バックアップを復元
cicada ipod list-backups        # 既存のバックアップ一覧
cicada ipod consent             # Music.appの同意を確認/付与
cicada ipod eject               # iPodを安全に取り出す
```

すべてのオプションを見るには`cicada ipod --help`または
`cicada ipod <サブコマンド> --help`を使用してください。（このインストール
が編集可能モードなのは意図的です：アプリの静的ファイルはリポジトリの
チェックアウトを基準に実行時に解決され、パッケージ化されていません —
そのため編集不可のインストールは推奨されません。）

連携全体の技術的な詳細は
[`docs/IPOD_INTEGRATION.md`](docs/IPOD_INTEGRATION.md)に、段階ごとの
vendoring記録は[`docs/VENDORED.md`](docs/VENDORED.md)にあります。

---

## 📁 プロジェクト構造

| ファイル | 責任 |
|---|---|
| `run.py` | エントリーポイント。アプリ本体は `cicada/core/main.py`（FastAPIサーバー、REST/WebSocketエンドポイント、HTML/CSS/JSインターフェース）。 |
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

**サードパーティのコード:** iPod連携モジュールには、
[iOpenPod](https://github.com/TheRealSavi/iOpenPod)（MIT）および
[dstaley/hashab](https://github.com/dstaley/hashab)（The
Unlicense/パブリックドメイン）から取り込んだコードが含まれています。
どちらもGPLv3と互換性があり、その条項の下で再配布されています。
完全な帰属表示は[`NOTICE`](NOTICE)を、何が・どこから・どのコミットで
取り込まれたかの詳細は[`docs/VENDORED.md`](docs/VENDORED.md)を
ご覧ください。

Created with ❤️ by **JJaroll**
