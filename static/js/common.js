// Extraído de cicada/core/main.py — sin cambios de comportamiento. Ver docs/IPOD_INTEGRATION.md
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

    // Re-renderiza listas dinámicas ya pobladas para que también cambien de idioma
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

    // Textos de estado que no usan data-i18n porque a veces muestran datos reales
    // (nombre de archivo, título de pista) en vez de una frase traducible.
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
let sessionFiles = [];
let hasStartedProcessing = false;
let hasPlayedTrack = false;
let currentWsStatusKey = "ws_connecting_short";
let currentWsColor = "#9ca3af";
let currentStatusPillKey = "player_waiting_status";
let currentStatusPillColor = "#10b981";

// --- Navegación entre vistas ---
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
    // El módulo derecho no aporta nada en PLAYLISTS (se oculta); en LIBRARY funciona
    // como reproductor en vez de panel de progreso.
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

function escapeHtml(text) {
    let div = document.createElement("div");
    div.textContent = text == null ? "" : text;
    return div.innerHTML;
}

function formatTime(seconds) {
    if (!isFinite(seconds) || seconds < 0) return "0:00";
    let m = Math.floor(seconds / 60);
    let s = Math.floor(seconds % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
}

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

// --- Modal "Sobre" (About): se abre al hacer clic en el logo "C." de la barra lateral ---
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

// --- Modal de apoyo (Ko-fi): tras completar un lote grande de canciones ---
const KOFI_SUPPORT_THRESHOLD = 250;
const MANUAL_TAGGING_MINUTES_PER_SONG = 5; // estimación de tiempo de etiquetado manual por canción

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

// --- Aviso de actualización: comprueba el último release estable de GitHub ---
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

// Nombre de archivo de logo (en inglés) para cada color de acento (en español)
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

        // Reflejar los cambios en los campos ya visibles de otras pestañas, sin recargar la página
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

// --- IPOD SYNC LOGIC ---
