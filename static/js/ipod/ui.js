// static/js/ipod/ui.js — Eventos, orquestación y estado de la sección iPod:
// ipodState, cambio de categoría/vista, carrito de sincronización, menú
// contextual, drag-drop de playlists, modales, filtros y las acciones de
// escanear/reparar/expulsar/respaldar. Consume static/js/ipod/api.js (red) y
// static/js/ipod/render.js (plantillas); ambos deben cargar antes que este.

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
    selectedAudiobookIndex: 0,
    syncBasket: [],           // pistas locales pendientes de enviar al iPod (por source_path)
    syncBasketPlaylists: []   // playlists pendientes de crear: {name, source_paths}
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

// --- ESCANEO DEL DISPOSITIVO ---
async function scanIpod() {
    const container = document.getElementById("ipod-info-container");
    const noDevice = document.getElementById("ipod-no-device");
    const noControl = document.getElementById("ipod-no-control");
    const mainBrowser = document.getElementById("ipod-main-browser");

    try {
        const { data } = await ipodFetchScan();

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

            // Actualiza la línea base de reproducciones (rating/play_count/etc.)
            // en segundo plano: solo lee el dispositivo y escribe SQLite local,
            // nunca el iPod — si falla, no debe romper el escaneo visible.
            ipodSyncPlayback().catch(e => console.error("Error sincronizando playback state:", e));
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
        if (typeof updateLibraryIpodButton === "function") updateLibraryIpodButton();
        if (typeof updatePlaylistIpodButton === "function") updatePlaylistIpodButton();
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
            ipodFetchTracks(),
            ipodFetchPlaylists(),
            ipodFetchPhotos(),
            ipodFetchVideos(),
            ipodFetchPodcasts(),
            ipodFetchAudiobooks()
        ]);

        ipodState.tracks = (tRes.status === "fulfilled" && tRes.value.res.ok) ? (tRes.value.data.tracks || []) : [];
        ipodState.playlists = (pRes.status === "fulfilled" && pRes.value.res.ok) ? (pRes.value.data.playlists || []) : [];
        ipodState.photos = (phRes.status === "fulfilled" && phRes.value.res.ok) ? (phRes.value.data.photos || []) : [];
        ipodState.videos = (vRes.status === "fulfilled" && vRes.value.res.ok) ? (vRes.value.data.videos || []) : [];
        ipodState.podcasts = (podRes.status === "fulfilled" && podRes.value.res.ok) ? (podRes.value.data.podcasts || []) : [];
        ipodState.audiobooks = (abRes.status === "fulfilled" && abRes.value.res.ok) ? (abRes.value.data.audiobooks || []) : [];

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
        "ipod-view-audiobooks",
        "ipod-view-sync"
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
        case "sync":
            renderIpodSyncBasket();
            break;
    }
}

// --- CARRITO DE SINCRONIZACIÓN (pendientes de enviar al iPod) ---
// Cada item: {source_path, title, artist, album, filetype, length_ms}
function addToSyncBasket(items) {
    const have = new Set(ipodState.syncBasket.map(i => i.source_path));
    let added = 0;
    for (const it of (items || [])) {
        if (it && it.source_path && !have.has(it.source_path)) {
            ipodState.syncBasket.push(it);
            have.add(it.source_path);
            added++;
        }
    }
    updateSyncBasketBadge();
    if (ipodState.currentCategory === "sync") renderIpodSyncBasket();
    return added;
}

function removeFromSyncBasket(sourcePath) {
    ipodState.syncBasket = ipodState.syncBasket.filter(i => i.source_path !== sourcePath);
    // Mantiene syncBasketPlaylists en sincronía: si una pista sale del carrito, también
    // sale de cualquier playlist pendiente que la referenciaba (si no, la playlist podía
    // terminar refiriendo solo paths que ya no se envían, y el backend la descartaba entera).
    ipodState.syncBasketPlaylists = ipodState.syncBasketPlaylists
        .map(p => ({ ...p, source_paths: p.source_paths.filter(sp => sp !== sourcePath) }))
        .filter(p => p.source_paths.length > 0);
    updateSyncBasketBadge();
    renderIpodSyncBasket();
}

