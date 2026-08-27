// Gestión de podcasts: suscribirse por RSS, descargar episodios a un
// caché local, y agregar los ya descargados al carrito de sync del
// iPod (kind="podcast"). Selección múltiple calcada del flujo de
// audiolibros (library_audiobooks.js), pero limitada a episodios con
// status "downloaded" — no tiene sentido sincronizar algo que no está
// en disco todavía.
let podcastFeeds = [];
let podcastSelectedFeedUrl = null;
let podcastSelectMode = false;
let podcastSelected = new Set(); // guids

async function subscribePodcastFeed() {
    let url = document.getElementById("podcast_feed_url").value.trim();
    if (!url) return;
    let listEl = document.getElementById("podcast-feeds-list");
    try {
        let res = await fetch('/api/podcasts/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ feed_url: url })
        });
        let data = await res.json();
        if (!res.ok) throw new Error(data.detail || t("error_unknown"));

        document.getElementById("podcast_feed_url").value = "";
        podcastSelectedFeedUrl = data.feed_url;
        await loadPodcastFeeds();
    } catch (e) {
        if (listEl) listEl.insertAdjacentHTML('afterbegin',
            '<p class="font-data-sm text-[13px] text-[#f43f5e]">' + t("error_prefix") + e.message + '</p>');
    }
}

async function loadPodcastFeeds() {
    try {
        let res = await fetch('/api/podcasts');
        let data = await res.json();
        podcastFeeds = data.feeds || [];
        if (!podcastSelectedFeedUrl && podcastFeeds.length) {
            podcastSelectedFeedUrl = podcastFeeds[0].feed_url;
        }
        renderPodcastFeeds();
        renderPodcastEpisodes();
    } catch (e) {
        console.error("Error cargando podcasts:", e);
    }
}

