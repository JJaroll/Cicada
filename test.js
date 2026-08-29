// Archivo de pruebas y scripts auxiliares de interfaz.

            const I18N = {
                es: {
                    nav_metadata: "Metadatos", nav_download: "Descarga", nav_playlist: "Playlist", nav_library: "Biblioteca",
                    settings_tooltip: "Ajustes", connection_tooltip: "Estado de conexión",
                    settings_title: "Ajustes",
                    settings_theme_title: "TEMA",
                    settings_theme_dark: "Grafito",
                    settings_theme_light: "Aluminio",
                    settings_color_title: "COLOR NANO",
                    settings_language_title: "Idioma",
                    settings_spotify_title: "Cuenta de Spotify",
                    settings_spotify_connected: "Conectado a Spotify",
                    settings_spotify_not_connected: "No conectado a Spotify",
                    settings_spotify_connect_btn: "Conectar con Spotify",
                    settings_spotify_reconnect_btn: "Reconectar con Spotify",
                    settings_credentials_title: "Claves de Acceso",
                    settings_credentials_help_tooltip: "¿Cómo obtener las claves?",
                    settings_acoustid_label: "Clave de AcoustID",
                    settings_spotify_id_label: "ID de Cliente de Spotify",
                    settings_spotify_secret_label: "Clave Secreta de Spotify",
                    settings_identification_title: "Identificación de Canciones",
                    settings_plan_c_label: "Adivinar por el nombre del archivo cuando no se reconoce la canción",
                    settings_plan_c_hint: "Apagado por defecto: suele ser poco preciso. Si está apagado, esos archivos se reportan como error en vez de adivinar el título/artista.",
                    settings_folders_title: "Carpetas Predeterminadas",
                    settings_library_dir_label: "Carpeta de tu Biblioteca",
                    settings_input_dir_label: "Carpeta de Origen (Metadatos)",
                    settings_output_dir_label: "Carpeta de Destino (Metadatos)",
                    about_tooltip: "Sobre Cicada",
                    about_version: "Versión 1.1.1",
                    about_description: "Herramienta local de organización musical y sincronización automática de metadatos de alta fidelidad.",
                    about_author_label: "Desarrollado por",
                    about_license: "Distribuido bajo Licencia GNU GPLv3",
                    about_terms: "Términos y Condiciones",
                    about_github_btn: "Ver en GitHub",
                    about_contribute_btn: "Contribuir",
                    kofi_support_title: "¡Gran trabajo!",
                    kofi_support_message: "Has etiquetado {count} canciones en {time}. Hacer esto a mano te habría tomado {manual_time}. Apoya a mantener Cicada libre de anuncios.",
                    update_available_text: "Nueva versión disponible: v{version}",
                    update_available_link: "Ver última versión",
                    common_choose: "Elegir", common_cancel: "Cancelar", common_save: "Guardar",
                    settings_saving: "Guardando...", settings_saved: "Guardado ✓",
                    process_folders_title: "Carpetas de Trabajo",
                    process_source_label: "Carpeta de Origen", process_dest_label: "Carpeta de Destino",
                    process_start_btn: "Iniciar", process_cancel_btn: "Cancelar", process_cancel_full: "Cancelar Proceso",
                    process_recent_activity_title: "Actividad Reciente",
                    process_no_files_yet: "Todavía no se procesó ningún archivo en esta sesión.",
                    process_view_more: "Ver más",
                    process_progress_title: "Progreso", process_connection_title: "Conexión",
                    process_activity_log_title: "Registro de Actividad",
                    process_log_ready: "Listo. Esperando instrucciones...",
                    process_connecting_btn: "Conectando...", process_cancelling_btn: "Cancelando...",
                    process_waiting_first_file: "Esperando el primer archivo...",
                    process_scanning_library: "Escaneando biblioteca",
                    process_starting_status: "Iniciando", process_starting_track: "Iniciando...",
                    process_track_of: "Pista {current} de {total}",
                    process_skipped: "Saltado", process_processing: "Procesando",
                    process_done_all: "Todas las pistas procesadas", process_stopped: "Proceso detenido",
                    process_cancelled_status: "Cancelado", process_completed_status: "Completado",
                    process_report_saved: "Reporte guardado en: ",
                    ws_connected: "Conectado", ws_connecting_short: "Conectando", ws_connecting_dots: "Conectando...",
                    ws_error: "Error", ws_disconnected: "Desconectado",
                    log_ws_error: "Error en la conexión con el servidor (WebSocket desconectado).",
                    log_ws_closed: "Conexión cerrada. Refresca la página para reconectar.",
                    alert_both_paths_required: "Ambas rutas son requeridas.",
                    log_starting_process: "Iniciando petición de procesamiento...",
                    log_connect_error: "Error al conectar con el servidor: ",
                    spotify_link_title: "Enlace de Spotify", spotify_analyze_btn: "Analizar",
                    spotify_tracks_found_title: "Canciones Encontradas", spotify_select_all: "Seleccionar Todas",
                    spotify_hint_paste_link: "Pega un link de Spotify (canción, álbum o playlist) y presiona Analizar para ver las canciones.",
                    spotify_download_selected_btn: "Descargar Seleccionadas",
                    alert_paste_link_first: "Pega un link de Spotify primero.",
                    spotify_analyzing_status: "Analizando enlace...", spotify_analyzing_btn: "Analizando...",
                    error_unknown: "Error desconocido", error_prefix: "Error: ",
                    spotify_could_not_analyze: "No se pudo analizar el enlace.",
                    spotify_no_tracks_found: "No se encontraron pistas en ese enlace.",
                    track_untitled: "Sin título", track_unknown_artist: "Artista Desconocido", track_unknown_album: "Álbum Desconocido",
                    alert_choose_dest_folder: "Elige una carpeta de destino.",
                    alert_select_at_least_one_track: "Selecciona al menos una pista.",
                    spotify_downloading_btn: "Descargando...",
                    log_starting_spotify_download: "Iniciando descarga de {n} pista(s) de Spotify...",
                    spotify_preparing_download: "Preparando descarga",
                    spotify_waiting_first_track: "Esperando la primera pista...",
                    playlists_my_playlists_title: "Mis Playlists", playlists_loading: "Cargando tus playlists...",
                    playlists_choose_hint: "Elige una playlist de la izquierda para ver sus canciones.",
                    playlists_choose_title: "Elige una playlist",
                    playlists_local_library_label: "Tu Biblioteca Local", playlists_replicate_btn: "Replicar Playlist",
                    playlists_preview_title: "Vista Previa de la Playlist",
                    playlists_preview_hint: "Elige una playlist y presiona Replicar Playlist para armar aquí la vista previa. Vas a poder arrastrar las canciones para reordenarlas y destildar las que no quieras incluir.",
                    playlists_m3u8_name_placeholder: "Nombre de la playlist", playlists_generate_btn: "Generar Playlist",
                    playlists_no_playlists_found: "No se encontraron playlists en tu cuenta.",
                    playlists_track_count_suffix: " pistas",
                    playlists_loading_songs: "Cargando canciones...", playlists_no_songs: "Esta playlist no tiene canciones.",
                    alert_choose_local_library_first: "Elige la carpeta de tu biblioteca local primero.",
                    alert_playlist_no_songs_loaded: "Esta playlist no tiene canciones cargadas.",
                    confirm_replicate: "Se van a buscar las {n} canciones de '{name}' en tu biblioteca local ({dir}) para armar una playlist .m3u8.\\n\\n¿Continuar?",
                    playlists_searching_btn: "Buscando...",
                    alert_error_searching_matches: "Error buscando coincidencias: ",
                    playlists_not_found_suffix: " · no encontrada en tu biblioteca",
                    playlists_summary: "{matched}/{total} encontradas · {included} incluidas",
                    alert_error_associating_file: "Error asociando el archivo: ",
                    confirm_manual_match: "Se van a reescribir los tags de:\\n{path}\\n\\ncon los datos de '{artist} - {title}' (Spotify), y el archivo se va a reorganizar dentro de tu biblioteca.\\n\\n¿Continuar?",
                    alert_no_songs_to_generate: "No hay canciones incluidas para generar la playlist.",
                    playlists_generating_btn: "Generando...",
                    alert_playlist_generated: "Playlist generada en: ",
                    log_playlist_generated: "Playlist '{name}' generada en: {path}",
                    alert_error_generating_playlist: "Error generando la playlist: ",
                    default_playlist_name: "Mi Playlist", default_playlist_name_generic: "Playlist",
                    library_my_library_title: "Mi Biblioteca", library_save_scan_btn: "Guardar y Buscar Canciones",
                    library_group_by_label: "Agrupar por", library_group_all: "Todas", library_group_artist: "Artista",
                    library_group_album: "Álbum", library_group_playlist: "Playlist",
                    library_configure_hint: "Configura la carpeta de tu biblioteca arriba para verla aquí.",
                    alert_choose_folder_first: "Elige una carpeta primero.",
                    alert_error_saving_config: "Error guardando la configuración: ",
                    library_scanning: "Escaneando biblioteca...", library_track_count_suffix: " canciones",
                    library_no_songs_in_folder: "No se encontraron canciones en esa carpeta.",
                    library_no_playlist_group: "Sin playlist",
                    library_search_placeholder: "Buscar por título, artista o álbum...",
                    library_no_search_results: "No se encontraron canciones que coincidan con la búsqueda.",
                    library_sort_alpha: "A-Z", library_sort_tooltip: "Orden alfabético",
                    library_view_list: "Lista", library_view_grid: "Grilla",
                    alert_error_saving_settings: "Error guardando ajustes: ",
                    player_waiting_status: "En espera", player_cicada_label: "Cicada", player_no_cover: "Sin carátula",
                    player_waiting_title: "En espera...", player_configure_source_hint: "Configura una fuente para comenzar",
                    player_remaining_time_label: "Tiempo Restante", player_progress_label: "Avance",
                    player_cancel_process_btn: "Cancelar Proceso", player_title: "Reproductor",
                    player_nothing_playing: "Nada sonando", player_choose_song_hint: "Elige una canción de tu biblioteca"
                },
                en: {
                    nav_metadata: "Metadata", nav_download: "Download", nav_playlist: "Playlist", nav_library: "Library",
                    settings_tooltip: "Settings", connection_tooltip: "Connection status",
                    settings_title: "Settings",
                    settings_theme_title: "THEME",
                    settings_theme_dark: "Graphite",
                    settings_theme_light: "Aluminum",
                    settings_color_title: "NANO COLOR",
                    settings_language_title: "Language",
                    settings_spotify_title: "Spotify Account",
                    settings_spotify_connected: "Connected to Spotify",
                    settings_spotify_not_connected: "Not connected to Spotify",
                    settings_spotify_connect_btn: "Connect with Spotify",
                    settings_spotify_reconnect_btn: "Reconnect with Spotify",
                    settings_credentials_title: "Access Keys",
                    settings_credentials_help_tooltip: "How do I get these keys?",
                    settings_acoustid_label: "AcoustID Key",
                    settings_spotify_id_label: "Spotify Client ID",
                    settings_spotify_secret_label: "Spotify Client Secret",
                    settings_identification_title: "Song Identification",
                    settings_plan_c_label: "Guess from the file name when a song isn't recognized",
                    settings_plan_c_hint: "Off by default: it tends to be inaccurate. When off, those files are reported as errors instead of guessing the title/artist.",
                    settings_folders_title: "Default Folders",
                    settings_library_dir_label: "Your Library Folder",
                    settings_input_dir_label: "Source Folder (Metadata)",
                    settings_output_dir_label: "Destination Folder (Metadata)",
                    about_tooltip: "About Cicada",
                    about_version: "Version 1.1.1",
                    about_description: "Local music organization tool with high-fidelity automatic metadata syncing.",
                    about_author_label: "Developed by",
                    about_license: "Distributed under the GNU GPLv3 License",
                    about_terms: "Terms and Conditions",
                    about_github_btn: "View on GitHub",
                    about_contribute_btn: "Contribute",
                    kofi_support_title: "Great work!",
                    kofi_support_message: "You've tagged {count} songs in {time}. Doing this by hand would have taken you {manual_time}. Support keeping Cicada ad-free.",
                    update_available_text: "New version available: v{version}",
                    update_available_link: "View latest release",
                    common_choose: "Choose", common_cancel: "Cancel", common_save: "Save",
                    settings_saving: "Saving...", settings_saved: "Saved ✓",
                    process_folders_title: "Working Folders",
                    process_source_label: "Source Folder", process_dest_label: "Destination Folder",
                    process_start_btn: "Start", process_cancel_btn: "Cancel", process_cancel_full: "Cancel Process",
                    process_recent_activity_title: "Recent Activity",
                    process_no_files_yet: "No files have been processed in this session yet.",
                    process_view_more: "View more",
                    process_progress_title: "Progress", process_connection_title: "Connection",
                    process_activity_log_title: "Activity Log",
                    process_log_ready: "Ready. Waiting for instructions...",
                    process_connecting_btn: "Connecting...", process_cancelling_btn: "Cancelling...",
                    process_waiting_first_file: "Waiting for the first file...",
                    process_scanning_library: "Scanning library",
                    process_starting_status: "Starting", process_starting_track: "Starting...",
                    process_track_of: "Track {current} of {total}",
                    process_skipped: "Skipped", process_processing: "Processing",
                    process_done_all: "All tracks processed", process_stopped: "Process stopped",
                    process_cancelled_status: "Cancelled", process_completed_status: "Completed",
                    process_report_saved: "Report saved at: ",
                    ws_connected: "Connected", ws_connecting_short: "Connecting", ws_connecting_dots: "Connecting...",
                    ws_error: "Error", ws_disconnected: "Disconnected",
                    log_ws_error: "Error connecting to the server (WebSocket disconnected).",
                    log_ws_closed: "Connection closed. Refresh the page to reconnect.",
                    alert_both_paths_required: "Both paths are required.",
                    log_starting_process: "Starting processing request...",
                    log_connect_error: "Error connecting to the server: ",
                    spotify_link_title: "Spotify Link", spotify_analyze_btn: "Analyze",
                    spotify_tracks_found_title: "Songs Found", spotify_select_all: "Select All",
                    spotify_hint_paste_link: "Paste a Spotify link (song, album or playlist) and press Analyze to see the songs.",
                    spotify_download_selected_btn: "Download Selected",
                    alert_paste_link_first: "Paste a Spotify link first.",
                    spotify_analyzing_status: "Analyzing link...", spotify_analyzing_btn: "Analyzing...",
                    error_unknown: "Unknown error", error_prefix: "Error: ",
                    spotify_could_not_analyze: "Couldn't analyze the link.",
                    spotify_no_tracks_found: "No tracks found in that link.",
                    track_untitled: "Untitled", track_unknown_artist: "Unknown Artist", track_unknown_album: "Unknown Album",
                    alert_choose_dest_folder: "Choose a destination folder.",
                    alert_select_at_least_one_track: "Select at least one track.",
                    spotify_downloading_btn: "Downloading...",
                    log_starting_spotify_download: "Starting download of {n} Spotify track(s)...",
                    spotify_preparing_download: "Preparing download",
                    spotify_waiting_first_track: "Waiting for the first track...",
                    playlists_my_playlists_title: "My Playlists", playlists_loading: "Loading your playlists...",
                    playlists_choose_hint: "Choose a playlist on the left to see its songs.",
                    playlists_choose_title: "Choose a playlist",
                    playlists_local_library_label: "Your Local Library", playlists_replicate_btn: "Replicate Playlist",
                    playlists_preview_title: "Playlist Preview",
                    playlists_preview_hint: "Choose a playlist and press Replicate Playlist to build the preview here. You'll be able to drag songs to reorder them and uncheck the ones you don't want to include.",
                    playlists_m3u8_name_placeholder: "Playlist name", playlists_generate_btn: "Generate Playlist",
                    playlists_no_playlists_found: "No playlists found in your account.",
                    playlists_track_count_suffix: " tracks",
                    playlists_loading_songs: "Loading songs...", playlists_no_songs: "This playlist has no songs.",
                    alert_choose_local_library_first: "Choose your local library folder first.",
                    alert_playlist_no_songs_loaded: "This playlist has no songs loaded.",
                    confirm_replicate: "The {n} songs from '{name}' will be searched for in your local library ({dir}) to build an .m3u8 playlist.\\n\\nContinue?",
                    playlists_searching_btn: "Searching...",
                    alert_error_searching_matches: "Error searching for matches: ",
                    playlists_not_found_suffix: " · not found in your library",
                    playlists_summary: "{matched}/{total} found · {included} included",
                    alert_error_associating_file: "Error associating the file: ",
                    confirm_manual_match: "The tags of:\\n{path}\\n\\nwill be rewritten with the data from '{artist} - {title}' (Spotify), and the file will be reorganized within your library.\\n\\nContinue?",
                    alert_no_songs_to_generate: "There are no songs included to generate the playlist.",
                    playlists_generating_btn: "Generating...",
                    alert_playlist_generated: "Playlist generated at: ",
                    log_playlist_generated: "Playlist '{name}' generated at: {path}",
                    alert_error_generating_playlist: "Error generating the playlist: ",
                    default_playlist_name: "My Playlist", default_playlist_name_generic: "Playlist",
                    library_my_library_title: "My Library", library_save_scan_btn: "Save and Scan Songs",
                    library_group_by_label: "Group by", library_group_all: "All", library_group_artist: "Artist",
                    library_group_album: "Album", library_group_playlist: "Playlist",
                    library_configure_hint: "Set your library folder above to see it here.",
                    alert_choose_folder_first: "Choose a folder first.",
                    alert_error_saving_config: "Error saving the configuration: ",
                    library_scanning: "Scanning library...", library_track_count_suffix: " songs",
                    library_no_songs_in_folder: "No songs found in that folder.",
                    library_no_playlist_group: "No playlist",
                    library_search_placeholder: "Search by title, artist or album...",
                    library_no_search_results: "No songs match your search.",
                    library_sort_alpha: "A-Z", library_sort_tooltip: "Alphabetical order",
                    library_view_list: "List", library_view_grid: "Grid",
                    alert_error_saving_settings: "Error saving settings: ",
                    player_waiting_status: "Waiting", player_cicada_label: "Cicada", player_no_cover: "No cover",
                    player_waiting_title: "Waiting...", player_configure_source_hint: "Set up a source to get started",
                    player_remaining_time_label: "Time Remaining", player_progress_label: "Progress",
                    player_cancel_process_btn: "Cancel Process", player_title: "Player",
                    player_nothing_playing: "Nothing playing", player_choose_song_hint: "Choose a song from your library"
                },
                ja: {
                    nav_metadata: "メタデータ", nav_download: "ダウンロード", nav_playlist: "プレイリスト", nav_library: "ライブラリ",
                    settings_tooltip: "設定", connection_tooltip: "接続状態",
                    settings_title: "設定",
                    settings_theme_title: "テーマ",
                    settings_theme_dark: "グラファイト",
                    settings_theme_light: "アルミニウム",
                    settings_color_title: "ナノカラー",
                    settings_language_title: "言語",
                    settings_spotify_title: "Spotifyアカウント",
                    settings_spotify_connected: "Spotifyに接続済み",
                    settings_spotify_not_connected: "Spotifyに未接続",
                    settings_spotify_connect_btn: "Spotifyで接続",
                    settings_spotify_reconnect_btn: "Spotifyに再接続",
                    settings_credentials_title: "アクセスキー",
                    settings_credentials_help_tooltip: "キーの取得方法は?",
                    settings_acoustid_label: "AcoustIDキー",
                    settings_spotify_id_label: "SpotifyクライアントID",
                    settings_spotify_secret_label: "Spotifyクライアントシークレット",
                    settings_identification_title: "楽曲の識別",
                    settings_plan_c_label: "認識できない場合はファイル名から推測する",
                    settings_plan_c_hint: "デフォルトではオフです（精度が低いため）。オフの場合、認識できなかったファイルは推測せずエラーとして報告されます。",
                    settings_folders_title: "デフォルトフォルダ",
                    settings_library_dir_label: "ライブラリフォルダ",
                    settings_input_dir_label: "入力フォルダ（メタデータ）",
                    settings_output_dir_label: "出力フォルダ（メタデータ）",
                    about_tooltip: "Cicadaについて",
                    about_version: "バージョン 1.1.1",
                    about_description: "高精度なメタデータの自動同期を行う、ローカル音楽整理ツール。",
                    about_author_label: "開発者:",
                    about_license: "GNU GPLv3ライセンスの下で配布",
                    about_terms: "利用規約",
                    about_github_btn: "GitHubで見る",
                    about_contribute_btn: "支援する",
                    kofi_support_title: "お疲れ様でした!",
                    kofi_support_message: "{count}曲にタグ付けし、所要時間は{time}でした。手作業で行うと{manual_time}かかっていたはずです。Cicadaを広告なしで維持するためにご支援ください。",
                    update_available_text: "新しいバージョンがあります: v{version}",
                    update_available_link: "最新リリースを見る",
                    common_choose: "選択", common_cancel: "キャンセル", common_save: "保存",
                    settings_saving: "保存中...", settings_saved: "保存しました ✓",
                    process_folders_title: "作業フォルダ",
                    process_source_label: "入力フォルダ", process_dest_label: "出力フォルダ",
                    process_start_btn: "開始", process_cancel_btn: "キャンセル", process_cancel_full: "処理をキャンセル",
                    process_recent_activity_title: "最近のアクティビティ",
                    process_no_files_yet: "このセッションではまだファイルが処理されていません。",
                    process_view_more: "もっと見る",
                    process_progress_title: "進捗", process_connection_title: "接続",
                    process_activity_log_title: "アクティビティログ",
                    process_log_ready: "準備完了。指示を待機中...",
                    process_connecting_btn: "接続中...", process_cancelling_btn: "キャンセル中...",
                    process_waiting_first_file: "最初のファイルを待機中...",
                    process_scanning_library: "ライブラリをスキャン中",
                    process_starting_status: "開始中", process_starting_track: "開始中...",
                    process_track_of: "{total}中{current}曲目",
                    process_skipped: "スキップ", process_processing: "処理中",
                    process_done_all: "すべての曲を処理しました", process_stopped: "処理を停止しました",
                    process_cancelled_status: "キャンセル済み", process_completed_status: "完了",
                    process_report_saved: "レポートの保存先: ",
                    ws_connected: "接続済み", ws_connecting_short: "接続中", ws_connecting_dots: "接続中...",
                    ws_error: "エラー", ws_disconnected: "切断されました",
                    log_ws_error: "サーバーとの接続エラー（WebSocket切断）。",
                    log_ws_closed: "接続が閉じられました。ページを更新して再接続してください。",
                    alert_both_paths_required: "両方のパスが必要です。",
                    log_starting_process: "処理リクエストを開始しています...",
                    log_connect_error: "サーバーへの接続エラー: ",
                    spotify_link_title: "Spotifyリンク", spotify_analyze_btn: "分析",
                    spotify_tracks_found_title: "見つかった楽曲", spotify_select_all: "すべて選択",
                    spotify_hint_paste_link: "Spotifyのリンク（楽曲、アルバム、またはプレイリスト）を貼り付けて「分析」を押してください。",
                    spotify_download_selected_btn: "選択した曲をダウンロード",
                    alert_paste_link_first: "まずSpotifyのリンクを貼り付けてください。",
                    spotify_analyzing_status: "リンクを分析中...", spotify_analyzing_btn: "分析中...",
                    error_unknown: "不明なエラー", error_prefix: "エラー: ",
                    spotify_could_not_analyze: "リンクを分析できませんでした。",
                    spotify_no_tracks_found: "このリンクには楽曲が見つかりませんでした。",
                    track_untitled: "タイトルなし", track_unknown_artist: "不明のアーティスト", track_unknown_album: "不明のアルバム",
                    alert_choose_dest_folder: "保存先フォルダを選択してください。",
                    alert_select_at_least_one_track: "少なくとも1曲を選択してください。",
                    spotify_downloading_btn: "ダウンロード中...",
                    log_starting_spotify_download: "Spotifyの{n}曲のダウンロードを開始しています...",
                    spotify_preparing_download: "ダウンロードを準備中",
                    spotify_waiting_first_track: "最初の曲を待機中...",
                    playlists_my_playlists_title: "マイプレイリスト", playlists_loading: "プレイリストを読み込み中...",
                    playlists_choose_hint: "左のリストからプレイリストを選んで曲を表示します。",
                    playlists_choose_title: "プレイリストを選択",
                    playlists_local_library_label: "ローカルライブラリ", playlists_replicate_btn: "プレイリストを複製",
                    playlists_preview_title: "プレイリストプレビュー",
                    playlists_preview_hint: "プレイリストを選んで「プレイリストを複製」を押すと、ここにプレビューが作成されます。曲をドラッグして並び替えたり、不要な曲のチェックを外したりできます。",
                    playlists_m3u8_name_placeholder: "プレイリスト名", playlists_generate_btn: "プレイリストを作成",
                    playlists_no_playlists_found: "あなたのアカウントにプレイリストが見つかりませんでした。",
                    playlists_track_count_suffix: " 曲",
                    playlists_loading_songs: "楽曲を読み込み中...", playlists_no_songs: "このプレイリストには楽曲がありません。",
                    alert_choose_local_library_first: "まずローカルライブラリのフォルダを選択してください。",
                    alert_playlist_no_songs_loaded: "このプレイリストには読み込まれた楽曲がありません。",
                    confirm_replicate: "'{name}'の{n}曲をローカルライブラリ（{dir}）から検索して.m3u8プレイリストを作成します。\\n\\n続けますか？",
                    playlists_searching_btn: "検索中...",
                    alert_error_searching_matches: "一致する曲の検索中にエラーが発生しました: ",
                    playlists_not_found_suffix: " ・ ライブラリ内に見つかりません",
                    playlists_summary: "{matched}/{total} 件一致 ・ {included} 件を含む",
                    alert_error_associating_file: "ファイルの関連付け中にエラーが発生しました: ",
                    confirm_manual_match: "次のファイルのタグを書き換えます:\\n{path}\\n\\nSpotifyの'{artist} - {title}'のデータで上書きし、ファイルはライブラリ内で整理されます。\\n\\n続けますか？",
                    alert_no_songs_to_generate: "プレイリストを作成するための曲が含まれていません。",
                    playlists_generating_btn: "作成中...",
                    alert_playlist_generated: "プレイリストを作成しました: ",
                    log_playlist_generated: "プレイリスト「{name}」を作成しました: {path}",
                    alert_error_generating_playlist: "プレイリストの作成中にエラーが発生しました: ",
                    default_playlist_name: "マイプレイリスト", default_playlist_name_generic: "プレイリスト",
                    library_my_library_title: "マイライブラリ", library_save_scan_btn: "保存して曲を検索",
                    library_group_by_label: "グループ化", library_group_all: "すべて", library_group_artist: "アーティスト",
                    library_group_album: "アルバム", library_group_playlist: "プレイリスト",
                    library_configure_hint: "上のライブラリフォルダを設定するとここに表示されます。",
                    alert_choose_folder_first: "まずフォルダを選択してください。",
                    alert_error_saving_config: "設定の保存中にエラーが発生しました: ",
                    library_scanning: "ライブラリをスキャン中...", library_track_count_suffix: " 曲",
                    library_no_songs_in_folder: "このフォルダには楽曲が見つかりませんでした。",
                    library_no_playlist_group: "プレイリストなし",
                    library_search_placeholder: "タイトル、アーティスト、アルバムで検索...",
                    library_no_search_results: "検索に一致する曲が見つかりませんでした。",
                    library_sort_alpha: "A-Z", library_sort_tooltip: "アルファベット順",
                    library_view_list: "リスト", library_view_grid: "グリッド",
                    alert_error_saving_settings: "設定の保存中にエラーが発生しました: ",
                    player_waiting_status: "待機中", player_cicada_label: "Cicada", player_no_cover: "カバーなし",
                    player_waiting_title: "待機中...", player_configure_source_hint: "ソースを設定して開始してください",
                    player_remaining_time_label: "残り時間", player_progress_label: "進捗",
                    player_cancel_process_btn: "処理をキャンセル", player_title: "プレーヤー",
                    player_nothing_playing: "再生中の曲はありません", player_choose_song_hint: "ライブラリから曲を選択してください"
                }
            };

            let currentLang = localStorage.getItem("cicada_lang") || "es";

            function t(key, vars) {
                let dict = I18N[currentLang] || I18N.es;
                let str = dict[key] !== undefined ? dict[key] : (I18N.es[key] !== undefined ? I18N.es[key] : key);
                if (vars) {
                    Object.keys(vars).forEach(function(k) {
                        str = str.split("{" + k + "}").join(vars[k]);
                    });
                }
                return str;
            }

            function applyLanguage(lang) {
                currentLang = I18N[lang] ? lang : "es";
                localStorage.setItem("cicada_lang", currentLang);
                document.documentElement.lang = currentLang;

                document.querySelectorAll("[data-i18n]").forEach(function(el) {
                    el.textContent = t(el.getAttribute("data-i18n"));
                });
                document.querySelectorAll("[data-i18n-placeholder]").forEach(function(el) {
                    el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
                });
                document.querySelectorAll("[data-i18n-title]").forEach(function(el) {
                    el.setAttribute("title", t(el.getAttribute("data-i18n-title")));
                });
                document.querySelectorAll(".lang-btn").forEach(function(btn) {
                    btn.classList.toggle("active", btn.dataset.lang === currentLang);
                });

                if (typeof refreshSpotifyDownloadButton === "function") refreshSpotifyDownloadButton();
                if (typeof resolvedSpotifyTracks !== "undefined" && resolvedSpotifyTracks.length > 0) renderSpotifyTrackList();
                if (typeof userPlaylists !== "undefined" && userPlaylists.length > 0) loadSpotifyPlaylists();
                if (typeof replicateMatches !== "undefined" && replicateMatches.length > 0) renderReplicateTrackList();
                if (typeof libraryTracks !== "undefined" && libraryTracks.length > 0) {
                    renderLibraryBrowser();
                    let libCountEl = document.getElementById("library-track-count");
                    if (libCountEl) libCountEl.textContent = libraryTracks.length + t("library_track_count_suffix");
                }
                let settingsModal = document.getElementById("settings-modal");
                if (settingsModal && !settingsModal.classList.contains("hidden") && typeof refreshSpotifyAuthStatus === "function") {
                    refreshSpotifyAuthStatus();
                }

                if (typeof setWsStatus === "function") setWsStatus(currentWsStatusKey, currentWsColor);
                if (typeof setStatusPill === "function") setStatusPill(currentStatusPillKey, currentStatusPillColor);
                if (!hasStartedProcessing) {
                    let tt = document.getElementById("track-title");
                    let ts = document.getElementById("track-subtitle");
                    if (tt) tt.textContent = t("player_waiting_title");
                    if (ts) ts.textContent = t("player_configure_source_hint");
                }
                if (!hasPlayedTrack) {
                    let ptt = document.getElementById("playerTrackTitle");
                    let pta = document.getElementById("playerTrackArtist");
                    if (ptt) ptt.textContent = t("player_nothing_playing");
                    if (pta) pta.textContent = t("player_choose_song_hint");
                }
            }

            let wsUrl = (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host + "/ws";
            let ws = new WebSocket(wsUrl);

            let logContainer = document.getElementById("log-container");
            let bar = document.getElementById("bar");
            let progressLabel = document.getElementById("progress_label");
            let etaDisplay = document.getElementById("eta_display");
            let statPct = document.getElementById("stat-progress-pct");
            let statCount = document.getElementById("stat-progress-count");
            let statWs = document.getElementById("stat-ws-status");
            let wsStatusLabel = document.getElementById("ws-status-label");
            let wsStatusDot = document.getElementById("ws-status-dot");
            let statusPill = document.getElementById("status-pill");
            let trackTitle = document.getElementById("track-title");
            let trackSubtitle = document.getElementById("track-subtitle");
            let processFileGrid = document.getElementById("process-file-grid");
            let libraryAudio = document.getElementById("library-audio");

            let sessionFiles = [];
            let hasStartedProcessing = false;
            let hasPlayedTrack = false;
            let currentWsStatusKey = "ws_connecting_short";
            let currentWsColor = "#9ca3af";
            let currentStatusPillKey = "player_waiting_status";
            let currentStatusPillColor = "#10b981";

            function showView(name) {
                document.querySelectorAll(".view").forEach(function(el) { el.classList.remove("active"); });
                document.getElementById("view-" + name).classList.add("active");
                document.querySelectorAll(".nav-item").forEach(function(el) {
                    if (el.dataset.view === name) {
                        el.classList.add("nav-item-active");
                        el.classList.remove("nav-item-inactive");
                    } else {
                        el.classList.remove("nav-item-active");
                        el.classList.add("nav-item-inactive");
                    }
                });
                let processModule = document.getElementById("process-module");
                let progressPanel = document.getElementById("progress-panel");
                let playerPanel = document.getElementById("player-panel");
                if (name === "playlists") {
                    processModule.style.display = "none";
                } else if (name === "library") {
                    processModule.style.display = "flex";
                    progressPanel.classList.add("hidden");
                    progressPanel.classList.remove("flex");
                    playerPanel.classList.remove("hidden");
                    playerPanel.classList.add("flex");
                } else {
                    processModule.style.display = "flex";
                    playerPanel.classList.add("hidden");
                    playerPanel.classList.remove("flex");
                    progressPanel.classList.remove("hidden");
                    progressPanel.classList.add("flex");
                }
            }

            function setWsStatus(key, color) {
                currentWsStatusKey = key;
                currentWsColor = color;
                let label = t(key);
                if (statWs) statWs.textContent = label;
                if (wsStatusLabel) wsStatusLabel.textContent = label;
                if (wsStatusDot) wsStatusDot.style.backgroundColor = color;
            }

            function setStatusPill(key, colorHex) {
                currentStatusPillKey = key;
                currentStatusPillColor = colorHex;
                if (!statusPill) return;
                statusPill.textContent = t(key);
                statusPill.style.color = colorHex;
                statusPill.style.backgroundColor = colorHex + "33";
            }

            function appendLog(message, kind) {
                let colorClass = {
                    "error": "text-[#f43f5e]",
                    "success": "text-secondary",
                    "info": "text-accent",
                    "detail": "text-muted/50 pl-3",
                    "skip": "text-[#f59e0b]"
                }[kind] || "text-muted/70";
                let p = document.createElement("p");
                p.className = "mt-1 " + colorClass;
                p.textContent = "> " + message;
                logContainer.appendChild(p);
                logContainer.scrollTop = logContainer.scrollHeight;
            }

            function fileCardHtml(name, sub) {
                return '<div class="bg-btn border border-theme rounded-lg p-3 flex items-center gap-3">' +
                    '<div class="w-8 h-8 rounded bg-accent/20 flex items-center justify-center flex-shrink-0">' +
                    '<span class="material-symbols-outlined text-accent text-[18px]">audio_file</span></div>' +
                    '<div class="overflow-hidden"><p class="font-data-sm text-[13px] truncate">' + name + '</p>' +
                    '<p class="font-label-caps text-[10px] text-muted/40">' + sub + '</p></div></div>';
            }

            function addFileCard(name, sub) {
                sessionFiles.unshift({name: name, sub: sub});
                if (sessionFiles.length > 24) sessionFiles.pop();
                renderFileGrids();
            }

            function renderFileGrids() {
                if (sessionFiles.length === 0) return;
                let cardsHtml = sessionFiles.map(function(f) { return fileCardHtml(f.name, f.sub); }).join("");
                if (processFileGrid) processFileGrid.innerHTML = cardsHtml;
            }

            async function pickFolder(inputId) {
                try {
                    let res = await fetch('/api/select_folder');
                    let data = await res.json();
                    if (data.path) {
                        document.getElementById(inputId).value = data.path;
                    }
                } catch (e) {
                    console.error("Error al seleccionar carpeta:", e);
                }
            }

            ws.onopen = function() {
                setWsStatus("ws_connected", "#10b981");
            };

            ws.onerror = function() {
                appendLog(t("log_ws_error"), "error");
                setWsStatus("ws_error", "#f43f5e");
                resetUi();
            };

            ws.onclose = function() {
                appendLog(t("log_ws_closed"), "skip");
                setWsStatus("ws_disconnected", "#f43f5e");
                resetUi();
            };

            ws.onmessage = function(event) {
                let data = JSON.parse(event.data);

                if (data.eta) {
                    etaDisplay.textContent = data.eta;
                }

                if (data.type === 'progress') {
                    let pct = Math.round((data.current / data.total) * 100);
                    progressLabel.textContent = pct + "%";
                    bar.style.width = pct + "%";
                    statCount.textContent = data.current + "/" + data.total;
                    statPct.textContent = pct + "%";

                    let isSkipped = data.file.startsWith("(Saltado)");
                    hasStartedProcessing = true;
                    trackTitle.textContent = data.file;
                    trackSubtitle.textContent = t("process_track_of", {current: data.current, total: data.total});
                    setStatusPill(isSkipped ? "process_skipped" : "process_processing", isSkipped ? "#f59e0b" : "#10b981");

                    appendLog("[" + data.current + "/" + data.total + "] " + data.file, isSkipped ? "skip" : "success");
                    addFileCard(data.file, t("process_track_of", {current: data.current, total: data.total}));
                } else if (data.type === 'detail') {
                    appendLog(data.message, "detail");
                } else if (data.type === 'cover') {
                    let img = document.getElementById("currentCover");
                    let placeholder = document.getElementById("coverPlaceholder");
                    if (data.url) {
                        img.src = data.url;
                        img.onload = function() {
                            img.classList.remove("hidden");
                            placeholder.classList.add("hidden");
                        };
                    } else {
                        img.classList.add("hidden");
                        placeholder.classList.remove("hidden");
                    }
                } else if (data.type === 'done') {
                    let isCancel = data.message.includes('cancelado') || data.message.includes('detenido');
                    appendLog(data.message, isCancel ? "skip" : "success");
                    if (data.report_path) {
                        appendLog(t("process_report_saved") + data.report_path, "info");
                    }
                    if (!isCancel) bar.style.width = '100%';

                    progressLabel.textContent = isCancel ? t("process_cancelled_status") : t("process_completed_status");
                    setStatusPill(isCancel ? "process_cancelled_status" : "process_completed_status", isCancel ? "#f43f5e" : "#10b981");
                    hasStartedProcessing = true;
                    trackSubtitle.textContent = isCancel ? t("process_stopped") : t("process_done_all");
                    if (!isCancel) showKofiSupport(data.count, data.elapsed_seconds, data.total_files);
                    resetUi();
                } else if (data.type === 'debug_update_available') {
                    renderUpdateBanner(data);
                } else {
                    let isError = data.type === 'error';
                    appendLog(data.message, isError ? "error" : "info");
                    if (isError && (data.message === "Directorio de entrada no válido." || data.message.includes("cancelado"))) {
                        resetUi();
                    }
                }
            };

            function resetUi() {
                let startBtn = document.getElementById("startBtn");
                if (startBtn) {
                    startBtn.disabled = false;
                    startBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">play_arrow</span> ' + t("process_start_btn");
                    startBtn.classList.remove("opacity-50");
                }
                document.querySelectorAll(".cancel-action").forEach(function(btn) {
                    btn.classList.add("hidden");
                    btn.disabled = false;
                    btn.innerHTML = '<span class="material-symbols-outlined text-[20px]">stop</span> ' + t("process_cancel_btn");
                });
                let downloadBtn = document.getElementById("spotifyDownloadBtn");
                if (downloadBtn) downloadBtn.dataset.busy = "0";
                refreshSpotifyDownloadButton();
            }

            function startProcess() {
                let input_dir = document.getElementById("input_dir").value;
                let output_dir = document.getElementById("output_dir").value;

                if (!input_dir || !output_dir) {
                    alert(t("alert_both_paths_required"));
                    return;
                }

                let startBtn = document.getElementById("startBtn");
                startBtn.disabled = true;
                startBtn.innerHTML = '<span class="material-symbols-outlined text-[20px]">sync</span> ' + t("process_connecting_btn");
                startBtn.classList.add("opacity-50");
                document.querySelectorAll(".cancel-action").forEach(function(btn) { btn.classList.remove("hidden"); });

                logContainer.innerHTML = "";
                appendLog(t("log_starting_process"), "info");
                bar.style.width = '0%';
                progressLabel.textContent = "0%";
                statCount.textContent = "0/0";
                statPct.textContent = "0%";
                setStatusPill("process_starting_status", "#06b6d4");
                hasStartedProcessing = true;
                trackTitle.textContent = t("process_starting_track");
                trackSubtitle.textContent = t("process_scanning_library");
                sessionFiles = [];
                if (processFileGrid) processFileGrid.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("process_waiting_first_file") + '</p>';

                let img = document.getElementById("currentCover");
                let placeholder = document.getElementById("coverPlaceholder");
                img.classList.add("hidden");
                placeholder.classList.remove("hidden");

                fetch('/api/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({input_dir: input_dir, output_dir: output_dir})
                }).then(function(r) { return r.json(); }).then(function(d) {
                    console.log(d);
                }).catch(function(e) {
                    appendLog(t("log_connect_error") + e, "error");
                    resetUi();
                });
            }

            function cancelProcess() {
                document.querySelectorAll(".cancel-action").forEach(function(btn) {
                    btn.disabled = true;
                    btn.innerHTML = '<span class="material-symbols-outlined text-[20px]">sync</span> ' + t("process_cancelling_btn");
                });

                fetch('/api/cancel', {method: 'POST'})
                    .then(function(r) { return r.json(); })
                    .then(function(d) { console.log(d); })
                    .catch(function(e) { console.error("Error al cancelar:", e); });
            }

            let resolvedSpotifyTracks = [];

            function escapeHtml(text) {
                let div = document.createElement("div");
                div.textContent = text == null ? "" : text;
                return div.innerHTML;
            }

            async function resolveSpotifyUrl() {
                let url = document.getElementById("spotify_url").value.trim();
                let statusEl = document.getElementById("spotify-resolve-status");
                let listEl = document.getElementById("spotify-track-list");
                let resolveBtn = document.getElementById("resolveBtn");

                if (!url) {
                    alert(t("alert_paste_link_first"));
                    return;
                }

                resolveBtn.disabled = true;
                resolveBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">sync</span> ' + t("spotify_analyzing_btn");
                statusEl.textContent = "";
                listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("spotify_analyzing_status") + '</p>';

                try {
                    let res = await fetch('/api/spotify/resolve', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({url: url})
                    });
                    let data = await res.json();

                    if (!res.ok) {
                        throw new Error(data.detail || t("error_unknown"));
                    }

                    resolvedSpotifyTracks = data.tracks || [];
                    renderSpotifyTrackList();
                } catch (e) {
                    statusEl.textContent = t("error_prefix") + e.message;
                    listEl.innerHTML = '<p class="font-data-sm text-[13px] text-[#f43f5e]">' + t("spotify_could_not_analyze") + '</p>';
                    resolvedSpotifyTracks = [];
                    updateSpotifySelectionCount();
                } finally {
                    resolveBtn.disabled = false;
                    resolveBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">search</span> ' + t("spotify_analyze_btn");
                }
            }

            function renderSpotifyTrackList() {
                let listEl = document.getElementById("spotify-track-list");
                let countEl = document.getElementById("spotify-track-count");

                if (resolvedSpotifyTracks.length === 0) {
                    listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("spotify_no_tracks_found") + '</p>';
                    countEl.textContent = "";
                    updateSpotifySelectionCount();
                    return;
                }

                countEl.textContent = "(" + resolvedSpotifyTracks.length + ")";

                listEl.innerHTML = resolvedSpotifyTracks.map(function(track, i) {
                    let cover = track.artwork_url
                        ? '<img src="' + track.artwork_url + '" class="w-10 h-10 rounded object-cover bg-input flex-shrink-0"/>'
                        : '<div class="w-10 h-10 rounded bg-input flex items-center justify-center flex-shrink-0"><span class="material-symbols-outlined text-[18px] text-muted/40">music_note</span></div>';
                    let title = escapeHtml(track.title || t("track_untitled"));
                    let artist = escapeHtml(track.artist || t("track_unknown_artist"));
                    return '<label class="flex items-center gap-3 bg-btn border border-theme rounded-lg p-3 cursor-pointer hover:bg-btn-hover transition-colors">' +
                        '<input type="checkbox" class="spotify-track-checkbox cicada-checkbox" data-index="' + i + '" checked onchange="updateSpotifySelectionCount()"/>' +
                        cover +
                        '<div class="overflow-hidden flex-1">' +
                        '<p class="font-data-sm text-[14px] truncate">' + title + '</p>' +
                        '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + artist + '</p>' +
                        '</div></label>';
                }).join("");

                let selectAll = document.getElementById("spotify-select-all");
                selectAll.checked = true;
                selectAll.indeterminate = false;
                updateSpotifySelectionCount();
            }

            function toggleSelectAllTracks(checked) {
                document.querySelectorAll(".spotify-track-checkbox").forEach(function(cb) { cb.checked = checked; });
                updateSpotifySelectionCount();
            }

            function updateSpotifySelectionCount() {
                let checkboxes = document.querySelectorAll(".spotify-track-checkbox");
                let selected = document.querySelectorAll(".spotify-track-checkbox:checked").length;

                let selectAll = document.getElementById("spotify-select-all");
                if (selectAll) {
                    selectAll.checked = checkboxes.length > 0 && selected === checkboxes.length;
                    selectAll.indeterminate = selected > 0 && selected < checkboxes.length;
                }

                refreshSpotifyDownloadButton();
            }

            function refreshSpotifyDownloadButton() {
                let btn = document.getElementById("spotifyDownloadBtn");
                if (!btn) return;
                if (btn.disabled && btn.dataset.busy === "1") return;
                let n = document.querySelectorAll(".spotify-track-checkbox:checked").length;
                btn.disabled = n === 0;
                btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">download</span> ' + t("spotify_download_selected_btn") + ' (<span id="spotify-selected-count">' + n + '</span>)';
            }

            function startSpotifyDownload() {
                let output_dir = document.getElementById("spotify_output_dir").value;
                if (!output_dir) {
                    alert(t("alert_choose_dest_folder"));
                    return;
                }

                let selectedTracks = Array.from(document.querySelectorAll(".spotify-track-checkbox"))
                    .filter(function(cb) { return cb.checked; })
                    .map(function(cb) { return resolvedSpotifyTracks[parseInt(cb.dataset.index, 10)]; });

                if (selectedTracks.length === 0) {
                    alert(t("alert_select_at_least_one_track"));
                    return;
                }

                let downloadBtn = document.getElementById("spotifyDownloadBtn");
                downloadBtn.disabled = true;
                downloadBtn.dataset.busy = "1";
                downloadBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">sync</span> ' + t("spotify_downloading_btn");
                document.querySelectorAll(".cancel-action").forEach(function(btn) { btn.classList.remove("hidden"); });

                logContainer.innerHTML = "";
                appendLog(t("log_starting_spotify_download", {n: selectedTracks.length}), "info");
                bar.style.width = '0%';
                progressLabel.textContent = "0%";
                statCount.textContent = "0/0";
                statPct.textContent = "0%";
                setStatusPill("process_starting_status", "#06b6d4");
                hasStartedProcessing = true;
                trackTitle.textContent = t("process_starting_track");
                trackSubtitle.textContent = t("spotify_preparing_download");
                sessionFiles = [];
                if (processFileGrid) processFileGrid.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("spotify_waiting_first_track") + '</p>';

                let img = document.getElementById("currentCover");
                let placeholder = document.getElementById("coverPlaceholder");
                img.classList.add("hidden");
                placeholder.classList.remove("hidden");

                fetch('/api/spotify/download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({tracks: selectedTracks, output_dir: output_dir})
                }).then(function(r) { return r.json(); }).then(function(d) {
                    console.log(d);
                }).catch(function(e) {
                    appendLog(t("log_connect_error") + e, "error");
                    resetUi();
                });
            }

            let userPlaylists = [];
            let currentPlaylistTracks = [];
            let currentPlaylistName = "";
            let replicateMatches = [];

            async function loadSpotifyPlaylists() {
                let listEl = document.getElementById("playlists-list");
                listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("playlists_loading") + '</p>';
                try {
                    let res = await fetch('/api/spotify/playlists');
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    userPlaylists = data.playlists || [];
                    if (userPlaylists.length === 0) {
                        listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("playlists_no_playlists_found") + '</p>';
                        return;
                    }

                    listEl.innerHTML = userPlaylists.map(function(p, i) {
                        let cover = p.image_url
                            ? '<img src="' + p.image_url + '" class="w-10 h-10 rounded object-cover bg-input flex-shrink-0"/>'
                            : '<div class="w-10 h-10 rounded bg-input flex items-center justify-center flex-shrink-0"><span class="material-symbols-outlined text-[18px] text-muted/40">queue_music</span></div>';
                        return '<div class="playlist-item flex items-center gap-3 bg-btn border border-theme rounded-lg p-2 cursor-pointer hover:bg-btn-hover transition-colors" data-index="' + i + '" onclick="selectPlaylist(' + i + ')">' +
                            cover +
                            '<div class="overflow-hidden flex-1">' +
                            '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(p.name) + '</p>' +
                            '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + p.track_count + t("playlists_track_count_suffix") + '</p>' +
                            '</div></div>';
                    }).join("");
                } catch (e) {
                    listEl.innerHTML = '<p class="font-data-sm text-[13px] text-[#f43f5e]">' + t("error_prefix") + e.message + '</p>';
                }
            }

            async function selectPlaylist(index) {
                let playlist = userPlaylists[index];
                if (!playlist) return;

                document.querySelectorAll(".playlist-item").forEach(function(el) { el.classList.remove("ring-2", "ring-primary"); });
                let el = document.querySelector('.playlist-item[data-index="' + index + '"]');
                if (el) el.classList.add("ring-2", "ring-primary");

                currentPlaylistName = playlist.name;
                let titleEl = document.getElementById("playlist-detail-title");
                titleEl.removeAttribute("data-i18n");
                titleEl.textContent = playlist.name;

                let trackListEl = document.getElementById("playlist-track-list");
                trackListEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("playlists_loading_songs") + '</p>';
                document.getElementById("replicate-controls").style.display = "none";

                replicateMatches = [];
                document.getElementById("replicate-track-list").innerHTML = "";
                document.getElementById("replicate-match-summary").textContent = "";
                document.getElementById("generate-m3u8-controls").classList.add("hidden");
                document.getElementById("generate-m3u8-controls").classList.remove("flex");
                document.getElementById("replicate-empty-hint").classList.remove("hidden");

                try {
                    let res = await fetch('/api/spotify/resolve', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({url: 'https://open.spotify.com/playlist/' + playlist.id})
                    });
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    currentPlaylistTracks = data.tracks || [];
                    renderPlaylistTrackPreview();
                    document.getElementById("replicate-controls").style.display = "flex";
                } catch (e) {
                    trackListEl.innerHTML = '<p class="font-data-sm text-[13px] text-[#f43f5e]">' + t("error_prefix") + e.message + '</p>';
                }
            }

            function renderPlaylistTrackPreview() {
                let trackListEl = document.getElementById("playlist-track-list");
                if (currentPlaylistTracks.length === 0) {
                    trackListEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("playlists_no_songs") + '</p>';
                    return;
                }
                trackListEl.innerHTML = currentPlaylistTracks.map(function(track) {
                    return '<div class="flex items-center gap-3 bg-btn border border-theme rounded-lg p-2">' +
                        '<span class="material-symbols-outlined text-[16px] text-muted/40">music_note</span>' +
                        '<div class="overflow-hidden flex-1">' +
                        '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(track.title) + '</p>' +
                        '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + escapeHtml(track.artist) + '</p>' +
                        '</div></div>';
                }).join("");
            }

            async function replicatePlaylist() {
                let libraryDir = document.getElementById("library_dir").value.trim();
                if (!libraryDir) {
                    alert(t("alert_choose_local_library_first"));
                    return;
                }
                if (currentPlaylistTracks.length === 0) {
                    alert(t("alert_playlist_no_songs_loaded"));
                    return;
                }

                let confirmed = confirm(t("confirm_replicate", {n: currentPlaylistTracks.length, name: currentPlaylistName, dir: libraryDir}));
                if (!confirmed) return;

                let btn = document.getElementById("replicateBtn");
                btn.disabled = true;
                btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">sync</span> ' + t("playlists_searching_btn");

                try {
                    let res = await fetch('/api/library/match', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({tracks: currentPlaylistTracks, library_dir: libraryDir})
                    });
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    replicateMatches = data.matches.map(function(m) {
                        let entry = Object.assign({}, m);
                        entry.included = !!m.path;
                        return entry;
                    });

                    document.getElementById("replicate-empty-hint").classList.add("hidden");
                    document.getElementById("generate-m3u8-controls").classList.remove("hidden");
                    document.getElementById("generate-m3u8-controls").classList.add("flex");
                    document.getElementById("m3u8_name").value = currentPlaylistName || t("default_playlist_name");
                    renderReplicateTrackList();
                } catch (e) {
                    alert(t("alert_error_searching_matches") + e.message);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">content_copy</span> ' + t("playlists_replicate_btn");
                }
            }

            function renderReplicateTrackList() {
                let container = document.getElementById("replicate-track-list");
                container.innerHTML = replicateMatches.map(function(m, i) {
                    let matched = !!m.path;
                    let rowClasses = matched ? "bg-btn" : "bg-white/[0.02] opacity-75";
                    let statusIcon = matched
                        ? '<span class="material-symbols-outlined text-[16px] text-secondary" title="Encontrada">check_circle</span>'
                        : '<span class="material-symbols-outlined text-[16px] text-muted/40" title="No encontrada">help</span>';
                    let manualBtn = matched ? '' :
                        '<button type="button" onclick="manualMatchTrack(' + i + ')" title="Asociar con un archivo de mi biblioteca" class="material-symbols-outlined text-[16px] text-accent/80 hover:text-accent">attach_file</button>' +
                        '<button type="button" onclick="downloadMissingTrack(' + i + ')" title="Descargar e inyectar metadatos" class="material-symbols-outlined text-[16px] text-secondary hover:text-accent ml-1">download</button>';
                    return '<div class="replicate-track-row flex items-center gap-2 ' + rowClasses + ' border border-transparent rounded-lg p-2" ' +
                        'draggable="true" data-index="' + i + '" ' +
                        'ondragstart="handleTrackDragStart(event, ' + i + ')" ondragend="handleTrackDragEnd(event)" ' +
                        'ondragover="handleTrackDragOver(event)" ondragleave="handleTrackDragLeave(event)" ondrop="handleTrackDrop(event, ' + i + ')">' +
                        '<span class="material-symbols-outlined text-[18px] text-muted/40 cursor-grab" title="Arrastrar para reordenar">drag_indicator</span>' +
                        '<input type="checkbox" class="cicada-checkbox" data-index="' + i + '" ' + (matched && m.included ? 'checked' : '') + ' ' + (matched ? '' : 'disabled') + ' onchange="toggleReplicateTrackIncluded(' + i + ', this.checked)"/>' +
                        statusIcon +
                        '<div class="overflow-hidden flex-1">' +
                        '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(m.title) + '</p>' +
                        '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + escapeHtml(m.artist) + (matched ? '' : t("playlists_not_found_suffix")) + '</p>' +
                        '</div>' + manualBtn + '</div>';
                }).join("");
                updateReplicateSummary();
            }

            let dragSourceIndex = null;

            function handleTrackDragStart(e, index) {
                dragSourceIndex = index;
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("text/plain", String(index));
                e.currentTarget.classList.add("opacity-40");
            }

            function handleTrackDragEnd(e) {
                e.currentTarget.classList.remove("opacity-40");
                document.querySelectorAll(".replicate-track-row").forEach(function(row) {
                    row.classList.remove("border-accent");
                });
                dragSourceIndex = null;
            }

            function handleTrackDragOver(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                e.currentTarget.classList.add("border-accent");
            }

            function handleTrackDragLeave(e) {
                e.currentTarget.classList.remove("border-accent");
            }

            function handleTrackDrop(e, targetIndex) {
                e.preventDefault();
                e.currentTarget.classList.remove("border-accent");
                if (dragSourceIndex === null || dragSourceIndex === targetIndex) return;
                let moved = replicateMatches.splice(dragSourceIndex, 1)[0];
                replicateMatches.splice(targetIndex, 0, moved);
                dragSourceIndex = null;
                renderReplicateTrackList();
            }

            function toggleReplicateTrackIncluded(index, checked) {
                if (replicateMatches[index]) replicateMatches[index].included = checked;
                updateReplicateSummary();
            }

            function updateReplicateSummary() {
                let matchedCount = replicateMatches.filter(function(m) { return !!m.path; }).length;
                let includedCount = replicateMatches.filter(function(m) { return m.included && m.path; }).length;
                document.getElementById("replicate-match-summary").textContent = t("playlists_summary", {matched: matchedCount, total: replicateMatches.length, included: includedCount});
                document.getElementById("generateM3u8Btn").disabled = includedCount === 0;
            }
            
            async function manualMatchTrack(index) {
                let entry = replicateMatches[index];
                if (!entry) return;

                let libraryDir = document.getElementById("library_dir").value.trim();
                if (!libraryDir) {
                    alert(t("alert_choose_local_library_first"));
                    return;
                }

                let pickRes = await fetch('/api/select_file');
                let pickData = await pickRes.json();
                if (!pickData.path) return;

                let confirmed = confirm(t("confirm_manual_match", {path: pickData.path, artist: entry.artist, title: entry.title}));
                if (!confirmed) return;

                try {
                    let res = await fetch('/api/library/manual_match', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({track: entry, file_path: pickData.path, library_dir: libraryDir})
                    });
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    replicateMatches[index].path = data.path;
                    replicateMatches[index].included = true;
                    renderReplicateTrackList();
                } catch (e) {
                    alert(t("alert_error_associating_file") + e.message);
                }
            }

            async function downloadMissingTrack(index) {
                let entry = replicateMatches[index];
                if (!entry) return;

                let libraryDir = document.getElementById("library_dir").value.trim();
                if (!libraryDir) {
                    alert(t("alert_choose_local_library_first"));
                    return;
                }

                let confirmed = confirm("¿Deseas descargar '" + entry.title + "' a tu biblioteca? (La descarga se procesará de forma inmediata, esto puede tomar unos segundos)");
                if (!confirmed) return;

                let originalBtnHTML = null;
                let btn = null;
                let row = document.querySelector('.replicate-track-row[data-index="' + index + '"]');
                if (row) {
                    btn = row.querySelector('button[title*="Descargar"]');
                    if (btn) {
                        originalBtnHTML = btn.innerHTML;
                        btn.innerHTML = 'hourglass_empty';
                        btn.classList.add('animate-spin');
                        btn.disabled = true;
                    }
                }

                try {
                    let res = await fetch('/api/spotify/download_single', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({track: entry, output_dir: libraryDir})
                    });
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    replicateMatches[index].path = data.path;
                    replicateMatches[index].included = true;
                    renderReplicateTrackList();
                } catch (e) {
                    alert("Error al descargar: " + e.message);
                    if (btn && originalBtnHTML) {
                        btn.innerHTML = originalBtnHTML;
                        btn.classList.remove('animate-spin');
                        btn.disabled = false;
                    }
                }
            }

            async function generatePlaylistM3u8() {
                let name = document.getElementById("m3u8_name").value.trim() || t("default_playlist_name_generic");
                let libraryDir = document.getElementById("library_dir").value.trim();
                let filePaths = replicateMatches.filter(function(m) { return m.included && m.path; }).map(function(m) { return m.path; });

                if (filePaths.length === 0) {
                    alert(t("alert_no_songs_to_generate"));
                    return;
                }

                let btn = document.getElementById("generateM3u8Btn");
                btn.disabled = true;
                btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">sync</span> ' + t("playlists_generating_btn");

                try {
                    let res = await fetch('/api/library/generate_playlist', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({playlist_name: name, file_paths: filePaths, output_dir: libraryDir})
                    });
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    alert(t("alert_playlist_generated") + data.m3u8_path);
                    appendLog(t("log_playlist_generated", {name: name, path: data.m3u8_path}), "success");
                } catch (e) {
                    alert(t("alert_error_generating_playlist") + e.message);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">save</span> ' + t("playlists_generate_btn");
                }
            }

            let libraryTracks = [];
            let libraryPlaylists = [];
            let libraryGrouping = "all";
            let libraryViewMode = "list";
            let librarySortAlpha = true;
            let librarySearchQuery = "";
            let libraryQueues = {};
            let currentQueueKey = null;
            let currentQueueIndex = -1;

            async function loadLibraryConfig() {
                try {
                    let res = await fetch('/api/library/config');
                    let data = await res.json();
                    let dir = data.library_dir || "";
                    if (!dir) return;

                    let browseInput = document.getElementById("library_browse_dir");
                    if (browseInput) browseInput.value = dir;
                    let replicateInput = document.getElementById("library_dir");
                    if (replicateInput && !replicateInput.value) replicateInput.value = dir;

                    await scanLibrary(dir);
                } catch (e) {
                    console.error("Error cargando configuración de biblioteca:", e);
                }
            }

            async function saveLibraryDirAndScan() {
                let dir = document.getElementById("library_browse_dir").value.trim();
                if (!dir) {
                    alert(t("alert_choose_folder_first"));
                    return;
                }
                try {
                    await fetch('/api/library/config', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({library_dir: dir})
                    });
                    let replicateInput = document.getElementById("library_dir");
                    if (replicateInput) replicateInput.value = dir;
                    await scanLibrary(dir);
                } catch (e) {
                    alert(t("alert_error_saving_config") + e.message);
                }
            }

            async function scanLibrary(dir) {
                let browserEl = document.getElementById("library-browser");
                browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("library_scanning") + '</p>';
                try {
                    let res = await fetch('/api/library/browse?library_dir=' + encodeURIComponent(dir));
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    libraryTracks = data.tracks || [];
                    libraryPlaylists = data.playlists || [];
                    document.getElementById("library-track-count").textContent = libraryTracks.length + t("library_track_count_suffix");
                    renderLibraryBrowser();
                } catch (e) {
                    browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-[#f43f5e]">' + t("error_prefix") + e.message + '</p>';
                }
            }

            function setLibraryGrouping(group) {
                libraryGrouping = group;
                document.querySelectorAll(".library-group-btn[data-group]").forEach(function(btn) {
                    btn.classList.toggle("active", btn.dataset.group === group);
                });
                renderLibraryBrowser();
            }

            function filterLibrary() {
                librarySearchQuery = document.getElementById("library_search").value.trim().toLowerCase();
                renderLibraryBrowser();
            }

            function matchesLibrarySearch(track) {
                if (!librarySearchQuery) return true;
                return (track.title || "").toLowerCase().includes(librarySearchQuery) ||
                    (track.artist || "").toLowerCase().includes(librarySearchQuery) ||
                    (track.album || "").toLowerCase().includes(librarySearchQuery);
            }

            function toggleLibrarySort() {
                librarySortAlpha = !librarySortAlpha;
                document.getElementById("library-sort-btn").classList.toggle("active", librarySortAlpha);
                renderLibraryBrowser();
            }

            function sortTracksAlpha(tracks) {
                return tracks.slice().sort(function(a, b) { return (a.title || "").localeCompare(b.title || ""); });
            }

            function setLibraryViewMode(mode) {
                libraryViewMode = mode;
                document.getElementById("library-view-list-btn").classList.toggle("active", mode === "list");
                document.getElementById("library-view-grid-btn").classList.toggle("active", mode === "grid");
                renderLibraryBrowser();
            }

            function libraryTracksContainerClass() {
                return libraryViewMode === "grid"
                    ? "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3"
                    : "flex flex-col gap-0.5";
            }

            function libraryTrackRowHtml(track, queueKey, index) {
                let subtitle = libraryGrouping === "album"
                    ? escapeHtml(track.artist || "")
                    : escapeHtml(track.artist || "") + (track.album ? " &middot; " + escapeHtml(track.album) : "");
                return '<div class="flex items-center gap-3 px-2 py-1.5 rounded-lg cursor-pointer hover:bg-btn-hover transition-colors" onclick="playFromQueue(\\'' + queueKey + '\\', ' + index + ')" oncontextmenu="showLibraryContextMenu(event, \\'' + escapeHtml(track.path.replace(/\\/g, '\\\\').replace(/'/g, "\\'")) + '\\')">' +
                    '<span class="material-symbols-outlined text-[18px] text-muted/40">music_note</span>' +
                    '<div class="overflow-hidden flex-1">' +
                    '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(track.title) + '</p>' +
                    '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + subtitle + '</p>' +
                    '</div></div>';
            }

            function libraryTrackCardHtml(track, queueKey, index) {
                return '<div class="flex flex-col gap-2 p-2 rounded-lg cursor-pointer hover:bg-btn-hover transition-colors" onclick="playFromQueue(\\'' + queueKey + '\\', ' + index + ')" oncontextmenu="showLibraryContextMenu(event, \\'' + escapeHtml(track.path.replace(/\\/g, '\\\\').replace(/'/g, "\\'")) + '\\')">' +
                    '<div class="relative w-full aspect-square rounded-lg bg-btn overflow-hidden flex items-center justify-center">' +
                    '<span class="material-symbols-outlined text-[28px] text-muted/30">music_note</span>' +
                    '<img src="/api/library/artwork?path=' + encodeURIComponent(track.path) + '" class="absolute inset-0 w-full h-full object-cover" loading="lazy" onerror="this.remove()" alt="">' +
                    '</div>' +
                    '<div class="overflow-hidden">' +
                    '<p class="font-data-sm text-[13px] truncate">' + escapeHtml(track.title) + '</p>' +
                    '<p class="font-label-caps text-[10px] text-muted/40 truncate">' + escapeHtml(track.artist || "") + '</p>' +
                    '</div></div>';
            }

            let contextMenuTrackPath = null;
            function showLibraryContextMenu(event, path) {
                event.preventDefault();
                event.stopPropagation();
                contextMenuTrackPath = path;
                const menu = document.getElementById("library-context-menu");
                menu.style.display = "flex";
                
                let x = event.clientX;
                let y = event.clientY;
                if (x + 220 > window.innerWidth) x -= 220;
                if (y + menu.offsetHeight > window.innerHeight) y -= menu.offsetHeight;
                
                menu.style.left = x + "px";
                menu.style.top = y + "px";
            }
            
            document.addEventListener('click', function(e) {
                const menu = document.getElementById("library-context-menu");
                if (menu && menu.style.display === "flex") {
                    menu.style.display = "none";
                }
            });

            async function contextShowInFolder() {
                if (!contextMenuTrackPath) return;
                try {
                    await fetch('/api/library/show_in_folder', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path: contextMenuTrackPath })
                    });
                } catch (e) {
                    console.error("Error abriendo carpeta:", e);
                }
            }

            async function contextDeleteTrack() {
                if (!contextMenuTrackPath) return;
                if (!confirm("¿Estás seguro de que deseas eliminar esta pista de la biblioteca? Esta acción no se puede deshacer.")) return;
                try {
                    let res = await fetch('/api/library/track', {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path: contextMenuTrackPath })
                    });
                    if (res.ok) {
                        let libraryDir = document.getElementById("library_dir").value || document.getElementById("input_dir").value;
                        if (libraryDir) scanLibrary(libraryDir);
                    } else {
                        let data = await res.json();
                        alert("Error: " + data.detail);
                    }
                } catch (e) {
                    console.error("Error eliminando pista:", e);
                }
            }

            async function contextGetInfo() {
                if (!contextMenuTrackPath) return;
                try {
                    let res = await fetch('/api/library/track_info?path=' + encodeURIComponent(contextMenuTrackPath));
                    let meta = await res.json();
                    
                    document.getElementById("info_title").value = meta.title || "";
                    document.getElementById("info_artist").value = meta.artist || "";
                    document.getElementById("info_album").value = meta.album || "";
                    document.getElementById("info_album_artist").value = meta.album_artist || "";
                    document.getElementById("info_composer").value = meta.composer || "";
                    document.getElementById("info_grouping").value = meta.grouping || "";
                    document.getElementById("info_genre").value = meta.genre || "";
                    document.getElementById("info_year").value = meta.year || "";
                    document.getElementById("info_bpm").value = meta.bpm || "";
                    document.getElementById("info_track_number").value = meta.track_number || "";
                    document.getElementById("info_track_count").value = meta.track_count || "";
                    document.getElementById("info_disc_number").value = meta.disc_number || "";
                    document.getElementById("info_disc_count").value = meta.disc_count || "";
                    document.getElementById("info_compilation").checked = meta.compilation || false;
                    document.getElementById("info_comments").value = meta.comments || "";
                    
                    document.getElementById("track-info-modal").classList.remove("hidden");
                    document.getElementById("track-info-modal").classList.add("flex");
                } catch (e) {
                    console.error("Error obteniendo info:", e);
                    alert("Error obteniendo info de la pista.");
                }
            }

            function closeTrackInfoModal() {
                document.getElementById("track-info-modal").classList.remove("flex");
                document.getElementById("track-info-modal").classList.add("hidden");
            }
            
            async function saveTrackInfo() {
                if (!contextMenuTrackPath) return;
                const meta = {
                    title: document.getElementById("info_title").value,
                    artist: document.getElementById("info_artist").value,
                    album: document.getElementById("info_album").value,
                    album_artist: document.getElementById("info_album_artist").value,
                    composer: document.getElementById("info_composer").value,
                    grouping: document.getElementById("info_grouping").value,
                    genre: document.getElementById("info_genre").value,
                    year: document.getElementById("info_year").value,
                    bpm: document.getElementById("info_bpm").value,
                    track_number: document.getElementById("info_track_number").value,
                    track_count: document.getElementById("info_track_count").value,
                    disc_number: document.getElementById("info_disc_number").value,
                    disc_count: document.getElementById("info_disc_count").value,
                    compilation: document.getElementById("info_compilation").checked,
                    comments: document.getElementById("info_comments").value
                };
                
                try {
                    let res = await fetch('/api/library/track_info', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path: contextMenuTrackPath, metadata: meta })
                    });
                    if (res.ok) {
                        closeTrackInfoModal();
                        let libraryDir = document.getElementById("library_dir").value || document.getElementById("input_dir").value;
                        if (libraryDir) scanLibrary(libraryDir);
                    } else {
                        let data = await res.json();
                        alert("Error: " + data.detail);
                    }
                } catch (e) {
                    console.error("Error guardando info:", e);
                    alert("Error al guardar información.");
                }
            }

            function libraryGroupSectionHtml(name, tracks, key) {
                let rowFn = libraryViewMode === "grid" ? libraryTrackCardHtml : libraryTrackRowHtml;
                return '<details class="library-group" open>' +
                    '<summary class="font-label-caps text-[13px] text-main font-bold py-2 mt-1">' + escapeHtml(name) +
                    ' <span class="font-normal text-[12px] text-muted">(' + tracks.length + ')</span></summary>' +
                    '<div class="' + libraryTracksContainerClass() + ' pl-3 pb-2">' +
                    tracks.map(function(track, i) { return rowFn(track, key, i); }).join("") +
                    '</div></details>';
            }

            function renderLibraryBrowser() {
                let browserEl = document.getElementById("library-browser");
                libraryQueues = {};
                browserEl.className = "flex flex-col gap-1";

                if (libraryTracks.length === 0) {
                    browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("library_no_songs_in_folder") + '</p>';
                    return;
                }

                let filtered = libraryTracks.filter(matchesLibrarySearch);
                if (filtered.length === 0) {
                    browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("library_no_search_results") + '</p>';
                    return;
                }

                if (libraryGrouping === "all") {
                    let sorted = librarySortAlpha ? sortTracksAlpha(filtered) : filtered;
                    libraryQueues["all"] = sorted;
                    browserEl.className = libraryTracksContainerClass();
                    let rowFn = libraryViewMode === "grid" ? libraryTrackCardHtml : libraryTrackRowHtml;
                    browserEl.innerHTML = sorted.map(function(track, i) { return rowFn(track, "all", i); }).join("");
                    return;
                }

                if (libraryGrouping === "playlist") {
                    let sections = libraryPlaylists.map(function(p) {
                        let pathSet = new Set(p.paths);
                        return {name: p.name, tracks: filtered.filter(function(track) { return pathSet.has(track.path); })};
                    });
                    let assigned = new Set();
                    sections.forEach(function(s) { s.tracks.forEach(function(track) { assigned.add(track.path); }); });
                    let unassigned = filtered.filter(function(track) { return !assigned.has(track.path); });
                    if (unassigned.length > 0) sections.push({name: t("library_no_playlist_group"), tracks: unassigned});

                    if (librarySortAlpha) {
                        sections.sort(function(a, b) { return a.name.localeCompare(b.name); });
                        sections.forEach(function(s) { s.tracks = sortTracksAlpha(s.tracks); });
                    }

                    browserEl.innerHTML = sections.filter(function(s) { return s.tracks.length > 0; }).map(function(s) {
                        let key = "pl:" + s.name;
                        libraryQueues[key] = s.tracks;
                        return libraryGroupSectionHtml(s.name, s.tracks, key);
                    }).join("");
                    return;
                }

                let groupKeyFn = libraryGrouping === "album"
                    ? function(track) { return (track.artist || t("track_unknown_artist")) + " — " + (track.album || t("track_unknown_album")); }
                    : function(track) { return track.artist || t("track_unknown_artist"); };

                let groups = {};
                filtered.forEach(function(track) {
                    let key = groupKeyFn(track);
                    if (!groups[key]) groups[key] = [];
                    groups[key].push(track);
                });
                let groupNames = Object.keys(groups);
                if (librarySortAlpha) groupNames.sort(function(a, b) { return a.localeCompare(b); });

                browserEl.innerHTML = groupNames.map(function(name) {
                    let key = libraryGrouping + ":" + name;
                    let tracks = librarySortAlpha ? sortTracksAlpha(groups[name]) : groups[name];
                    libraryQueues[key] = tracks;
                    return libraryGroupSectionHtml(name, tracks, key);
                }).join("");
            }

            function playFromQueue(key, index) {
                currentQueueKey = key;
                currentQueueIndex = index;
                playCurrentQueueTrack();
            }

            function playCurrentQueueTrack() {
                let queue = libraryQueues[currentQueueKey];
                if (!queue || !queue[currentQueueIndex]) return;
                let track = queue[currentQueueIndex];

                hasPlayedTrack = true;
                document.getElementById("playerTrackTitle").textContent = track.title || t("track_untitled");
                document.getElementById("playerTrackArtist").textContent = (track.artist || "") + (track.album ? " · " + track.album : "");

                let cover = document.getElementById("playerCover");
                let placeholder = document.getElementById("playerCoverPlaceholder");
                cover.classList.add("hidden");
                placeholder.classList.remove("hidden");
                cover.onload = function() { cover.classList.remove("hidden"); placeholder.classList.add("hidden"); };
                cover.onerror = function() { cover.classList.add("hidden"); placeholder.classList.remove("hidden"); };
                cover.src = '/api/library/artwork?path=' + encodeURIComponent(track.path);

                libraryAudio.src = '/api/library/stream?path=' + encodeURIComponent(track.path);
                libraryAudio.play().catch(function(e) { console.error("Error reproduciendo:", e); });
                setPlayPauseIcon(true);
            }

            function togglePlayPause() {
                if (!libraryAudio.src) return;
                if (libraryAudio.paused) {
                    libraryAudio.play();
                    setPlayPauseIcon(true);
                } else {
                    libraryAudio.pause();
                    setPlayPauseIcon(false);
                }
            }

            function setPlayPauseIcon(playing) {
                document.getElementById("playerPlayPauseIcon").textContent = playing ? "pause" : "play_arrow";
            }

            let isShuffle = false;
            let repeatMode = 0;

            function toggleShuffle() {
                isShuffle = !isShuffle;
                let btn = document.getElementById("btnShuffle");
                if (isShuffle) {
                    btn.classList.remove("text-sidebar/40");
                    btn.classList.add("text-accent");
                } else {
                    btn.classList.remove("text-accent");
                    btn.classList.add("text-sidebar/40");
                }
            }

            function toggleRepeat() {
                repeatMode = (repeatMode + 1) % 3;
                let btn = document.getElementById("btnRepeat");
                if (repeatMode === 0) {
                    btn.classList.remove("text-accent");
                    btn.classList.add("text-sidebar/40");
                    btn.textContent = "repeat";
                } else if (repeatMode === 1) {
                    btn.classList.remove("text-sidebar/40");
                    btn.classList.add("text-accent");
                    btn.textContent = "repeat";
                } else if (repeatMode === 2) {
                    btn.classList.remove("text-sidebar/40");
                    btn.classList.add("text-accent");
                    btn.textContent = "repeat_one";
                }
            }

            function playNextTrack(auto = false) {
                let queue = libraryQueues[currentQueueKey];
                if (!queue) return;
                
                if (auto === true && repeatMode === 2) {
                    libraryAudio.currentTime = 0;
                    libraryAudio.play();
                    return;
                }
                
                if (isShuffle) {
                    currentQueueIndex = Math.floor(Math.random() * queue.length);
                } else {
                    if (currentQueueIndex >= queue.length - 1) {
                        if (repeatMode === 1) {
                            currentQueueIndex = 0;
                        } else {
                            if (auto === true) setPlayPauseIcon(false);
                            return;
                        }
                    } else {
                        currentQueueIndex += 1;
                    }
                }
                playCurrentQueueTrack();
            }

            function playPrevTrack() {
                let queue = libraryQueues[currentQueueKey];
                if (!queue) return;
                
                if (isShuffle) {
                    currentQueueIndex = Math.floor(Math.random() * queue.length);
                } else {
                    if (currentQueueIndex <= 0) {
                        currentQueueIndex = 0;
                    } else {
                        currentQueueIndex -= 1;
                    }
                }
                playCurrentQueueTrack();
            }

            function formatTime(seconds) {
                if (!isFinite(seconds) || seconds < 0) return "0:00";
                let m = Math.floor(seconds / 60);
                let s = Math.floor(seconds % 60);
                return m + ":" + (s < 10 ? "0" : "") + s;
            }

            function seekPlayer(e) {
                if (!libraryAudio.duration) return;
                let rect = document.getElementById("playerSeekTrack").getBoundingClientRect();
                let ratio = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1);
                libraryAudio.currentTime = ratio * libraryAudio.duration;
            }

            function setVolumeFromClick(e) {
                let rect = document.getElementById("playerVolumeTrack").getBoundingClientRect();
                let ratio = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1);
                setVolume(ratio);
            }

            function setVolume(vol) {
                libraryAudio.volume = vol;
            }

            libraryAudio.addEventListener("volumechange", function() {
                let pct = libraryAudio.volume * 100;
                document.getElementById("playerVolumeFill").style.width = pct + "%";
            });

            libraryAudio.addEventListener("timeupdate", function() {
                if (!libraryAudio.duration) return;
                let pct = (libraryAudio.currentTime / libraryAudio.duration) * 100;
                document.getElementById("playerSeekFill").style.width = pct + "%";
                document.getElementById("playerCurrentTime").textContent = formatTime(libraryAudio.currentTime);
                document.getElementById("playerDuration").textContent = formatTime(libraryAudio.duration);
            });
            libraryAudio.addEventListener("ended", function() {
                playNextTrack(true);
            });
            libraryAudio.addEventListener("pause", function() { setPlayPauseIcon(false); });
            libraryAudio.addEventListener("play", function() { setPlayPauseIcon(true); });

            function openSettings() {
                loadSettingsIntoForm();
                refreshSpotifyAuthStatus();
                let modal = document.getElementById("settings-modal");
                modal.classList.remove("hidden");
                modal.classList.add("flex");
            }

            async function refreshSpotifyAuthStatus() {
                let statusEl = document.getElementById("settings-spotify-status");
                let btn = document.getElementById("settings-spotify-connect-btn");
                if (!statusEl || !btn) return;
                try {
                    let res = await fetch('/api/auth/status');
                    let data = await res.json();
                    if (data.connected) {
                        statusEl.textContent = t("settings_spotify_connected");
                        btn.textContent = t("settings_spotify_reconnect_btn");
                    } else {
                        statusEl.textContent = t("settings_spotify_not_connected");
                        btn.textContent = t("settings_spotify_connect_btn");
                    }
                } catch (e) {
                    console.error("Error consultando el estado de Spotify:", e);
                }
            }

            function closeSettings() {
                let modal = document.getElementById("settings-modal");
                modal.classList.add("hidden");
                modal.classList.remove("flex");
            }

            function openAbout() {
                let modal = document.getElementById("about-modal");
                modal.classList.remove("hidden");
                modal.classList.add("flex");
            }

            function closeAbout() {
                let modal = document.getElementById("about-modal");
                modal.classList.add("hidden");
                modal.classList.remove("flex");
            }

            const KOFI_SUPPORT_THRESHOLD = 250;
            const MANUAL_TAGGING_MINUTES_PER_SONG = 5;

            function formatDurationWords(totalSeconds) {
                totalSeconds = Math.max(0, Math.round(totalSeconds));
                let h = Math.floor(totalSeconds / 3600);
                let m = Math.floor((totalSeconds % 3600) / 60);
                let s = totalSeconds % 60;
                if (h > 0) return h + "h " + m + "m";
                if (m > 0) return m + "m " + s + "s";
                return s + "s";
            }

            function showKofiSupport(count, elapsedSeconds, totalFiles) {
                if (!count) return;
                if (!totalFiles || totalFiles < KOFI_SUPPORT_THRESHOLD) return;

                let manualSeconds = count * MANUAL_TAGGING_MINUTES_PER_SONG * 60;
                let message = t("kofi_support_message", {
                    count: count,
                    time: formatDurationWords(elapsedSeconds),
                    manual_time: formatDurationWords(manualSeconds)
                });

                document.getElementById("kofi-support-message").textContent = message;
                let modal = document.getElementById("kofi-modal");
                modal.classList.remove("hidden");
                modal.classList.add("flex");
            }

            function closeKofiSupport() {
                let modal = document.getElementById("kofi-modal");
                modal.classList.add("hidden");
                modal.classList.remove("flex");
            }

            function renderUpdateBanner(data) {
                if (localStorage.getItem("cicada_dismissed_update") === data.latest_version) return;

                document.getElementById("update-banner-text").textContent = t("update_available_text", {version: data.latest_version});
                let link = document.getElementById("update-banner-link");
                link.href = data.url;
                link.textContent = t("update_available_link");

                let banner = document.getElementById("update-banner");
                banner.dataset.latestVersion = data.latest_version;
                banner.classList.remove("hidden");
                banner.classList.add("flex");
            }

            function checkForUpdates() {
                fetch('/api/check_update').then(function(r) { return r.json(); }).then(function(data) {
                    if (!data.update_available) return;
                    renderUpdateBanner(data);
                }).catch(function(e) { console.error("Error comprobando actualizaciones:", e); });
            }

            function dismissUpdateBanner() {
                let banner = document.getElementById("update-banner");
                if (banner.dataset.latestVersion) {
                    localStorage.setItem("cicada_dismissed_update", banner.dataset.latestVersion);
                }
                banner.classList.add("hidden");
                banner.classList.remove("flex");
            }

            function toggleSecretVisibility(inputId, btn) {
                let input = document.getElementById(inputId);
                if (input.type === "password") {
                    input.type = "text";
                    btn.textContent = "visibility_off";
                } else {
                    input.type = "password";
                    btn.textContent = "visibility";
                }
            }

            function selectThemeUI(theme) {
                document.getElementById('settings_theme').value = theme;
                document.querySelectorAll('.theme-btn').forEach(function(btn) {
                    if (btn.dataset.themeVal === theme) {
                        btn.classList.add('border-accent', 'bg-accent-light', 'text-main');
                        btn.classList.remove('border-theme', 'bg-input', 'text-muted');
                    } else {
                        btn.classList.remove('border-accent', 'bg-accent-light', 'text-main');
                        btn.classList.add('border-theme', 'bg-input', 'text-muted');
                    }
                });
                document.documentElement.setAttribute('data-theme', theme);
            }

            const LOGO_FILE_BY_COLOR = {
                azul: 'blue',
                verde: 'green',
                morado: 'purple',
                naranja: 'orange',
                rosa: 'pink'
            };

            function setAccentColor(color) {
                document.documentElement.setAttribute('data-color', color);
                let favicon = document.getElementById('favicon-link');
                let logoFile = LOGO_FILE_BY_COLOR[color] || 'blue';
                if (favicon) favicon.href = '/static/logos/cicada_' + logoFile + '.svg';
            }

            function selectColorUI(color) {
                document.getElementById('settings_color').value = color;
                document.querySelectorAll('.color-btn').forEach(function(btn) {
                    if (btn.dataset.colorVal === color) {
                        btn.classList.add('border-[2.5px]', 'border-[#1a1b20]', 'ring-[4px]', 'ring-accent-light');
                    } else {
                        btn.classList.remove('border-[2.5px]', 'border-[#1a1b20]', 'ring-[4px]', 'ring-accent-light');
                    }
                });
                setAccentColor(color);
            }

            async function loadSettingsIntoForm() {
                try {
                    let res = await fetch('/api/settings');
                    let data = await res.json();
                    document.getElementById("settings_acoustid_key").value = data.acoustid_api_key || "";
                    document.getElementById("settings_spotify_id").value = data.spotify_client_id || "";
                    document.getElementById("settings_spotify_secret").value = data.spotify_client_secret || "";
                    document.getElementById("settings_plan_c_enabled").checked = !!data.plan_c_enabled;
                    document.getElementById("settings_library_dir").value = data.library_dir || "";
                    document.getElementById("settings_process_input_dir").value = data.process_input_dir || "";
                    document.getElementById("settings_process_output_dir").value = data.process_output_dir || "";
                    selectThemeUI(data.theme || "grafito");
                    selectColorUI(data.color_accent || "azul");
                } catch (e) {
                    console.error("Error cargando ajustes:", e);
                }
            }

            async function saveSettings() {
                let statusEl = document.getElementById("settings-status");
                let btn = document.getElementById("settingsSaveBtn");
                btn.disabled = true;
                statusEl.textContent = t("settings_saving");

                let payload = {
                    acoustid_api_key: document.getElementById("settings_acoustid_key").value,
                    spotify_client_id: document.getElementById("settings_spotify_id").value,
                    spotify_client_secret: document.getElementById("settings_spotify_secret").value,
                    plan_c_enabled: document.getElementById("settings_plan_c_enabled").checked,
                    library_dir: document.getElementById("settings_library_dir").value,
                    process_input_dir: document.getElementById("settings_process_input_dir").value,
                    process_output_dir: document.getElementById("settings_process_output_dir").value,
                    theme: document.getElementById("settings_theme").value,
                    color_accent: document.getElementById("settings_color").value
                };

                try {
                    let res = await fetch('/api/settings', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload)
                    });
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    let inputDirField = document.getElementById("input_dir");
                    if (inputDirField) inputDirField.value = payload.process_input_dir;
                    let outputDirField = document.getElementById("output_dir");
                    if (outputDirField) outputDirField.value = payload.process_output_dir;

                    let libraryBrowseField = document.getElementById("library_browse_dir");
                    if (libraryBrowseField) libraryBrowseField.value = payload.library_dir;
                    let replicateDirField = document.getElementById("library_dir");
                    if (replicateDirField) replicateDirField.value = payload.library_dir;

                    if (payload.library_dir) {
                        await scanLibrary(payload.library_dir);
                    }
                    
                    document.documentElement.setAttribute('data-theme', payload.theme);
                    setAccentColor(payload.color_accent);

                    statusEl.textContent = t("settings_saved");
                    setTimeout(function() { statusEl.textContent = ""; }, 2500);
                } catch (e) {
                    statusEl.textContent = "";
                    alert(t("alert_error_saving_settings") + e.message);
                } finally {
                    btn.disabled = false;
                }
            }

            async function prefillProcessDirsFromSettings() {
                try {
                    let res = await fetch('/api/settings');
                    let data = await res.json();
                    let inputDirField = document.getElementById("input_dir");
                    if (inputDirField && data.process_input_dir) inputDirField.value = data.process_input_dir;
                    let outputDirField = document.getElementById("output_dir");
                    if (outputDirField && data.process_output_dir) outputDirField.value = data.process_output_dir;
                } catch (e) {
                    console.error("Error precargando carpetas de PROCESS:", e);
                }
            }

            function handleSpotifyAuthRedirect() {
                let params = new URLSearchParams(window.location.search);
                let authResult = params.get("spotify_auth");
                if (!authResult) return;

                let reason = params.get("reason") || "";
                window.history.replaceState({}, document.title, window.location.pathname);
                openSettings();

                if (authResult === "error") {
                    setTimeout(function() {
                        let statusEl = document.getElementById("settings-spotify-status");
                        if (statusEl) statusEl.textContent = t("error_prefix") + (reason || t("error_unknown"));
                    }, 300);
                }
            }

            applyLanguage(currentLang);
            showView('process');
            loadLibraryConfig();
            prefillProcessDirsFromSettings();
            
            fetch('/api/settings').then(r => r.json()).then(data => {
                document.documentElement.setAttribute('data-theme', data.theme || "grafito");
                setAccentColor(data.color_accent || "azul");
            }).catch(e => console.error("Error loading theme", e));
            handleSpotifyAuthRedirect();
            checkForUpdates();
        