// Registra una playlist pendiente (nombre + tracks) y mete sus pistas al carrito.
function addPlaylistToSyncBasket(name, items) {
    addToSyncBasket(items);
    const paths = (items || []).map(i => i && i.source_path).filter(Boolean);
    if (!paths.length) return 0;
    ipodState.syncBasketPlaylists = ipodState.syncBasketPlaylists.filter(p => p.name !== name);
    ipodState.syncBasketPlaylists.push({ name: name, source_paths: paths });
    updateSyncBasketBadge();
    if (ipodState.currentCategory === "sync") renderIpodSyncBasket();
    return paths.length;
}

function removeSyncBasketPlaylist(name) {
    ipodState.syncBasketPlaylists = ipodState.syncBasketPlaylists.filter(p => p.name !== name);
    updateSyncBasketBadge();
    renderIpodSyncBasket();
}

function updateSyncBasketBadge() {
    const badge = document.getElementById("ipod-count-sync");
    if (badge) badge.textContent = ipodState.syncBasket.length;
}

function renderIpodSyncBasket() {
    const list = document.getElementById("ipod-sync-basket-list");
    const btn = document.getElementById("ipod-sync-now-btn");
    const label = document.getElementById("ipod-sync-now-label");
    const basket = ipodState.syncBasket;
    const playlists = ipodState.syncBasketPlaylists;
    updateSyncBasketBadge();
    if (btn) btn.disabled = basket.length === 0 && playlists.length === 0;
    if (label) label.textContent = basket.length
        ? t("ipod_sync_now") + " (" + basket.length + ")"
        : t("ipod_sync_now");
    if (!list) return;
    if (!basket.length && !playlists.length) {
        list.innerHTML = '<p class="font-data-sm text-[13px] text-muted/60 text-center py-8" data-i18n="ipod_sync_empty">'
            + t("ipod_sync_empty") + '</p>';
        return;
    }
    let plHtml = "";
    if (playlists.length) {
        plHtml = '<div class="flex flex-col gap-1 pb-2 mb-1 border-b border-theme">' +
            '<span class="font-label-caps text-[11px] text-muted/50 uppercase px-1">' + t("ipod_sync_playlists") + '</span>' +
            playlists.map(p => ipodSyncBasketPlaylistRowHtml(p)).join("") + '</div>';
    }
    list.innerHTML = plHtml + basket.map(it => ipodSyncBasketTrackRowHtml(it)).join("");
}

