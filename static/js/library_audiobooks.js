// Exploración de carpeta para audiolibros — calcado del flujo de música en
// library.js, pero sin tags de biblioteca organizada: metadata leída
// directo del archivo (título/autor/narrador/duración/capítulos).
let audiobookResults = [];
let audiobookSelectMode = false;
let audiobookSelected = new Set();

async function scanAudiobookFolder() {
    let dir = document.getElementById("audiobook_browse_dir").value.trim();
    if (!dir) {
        alert(t("alert_choose_folder_first"));
        return;
    }
    let browserEl = document.getElementById("audiobook-browser");
    browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("library_scanning") + '</p>';
    try {
        let res = await fetch('/api/library/browse_audiobooks?library_dir=' + encodeURIComponent(dir));
        let data = await res.json();
        if (!res.ok) throw new Error(data.detail || t("error_unknown"));

        audiobookResults = data.audiobooks || [];
        document.getElementById("audiobook-count").textContent = audiobookResults.length + t("library_track_count_suffix");
        renderAudiobookBrowser();
    } catch (e) {
        browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-[#f43f5e]">' + t("error_prefix") + e.message + '</p>';
    }
}

function formatAudiobookDuration(durationMs) {
    if (!durationMs) return "";
    return formatDurationWords(durationMs / 1000);
}

function audiobookRowHtml(ab) {
    let pathEscaped = escapeHtml(ab.path);
    let subtitleParts = [];
    if (ab.author) subtitleParts.push(escapeHtml(ab.author));
    if (ab.duration_ms) subtitleParts.push(formatAudiobookDuration(ab.duration_ms));
    if (ab.chapter_count) subtitleParts.push(ab.chapter_count + " " + t("ipod_tracks_count"));
    let subtitle = subtitleParts.join(" &middot; ");

    if (audiobookSelectMode) {
        let sel = audiobookSelected.has(ab.path);
        return '<div class="flex items-center gap-3 px-2 py-1.5 rounded-lg cursor-pointer transition-colors ' +
            (sel ? 'ring-1 ring-secondary bg-secondary/10' : 'hover:bg-btn-hover') + '" data-path="' + pathEscaped +
            '" onclick="toggleAudiobookSelect(this)">' +
            '<span class="material-symbols-outlined text-[18px] text-secondary">' + (sel ? 'check_circle' : 'radio_button_unchecked') + '</span>' +
            '<div class="overflow-hidden flex-1">' +
            '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(ab.title) + '</p>' +
            '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + subtitle + '</p>' +
            '</div></div>';
    }
    return '<div class="flex items-center gap-3 px-2 py-1.5 rounded-lg" data-path="' + pathEscaped + '">' +
        '<span class="material-symbols-outlined text-[18px] text-muted/40">menu_book</span>' +
        '<div class="overflow-hidden flex-1">' +
        '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(ab.title) + '</p>' +
        '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + subtitle + '</p>' +
        '</div></div>';
}

function renderAudiobookBrowser() {
    let browserEl = document.getElementById("audiobook-browser");
    if (audiobookResults.length === 0) {
        browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("library_no_songs_in_folder") + '</p>';
        return;
    }
    browserEl.innerHTML = audiobookResults.map(audiobookRowHtml).join("");
}

function updateAudiobookIpodButton() {
    const btn = document.getElementById("audiobook-add-ipod-btn");
    if (!btn) return;
    const uiEnabled = (typeof ipodUiEnabled === "undefined") || ipodUiEnabled;
    const connected = uiEnabled && (typeof ipodState !== "undefined") && ipodState.connected;
    if (!connected && audiobookSelectMode) exitAudiobookSelectMode();
    btn.classList.toggle("hidden", !connected);
    btn.classList.toggle("inline-flex", !!connected);
}

function onAudiobookIpodButton() {
    if (!audiobookSelectMode) {
        audiobookSelectMode = true;
        audiobookSelected.clear();
        renderAudiobookBrowser();
        updateAudiobookSelectUI();
    } else {
        commitAudiobookSelectionToIpod();
    }
}

function exitAudiobookSelectMode() {
    audiobookSelectMode = false;
    audiobookSelected.clear();
    renderAudiobookBrowser();
    updateAudiobookSelectUI();
}

function toggleAudiobookSelect(el) {
    const path = el.dataset.path;
    const now = !audiobookSelected.has(path);
    if (now) audiobookSelected.add(path); else audiobookSelected.delete(path);
    el.classList.toggle("ring-1", now);
    el.classList.toggle("ring-secondary", now);
    el.classList.toggle("bg-secondary/10", now);
    el.classList.toggle("hover:bg-btn-hover", !now);
    const icon = el.querySelector(".material-symbols-outlined");
    if (icon) icon.textContent = now ? "check_circle" : "radio_button_unchecked";
    updateAudiobookSelectUI();
}

function updateAudiobookSelectUI() {
    const label = document.getElementById("audiobook-add-ipod-label");
    const cancel = document.getElementById("audiobook-select-cancel-btn");
    const btn = document.getElementById("audiobook-add-ipod-btn");
    if (cancel) {
        cancel.classList.toggle("hidden", !audiobookSelectMode);
        cancel.classList.toggle("inline-flex", audiobookSelectMode);
    }
    if (label) {
        label.textContent = audiobookSelectMode
            ? t("library_add_selected").replace("{n}", audiobookSelected.size)
            : t("library_add_to_ipod");
    }
    if (btn) btn.classList.toggle("bg-secondary/25", audiobookSelectMode);
}

function commitAudiobookSelectionToIpod() {
    if (audiobookSelected.size === 0) { alert(t("library_select_none")); return; }
    const items = audiobookResults
        .filter(ab => audiobookSelected.has(ab.path))
        .map(ab => ({
            source_path: ab.path,
            title: ab.title || "",
            artist: ab.author || null,
            album_artist: ab.narrator || null,
            length_ms: ab.duration_ms || null,
            filetype: ab.filetype || null,
            kind: "audiobook",
        }));
    const added = (typeof addToSyncBasket === "function") ? addToSyncBasket(items) : 0;
    exitAudiobookSelectMode();
    alert(t("library_added_to_ipod").replace("{n}", added));
}
