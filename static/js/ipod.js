// static/js/ipod.js — Lógica de interfaz y control del iPod en Cicada

let ipodState = {
    connected: false,
    device: null,
    tracks: [],
    playlists: [],
    photos: [],
    videos: [],
    podcasts: [],
    audiobooks: [],
    currentCategory: 'songs',
    viewMode: 'list', // 'list' | 'grid'
    searchQuery: '',
    filters: {
        genre: '',
        year: '',
        artist: '',
        album: ''
    },
    selectedPlaylistIndex: 0,
    selectedPodcastIndex: 0,
    selectedAudiobookIndex: 0
};

function _setIpodButtons(enabled) {
    for (const id of ["btn-sync-ipod", "btn-backup-ipod", "btn-eject-ipod"]) {
        const b = document.getElementById(id);
        if (!b) continue;
        b.disabled = !enabled;
        b.classList.toggle("opacity-50", !enabled);
        b.classList.toggle("cursor-not-allowed", !enabled);
    }
}

function _escapeHtmlIpod(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, c =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function _formatMs(ms) {
    if (!ms || ms <= 0) return "--:--";
    const totalSec = Math.floor(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
}

function _formatBytes(b) {
    if (!b || b <= 0) return "0 B";
    if (b >= 1073741824) return (b / 1073741824).toFixed(1) + " GB";
    if (b >= 1048576) return (b / 1048576).toFixed(1) + " MB";
    if (b >= 1024) return (b / 1024).toFixed(1) + " KB";
    return b + " B";
}

// --- ESCANEO DEL DISPOSITIVO ---
async function scanIpod() {
    const container = document.getElementById("ipod-info-container");
    const noDevice = document.getElementById("ipod-no-device");
    const noControl = document.getElementById("ipod-no-control");
    const mainBrowser = document.getElementById("ipod-main-browser");

    try {
        const res = await fetch('/api/ipod/scan');
        const data = await res.json();

        if (data.state === "ready" && data.ipods && data.ipods.length > 0) {
            const ipod = data.ipods[0];
            ipodState.connected = true;
            ipodState.device = ipod;

            const nameEl = document.getElementById("ipod-name");
            if (nameEl) nameEl.textContent = ipod.ipod_name || "iPod";

            const modelParts = [ipod.model_family, ipod.generation, ipod.color].filter(Boolean);
            const modelEl = document.getElementById("ipod-model");
            if (modelEl) {
                modelEl.textContent = t("ipod_model_label") + ": " + (modelParts.join(" ") || t("ipod_unknown"));
            }

            const capEl = document.getElementById("ipod-capacity");
            if (capEl) {
                capEl.textContent = t("ipod_capacity_label") + ": " + (ipod.capacity || t("ipod_unknown"));
            }

            const fmtEl = document.getElementById("ipod-format");
            if (fmtEl) {
                fmtEl.textContent = t("ipod_signature_label") + ": " + (ipod.checksum || t("ipod_unknown"));
            }

            // Imagen del iPod
            const imgEl = document.getElementById("ipod-device-img");
            if (imgEl && ipod.image_url) {
                imgEl.src = ipod.image_url;
            }

            // Almacenamiento
            renderIpodStorage(ipod.storage);

            if (container) container.classList.remove("hidden");
            if (noDevice) noDevice.classList.add("hidden");
            if (noControl) noControl.classList.add("hidden");
            if (mainBrowser) mainBrowser.classList.remove("hidden");
            _setIpodButtons(true);

            await loadIpodLibrary();
            switchIpodCategory(ipodState.currentCategory || "songs");
        } else if (data.state === "no_ipod_control") {
            ipodState.connected = false;
            if (container) container.classList.add("hidden");
            if (mainBrowser) mainBrowser.classList.add("hidden");
            if (noDevice) noDevice.classList.add("hidden");
            if (noControl) noControl.classList.remove("hidden");
            _setIpodButtons(false);
        } else {
            ipodState.connected = false;
            if (container) container.classList.add("hidden");
            if (mainBrowser) mainBrowser.classList.add("hidden");
            if (noControl) noControl.classList.add("hidden");
            if (noDevice) noDevice.classList.remove("hidden");
            _setIpodButtons(false);
        }
    } catch (e) {
        console.error("Error escaneando iPod:", e);
        alert(t("ipod_scan_error"));
    }
}

// --- RENDER DE ALMACENAMIENTO ---
function renderIpodStorage(storage) {
    const storageText = document.getElementById("ipod-storage-text");
    if (!storage || storage.total_bytes === 0) {
        if (storageText) storageText.textContent = "Capacidad disponible";
        return;
    }

    const total = storage.total_bytes;
    const used = storage.used_bytes;
    const free = storage.free_bytes;

    const pctAudio = total > 0 ? (storage.audio_bytes / total) * 100 : 0;
    const pctVideo = total > 0 ? (storage.video_bytes / total) * 100 : 0;
    const pctPhotos = total > 0 ? (storage.photos_bytes / total) * 100 : 0;
    const pctPodcasts = total > 0 ? (storage.podcasts_bytes / total) * 100 : 0;
    const pctOther = total > 0 ? (storage.other_bytes / total) * 100 : 0;

    const segAudio = document.getElementById("storage-seg-audio");
    const segVideo = document.getElementById("storage-seg-video");
    const segPhotos = document.getElementById("storage-seg-photos");
    const segPodcasts = document.getElementById("storage-seg-podcasts");
    const segOther = document.getElementById("storage-seg-other");

    if (segAudio) {
        segAudio.style.width = pctAudio > 0 ? Math.max(pctAudio, 1.2).toFixed(2) + "%" : "0%";
        segAudio.title = `Audio: ${_formatBytes(storage.audio_bytes)} (${pctAudio.toFixed(1)}%)`;
    }
    if (segVideo) {
        segVideo.style.width = pctVideo > 0 ? Math.max(pctVideo, 1.2).toFixed(2) + "%" : "0%";
        segVideo.title = `Video: ${_formatBytes(storage.video_bytes)} (${pctVideo.toFixed(1)}%)`;
    }
    if (segPhotos) {
        segPhotos.style.width = pctPhotos > 0 ? Math.max(pctPhotos, 1.2).toFixed(2) + "%" : "0%";
        segPhotos.title = `Fotos: ${_formatBytes(storage.photos_bytes)} (${pctPhotos.toFixed(1)}%)`;
    }
    if (segPodcasts) {
        segPodcasts.style.width = pctPodcasts > 0 ? Math.max(pctPodcasts, 1.2).toFixed(2) + "%" : "0%";
        segPodcasts.title = `Podcasts: ${_formatBytes(storage.podcasts_bytes)} (${pctPodcasts.toFixed(1)}%)`;
    }
    if (segOther) {
        segOther.style.width = pctOther > 0 ? Math.max(pctOther, 1.2).toFixed(2) + "%" : "0%";
        segOther.title = `Otro: ${_formatBytes(storage.other_bytes)} (${pctOther.toFixed(1)}%)`;
    }

    // Actualizar leyendas con tamaños exactos
    const legAudio = document.getElementById("storage-legend-audio");
    const legVideo = document.getElementById("storage-legend-video");
    const legPhotos = document.getElementById("storage-legend-photos");
    const legOther = document.getElementById("storage-legend-other");

    if (legAudio) legAudio.textContent = `${t("ipod_storage_audio")} (${_formatBytes(storage.audio_bytes)})`;
    if (legVideo) legVideo.textContent = `${t("ipod_storage_video")} (${_formatBytes(storage.video_bytes)})`;
    if (legPhotos) legPhotos.textContent = `${t("ipod_storage_photos")} (${_formatBytes(storage.photos_bytes)})`;
    if (legOther) legOther.textContent = `${t("ipod_storage_other")} (${_formatBytes(storage.other_bytes)})`;

    if (storageText) {
        storageText.textContent = `${storage.formatted_used} ${t("ipod_storage_used")} · ${storage.formatted_free} ${t("ipod_storage_free")} (${storage.formatted_total})`;
    }
}

// --- CARGA DE CONTENIDO ---
async function loadIpodLibrary() {
    try {
        const [tRes, pRes, phRes, vRes, podRes, abRes] = await Promise.allSettled([
            fetch('/api/ipod/tracks'),
            fetch('/api/ipod/playlists'),
            fetch('/api/ipod/photos'),
            fetch('/api/ipod/videos'),
            fetch('/api/ipod/podcasts'),
            fetch('/api/ipod/audiobooks')
        ]);

        if (tRes.status === "fulfilled" && tRes.value.ok) {
            const data = await tRes.value.json();
            ipodState.tracks = data.tracks || [];
        } else {
            ipodState.tracks = [];
        }

        if (pRes.status === "fulfilled" && pRes.value.ok) {
            const data = await pRes.value.json();
            ipodState.playlists = data.playlists || [];
        } else {
            ipodState.playlists = [];
        }

        if (phRes.status === "fulfilled" && phRes.value.ok) {
            const data = await phRes.value.json();
            ipodState.photos = data.photos || [];
        } else {
            ipodState.photos = [];
        }

        if (vRes.status === "fulfilled" && vRes.value.ok) {
            const data = await vRes.value.json();
            ipodState.videos = data.videos || [];
        } else {
            ipodState.videos = [];
        }

        if (podRes.status === "fulfilled" && podRes.value.ok) {
            const data = await podRes.value.json();
            ipodState.podcasts = data.podcasts || [];
        } else {
            ipodState.podcasts = [];
        }

        if (abRes.status === "fulfilled" && abRes.value.ok) {
            const data = await abRes.value.json();
            ipodState.audiobooks = data.audiobooks || [];
        } else {
            ipodState.audiobooks = [];
        }

        // Actualizar contadores
        updateIpodCategoryCounts();

        // Poblar filtros
        populateIpodFilterDropdowns();

        // Renderizar vista actual
        renderCurrentIpodCategory();
    } catch (e) {
        console.error("Error cargando biblioteca del iPod:", e);
    }
}

function updateIpodCategoryCounts() {
    const cSongs = document.getElementById("ipod-count-songs");
    const cPls = document.getElementById("ipod-count-playlists");
    const cPhotos = document.getElementById("ipod-count-photos");
    const cVideos = document.getElementById("ipod-count-videos");
    const cPods = document.getElementById("ipod-count-podcasts");
    const cAbs = document.getElementById("ipod-count-audiobooks");

    if (cSongs) cSongs.textContent = ipodState.tracks.length;
    if (cPls) cPls.textContent = ipodState.playlists.length;
    if (cPhotos) cPhotos.textContent = ipodState.photos.length;
    if (cVideos) cVideos.textContent = ipodState.videos.length;
    if (cPods) cPods.textContent = ipodState.podcasts.length;
    if (cAbs) cAbs.textContent = ipodState.audiobooks.length;
}

// --- POBLAR DROPDOWNS DE FILTRO ---
function populateIpodFilterDropdowns() {
    const genres = new Set();
    const years = new Set();
    const artists = new Set();
    const albums = new Set();

    for (const t of ipodState.tracks) {
        if (t.genre) genres.add(t.genre);
        if (t.year && t.year > 0) years.add(t.year);
        if (t.artist) artists.add(t.artist);
        if (t.album) albums.add(t.album);
    }

    _fillSelect("ipod-filter-genre", Array.from(genres).sort());
    _fillSelect("ipod-filter-year", Array.from(years).sort((a, b) => b - a));
    _fillSelect("ipod-filter-artist", Array.from(artists).sort());
    _fillSelect("ipod-filter-album", Array.from(albums).sort());
}

function _fillSelect(id, items) {
    const sel = document.getElementById(id);
    if (!sel) return;
    const currentVal = sel.value;
    sel.innerHTML = `<option value="">${t("ipod_filter_all")}</option>` +
        items.map(it => `<option value="${_escapeHtmlIpod(it)}">${_escapeHtmlIpod(it)}</option>`).join("");
    if (currentVal) sel.value = currentVal;
}

// --- CAMBIO DE CATEGORÍA ---
function switchIpodCategory(category) {
    ipodState.currentCategory = category;

    // Actualizar botones de sub-sidebar
    document.querySelectorAll(".ipod-cat-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.cat === category);
    });

    // Ocultar todos los contenedores de categoría
    const containers = [
        "ipod-view-songs",
        "ipod-view-playlists",
        "ipod-view-photos",
        "ipod-view-videos",
        "ipod-view-podcasts",
        "ipod-view-audiobooks"
    ];
    containers.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add("hidden");
    });

    // Mostrar el contenedor de la categoría activa
    const targetEl = document.getElementById(`ipod-view-${category}`);
    if (targetEl) targetEl.classList.remove("hidden");

    // Visibilidad del switch de vista y filtros según la categoría
    const viewSwitch = document.getElementById("ipod-viewmode-switch");
    const filterBtn = document.getElementById("ipod-filter-btn");
    if (viewSwitch) {
        viewSwitch.style.display = (category === "songs") ? "flex" : "none";
    }
    if (filterBtn) {
        filterBtn.style.display = (category === "songs") ? "inline-flex" : "none";
    }

    renderCurrentIpodCategory();
}

