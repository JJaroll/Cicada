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
    return `
            <div class="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-btn-hover transition-colors group cursor-pointer" onclick="playIpodTrack(${i})" oncontextmenu="${_ipodCtxAttr(tr)}" title="${t("ipod_play_title")}">
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
        `;
}

function ipodSongCardHtml(tr, i) {
    return `
            <div class="ipod-media-card group cursor-pointer" onclick="playIpodTrack(${i})" oncontextmenu="${_ipodCtxAttr(tr)}" title="${t("ipod_play_title")}">
                <div class="aspect-square w-full rounded-lg bg-black/10 dark:bg-white/5 flex items-center justify-center relative overflow-hidden">
                    <span class="material-symbols-outlined text-[36px] text-muted/30 group-hover:text-accent transition-colors">album</span>
                    <span class="absolute bottom-1.5 right-1.5 px-1.5 py-0.5 rounded bg-black/60 text-white font-data-sm text-[10px]">${_formatMs(tr.length_ms)}</span>
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
    return `
            <div onclick="selectIpodPlaylist(${idx})" class="flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-accent-light text-accent font-semibold' : 'bg-btn hover:bg-btn-hover text-main'}">
                <div class="flex items-center gap-2 min-w-0">
                    <span class="material-symbols-outlined text-[16px] ${p.is_master ? 'text-secondary' : 'text-muted/60'}">${p.is_master ? 'folder_special' : 'queue_music'}</span>
                    <span class="font-data-sm text-[13px] truncate">${_escapeHtmlIpod(p.title || "—")}</span>
                </div>
                <span class="font-data-sm text-[11px] text-muted/60 flex-shrink-0 ml-1">${p.count || 0}</span>
            </div>
        `;
}

function ipodPlaylistTrackRowHtml(tr, i, isMaster) {
    const drag = isMaster ? "" :
        ` draggable="true" ondragstart="handleIpodTrackDragStart(event, ${i})" ondragend="handleIpodTrackDragEnd(event)" ondragover="handleIpodTrackDragOver(event)" ondrop="handleIpodTrackDrop(event)"`;
    return `
            <div data-ipod-track-idx="${i}"${drag}
                class="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-btn-hover transition-colors ${isMaster ? '' : 'cursor-grab'}">
                ${isMaster ? '' : '<span class="material-symbols-outlined text-[16px] text-muted/30 flex-shrink-0">drag_indicator</span>'}
                <span class="font-data-sm text-[12px] text-muted/40 w-6 text-right flex-shrink-0">${i + 1}</span>
                <div class="flex-1 min-w-0">
                    <div class="font-data-sm text-[13px] text-main truncate font-medium">${_escapeHtmlIpod(tr.title || t("track_untitled"))}</div>
                    <div class="font-data-sm text-[11px] text-muted/60 truncate">${_escapeHtmlIpod(tr.artist || "")}${tr.album ? ' — ' + _escapeHtmlIpod(tr.album) : ''}</div>
                </div>
                ${tr.source_path ? `<span class="material-symbols-outlined text-[15px] text-accent flex-shrink-0" title="${t('ipod_playlist_new_track')}">fiber_new</span>` : ''}
                <span class="font-data-sm text-[11px] text-muted/50">${_formatMs(tr.length_ms)}</span>
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
    return '<div class="flex items-center gap-3 px-2 py-1.5 rounded-lg bg-btn">' +
        '<span class="material-symbols-outlined text-[18px] text-secondary flex-shrink-0">music_note</span>' +
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
    return `
        <button type="button" onclick="addLibrarySongToIpodPlaylist('${p.replace(/'/g, "\\'")}')"
            class="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-btn-hover transition-colors text-left w-full">
            <span class="material-symbols-outlined text-[16px] text-accent flex-shrink-0">add</span>
            <div class="flex-1 min-w-0">
                <div class="font-data-sm text-[13px] text-main truncate font-medium">${_escapeHtmlIpod(l.title || t("track_untitled"))}</div>
                <div class="font-data-sm text-[11px] text-muted/60 truncate">${_escapeHtmlIpod(l.artist || "")}${l.album ? ' — ' + _escapeHtmlIpod(l.album) : ''}</div>
            </div>
        </button>`;
}

// --- Fotos / Videos ---
function ipodPhotoCardHtml(ph, idx) {
    return `
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
    `;
}

function ipodVideoCardHtml(vid, idx) {
    return `
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
    `;
}

// --- Podcasts / Episodios ---
function ipodPodcastSidebarItemHtml(pod, idx, isSelected) {
    return `
            <div onclick="selectIpodPodcast(${idx})" class="flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-accent-light text-accent font-semibold' : 'bg-btn hover:bg-btn-hover text-main'}">
                <div class="flex items-center gap-2 min-w-0">
                    <span class="material-symbols-outlined text-[16px]">podcasts</span>
                    <span class="font-data-sm text-[13px] truncate">${_escapeHtmlIpod(pod.name || "Podcast")}</span>
                </div>
                <span class="font-data-sm text-[11px] text-muted/60">${(pod.episodes || []).length}</span>
            </div>
        `;
}

function ipodEpisodeRowHtml(ep, i) {
    return `
            <div class="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-btn-hover transition-colors">
                <span class="font-data-sm text-[12px] text-muted/40 w-6 text-right">${i + 1}</span>
                <div class="flex-1 min-w-0">
                    <div class="font-data-sm text-[13px] text-main truncate font-medium">${_escapeHtmlIpod(ep.title)}</div>
                    <div class="font-data-sm text-[11px] text-muted/60 truncate">${ep.date || ""}</div>
                </div>
                <span class="font-data-sm text-[11px] text-muted/50">${_formatMs(ep.duration_ms)}</span>
            </div>
        `;
}

// --- Audiolibros / Capítulos ---
function ipodAudiobookSidebarItemHtml(ab, idx, isSelected) {
    return `
            <div onclick="selectIpodAudiobook(${idx})" class="flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-accent-light text-accent font-semibold' : 'bg-btn hover:bg-btn-hover text-main'}">
                <div class="flex items-center gap-2 min-w-0">
                    <span class="material-symbols-outlined text-[16px]">menu_book</span>
                    <span class="font-data-sm text-[13px] truncate">${_escapeHtmlIpod(ab.title || "Audiolibro")}</span>
                </div>
                <span class="font-data-sm text-[11px] text-muted/60">${(ab.chapters || []).length}</span>
            </div>
        `;
}

function ipodChapterRowHtml(ch, i, author) {
    return `
            <div class="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-btn-hover transition-colors">
                <span class="font-data-sm text-[12px] text-muted/40 w-6 text-right">${i + 1}</span>
                <div class="flex-1 min-w-0">
                    <div class="font-data-sm text-[13px] text-main truncate font-medium">${_escapeHtmlIpod(ch.title)}</div>
                    <div class="font-data-sm text-[11px] text-muted/60 truncate">${author || ""}</div>
                </div>
                <span class="font-data-sm text-[11px] text-muted/50">${_formatMs(ch.duration_ms)}</span>
            </div>
        `;
}