function renderPodcastFeeds() {
    let listEl = document.getElementById("podcast-feeds-list");
    if (!listEl) return;
    if (podcastFeeds.length === 0) {
        listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40 p-2">' + t("podcasts_no_subscriptions") + '</p>';
        return;
    }
    listEl.innerHTML = podcastFeeds.map(f => {
        let active = f.feed_url === podcastSelectedFeedUrl;
        return '<div class="flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer transition-colors ' +
            (active ? 'bg-secondary/15 text-secondary' : 'hover:bg-btn-hover') +
            '" onclick="selectPodcastFeed(' + JSON.stringify(f.feed_url).replace(/"/g, "&quot;") + ')">' +
            '<span class="material-symbols-outlined text-[18px]">podcasts</span>' +
            '<div class="overflow-hidden flex-1">' +
            '<p class="font-data-sm text-[13px] truncate">' + escapeHtml(f.title) + '</p>' +
            '<p class="font-label-caps text-[10px] text-muted/40 truncate">' + f.episode_count + ' episodios</p>' +
            '</div></div>';
    }).join("");
}

function selectPodcastFeed(feedUrl) {
    podcastSelectedFeedUrl = feedUrl;
    exitPodcastSelectMode();
    renderPodcastFeeds();
    renderPodcastEpisodes();
}

function _currentPodcastFeed() {
    return podcastFeeds.find(f => f.feed_url === podcastSelectedFeedUrl) || null;
}

function formatPodcastDuration(durationSeconds) {
    if (!durationSeconds) return "";
    return formatDurationWords(durationSeconds);
}

function podcastEpisodeRowHtml(ep) {
    let subtitleParts = [formatPodcastDuration(ep.duration_seconds)];
    let statusLabel = "";
    if (ep.status === "on_ipod") statusLabel = t("podcasts_status_on_ipod");
    else if (ep.status === "downloaded") statusLabel = t("podcasts_status_downloaded");
    else if (ep.status === "downloading") statusLabel = t("podcasts_status_downloading");
    else if (ep.last_error) statusLabel = t("podcasts_status_failed");
    if (statusLabel) subtitleParts.push(statusLabel);
    let subtitle = subtitleParts.filter(Boolean).join(" &middot; ");

    let canSelect = podcastSelectMode && ep.status === "downloaded";
    if (canSelect) {
        let sel = podcastSelected.has(ep.guid);
        return '<div class="flex items-center gap-3 px-2 py-1.5 rounded-lg cursor-pointer transition-colors ' +
            (sel ? 'ring-1 ring-secondary bg-secondary/10' : 'hover:bg-btn-hover') + '" data-guid="' + escapeHtml(ep.guid) +
            '" onclick="togglePodcastSelect(this)">' +
            '<span class="material-symbols-outlined text-[18px] text-secondary">' + (sel ? 'check_circle' : 'radio_button_unchecked') + '</span>' +
            '<div class="overflow-hidden flex-1">' +
            '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(ep.title) + '</p>' +
            '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + subtitle + '</p>' +
            '</div></div>';
    }

    let actionHtml = '';
    if (ep.status === "not_downloaded") {
        actionHtml = '<button type="button" onclick="event.stopPropagation();downloadPodcastEpisode(' +
            JSON.stringify(ep.guid).replace(/"/g, "&quot;") + ')" class="px-2 py-1 rounded-full bg-btn hover:bg-btn-hover font-label-caps text-[10px]">' +
            t("podcasts_download_btn") + '</button>';
    } else if (ep.status === "downloading") {
        actionHtml = '<span class="font-label-caps text-[10px] text-muted/50">' + t("podcasts_status_downloading") + '</span>';
    }

    return '<div class="flex items-center gap-3 px-2 py-1.5 rounded-lg' + (podcastSelectMode ? ' opacity-40' : '') + '" data-guid="' + escapeHtml(ep.guid) + '">' +
        '<span class="material-symbols-outlined text-[18px] text-muted/40">mic</span>' +
        '<div class="overflow-hidden flex-1">' +
        '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(ep.title) + '</p>' +
        '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + subtitle + '</p>' +
        (ep.last_error ? '<p class="font-label-caps text-[10px] text-[#f43f5e] truncate" title="' + escapeHtml(ep.last_error) + '">' + escapeHtml(ep.last_error) + '</p>' : '') +
        '</div>' + actionHtml + '</div>';
}

function renderPodcastEpisodes() {
    let listEl = document.getElementById("podcast-episodes-list");
    let titleEl = document.getElementById("podcast-episodes-title");
    if (!listEl) return;
    let feed = _currentPodcastFeed();
    if (!feed) {
        listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40 p-2">' + t("podcasts_pick_feed_hint") + '</p>';
        if (titleEl) titleEl.textContent = "";
        return;
    }
    if (titleEl) titleEl.textContent = feed.title;
    if (feed.episodes.length === 0) {
        listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40 p-2">' + t("podcasts_no_episodes") + '</p>';
        return;
    }
    listEl.innerHTML = feed.episodes.map(podcastEpisodeRowHtml).join("");
}

async function downloadPodcastEpisode(guid) {
    let feed = _currentPodcastFeed();
    if (!feed) return;
    let encodedFeed = encodeURIComponent(feed.feed_url);
    try {
        await fetch('/api/podcasts/' + encodedFeed + '/episodes/' + encodeURIComponent(guid) + '/download', { method: 'POST' });
    } catch (e) {
        console.error("Error iniciando descarga:", e);
        return;
    }
    pollPodcastDownload(feed.feed_url, guid);
}

async function pollPodcastDownload(feedUrl, guid) {
    let encodedFeed = encodeURIComponent(feedUrl);
    try {
        let res = await fetch('/api/podcasts/' + encodedFeed + '/episodes/' + encodeURIComponent(guid) + '/download');
        let prog = await res.json();
        if (prog.state === "downloading") {
            setTimeout(() => pollPodcastDownload(feedUrl, guid), 1500);
            return;
        }
    } catch (e) {
        console.error("Error consultando progreso de descarga:", e);
    }
    // Terminó (done/error) o falló la consulta: refresca desde el listado persistido.
    await loadPodcastFeeds();
}

// --- Selección múltiple → carrito de sync (episodios ya downloaded) ---

function updatePodcastIpodButton() {
    const btn = document.getElementById("podcast-add-ipod-btn");
    if (!btn) return;
    const uiEnabled = (typeof ipodUiEnabled === "undefined") || ipodUiEnabled;
    const connected = uiEnabled && (typeof ipodState !== "undefined") && ipodState.connected;
    if (!connected && podcastSelectMode) exitPodcastSelectMode();
    btn.classList.toggle("hidden", !connected);
    btn.classList.toggle("inline-flex", !!connected);
}

function onPodcastIpodButton() {
    if (!podcastSelectMode) {
        podcastSelectMode = true;
        podcastSelected.clear();
        renderPodcastEpisodes();
        updatePodcastSelectUI();
    } else {
        commitPodcastSelectionToIpod();
    }
}

function exitPodcastSelectMode() {
    podcastSelectMode = false;
    podcastSelected.clear();
    renderPodcastEpisodes();
    updatePodcastSelectUI();
}

function togglePodcastSelect(el) {
    const guid = el.dataset.guid;
    const now = !podcastSelected.has(guid);
    if (now) podcastSelected.add(guid); else podcastSelected.delete(guid);
    el.classList.toggle("ring-1", now);
    el.classList.toggle("ring-secondary", now);
    el.classList.toggle("bg-secondary/10", now);
    el.classList.toggle("hover:bg-btn-hover", !now);
    const icon = el.querySelector(".material-symbols-outlined");
    if (icon) icon.textContent = now ? "check_circle" : "radio_button_unchecked";
    updatePodcastSelectUI();
}

function updatePodcastSelectUI() {
    const label = document.getElementById("podcast-add-ipod-label");
    const cancel = document.getElementById("podcast-select-cancel-btn");
    const btn = document.getElementById("podcast-add-ipod-btn");
    if (cancel) {
        cancel.classList.toggle("hidden", !podcastSelectMode);
        cancel.classList.toggle("inline-flex", podcastSelectMode);
    }
    if (label) {
        label.textContent = podcastSelectMode
            ? t("library_add_selected").replace("{n}", podcastSelected.size)
            : t("library_add_to_ipod");
    }
    if (btn) btn.classList.toggle("bg-secondary/25", podcastSelectMode);
}

function commitPodcastSelectionToIpod() {
    if (podcastSelected.size === 0) { alert(t("library_select_none")); return; }
    let feed = _currentPodcastFeed();
    if (!feed) return;
    const items = feed.episodes
        .filter(ep => podcastSelected.has(ep.guid) && ep.status === "downloaded")
        .map(ep => ({
            source_path: ep.downloaded_path,
            title: ep.title || "",
            show_name: feed.title || null,
            genre: feed.category || null,
            episode_number: ep.episode_number || null,
            season_number: ep.season_number || null,
            length_ms: ep.duration_seconds ? ep.duration_seconds * 1000 : null,
            filetype: (ep.downloaded_path.split(".").pop() || "").toLowerCase(),
            kind: "podcast",
            guid: ep.guid, // no viaja a /media/sync — se usa localmente para mark_synced
        }));
    const added = (typeof addToSyncBasket === "function") ? addToSyncBasket(items) : 0;
    exitPodcastSelectMode();
    alert(t("library_added_to_ipod").replace("{n}", added));
}