function renderCurrentIpodCategory() {
    switch (ipodState.currentCategory) {
        case "songs":
            renderIpodSongs();
            break;
        case "playlists":
            renderIpodPlaylists();
            break;
        case "photos":
            renderIpodPhotos();
            break;
        case "videos":
            renderIpodVideos();
            break;
        case "podcasts":
            renderIpodPodcasts();
            break;
        case "audiobooks":
            renderIpodAudiobooks();
            break;
    }
}

// --- VISTA 1: CANCIONES ---
function renderIpodSongs() {
    const listContainer = document.getElementById("ipod-songs-list");
    const gridContainer = document.getElementById("ipod-songs-grid");
    if (!listContainer || !gridContainer) return;

    let filtered = ipodState.tracks.filter(t => {
        if (ipodState.searchQuery) {
            const q = ipodState.searchQuery.toLowerCase();
            const matches = (t.title && t.title.toLowerCase().includes(q)) ||
                (t.artist && t.artist.toLowerCase().includes(q)) ||
                (t.album && t.album.toLowerCase().includes(q)) ||
                (t.genre && t.genre.toLowerCase().includes(q));
            if (!matches) return false;
        }
        if (ipodState.filters.genre && t.genre !== ipodState.filters.genre) return false;
        if (ipodState.filters.year && String(t.year) !== String(ipodState.filters.year)) return false;
        if (ipodState.filters.artist && t.artist !== ipodState.filters.artist) return false;
        if (ipodState.filters.album && t.album !== ipodState.filters.album) return false;
        return true;
    });

    if (ipodState.viewMode === "list") {
        listContainer.classList.remove("hidden");
        gridContainer.classList.add("hidden");

        if (filtered.length === 0) {
            listContainer.innerHTML = `<div class="text-center py-10 text-muted/60 font-data-sm text-[13px]">${t("ipod_no_results")}</div>`;
            return;
        }

        listContainer.innerHTML = filtered.map((tr, i) => `
            <div class="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-btn-hover transition-colors group">
                <span class="font-data-sm text-[12px] text-muted/40 w-7 text-right flex-shrink-0">${i + 1}</span>
                <div class="w-8 h-8 rounded-lg bg-btn flex items-center justify-center flex-shrink-0 text-muted/40 group-hover:text-accent">
                    <span class="material-symbols-outlined text-[18px]">music_note</span>
                </div>
                <div class="flex-1 min-w-0">
                    <div class="font-data-sm text-[13px] text-main font-medium truncate">${_escapeHtmlIpod(tr.title || t("track_untitled"))}</div>
                    <div class="font-data-sm text-[12px] text-muted/60 truncate">
                        ${_escapeHtmlIpod(tr.artist || t("track_unknown_artist"))}${tr.album ? ' — ' + _escapeHtmlIpod(tr.album) : ''}
                    </div>
                </div>
                <div class="hidden md:flex items-center gap-4 text-[12px] font-data-sm text-muted/50 flex-shrink-0">
                    ${tr.genre ? `<span class="w-24 truncate">${_escapeHtmlIpod(tr.genre)}</span>` : ''}
                    ${tr.year ? `<span class="w-12 text-center">${tr.year}</span>` : ''}
                    <span class="w-14 text-right">${_formatMs(tr.length_ms)}</span>
                </div>
                <span class="font-data-sm text-[11px] text-muted/40 px-2 py-0.5 rounded bg-btn/50 flex-shrink-0">${_escapeHtmlIpod(tr.filetype || "")}</span>
            </div>
        `).join("");
    } else {
        listContainer.classList.add("hidden");
        gridContainer.classList.remove("hidden");

        if (filtered.length === 0) {
            gridContainer.innerHTML = `<div class="col-span-full text-center py-10 text-muted/60 font-data-sm text-[13px]">${t("ipod_no_results")}</div>`;
            return;
        }

        gridContainer.innerHTML = filtered.map((tr, i) => `
            <div class="ipod-media-card group">
                <div class="aspect-square w-full rounded-lg bg-black/10 dark:bg-white/5 flex items-center justify-center relative overflow-hidden">
                    <span class="material-symbols-outlined text-[36px] text-muted/30 group-hover:text-accent transition-colors">album</span>
                    <span class="absolute bottom-1.5 right-1.5 px-1.5 py-0.5 rounded bg-black/60 text-white font-data-sm text-[10px]">${_formatMs(tr.length_ms)}</span>
                </div>
                <div class="flex flex-col gap-0.5 min-w-0">
                    <h5 class="font-data-sm text-[13px] text-main font-medium truncate">${_escapeHtmlIpod(tr.title || t("track_untitled"))}</h5>
                    <p class="font-data-sm text-[11px] text-muted/60 truncate">${_escapeHtmlIpod(tr.artist || t("track_unknown_artist"))}</p>
                </div>
            </div>
        `).join("");
    }
}