// Envía el carrito al iPod vía el pipeline real (/media/sync), con gate de consentimiento.
async function syncBasketToIpod() {
    const basket = ipodState.syncBasket;
    if (!basket.length) return;
    const btn = document.getElementById("ipod-sync-now-btn");
    try {
        const { data: st } = await ipodFetchStatus();
        const dev = (st.devices || [])[0];
        if (!dev) { alert(t("ipod_write_no_device")); return; }
        if (!dev.guid_is_write_safe) { alert(t("ipod_write_unsafe")); return; }

        if (!confirm(t("ipod_sync_review").replace("{n}", basket.length))) return;

        let consentAck = false;
        if (!dev.music_app_consent_granted) {
            consentAck = confirm(t("ipod_write_consent"));
            if (!consentAck) return;
        }

        if (btn) btn.disabled = true;
        const tracks = basket.map(it => ({
            source_path: it.source_path,
            title: it.title || "",
            artist: it.artist || null,
            album: it.album || null,
            genre: it.genre || null,
            year: it.year || null,
            track_number: it.track_number || null,
            length_ms: it.length_ms || null,
            filetype: it.filetype || null,
        }));
        const playlists = ipodState.syncBasketPlaylists.map(p => ({ name: p.name, source_paths: p.source_paths }));
        const { res, data } = await ipodMediaSync({ tracks, consent_ack: consentAck, playlists });
        if (!res.ok) throw new Error(_ipodErr(data));
        if (data.success) {
            alert(t("ipod_write_ok").replace("{n}", data.tracks_written));
            ipodState.syncBasket = [];
            ipodState.syncBasketPlaylists = [];
            updateSyncBasketBadge();
            renderIpodSyncBasket();
            await loadIpodLibrary();
            switchIpodCategory("songs");
        } else {
            const restored = data.restored_from_backup ? t("ipod_write_rolled_back") : "";
            alert(t("ipod_write_failed") + (data.error || "") + restored);
        }
    } catch (e) {
        alert(t("error_prefix") + e.message);
    } finally {
        if (btn) btn.disabled = ipodState.syncBasket.length === 0;
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
    ipodState.filteredSongs = filtered;   // para reproducir por índice (#4)

    if (ipodState.viewMode === "list") {
        listContainer.classList.remove("hidden");
        gridContainer.classList.add("hidden");

        if (filtered.length === 0) {
            listContainer.innerHTML = `<div class="text-center py-10 text-muted/60 font-data-sm text-[13px]">${t("ipod_no_results")}</div>`;
            return;
        }

        listContainer.innerHTML = filtered.map((tr, i) => ipodSongRowHtml(tr, i)).join("");
    } else {
        listContainer.classList.add("hidden");
        gridContainer.classList.remove("hidden");

        if (filtered.length === 0) {
            gridContainer.innerHTML = `<div class="col-span-full text-center py-10 text-muted/60 font-data-sm text-[13px]">${t("ipod_no_results")}</div>`;
            return;
        }

        gridContainer.innerHTML = filtered.map((tr, i) => ipodSongCardHtml(tr, i)).join("");
    }
}

// --- Menú contextual de una canción del iPod: Agregar a Playlist / Eliminar del iPod ---
let ipodContextTrack = null;

function showIpodSongContextMenu(event, dbTrackId, title, artist) {
    event.preventDefault();
    event.stopPropagation();
    if (!dbTrackId) return;
    ipodContextTrack = { db_track_id: dbTrackId, title: title, artist: artist };
    hideIpodPlaylistSubmenu();
    const menu = document.getElementById("ipod-context-menu");
    if (!menu) return;
    menu.style.display = "flex";
    let x = event.clientX, y = event.clientY;
    if (x + 220 > window.innerWidth) x -= 220;
    if (y + menu.offsetHeight > window.innerHeight) y -= menu.offsetHeight;
    menu.style.left = x + "px";
    menu.style.top = y + "px";
}

document.addEventListener('click', function() {
    const menu = document.getElementById("ipod-context-menu");
    if (menu && menu.style.display === "flex") menu.style.display = "none";
    hideIpodPlaylistSubmenu();
});

function hideIpodPlaylistSubmenu() {
    const sub = document.getElementById("ipod-playlist-submenu");
    if (sub) sub.style.display = "none";
}

function showIpodPlaylistSubmenu(event) {
    const sub = document.getElementById("ipod-playlist-submenu");
    if (!sub) return;
    const userPls = (ipodState.playlists || []).filter(p => !p.is_master);
    sub.innerHTML = userPls.length
        ? userPls.map(p =>
            '<div class="context-menu-item" onclick="contextAddIpodTrackToPlaylist(' + _ipodAttrJson(p.title) + ')">' +
            '<span class="material-symbols-outlined text-[18px]">queue_music</span>' +
            '<span>' + _escapeHtmlIpod(p.title || "—") + '</span></div>'
          ).join("")
        : '<div class="context-menu-item" style="opacity:.5;cursor:default">' + t("ctx_ipod_no_playlists") + '</div>';

    const r = event.currentTarget.getBoundingClientRect();
    let x = r.right;
    if (x + 220 > window.innerWidth) x = Math.max(0, r.left - 220);
    let y = r.top;
    sub.style.display = "flex";
    if (y + sub.offsetHeight > window.innerHeight) y = Math.max(0, window.innerHeight - sub.offsetHeight - 8);
    sub.style.left = x + "px";
    sub.style.top = y + "px";
}

async function _ipodWriteGate() {
    const { data: st } = await ipodFetchStatus();
    const dev = (st.devices || [])[0];
    if (!dev) { alert(t("ipod_write_no_device")); return null; }
    if (!dev.guid_is_write_safe) { alert(t("ipod_write_unsafe")); return null; }
    let consentAck = false;
    if (!dev.music_app_consent_granted) {
        consentAck = confirm(t("ipod_write_consent"));
        if (!consentAck) return null;
    }
    return { consentAck };
}

async function contextAddIpodTrackToPlaylist(playlistName) {
    hideIpodPlaylistSubmenu();
    const menu = document.getElementById("ipod-context-menu");
    if (menu) menu.style.display = "none";
    if (!ipodContextTrack) return;
    const pl = (ipodState.playlists || []).find(p => p.title === playlistName);
    if (!pl) return;
    const already = (pl.tracks || []).some(tr => tr.db_track_id === ipodContextTrack.db_track_id);
    if (already) { alert(t("ctx_ipod_already_in_playlist").replace("{name}", pl.title)); return; }
    try {
        const gate = await _ipodWriteGate();
        if (!gate) return;
        const items = (pl.tracks || []).map(tr => ({ db_track_id: tr.db_track_id }));
        items.push({ db_track_id: ipodContextTrack.db_track_id });
        const { res, data } = await ipodPlaylistSet({
            playlist_name: pl.title, items: items, consent_ack: gate.consentAck,
        });
        if (!res.ok || !data.success) {
            alert(t("ipod_write_failed") + (data.error || _ipodErr(data)));
        } else {
            alert(t("ctx_ipod_added_to_playlist").replace("{name}", pl.title));
        }
        await loadIpodLibrary();
        renderIpodPlaylists();
    } catch (e) {
        alert(t("error_prefix") + e.message);
    }
}

async function contextRemoveFromIpod() {
    const menu = document.getElementById("ipod-context-menu");
    if (menu) menu.style.display = "none";
    if (!ipodContextTrack) return;
    if (!confirm(t("ctx_ipod_remove_confirm").replace("{title}", ipodContextTrack.title || ""))) return;
    try {
        const gate = await _ipodWriteGate();
        if (!gate) return;
        const { res, data } = await ipodTrackRemove({
            db_track_id: ipodContextTrack.db_track_id, consent_ack: gate.consentAck,
        });
        if (!res.ok || !data.success) {
            alert(t("ipod_write_failed") + (data.error || _ipodErr(data)));
        }
        await loadIpodLibrary();
        renderIpodSongs();
        renderIpodPlaylists();
    } catch (e) {
        alert(t("error_prefix") + e.message);
    }
}

// --- Reproducir una canción del iPod desde la biblioteca local (#4) ---
// Busca en la biblioteca local (libraryTracks) una pista que corresponda a la del
// iPod (por título + artista; fallback a título). Devuelve el track local o null.
function _findLocalTrack(iTrack) {
    if (typeof libraryTracks === "undefined" || !libraryTracks || !libraryTracks.length) return null;
    const nt = _normTxt(iTrack.title);
    if (!nt) return null;
    const na = _normTxt(iTrack.artist);
    let m = libraryTracks.find(l => _normTxt(l.title) === nt && _normTxt(l.artist) === na);
    if (!m) m = libraryTracks.find(l => _normTxt(l.title) === nt);
    return m || null;
}

function playIpodTrack(index) {
    const songs = ipodState.filteredSongs || [];
    const iTrack = songs[index];
    if (!iTrack) return;
    if (!_findLocalTrack(iTrack)) {
        alert(t("ipod_play_not_in_library"));
        return;
    }
    // Cola con las pistas del iPod que sí están en la biblioteca, para que
    // siguiente/anterior naveguen entre ellas. Reproduce desde la clickeada.
    const queue = [];
    let startIdx = 0;
    songs.forEach((s, si) => {
        const local = _findLocalTrack(s);
        if (local) {
            if (si === index) startIdx = queue.length;
            queue.push(local);
        }
    });
    if (typeof libraryQueues === "undefined") window.libraryQueues = {};
    libraryQueues["__ipod__"] = queue;
    if (typeof playFromQueue === "function") playFromQueue("__ipod__", startIdx);
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

    plsList.innerHTML = ipodState.playlists.map((p, idx) =>
        ipodPlaylistSidebarItemHtml(p, idx, idx === ipodState.selectedPlaylistIndex)
    ).join("");

    const selectedPl = ipodState.playlists[ipodState.selectedPlaylistIndex];
    if (selectedPl) {
        const isMaster = !!selectedPl.is_master;
        // Master = todas las canciones (no reordenable); usuario = sus pistas reales.
        const plTracks = isMaster ? ipodState.tracks : (selectedPl.tracks || []);
        if (titleEl) titleEl.textContent = selectedPl.title || "Playlist";
        if (countEl) countEl.textContent = plTracks.length + " " + t("ipod_tracks_count");

        const saveBtn = document.getElementById("ipod-playlist-save-order-btn");
        if (saveBtn) {
            const show = !isMaster && ipodPlaylistDirty;
            saveBtn.classList.toggle("hidden", !show);
            saveBtn.classList.toggle("inline-flex", show);
        }
        const addBtn = document.getElementById("ipod-playlist-add-btn");
        if (addBtn) {
            addBtn.classList.toggle("hidden", isMaster);
            addBtn.classList.toggle("inline-flex", !isMaster);
        }

        tracksList.innerHTML = plTracks.map((tr, i) => ipodPlaylistTrackRowHtml(tr, i, isMaster)).join("");
    }
}

// --- Reordenar pistas de una playlist del iPod (drag-drop -> persistir) ---
let ipodDragSourceIndex = null;
let ipodDraggedNode = null;
let ipodPlaylistDirty = false;

function handleIpodTrackDragStart(e, index) {
    ipodDragSourceIndex = index;
    ipodDraggedNode = e.currentTarget;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(index));
    e.currentTarget.classList.add("opacity-40");
}

