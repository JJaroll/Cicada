// Extraído de cicada/core/main.py — sin cambios de comportamiento. Ver docs/IPOD_INTEGRATION.md
let resolvedSpotifyTracks = [];

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

// --- Pestaña PLAYLISTS: navegar playlists, ver canciones y replicarlas contra la biblioteca local ---