// --- VISTA 2: PLAYLISTS ---
function renderIpodPlaylists() {
    const plsList = document.getElementById("ipod-playlists-list");
    const tracksList = document.getElementById("ipod-playlist-tracks-list");
    const titleEl = document.getElementById("ipod-playlist-title");
    const countEl = document.getElementById("ipod-playlist-count");
    if (!plsList || !tracksList) return;

    if (ipodState.playlists.length === 0) {
        plsList.innerHTML = `<p class="font-data-sm text-[12px] text-muted/40 p-2">No hay playlists en el iPod.</p>`;
        tracksList.innerHTML = `<p class="font-data-sm text-[12px] text-muted/40 p-4">Crea o importa una playlist para ver sus canciones.</p>`;
        return;
    }

    if (ipodState.selectedPlaylistIndex >= ipodState.playlists.length) {
        ipodState.selectedPlaylistIndex = 0;
    }

    plsList.innerHTML = ipodState.playlists.map((p, idx) => {
        const isSelected = idx === ipodState.selectedPlaylistIndex;
        return `
            <div onclick="selectIpodPlaylist(${idx})" class="flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-accent-light text-accent font-semibold' : 'bg-btn hover:bg-btn-hover text-main'}">
                <div class="flex items-center gap-2 min-w-0">
                    <span class="material-symbols-outlined text-[16px] ${p.is_master ? 'text-secondary' : 'text-muted/60'}">${p.is_master ? 'folder_special' : 'queue_music'}</span>
                    <span class="font-data-sm text-[13px] truncate">${_escapeHtmlIpod(p.title || "—")}</span>
                </div>
                <span class="font-data-sm text-[11px] text-muted/60 flex-shrink-0 ml-1">${p.count || 0}</span>
            </div>
        `;
    }).join("");

    const selectedPl = ipodState.playlists[ipodState.selectedPlaylistIndex];
    if (selectedPl) {
        if (titleEl) titleEl.textContent = selectedPl.title || "Playlist";
        if (countEl) countEl.textContent = (selectedPl.count || 0) + " " + t("ipod_tracks_count");

        // Mostrar canciones de la playlist (o las canciones generales si es la master)
        const displayTracks = ipodState.tracks.slice(0, selectedPl.count || ipodState.tracks.length);
        tracksList.innerHTML = displayTracks.map((tr, i) => `
            <div class="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-btn-hover transition-colors">
                <span class="font-data-sm text-[12px] text-muted/40 w-6 text-right flex-shrink-0">${i + 1}</span>
                <div class="flex-1 min-w-0">
                    <div class="font-data-sm text-[13px] text-main truncate font-medium">${_escapeHtmlIpod(tr.title || t("track_untitled"))}</div>
                    <div class="font-data-sm text-[11px] text-muted/60 truncate">${_escapeHtmlIpod(tr.artist || "")}${tr.album ? ' — ' + _escapeHtmlIpod(tr.album) : ''}</div>
                </div>
                <span class="font-data-sm text-[11px] text-muted/50">${_formatMs(tr.length_ms)}</span>
            </div>
        `).join("");
    }
}