function handleIpodTrackDragEnd(e) {
    e.currentTarget.classList.remove("opacity-40");
    ipodDraggedNode = null;
}

function handleIpodTrackDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (ipodDraggedNode && ipodDraggedNode !== e.currentTarget) {
        const b = e.currentTarget.getBoundingClientRect();
        const mid = b.y + b.height / 2;
        if (e.clientY - mid > 0) e.currentTarget.after(ipodDraggedNode);
        else e.currentTarget.before(ipodDraggedNode);
    }
}

function handleIpodTrackDrop(e) {
    e.preventDefault();
    if (ipodDragSourceIndex === null) return;
    ipodDragSourceIndex = null;
    ipodDraggedNode = null;
    const pl = ipodState.playlists[ipodState.selectedPlaylistIndex];
    if (!pl || !pl.tracks) return;
    const container = document.getElementById("ipod-playlist-tracks-list");
    const newOrder = [];
    container.querySelectorAll("[data-ipod-track-idx]").forEach(row => {
        const old = pl.tracks[parseInt(row.dataset.ipodTrackIdx, 10)];
        if (old) newOrder.push(old);
    });
    pl.tracks = newOrder;
    ipodPlaylistDirty = true;
    renderIpodPlaylists();
}

async function saveIpodPlaylistOrder() {
    const pl = ipodState.playlists[ipodState.selectedPlaylistIndex];
    if (!pl || pl.is_master || !pl.tracks) return;
    try {
        const { data: st } = await ipodFetchStatus();
        const dev = (st.devices || [])[0];
        if (!dev) { alert(t("ipod_write_no_device")); return; }
        if (!dev.guid_is_write_safe) { alert(t("ipod_write_unsafe")); return; }
        let consentAck = false;
        if (!dev.music_app_consent_granted) {
            consentAck = confirm(t("ipod_write_consent"));
            if (!consentAck) return;
        }
        const items = pl.tracks.map(tr => {
            if (tr.source_path) {
                return {
                    source_path: tr.source_path, title: tr.title || "",
                    artist: tr.artist || "", album: tr.album || "",
                    filetype: tr.filetype || (String(tr.source_path).split(".").pop() || "").toLowerCase(),
                };
            }
            return { db_track_id: tr.db_track_id };
        }).filter(it => it.source_path || it.db_track_id != null);
        const { res, data } = await ipodPlaylistSet({
            playlist_name: pl.title, items: items, consent_ack: consentAck,
        });
        if (!res.ok || !data.success) {
            alert(t("ipod_write_failed") + (data.error || _ipodErr(data)));
            await loadIpodLibrary();
        } else {
            ipodPlaylistDirty = false;
            alert(t("ipod_playlist_order_saved"));
            await loadIpodLibrary();
        }
        renderIpodPlaylists();
    } catch (e) {
        alert(t("error_prefix") + e.message);
    }
}

