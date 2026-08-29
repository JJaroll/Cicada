// Exploración y selección interactiva de audiolibros locales para el iPod.
let audiobookResults = [];
let audiobookSelectMode = true;
let audiobookSelected = new Set();

async function scanAudiobookFolder() {
    let dir = document.getElementById("audiobook_browse_dir").value.trim();
    if (!dir) {
        alert(t("alert_choose_folder_first"));
        return;
    }
    let browserEl = document.getElementById("audiobook-browser");
    browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40 p-3">' + t("library_scanning") + '</p>';
    try {
        let res = await fetch('/api/library/browse_audiobooks?library_dir=' + encodeURIComponent(dir));
        let data = await res.json();
        if (!res.ok) throw new Error(data.detail || t("error_unknown"));

        audiobookResults = data.audiobooks || [];
        audiobookSelected.clear();
        audiobookSelectMode = true;

        if (audiobookResults.length === 1) {
            audiobookSelected.add(audiobookResults[0].path);
        }

        renderAudiobookBrowser();
        updateAudiobookIpodButton();
        updateAudiobookSelectUI();
    } catch (e) {
        browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-[#f43f5e] p-3">' + t("error_prefix") + e.message + '</p>';
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

    let sel = audiobookSelected.has(ab.path);
    return '<div class="flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all ' +
        (sel ? 'ring-2 ring-accent bg-accent/15 border-transparent shadow-sm' : 'bg-black/10 dark:bg-white/5 hover:bg-black/20 dark:hover:bg-white/10 border border-transparent') +
        '" data-path="' + pathEscaped + '" onclick="toggleAudiobookSelect(this)">' +
        '<span class="material-symbols-outlined text-[22px] text-accent flex-shrink-0 transition-transform ' + (sel ? 'scale-110' : 'opacity-60') + '">' +
        (sel ? 'check_circle' : 'radio_button_unchecked') +
        '</span>' +
        '<div class="overflow-hidden flex-1">' +
        '<p class="font-data-sm text-[14px] font-semibold text-main truncate">' + escapeHtml(ab.title) + '</p>' +
        '<p class="font-label-caps text-[11px] text-muted/70 truncate mt-0.5">' + subtitle + '</p>' +
        '</div></div>';
}

function renderAudiobookBrowser() {
    let browserEl = document.getElementById("audiobook-browser");
    if (!browserEl) return;
    if (audiobookResults.length === 0) {
        browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40 p-3">' + t("library_no_songs_in_folder") + '</p>';
        return;
    }
    browserEl.innerHTML = audiobookResults.map(audiobookRowHtml).join("");
}

function updateAudiobookIpodButton() {
    const btn = document.getElementById("audiobook-add-ipod-btn");
    if (!btn) return;
    const connected = (typeof ipodState !== "undefined") && ipodState.connected;
    const hasResults = audiobookResults.length > 0;
    btn.classList.toggle("hidden", !(connected && hasResults));
    btn.classList.toggle("inline-flex", (connected && hasResults));
}

function onAudiobookIpodButton() {
    if (audiobookResults.length === 0) {
        alert("Primero busca y encuentra audiolibros en una carpeta.");
        return;
    }
    if (audiobookSelected.size === 0) {
        if (audiobookResults.length === 1) {
            audiobookSelected.add(audiobookResults[0].path);
            renderAudiobookBrowser();
            updateAudiobookSelectUI();
        } else {
            alert("Por favor selecciona al menos un audiolibro de la lista.");
            return;
        }
    }
    commitAudiobookSelectionToIpod();
}

function exitAudiobookSelectMode() {
    audiobookSelected.clear();
    renderAudiobookBrowser();
    updateAudiobookSelectUI();
}

function toggleAudiobookSelect(el) {
    const path = el.dataset.path;
    if (!path) return;
    const now = !audiobookSelected.has(path);
    if (now) audiobookSelected.add(path); else audiobookSelected.delete(path);
    el.classList.toggle("ring-2", now);
    el.classList.toggle("ring-accent", now);
    el.classList.toggle("bg-accent/15", now);
    el.classList.toggle("shadow-sm", now);
    const icon = el.querySelector(".material-symbols-outlined");
    if (icon) {
        icon.textContent = now ? "check_circle" : "radio_button_unchecked";
        icon.classList.toggle("scale-110", now);
        icon.classList.toggle("opacity-60", !now);
    }
    updateAudiobookSelectUI();
}

function updateAudiobookSelectUI() {
    const label = document.getElementById("audiobook-add-ipod-label");
    const countEl = document.getElementById("audiobook-count");
    const selectedCount = audiobookSelected.size;
    const totalCount = audiobookResults.length;

    if (countEl) {
        if (totalCount === 0) {
            countEl.textContent = "";
        } else if (selectedCount > 0) {
            countEl.textContent = `${selectedCount} de ${totalCount} seleccionados`;
        } else {
            countEl.textContent = `${totalCount} ${totalCount === 1 ? 'audiolibro' : 'audiolibros'}`;
        }
    }

    if (label) {
        label.textContent = selectedCount > 0
            ? `Agregar a iPod (${selectedCount})`
            : `Agregar a iPod`;
    }
}

function commitAudiobookSelectionToIpod() {
    if (audiobookSelected.size === 0) {
        alert(t("library_select_none"));
        return;
    }
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
    
    if (typeof closeAddAudiobookModal === "function") {
        closeAddAudiobookModal();
    }
    
    exitAudiobookSelectMode();
    alert(t("library_added_to_ipod").replace("{n}", added));
    
    if (typeof selectIpodCategory === "function") {
        selectIpodCategory("sync");
    }
}

