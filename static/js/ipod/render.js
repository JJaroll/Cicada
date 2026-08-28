// static/js/ipod/render.js — Plantillas puras datos → HTML del módulo iPod:
// utilidades de formato/escape y una fila/tarjeta por tipo de elemento (canción,
// playlist, foto, video, podcast/episodio, audiolibro/capítulo, picker de
// biblioteca). Sin fetch, sin ipodState, sin escritura a DOM — cada función
// recibe sus datos y devuelve un string, para poder reusarse en otros
// contextos (p.ej. una futura vista de dry-run).

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

function _formatDateAdded(unixSeconds) {
    if (!unixSeconds) return "";
    return new Date(unixSeconds * 1000).toLocaleDateString();
}

function _formatBytes(b) {
    if (!b || b <= 0) return "0 B";
    if (b >= 1073741824) return (b / 1073741824).toFixed(1) + " GB";
    if (b >= 1048576) return (b / 1048576).toFixed(1) + " MB";
    if (b >= 1024) return (b / 1024).toFixed(1) + " KB";
    return b + " B";
}

function _normTxt(s) {
    return String(s == null ? "" : s).toLowerCase().replace(/\s+/g, " ").trim();
}

function _ipodAttrJson(v) {
    return JSON.stringify(v == null ? "" : v).replace(/"/g, "&quot;");
}

function _ipodCtxAttr(tr) {
    return "showIpodSongContextMenu(event, " + _ipodAttrJson(tr.db_track_id) + ", " +
        _ipodAttrJson(tr.title) + ", " + _ipodAttrJson(tr.artist) + ")";
}

// --- Canciones (vista lista/grilla) ---
function ipodSongRowHtml(tr, i) {
    const artworkSrc = tr.db_track_id ? `/api/ipod/track/artwork?db_track_id=${encodeURIComponent(tr.db_track_id)}` : '';
    return `
            <div class="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-btn-hover transition-colors group cursor-pointer" onclick="playIpodTrack(${i})" oncontextmenu="${_ipodCtxAttr(tr)}" title="${t("ipod_play_title")}">
                <span class="font-data-sm text-[12px] text-muted/40 w-7 text-right flex-shrink-0">${i + 1}</span>
                <div class="w-8 h-8 rounded-lg bg-btn flex items-center justify-center flex-shrink-0 text-muted/40 group-hover:text-accent relative overflow-hidden border border-white/5">
                    <span class="material-symbols-outlined text-[18px]">music_note</span>
                    ${artworkSrc ? `<img src="${artworkSrc}" class="absolute inset-0 w-full h-full object-cover" loading="lazy" onerror="this.remove()" alt="">` : ''}
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
        `;
}

function ipodSongCardHtml(tr, i) {
    const artworkSrc = tr.db_track_id ? `/api/ipod/track/artwork?db_track_id=${encodeURIComponent(tr.db_track_id)}` : '';
    return `
            <div class="ipod-media-card group cursor-pointer" onclick="playIpodTrack(${i})" oncontextmenu="${_ipodCtxAttr(tr)}" title="${t("ipod_play_title")}">
                <div class="aspect-square w-full rounded-lg bg-black/10 dark:bg-white/5 flex items-center justify-center relative overflow-hidden border border-white/5 shadow-inner">
                    <span class="material-symbols-outlined text-[36px] text-muted/30 group-hover:text-accent transition-colors">album</span>
                    ${artworkSrc ? `<img src="${artworkSrc}" class="absolute inset-0 w-full h-full object-cover" loading="lazy" onerror="this.remove()" alt="">` : ''}
                    <span class="absolute bottom-1.5 right-1.5 px-1.5 py-0.5 rounded bg-black/60 text-white font-data-sm text-[10px] z-10 backdrop-blur-sm">${_formatMs(tr.length_ms)}</span>
                </div>
                <div class="flex flex-col gap-0.5 min-w-0">
                    <h5 class="font-data-sm text-[13px] text-main font-medium truncate">${_escapeHtmlIpod(tr.title || t("track_untitled"))}</h5>
                    <p class="font-data-sm text-[11px] text-muted/60 truncate">${_escapeHtmlIpod(tr.artist || t("track_unknown_artist"))}</p>
                </div>
            </div>
        `;
}

// --- Playlists ---
function ipodPlaylistSidebarItemHtml(p, idx, isSelected) {
    const isMaster = !!p.is_master;
    return `
            <div onclick="selectIpodPlaylist(${idx})" oncontextmenu="showIpodPlaylistContextMenu(event, ${idx})" class="group flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-accent-light text-accent font-semibold' : 'bg-btn hover:bg-btn-hover text-main'}">
                <div class="flex items-center gap-2 min-w-0">
                    <span class="material-symbols-outlined text-[16px] ${isMaster ? 'text-secondary' : 'text-muted/60'}">${isMaster ? 'folder_special' : 'queue_music'}</span>
                    <span class="font-data-sm text-[13px] truncate">${_escapeHtmlIpod(p.title || "—")}</span>
                </div>
                <div class="flex items-center gap-1 flex-shrink-0 ml-1">
                    <span class="font-data-sm text-[11px] text-muted/60">${p.count || 0}</span>
                    ${!isMaster ? `
                        <button type="button" onclick="deleteIpodPlaylist(event, ${idx})" class="opacity-0 group-hover:opacity-100 hover:text-red-400 p-0.5 rounded transition-opacity" title="Eliminar playlist">
                            <span class="material-symbols-outlined text-[15px]">close</span>
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
}

function ipodPlaylistTrackRowHtml(tr, i, isMaster) {
    const drag = isMaster ? "" :
        ` draggable="true" ondragstart="handleIpodTrackDragStart(event, ${i})" ondragend="handleIpodTrackDragEnd(event)" ondragover="handleIpodTrackDragOver(event)" ondrop="handleIpodTrackDrop(event)"`;
    const ctxAttr = isMaster ? _ipodCtxAttr(tr) : `showIpodPlaylistTrackContextMenu(event, ${i})`;
    return `
            <div data-ipod-track-idx="${i}"${drag} oncontextmenu="${ctxAttr}"
                class="group flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-btn-hover transition-colors ${isMaster ? '' : 'cursor-grab'}">
                ${isMaster ? '' : '<span class="material-symbols-outlined text-[16px] text-muted/30 flex-shrink-0">drag_indicator</span>'}
                <span class="font-data-sm text-[12px] text-muted/40 w-6 text-right flex-shrink-0">${i + 1}</span>
                <div class="flex-1 min-w-0">
                    <div class="font-data-sm text-[13px] text-main truncate font-medium">${_escapeHtmlIpod(tr.title || t("track_untitled"))}</div>
                    <div class="font-data-sm text-[11px] text-muted/60 truncate">${_escapeHtmlIpod(tr.artist || "")}${tr.album ? ' — ' + _escapeHtmlIpod(tr.album) : ''}</div>
                </div>
                ${tr.source_path ? `<span class="material-symbols-outlined text-[15px] text-accent flex-shrink-0" title="${t('ipod_playlist_new_track')}">fiber_new</span>` : ''}
                <span class="font-data-sm text-[11px] text-muted/50">${_formatMs(tr.length_ms)}</span>
                ${!isMaster ? `
                    <button type="button" onclick="removeTrackFromIpodPlaylist(event, ${i})" class="opacity-0 group-hover:opacity-100 text-muted/40 hover:text-red-400 p-0.5 rounded transition-opacity flex-shrink-0" title="Quitar de la playlist">
                        <span class="material-symbols-outlined text-[16px]">close</span>
                    </button>
                ` : ''}
            </div>`;
}

// --- Carrito de sincronización ---
function ipodSyncBasketPlaylistRowHtml(p) {
    return '<div class="flex items-center gap-3 px-2 py-1.5 rounded-lg bg-btn">' +
        '<span class="material-symbols-outlined text-[18px] text-secondary flex-shrink-0">playlist_play</span>' +
        '<div class="flex-1 min-w-0">' +
        '<div class="font-data-sm text-[13px] text-main truncate">' + _escapeHtmlIpod(p.name) + '</div>' +
        '<div class="font-data-sm text-[12px] text-muted/60">' + p.source_paths.length + ' ' + t("ipod_tracks_count") + '</div></div>' +
        '<button type="button" onclick="removeSyncBasketPlaylist(' + JSON.stringify(p.name).replace(/"/g, "&quot;") + ')" ' +
        'class="flex-shrink-0 text-muted/50 hover:text-[#f43f5e] transition-colors" title="' + t("ipod_sync_remove") + '">' +
        '<span class="material-symbols-outlined text-[18px]">close</span></button></div>';
}

function ipodSyncBasketTrackRowHtml(it) {
    const icon = it.kind === "audiobook" ? "menu_book" : "music_note";
    return '<div class="flex items-center gap-3 px-2 py-1.5 rounded-lg bg-btn">' +
        '<span class="material-symbols-outlined text-[18px] text-secondary flex-shrink-0">' + icon + '</span>' +
        '<div class="flex-1 min-w-0">' +
        '<div class="font-data-sm text-[13px] text-main truncate">' + _escapeHtmlIpod(it.title || "—") + '</div>' +
        '<div class="font-data-sm text-[12px] text-muted/60 truncate">' +
        _escapeHtmlIpod(it.artist || "") + (it.album ? " — " + _escapeHtmlIpod(it.album) : "") + '</div></div>' +
        '<button type="button" onclick="removeFromSyncBasket(' + JSON.stringify(it.source_path).replace(/"/g, "&quot;") + ')" ' +
        'class="flex-shrink-0 text-muted/50 hover:text-[#f43f5e] transition-colors" title="' + t("ipod_sync_remove") + '">' +
        '<span class="material-symbols-outlined text-[18px]">close</span></button></div>';
}

// --- Picker: agregar canción de la biblioteca local a una playlist del iPod ---
function ipodLibraryPickerRowHtml(l) {
    const p = _escapeHtmlIpod(l.path);
    const pl = (typeof ipodState !== "undefined" && ipodState.playlists) 
        ? ipodState.playlists[ipodState.selectedPlaylistIndex] 
        : null;

    let inPlaylist = false;
    let isNewlyAdded = false;

    if (pl && pl.tracks) {
        const normTitle = _normTxt(l.title || "");
        const normArtist = _normTxt(l.artist || "");
        inPlaylist = pl.tracks.some(tr => 
            (tr.source_path && tr.source_path === l.path) ||
            (normTitle && _normTxt(tr.title || "") === normTitle && _normTxt(tr.artist || "") === normArtist)
        );
        if (typeof ipodPlaylistNewlyAddedPaths !== "undefined" && ipodPlaylistNewlyAddedPaths.has(l.path)) {
            isNewlyAdded = true;
        }
    }

    let statusBadge = "";
    let icon = "add";
    let iconClass = "text-muted/50";
    let cardClass = "bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10";

    if (inPlaylist) {
        if (isNewlyAdded) {
            statusBadge = `<span class="px-2 py-0.5 rounded-md bg-accent/20 text-accent text-[10px] font-label-caps font-semibold">Seleccionada</span>`;
            icon = "check_circle";
            iconClass = "text-accent scale-110";
            cardClass = "ring-2 ring-accent bg-accent/15 shadow-sm";
        } else {
            statusBadge = `<span class="px-2 py-0.5 rounded-md bg-secondary/20 text-secondary text-[10px] font-label-caps font-semibold flex items-center gap-1"><span class="material-symbols-outlined text-[12px]">done_all</span> En playlist</span>`;
            icon = "check_circle";
            iconClass = "text-secondary";
            cardClass = "bg-secondary/10 border border-secondary/20";
        }
    }

    return `
        <div onclick="toggleLibrarySongInIpodPlaylist('${p.replace(/'/g, "\\'")}')"
            class="flex items-center gap-3 p-2.5 rounded-xl cursor-pointer transition-all ${cardClass}">
            <span class="material-symbols-outlined text-[20px] ${iconClass} flex-shrink-0 transition-transform">${icon}</span>
            <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                    <span class="font-data-sm text-[13px] text-main truncate font-medium">${_escapeHtmlIpod(l.title || t("track_untitled"))}</span>
                    ${statusBadge}
                </div>
                <div class="font-data-sm text-[11px] text-muted/60 truncate mt-0.5">${_escapeHtmlIpod(l.artist || "")}${l.album ? ' — ' + _escapeHtmlIpod(l.album) : ''}</div>
            </div>
        </div>`;
}

// --- Videos ---
function ipodVideoCardHtml(vid, idx) {
    const dur = vid.duration_ms ? _formatMs(vid.duration_ms) : "";
    const sz = vid.size_bytes ? _formatBytes(vid.size_bytes) : "";
    const subtitle = [vid.kind, sz].filter(Boolean).join(" • ");
    const videoId = vid.id || String(idx);
    return `
        <div class="ipod-media-card relative group flex flex-col justify-between overflow-hidden bg-black/20 dark:bg-white/5 border border-theme rounded-xl p-2.5 transition-all hover:border-accent/50 hover:shadow-md">
            <button type="button" class="hover-delete-btn" onclick="deleteIpodItem('video', '${_escapeHtmlIpod(videoId)}')" title="${t("ipod_delete_item")}">
                <span class="material-symbols-outlined text-[15px]">close</span>
            </button>
            <div class="aspect-video w-full rounded-lg bg-gradient-to-br from-neutral-800 to-neutral-950 flex items-center justify-center overflow-hidden relative border border-white/5 shadow-inner group-hover:scale-[1.01] transition-transform">
                <div class="flex flex-col items-center justify-center gap-1 text-muted/30 group-hover:text-accent transition-colors">
                    <span class="material-symbols-outlined text-[36px]">movie</span>
                </div>
                <img src="${vid.thumb || `/api/ipod/track/artwork?video_id=${encodeURIComponent(videoId)}`}" class="absolute inset-0 w-full h-full object-cover" loading="lazy" onerror="this.remove()" alt="">
                ${dur ? `<span class="absolute bottom-1.5 right-1.5 px-1.5 py-0.5 rounded bg-black/80 text-white/90 font-data-sm text-[10px] backdrop-blur-sm z-10">${dur}</span>` : ""}
            </div>
            <div class="flex flex-col gap-0.5 mt-2 min-w-0">
                <span class="font-data-sm text-[12px] text-main truncate font-medium" title="${_escapeHtmlIpod(vid.title || `Video #${idx + 1}`)}">${_escapeHtmlIpod(vid.title || `Video #${idx + 1}`)}</span>
                <span class="font-data-sm text-[10px] text-muted/60 truncate">${subtitle || vid.show_name || "Video"}</span>
            </div>
        </div>
    `;
}

// --- Podcasts / Episodios ---
function ipodPodcastSidebarItemHtml(pod, idx, isSelected) {
    return `
            <div onclick="selectIpodPodcast(${idx})" oncontextmenu="showIpodPodcastContextMenu(event, ${idx})" class="flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-accent-light text-accent font-semibold' : 'bg-btn hover:bg-btn-hover text-main'}">
                <div class="flex items-center gap-2 min-w-0">
                    <span class="material-symbols-outlined text-[16px]">podcasts</span>
                    <span class="font-data-sm text-[13px] truncate">${_escapeHtmlIpod(pod.name || "Podcast")}</span>
                </div>
                <span class="font-data-sm text-[11px] text-muted/60">${(pod.episodes || []).length}</span>
            </div>
        `;
}

function ipodEpisodeRowHtml(ep, i, podName) {
    const epId = ep.id || "";
    const pName = podName || "";
    return `
            <div oncontextmenu="showIpodEpisodeContextMenu(event, '${epId}', '${_escapeHtmlIpod(ep.title).replace(/'/g, "\\'")}', '${_escapeHtmlIpod(pName).replace(/'/g, "\\'")}')" class="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-btn-hover transition-colors cursor-pointer">
                <span class="font-data-sm text-[12px] text-muted/40 w-6 text-right">${i + 1}</span>
                <div class="flex-1 min-w-0">
                    <div class="font-data-sm text-[13px] text-main truncate font-medium">${_escapeHtmlIpod(ep.title)}</div>
                    <div class="font-data-sm text-[11px] text-muted/60 truncate">${_formatDateAdded(ep.date_added)}</div>
                </div>
                <span class="font-data-sm text-[11px] text-muted/50">${_formatMs(ep.duration_ms)}</span>
            </div>
        `;
}

// --- Audiolibros / Capítulos ---
function ipodAudiobookSidebarItemHtml(ab, idx, isSelected) {
    return `
            <div onclick="selectIpodAudiobook(${idx})" oncontextmenu="showIpodAudiobookContextMenu(event, ${idx})" class="flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-accent-light text-accent font-semibold' : 'bg-btn hover:bg-btn-hover text-main'}">
                <div class="flex items-center gap-2 min-w-0">
                    <span class="material-symbols-outlined text-[16px]">menu_book</span>
                    <span class="font-data-sm text-[13px] truncate">${_escapeHtmlIpod(ab.title || "Audiolibro")}</span>
                </div>
                <span class="font-data-sm text-[11px] text-muted/60">${(ab.chapters || []).length}</span>
            </div>
        `;
}

function ipodChapterRowHtml(ch, i, author, abTitle) {
    const chId = ch.id || "";
    return `
            <div oncontextmenu="showIpodChapterContextMenu(event, '${chId}', '${_escapeHtmlIpod(ch.title).replace(/'/g, "\\'")}', '${_escapeHtmlIpod(abTitle || author || "").replace(/'/g, "\\'")}')" class="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-btn-hover transition-colors cursor-pointer">
                <span class="font-data-sm text-[12px] text-muted/40 w-6 text-right">${i + 1}</span>
                <div class="flex-1 min-w-0">
                    <div class="font-data-sm text-[13px] text-main truncate font-medium">${_escapeHtmlIpod(ch.title)}</div>
                    <div class="font-data-sm text-[11px] text-muted/60 truncate">${author || ""}</div>
                </div>
                <span class="font-data-sm text-[11px] text-muted/50">${_formatMs(ch.duration_ms)}</span>
            </div>
        `;
}

// --- Conflictos de rating (local vs. dispositivo vs. baseline) ---
function _starsText(rating0to100) {
    const n = Math.max(0, Math.min(5, Math.round((rating0to100 || 0) / 20)));
    return "★".repeat(n) + "☆".repeat(5 - n);
}

function ipodConflictRowHtml(c) {
    const name = c.title
        ? _escapeHtmlIpod(c.title) + (c.artist ? " — " + _escapeHtmlIpod(c.artist) : "")
        : t("track_untitled");
    return `
        <div class="flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg bg-btn">
            <div class="flex-1 min-w-0">
                <div class="font-data-sm text-[13px] text-main font-medium truncate">${name}</div>
                <div class="font-data-sm text-[12px] text-muted/60 truncate">
                    ${t("ipod_conflicts_local_label")}: ${_starsText(c.local_rating)} (${c.local_rating})
                    &nbsp;·&nbsp;
                    ${t("ipod_conflicts_device_label")}: ${_starsText(c.device_rating)} (${c.device_rating})
                </div>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
                <button type="button" onclick="resolveIpodConflict(${_ipodAttrJson(c.ipod_dbid)}, 'local')" class="px-3 py-1.5 rounded-full bg-accent-light text-accent font-label-caps text-[11px] hover:brightness-110 transition-all">${t("ipod_conflicts_use_local")}</button>
                <button type="button" onclick="resolveIpodConflict(${_ipodAttrJson(c.ipod_dbid)}, 'device')" class="px-3 py-1.5 rounded-full bg-btn-hover text-main font-label-caps text-[11px] hover:brightness-110 transition-all">${t("ipod_conflicts_use_device")}</button>
            </div>
        </div>
    `;
}

// --- Fotos (Galería / Cuadrícula solo lectura) ---
function ipodPhotoCardHtml(p, idx) {
    const sizeText = _formatBytes(p.size_bytes);
    const thumbUrl = p.thumb_url || `/api/ipod/photos/thumbnail?path=${encodeURIComponent(p.rel_path)}`;
    
    return `
        <div class="ipod-media-card group cursor-pointer relative" onclick="openPhotoLightbox(${idx})">
            <!-- Contenedor Cuadrado de la Imagen con aspect-ratio garantizado -->
            <div class="aspect-square w-full rounded-lg bg-black/20 dark:bg-white/5 flex items-center justify-center relative overflow-hidden border border-white/5 shadow-inner" style="aspect-ratio: 1 / 1; width: 100%;">
                <span class="material-symbols-outlined text-[36px] text-muted/30 group-hover:text-accent transition-colors">photo</span>
                <img src="${thumbUrl}" alt="${_escapeHtmlIpod(p.filename)}" loading="lazy" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-300 z-[1]"/>
                
                <!-- Overlay de apertura en pantalla completa en hover -->
                <div class="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end justify-end p-2 z-[2]">
                    <span class="p-1.5 rounded-full bg-black/60 text-white transition-transform hover:scale-110 flex items-center justify-center" title="Ver en pantalla completa">
                        <span class="material-symbols-outlined text-[16px]">fullscreen</span>
                    </span>
                </div>
            </div>

            <!-- Metadata inferior -->
            <div class="flex flex-col gap-0.5 min-w-0">
                <h5 class="font-data-sm text-[12px] text-main font-medium truncate" title="${_escapeHtmlIpod(p.filename)}">${_escapeHtmlIpod(p.filename)}</h5>
                <p class="font-data-sm text-[10px] text-muted/60 truncate">${sizeText}</p>
            </div>
        </div>
    `;
}