function selectIpodPlaylist(idx) {
    ipodState.selectedPlaylistIndex = idx;
    ipodPlaylistDirty = false;   // descarta cambios no guardados al cambiar
    renderIpodPlaylists();
}

// --- Agregar canciones de la biblioteca local a una playlist del iPod ---
function openIpodPlaylistAddPicker() {
    const pl = ipodState.playlists[ipodState.selectedPlaylistIndex];
    if (!pl || pl.is_master) return;
    const modal = document.getElementById("ipod-playlist-add-modal");
    if (!modal) return;
    modal.classList.remove("hidden");
    modal.classList.add("flex");
    const search = document.getElementById("ipod-playlist-add-search");
    if (search) search.value = "";
    renderIpodAddPickerList("");
}

function closeIpodPlaylistAddModal() {
    const modal = document.getElementById("ipod-playlist-add-modal");
    if (!modal) return;
    modal.classList.add("hidden");
    modal.classList.remove("flex");
}

function renderIpodAddPickerList(query) {
    const list = document.getElementById("ipod-playlist-add-list");
    if (!list) return;
    if (typeof libraryTracks === "undefined" || !libraryTracks || !libraryTracks.length) {
        list.innerHTML = `<p class="font-data-sm text-[12px] text-muted/40 p-2">${t("ipod_playlist_add_empty")}</p>`;
        return;
    }
    const q = _normTxt(query || "");
    const matches = (q
        ? libraryTracks.filter(l => _normTxt((l.title || "") + " " + (l.artist || "") + " " + (l.album || "")).includes(q))
        : libraryTracks).slice(0, 200);
    if (!matches.length) {
        list.innerHTML = `<p class="font-data-sm text-[12px] text-muted/40 p-2">${t("ipod_playlist_add_noresults")}</p>`;
        return;
    }
    list.innerHTML = matches.map(l => ipodLibraryPickerRowHtml(l)).join("");
}

