// Extraído de cicada/core/main.py — sin cambios de comportamiento. Ver docs/IPOD_INTEGRATION.md
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

    // Al cambiar de playlist, el preview de replicación anterior ya no aplica
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

        // Conservamos el track de Spotify completo (álbum, artwork, ISRC, etc.), no
        // solo title/artist/path: hace falta para re-etiquetar si el usuario asocia
        // manualmente un archivo que el fuzzy matching no encontró solo.
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
        // Solo las pistas no encontradas automáticamente pueden asociarse a mano o descargarse;
        // las que ya matchearon quedan intactas.
        let manualBtn = matched ? '' :
            '<button type="button" onclick="manualMatchTrack(' + i + ')" title="Asociar con un archivo de mi biblioteca" class="material-symbols-outlined text-[16px] text-accent/80 hover:text-accent">attach_file</button>' +
            '<button type="button" onclick="downloadMissingTrack(' + i + ')" title="Descargar e inyectar metadatos" class="material-symbols-outlined text-[16px] text-secondary hover:text-accent ml-1">download</button>';
        return '<div class="replicate-track-row flex items-center gap-2 ' + rowClasses + ' border border-transparent rounded-lg p-2" ' +
            'draggable="true" data-index="' + i + '" ' +
            'ondragstart="handleTrackDragStart(event, ' + i + ')" ondragend="handleTrackDragEnd(event)" ' +
            'ondragover="handleTrackDragOver(event)" ondrop="handleTrackDrop(event)">' +
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

// --- Drag and drop libre para reordenar el preview de la playlist ---
let dragSourceIndex = null;
let draggedNode = null;

function handleTrackDragStart(e, index) {
    dragSourceIndex = index;
    draggedNode = e.currentTarget;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(index));
    e.currentTarget.classList.add("opacity-40", "dragging");
}

function handleTrackDragEnd(e) {
    e.currentTarget.classList.remove("opacity-40", "dragging");
    draggedNode = null;
}

function handleTrackDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    
    if (draggedNode && draggedNode !== e.currentTarget) {
        const bounding = e.currentTarget.getBoundingClientRect();
        const offset = bounding.y + (bounding.height / 2);
        if (e.clientY - offset > 0) {
            e.currentTarget.after(draggedNode);
        } else {
            e.currentTarget.before(draggedNode);
        }
    }
}

function handleTrackDrop(e) {
    e.preventDefault();
    if (dragSourceIndex === null) return;
    
    const container = document.getElementById("replicate-track-list");
    const newRows = container.querySelectorAll(".replicate-track-row");
    let newMatches = [];
    newRows.forEach(row => {
        let oldIdx = parseInt(row.dataset.index);
        newMatches.push(replicateMatches[oldIdx]);
    });
    
    replicateMatches = newMatches;
    dragSourceIndex = null;
    draggedNode = null;
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
    if (!pickData.path) return; // el usuario cerró el diálogo sin elegir nada

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
    // Encontrar el botón visualmente para mostrar estado de carga
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

// --- Pestaña LIBRARY: carpeta persistente, navegador agrupable y reproductor ---