function selectIpodPlaylist(idx) {
    ipodState.selectedPlaylistIndex = idx;
    renderIpodPlaylists();
}

// --- VISTA 3: FOTOS ---
function renderIpodPhotos() {
    const grid = document.getElementById("ipod-photos-grid");
    const empty = document.getElementById("ipod-photos-empty");
    if (!grid) return;

    if (ipodState.photos.length === 0) {
        grid.innerHTML = "";
        if (empty) empty.classList.remove("hidden");
        return;
    }

    if (empty) empty.classList.add("hidden");
    grid.innerHTML = ipodState.photos.map((ph, idx) => `
        <div class="ipod-media-card relative group">
            <button type="button" class="hover-delete-btn" onclick="deleteIpodItem('photo', ${idx})" title="${t("ipod_delete_item")}">
                <span class="material-symbols-outlined text-[16px]">remove</span>
            </button>
            <div class="aspect-square w-full rounded-lg bg-black/10 dark:bg-white/5 flex items-center justify-center overflow-hidden">
                ${ph.url ? `<img src="${ph.url}" class="w-full h-full object-cover"/>` : '<span class="material-symbols-outlined text-[32px] text-muted/30">image</span>'}
            </div>
            <div class="flex flex-col gap-0.5">
                <span class="font-data-sm text-[12px] text-main truncate font-medium">${_escapeHtmlIpod(ph.title || `Foto #${idx + 1}`)}</span>
                <span class="font-data-sm text-[10px] text-muted/60">${ph.date || _formatBytes(ph.size)}</span>
            </div>
        </div>
    `).join("");
}

// --- VISTA 4: VIDEOS ---
function renderIpodVideos() {
    const grid = document.getElementById("ipod-videos-grid");
    const empty = document.getElementById("ipod-videos-empty");
    if (!grid) return;

    if (ipodState.videos.length === 0) {
        grid.innerHTML = "";
        if (empty) empty.classList.remove("hidden");
        return;
    }

    if (empty) empty.classList.add("hidden");
    grid.innerHTML = ipodState.videos.map((vid, idx) => `
        <div class="ipod-media-card relative group">
            <button type="button" class="hover-delete-btn" onclick="deleteIpodItem('video', ${idx})" title="${t("ipod_delete_item")}">
                <span class="material-symbols-outlined text-[16px]">remove</span>
            </button>
            <div class="aspect-video w-full rounded-lg bg-black/10 dark:bg-white/5 flex items-center justify-center overflow-hidden relative">
                ${vid.thumb ? `<img src="${vid.thumb}" class="w-full h-full object-cover"/>` : '<span class="material-symbols-outlined text-[36px] text-muted/30">movie</span>'}
                <span class="absolute bottom-1.5 right-1.5 px-1.5 py-0.5 rounded bg-black/60 text-white font-data-sm text-[10px]">${_formatMs(vid.duration_ms)}</span>
            </div>
            <div class="flex flex-col gap-0.5">
                <span class="font-data-sm text-[12px] text-main truncate font-medium">${_escapeHtmlIpod(vid.title || `Video #${idx + 1}`)}</span>
                <span class="font-data-sm text-[10px] text-muted/60">${vid.resolution || _formatBytes(vid.size)}</span>
            </div>
        </div>
    `).join("");
}

// --- VISTA 5: PODCASTS ---
function renderIpodPodcasts() {
    const pList = document.getElementById("ipod-podcasts-list");
    const epList = document.getElementById("ipod-podcast-episodes-list");
    const titleEl = document.getElementById("ipod-podcast-title");
    const countEl = document.getElementById("ipod-podcast-count");
    if (!pList || !epList) return;

    if (ipodState.podcasts.length === 0) {
        pList.innerHTML = `<p class="font-data-sm text-[12px] text-muted/40 p-2">No hay podcasts suscritos en el iPod.</p>`;
        epList.innerHTML = `<p class="font-data-sm text-[12px] text-muted/40 p-4">Agrega podcasts o sincroniza feeds para ver sus episodios.</p>`;
        return;
    }

    pList.innerHTML = ipodState.podcasts.map((pod, idx) => {
        const isSelected = idx === ipodState.selectedPodcastIndex;
        return `
            <div onclick="selectIpodPodcast(${idx})" class="flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-accent-light text-accent font-semibold' : 'bg-btn hover:bg-btn-hover text-main'}">
                <div class="flex items-center gap-2 min-w-0">
                    <span class="material-symbols-outlined text-[16px]">podcasts</span>
                    <span class="font-data-sm text-[13px] truncate">${_escapeHtmlIpod(pod.name || "Podcast")}</span>
                </div>
                <span class="font-data-sm text-[11px] text-muted/60">${(pod.episodes || []).length}</span>
            </div>
        `;
    }).join("");

    const currentPod = ipodState.podcasts[ipodState.selectedPodcastIndex];
    if (currentPod) {
        if (titleEl) titleEl.textContent = currentPod.name || "Podcast";
        const episodes = currentPod.episodes || [];
        if (countEl) countEl.textContent = episodes.length + " episodios";

        epList.innerHTML = episodes.map((ep, i) => `
            <div class="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-btn-hover transition-colors">
                <span class="font-data-sm text-[12px] text-muted/40 w-6 text-right">${i + 1}</span>
                <div class="flex-1 min-w-0">
                    <div class="font-data-sm text-[13px] text-main truncate font-medium">${_escapeHtmlIpod(ep.title)}</div>
                    <div class="font-data-sm text-[11px] text-muted/60 truncate">${ep.date || ""}</div>
                </div>
                <span class="font-data-sm text-[11px] text-muted/50">${_formatMs(ep.duration_ms)}</span>
            </div>
        `).join("");
    }
}

function selectIpodPodcast(idx) {
    ipodState.selectedPodcastIndex = idx;
    renderIpodPodcasts();
}

// --- VISTA 6: AUDIOLIBROS ---
function renderIpodAudiobooks() {
    const abList = document.getElementById("ipod-audiobooks-list");
    const chList = document.getElementById("ipod-audiobook-chapters-list");
    const titleEl = document.getElementById("ipod-audiobook-title");
    const countEl = document.getElementById("ipod-audiobook-count");
    if (!abList || !chList) return;

    if (ipodState.audiobooks.length === 0) {
        abList.innerHTML = `<p class="font-data-sm text-[12px] text-muted/40 p-2">No hay audiolibros en el iPod.</p>`;
        chList.innerHTML = `<p class="font-data-sm text-[12px] text-muted/40 p-4">Agrega audiolibros para ver sus capítulos.</p>`;
        return;
    }

    abList.innerHTML = ipodState.audiobooks.map((ab, idx) => {
        const isSelected = idx === ipodState.selectedAudiobookIndex;
        return `
            <div onclick="selectIpodAudiobook(${idx})" class="flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-accent-light text-accent font-semibold' : 'bg-btn hover:bg-btn-hover text-main'}">
                <div class="flex items-center gap-2 min-w-0">
                    <span class="material-symbols-outlined text-[16px]">menu_book</span>
                    <span class="font-data-sm text-[13px] truncate">${_escapeHtmlIpod(ab.title || "Audiolibro")}</span>
                </div>
                <span class="font-data-sm text-[11px] text-muted/60">${(ab.chapters || []).length}</span>
            </div>
        `;
    }).join("");

    const currentAb = ipodState.audiobooks[ipodState.selectedAudiobookIndex];
    if (currentAb) {
        if (titleEl) titleEl.textContent = currentAb.title || "Audiolibro";
        const chapters = currentAb.chapters || [];
        if (countEl) countEl.textContent = chapters.length + " pistas";

        chList.innerHTML = chapters.map((ch, i) => `
            <div class="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-btn-hover transition-colors">
                <span class="font-data-sm text-[12px] text-muted/40 w-6 text-right">${i + 1}</span>
                <div class="flex-1 min-w-0">
                    <div class="font-data-sm text-[13px] text-main truncate font-medium">${_escapeHtmlIpod(ch.title)}</div>
                    <div class="font-data-sm text-[11px] text-muted/60 truncate">${currentAb.author || ""}</div>
                </div>
                <span class="font-data-sm text-[11px] text-muted/50">${_formatMs(ch.duration_ms)}</span>
            </div>
        `).join("");
    }
}

function selectIpodAudiobook(idx) {
    ipodState.selectedAudiobookIndex = idx;
    renderIpodAudiobooks();
}

// --- BÚSQUEDA Y FILTROS ---
function handleIpodSearch(val) {
    ipodState.searchQuery = val.trim();
    renderCurrentIpodCategory();
}

function toggleIpodFilters() {
    const panel = document.getElementById("ipod-filters-panel");
    if (panel) panel.classList.toggle("hidden");
}

function applyIpodFilter(type, value) {
    ipodState.filters[type] = value;
    const badge = document.getElementById("ipod-active-filters-badge");
    const hasActive = Object.values(ipodState.filters).some(v => Boolean(v));
    if (badge) badge.classList.toggle("hidden", !hasActive);
    renderIpodSongs();
}

function resetIpodFilters() {
    ipodState.filters = { genre: '', year: '', artist: '', album: '' };
    ["ipod-filter-genre", "ipod-filter-year", "ipod-filter-artist", "ipod-filter-album"].forEach(id => {
        const sel = document.getElementById(id);
        if (sel) sel.value = "";
    });
    const badge = document.getElementById("ipod-active-filters-badge");
    if (badge) badge.classList.add("hidden");
    renderIpodSongs();
}

function setIpodViewMode(mode) {
    ipodState.viewMode = mode;
    const listBtn = document.getElementById("ipod-viewmode-list-btn");
    const gridBtn = document.getElementById("ipod-viewmode-grid-btn");
    if (listBtn) listBtn.classList.toggle("active", mode === "list");
    if (gridBtn) gridBtn.classList.toggle("active", mode === "grid");
    renderIpodSongs();
}

// --- ACCIONES Y MODALES ---
function handleIpodAddAction() {
    switch (ipodState.currentCategory) {
        case "songs":
            alert("Selecciona canciones de tu biblioteca de Cicada para sincronizarlas con el botón 'Sync'.");
            break;
        case "playlists":
            openCreatePlaylistModal();
            break;
        case "photos":
            _mockAddPhoto();
            break;
        case "videos":
            _mockAddVideo();
            break;
        case "podcasts":
            _mockAddPodcast();
            break;
        case "audiobooks":
            _mockAddAudiobook();
            break;
    }
}

function _mockAddPhoto() {
    const name = prompt("Nombre o descripción de la foto a agregar:");
    if (!name) return;
    ipodState.photos.push({
        title: name,
        date: new Date().toLocaleDateString(),
        size: 1500000
    });
    updateIpodCategoryCounts();
    renderIpodPhotos();
}

function _mockAddVideo() {
    const name = prompt("Título del video a agregar:");
    if (!name) return;
    ipodState.videos.push({
        title: name,
        resolution: "720x480 (iPod Video)",
        duration_ms: 180000,
        size: 45000000
    });
    updateIpodCategoryCounts();
    renderIpodVideos();
}

function _mockAddPodcast() {
    const name = prompt("Nombre del Podcast a suscribir:");
    if (!name) return;
    ipodState.podcasts.push({
        name: name,
        episodes: [
            { title: "Episodio 1: Introducción", date: new Date().toLocaleDateString(), duration_ms: 1200000 },
            { title: "Episodio 2: Especial", date: new Date().toLocaleDateString(), duration_ms: 1850000 }
        ]
    });
    updateIpodCategoryCounts();
    renderIpodPodcasts();
}

function _mockAddAudiobook() {
    const name = prompt("Título del audiolibro a agregar:");
    if (!name) return;
    ipodState.audiobooks.push({
        title: name,
        author: "Autor",
        chapters: [
            { title: "Capítulo 1", duration_ms: 900000 },
            { title: "Capítulo 2", duration_ms: 1100000 }
        ]
    });
    updateIpodCategoryCounts();
    renderIpodAudiobooks();
}

function deleteIpodItem(type, idx) {
    if (!confirm(t("ipod_delete_confirm"))) return;
    if (type === "photo") {
        ipodState.photos.splice(idx, 1);
        updateIpodCategoryCounts();
        renderIpodPhotos();
    } else if (type === "video") {
        ipodState.videos.splice(idx, 1);
        updateIpodCategoryCounts();
        renderIpodVideos();
    }
}

// Modal Crear Playlist
function openCreatePlaylistModal() {
    const modal = document.getElementById("ipod-create-playlist-modal");
    const input = document.getElementById("new_playlist_name");
    if (input) input.value = "";
    if (modal) {
        modal.classList.remove("hidden");
        modal.classList.add("flex");
    }
}

function closeCreatePlaylistModal() {
    const modal = document.getElementById("ipod-create-playlist-modal");
    if (modal) {
        modal.classList.add("hidden");
        modal.classList.remove("flex");
    }
}

async function submitCreatePlaylist() {
    const input = document.getElementById("new_playlist_name");
    const name = input ? input.value.trim() : "";
    if (!name) {
        alert("Por favor ingresa un nombre para la playlist.");
        return;
    }

    try {
        await _postJson("/api/ipod/playlists/create", { name });
        ipodState.playlists.push({ title: name, count: 0, is_master: false });
        updateIpodCategoryCounts();
        renderIpodPlaylists();
        closeCreatePlaylistModal();
    } catch (e) {
        alert("Error creando playlist: " + e.message);
    }
}

// Modal Importar Playlist
function openImportPlaylistModal() {
    const modal = document.getElementById("ipod-import-playlist-modal");
    const container = document.getElementById("ipod-import-playlist-options");
    if (modal) {
        modal.classList.remove("hidden");
        modal.classList.add("flex");
    }

    // Listar playlists locales disponibles desde la biblioteca de Cicada
    if (container) {
        container.innerHTML = `
            <div onclick="selectImportPlaylist('Mis Favoritas (Cicada)')" class="flex items-center justify-between p-2 rounded-lg bg-btn hover:bg-btn-hover cursor-pointer">
                <span class="font-data-sm text-[13px] text-main">Mis Favoritas (Cicada)</span>
                <span class="font-label-caps text-[10px] text-accent">Importar</span>
            </div>
            <div onclick="selectImportPlaylist('Descargas Recientes')" class="flex items-center justify-between p-2 rounded-lg bg-btn hover:bg-btn-hover cursor-pointer">
                <span class="font-data-sm text-[13px] text-main">Descargas Recientes</span>
                <span class="font-label-caps text-[10px] text-accent">Importar</span>
            </div>
        `;
    }
}

function closeImportPlaylistModal() {
    const modal = document.getElementById("ipod-import-playlist-modal");
    if (modal) {
        modal.classList.add("hidden");
        modal.classList.remove("flex");
    }
}

async function selectImportPlaylist(name) {
    try {
        await _postJson("/api/ipod/playlists/import", { source_name: name, tracks: [] });
        ipodState.playlists.push({ title: name, count: 0, is_master: false });
        updateIpodCategoryCounts();
        renderIpodPlaylists();
        closeImportPlaylistModal();
        alert(`Playlist '${name}' importada.`);
    } catch (e) {
        alert("Error importando playlist: " + e.message);
    }
}

// --- EXPULSAR IPOD ---
async function ejectIpod() {
    if (!confirm(t("ipod_eject_confirm"))) return;
    try {
        const { res, data } = await _postJson("/api/ipod/eject", { force: false });
        if (data.ejected) {
            alert(t("ipod_eject_success"));
            scanIpod();
        } else {
            alert("No se pudo expulsar el iPod: " + (data.message || ""));
        }
    } catch (e) {
        alert("Error al expulsar: " + e.message);
    }
}

// --- SINCRONIZACIÓN Y BACKUPS (conservados y adaptados) ---
function _ipodErr(data) {
    const d = data && data.detail;
    if (!d) return t("error_unknown");
    return (typeof d === "object" ? (d.error || d.code) : d) || t("error_unknown");
}

async function _postJson(url, body) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await res.json(); } catch (_) {}
    return { res, data };
}

async function syncIpod() {
    const btn = document.getElementById("btn-sync-ipod");
    try {
        const st = await (await fetch("/api/ipod/status")).json();
        const dev = (st.devices || [])[0];
        if (!dev) { alert(t("ipod_write_no_device")); return; }
        if (!dev.guid_is_write_safe) { alert(t("ipod_write_unsafe")); return; }

        const tData = await (await fetch("/api/ipod/tracks")).json();
        const tracks = tData.tracks || [];
        if (!tracks.length) { alert(t("ipod_write_empty")); return; }

        if (btn) btn.disabled = true;
        const { res: planRes, data: plan } = await _postJson("/api/ipod/plan", { tracks });
        if (!planRes.ok) throw new Error(_ipodErr(plan));

        if (!confirm(t("ipod_write_review").replace("{n}", plan.tracks_count))) return;

        let consentAck = false;
        if (plan.consent_needed) {
            consentAck = confirm(t("ipod_write_consent"));
            if (!consentAck) return;
        }

        const { res: applyRes, data: result } = await _postJson(
            "/api/ipod/apply", { plan_id: plan.plan_id, consent_ack: consentAck });
        if (!applyRes.ok) throw new Error(_ipodErr(result));

        if (result.success) {
            alert(t("ipod_write_ok").replace("{n}", result.tracks_written));
            loadIpodLibrary();
        } else {
            const restored = result.restored_from_backup ? t("ipod_write_rolled_back") : "";
            alert(t("ipod_write_failed") + (result.error || "") + restored);
        }
    } catch (e) {
        alert(t("error_prefix") + e.message);
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function backupIpod() {
    if (!confirm(t("ipod_backup_confirm"))) return;
    const btn = document.getElementById("btn-backup-ipod");
    try {
        if (btn) btn.disabled = true;
        const { res, data } = await _postJson("/api/ipod/backup", { full: false });
        if (!res.ok) throw new Error(_ipodErr(data));
        const mb = data.size_bytes ? (data.size_bytes / 1048576).toFixed(1) + " MB" : "";
        alert(t("ipod_backup_ok").replace("{path}", data.path || "—").replace("{size}", mb));
    } catch (e) {
        alert(t("error_prefix") + e.message);
    } finally {
        if (btn) btn.disabled = false;
    }
}