function addLibrarySongToIpodPlaylist(path) {
    const pl = ipodState.playlists[ipodState.selectedPlaylistIndex];
    if (!pl || pl.is_master) return;
    const l = libraryTracks.find(x => x.path === path);
    if (!l) return;
    if (!pl.tracks) pl.tracks = [];
    pl.tracks.push({
        source_path: l.path, title: l.title || "", artist: l.artist || "",
        album: l.album || "", length_ms: null, db_track_id: null,
        filetype: (String(l.path).split(".").pop() || "").toLowerCase(),
    });
    ipodPlaylistDirty = true;
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
    grid.innerHTML = ipodState.photos.map((ph, idx) => ipodPhotoCardHtml(ph, idx)).join("");
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
    grid.innerHTML = ipodState.videos.map((vid, idx) => ipodVideoCardHtml(vid, idx)).join("");
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

    pList.innerHTML = ipodState.podcasts.map((pod, idx) =>
        ipodPodcastSidebarItemHtml(pod, idx, idx === ipodState.selectedPodcastIndex)
    ).join("");

    const currentPod = ipodState.podcasts[ipodState.selectedPodcastIndex];
    if (currentPod) {
        if (titleEl) titleEl.textContent = currentPod.name || "Podcast";
        const episodes = currentPod.episodes || [];
        if (countEl) countEl.textContent = episodes.length + " episodios";

        epList.innerHTML = episodes.map((ep, i) => ipodEpisodeRowHtml(ep, i)).join("");
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

    abList.innerHTML = ipodState.audiobooks.map((ab, idx) =>
        ipodAudiobookSidebarItemHtml(ab, idx, idx === ipodState.selectedAudiobookIndex)
    ).join("");

    const currentAb = ipodState.audiobooks[ipodState.selectedAudiobookIndex];
    if (currentAb) {
        if (titleEl) titleEl.textContent = currentAb.title || "Audiolibro";
        const chapters = currentAb.chapters || [];
        if (countEl) countEl.textContent = chapters.length + " pistas";

        chList.innerHTML = chapters.map((ch, i) => ipodChapterRowHtml(ch, i, currentAb.author)).join("");
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
        const { res, data } = await ipodPlaylistsCreate({ name });
        if (!res.ok) { alert(_ipodErr(data)); return; }
        ipodState.playlists.push({ title: name, count: 0, is_master: false });
        updateIpodCategoryCounts();
        renderIpodPlaylists();
        closeCreatePlaylistModal();
    } catch (e) {
        alert(t("error_prefix") + e.message);
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
        const { res, data } = await ipodPlaylistsImport({ source_name: name, tracks: [] });
        if (!res.ok) { alert(_ipodErr(data)); return; }
        ipodState.playlists.push({ title: name, count: 0, is_master: false });
        updateIpodCategoryCounts();
        renderIpodPlaylists();
        closeImportPlaylistModal();
        alert(`Playlist '${name}' importada.`);
    } catch (e) {
        alert(t("error_prefix") + e.message);
    }
}

// --- EXPULSAR IPOD ---
async function ejectIpod() {
    if (!confirm(t("ipod_eject_confirm"))) return;
    try {
        const { res, data } = await ipodEject({ force: false });
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
async function syncIpod() {
    const btn = document.getElementById("btn-sync-ipod");
    try {
        const { data: st } = await ipodFetchStatus();
        const dev = (st.devices || [])[0];
        if (!dev) { alert(t("ipod_write_no_device")); return; }
        if (!dev.guid_is_write_safe) { alert(t("ipod_write_unsafe")); return; }

        const { data: tData } = await ipodFetchTracks();
        const tracks = tData.tracks || [];
        if (!tracks.length) { alert(t("ipod_write_empty")); return; }

        if (btn) btn.disabled = true;
        const { res: planRes, data: plan } = await ipodPlanCreate({ tracks });
        if (!planRes.ok) throw new Error(_ipodErr(plan));

        if (!confirm(t("ipod_write_review").replace("{n}", plan.tracks_count))) return;

        let consentAck = false;
        if (plan.consent_needed) {
            consentAck = confirm(t("ipod_write_consent"));
            if (!consentAck) return;
        }

        const { res: applyRes, data: result } = await ipodApplyPlan(
            { plan_id: plan.plan_id, consent_ack: consentAck });
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
        const { res, data } = await ipodBackupNow({ full: false });
        if (!res.ok) throw new Error(_ipodErr(data));
        const mb = data.size_bytes ? (data.size_bytes / 1048576).toFixed(1) + " MB" : "";
        alert(t("ipod_backup_ok").replace("{path}", data.path || "—").replace("{size}", mb));
    } catch (e) {
        alert(t("error_prefix") + e.message);
    } finally {
        if (btn) btn.disabled = false;
    }
}

