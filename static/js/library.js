// Extraído de cicada/core/main.py — sin cambios de comportamiento. Ver docs/IPOD_INTEGRATION.md
let libraryTracks = [];
let librarySelectMode = false;          // modo "Agregar a iPod": selección múltiple
let librarySelected = new Set();        // paths seleccionados
let libraryPlaylists = [];
let libraryGrouping = "all";
let libraryViewMode = "list";
let librarySortAlpha = true;
let librarySearchQuery = "";
async function loadLibraryConfig() {
    try {
        let res = await fetch('/api/library/config');
        let data = await res.json();
        let dir = data.library_dir || "";
        if (!dir) return;

        let browseInput = document.getElementById("library_browse_dir");
        if (browseInput) browseInput.value = dir;
        // Precarga también el campo de la pestaña PLAYLISTS si todavía está vacío
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
    let pathEscaped = escapeHtml(track.path);
    if (librarySelectMode) {
        const sel = librarySelected.has(track.path);
        return '<div class="flex items-center gap-3 px-2 py-1.5 rounded-lg cursor-pointer transition-colors ' +
            (sel ? 'ring-1 ring-secondary bg-secondary/10' : 'hover:bg-btn-hover') + '" data-path="' + pathEscaped +
            '" onclick="toggleLibrarySelectTrack(this)">' +
            '<span class="material-symbols-outlined text-[18px] text-secondary">' + (sel ? 'check_circle' : 'radio_button_unchecked') + '</span>' +
            '<div class="overflow-hidden flex-1">' +
            '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(track.title) + '</p>' +
            '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + subtitle + '</p>' +
            '</div></div>';
    }
    return '<div class="flex items-center gap-3 px-2 py-1.5 rounded-lg cursor-pointer hover:bg-btn-hover transition-colors" data-path="' + pathEscaped + '" onclick="playFromQueue(\'' + queueKey + '\', ' + index + ')" oncontextmenu="showLibraryContextMenu(event, this)">' +
        '<span class="material-symbols-outlined text-[18px] text-muted/40">music_note</span>' +
        '<div class="overflow-hidden flex-1">' +
        '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(track.title) + '</p>' +
        '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + subtitle + '</p>' +
        '</div></div>';
}

function libraryTrackCardHtml(track, queueKey, index) {
    let pathEscaped = escapeHtml(track.path);
    if (librarySelectMode) {
        const sel = librarySelected.has(track.path);
        return '<div class="flex flex-col gap-2 p-2 rounded-lg cursor-pointer transition-colors ' +
            (sel ? 'ring-1 ring-secondary bg-secondary/10' : 'hover:bg-btn-hover') + '" data-path="' + pathEscaped +
            '" onclick="toggleLibrarySelectTrack(this)">' +
            '<div class="relative w-full aspect-square rounded-lg bg-btn overflow-hidden flex items-center justify-center">' +
            '<span class="material-symbols-outlined text-[28px] text-muted/30">music_note</span>' +
            '<img src="/api/library/artwork?path=' + encodeURIComponent(track.path) + '" class="absolute inset-0 w-full h-full object-cover" loading="lazy" onerror="this.remove()" alt="">' +
            (sel ? '<span class="absolute top-1 right-1 material-symbols-outlined text-[20px] text-secondary bg-card rounded-full leading-none">check_circle</span>' : '') +
            '</div>' +
            '<div class="overflow-hidden">' +
            '<p class="font-data-sm text-[13px] truncate">' + escapeHtml(track.title) + '</p>' +
            '<p class="font-label-caps text-[10px] text-muted/40 truncate">' + escapeHtml(track.artist || "") + '</p>' +
            '</div></div>';
    }
    return '<div class="flex flex-col gap-2 p-2 rounded-lg cursor-pointer hover:bg-btn-hover transition-colors" data-path="' + pathEscaped + '" onclick="playFromQueue(\'' + queueKey + '\', ' + index + ')" oncontextmenu="showLibraryContextMenu(event, this)">' +
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
function showLibraryContextMenu(event, el) {
    event.preventDefault();
    event.stopPropagation();
    contextMenuTrackPath = el.dataset.path;
    const menu = document.getElementById("library-context-menu");
    menu.style.display = "flex";
    
    // Adjust position
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

function libraryGroupSectionHtml(name, tracks, key) {
    let rowFn = libraryViewMode === "grid" ? libraryTrackCardHtml : libraryTrackRowHtml;
    let selAll = librarySelectMode
        ? ' <button type="button" onclick="event.preventDefault();event.stopPropagation();selectLibraryGroup(' + JSON.stringify(key).replace(/"/g, "&quot;") + ')" class="ml-2 font-normal text-[11px] text-secondary hover:underline">' + t("library_select_all_group") + '</button>'
        : '';
    return '<details class="library-group" open>' +
        '<summary class="font-label-caps text-[13px] text-main font-bold py-2 mt-1">' + escapeHtml(name) +
        ' <span class="font-normal text-[12px] text-muted">(' + tracks.length + ')</span>' + selAll + '</summary>' +
        '<div class="' + libraryTracksContainerClass() + ' pl-3 pb-2">' +
        tracks.map(function(track, i) { return rowFn(track, key, i); }).join("") +
        '</div></details>';
}

function renderLibraryBrowser() {
    let browserEl = document.getElementById("library-browser");
    libraryQueues = {};
    browserEl.className = "flex flex-col gap-1";
    updateLibraryIpodButton();

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

// --- Agregar a iPod (modo selección; alimenta el carrito de sincronización) ---
function updateLibraryIpodButton() {
    const btn = document.getElementById("library-add-ipod-btn");
    if (!btn) return;
    const connected = (typeof ipodState !== "undefined") && ipodState.connected;
    if (!connected && librarySelectMode) exitLibrarySelectMode();
    btn.classList.toggle("hidden", !connected);
    btn.classList.toggle("inline-flex", !!connected);
}

function onLibraryIpodButton() {
    if (!librarySelectMode) {
        librarySelectMode = true;
        librarySelected.clear();
        renderLibraryBrowser();
        updateLibrarySelectUI();
    } else {
        commitLibrarySelectionToIpod();
    }
}

function exitLibrarySelectMode() {
    librarySelectMode = false;
    librarySelected.clear();
    renderLibraryBrowser();
    updateLibrarySelectUI();
}

function toggleLibrarySelectTrack(el) {
    const path = el.dataset.path;
    const now = !librarySelected.has(path);
    if (now) librarySelected.add(path); else librarySelected.delete(path);
    el.classList.toggle("ring-1", now);
    el.classList.toggle("ring-secondary", now);
    el.classList.toggle("bg-secondary/10", now);
    el.classList.toggle("hover:bg-btn-hover", !now);
    const icon = el.querySelector(".material-symbols-outlined");
    if (icon) {
        const cur = icon.textContent.trim();
        if (cur === "radio_button_unchecked" || cur === "check_circle") {
            icon.textContent = now ? "check_circle" : "radio_button_unchecked";
        }
    }
    updateLibrarySelectUI();
}

function selectLibraryGroup(key) {
    (libraryQueues[key] || []).forEach(tr => { if (tr && tr.path) librarySelected.add(tr.path); });
    renderLibraryBrowser();
    updateLibrarySelectUI();
}

function updateLibrarySelectUI() {
    const label = document.getElementById("library-add-ipod-label");
    const cancel = document.getElementById("library-select-cancel-btn");
    const btn = document.getElementById("library-add-ipod-btn");
    if (cancel) {
        cancel.classList.toggle("hidden", !librarySelectMode);
        cancel.classList.toggle("inline-flex", librarySelectMode);
    }
    if (label) {
        label.textContent = librarySelectMode
            ? t("library_add_selected").replace("{n}", librarySelected.size)
            : t("library_add_to_ipod");
    }
    if (btn) btn.classList.toggle("bg-secondary/25", librarySelectMode);
}

function commitLibrarySelectionToIpod() {
    if (librarySelected.size === 0) { alert(t("library_select_none")); return; }
    const items = libraryTracks
        .filter(tr => librarySelected.has(tr.path))
        .map(tr => ({
            source_path: tr.path,
            title: tr.title || "",
            artist: tr.artist || null,
            album: tr.album || null,
            length_ms: tr.duration_ms || tr.length_ms || null,
            filetype: (String(tr.path).split(".").pop() || "").toLowerCase(),
        }));
    const added = (typeof addToSyncBasket === "function") ? addToSyncBasket(items) : 0;
    exitLibrarySelectMode();
    alert(t("library_added_to_ipod").replace("{n}", added));
}

// --- Reproductor ---
