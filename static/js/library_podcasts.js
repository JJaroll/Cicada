// Gestión de suscripción, descarga y selección de podcasts para el iPod.
let podcastFeeds = [];
let podcastSelectedFeedUrl = null;
let podcastSelectMode = true;
let podcastSelected = new Set();

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
            '<p class="font-data-sm text-[13px] text-[#f43f5e] p-2">' + t("error_prefix") + e.message + '</p>');
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
        updatePodcastIpodButton();
        updatePodcastSelectUI();
    } catch (e) {
        console.error("Error cargando podcasts:", e);
    }
}

function renderPodcastFeeds() {
    let listEl = document.getElementById("podcast-feeds-list");
    if (!listEl) return;
    if (podcastFeeds.length === 0) {
        listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40 p-3">' + t("podcasts_no_subscriptions") + '</p>';
        return;
    }
    listEl.innerHTML = podcastFeeds.map(f => {
        let active = f.feed_url === podcastSelectedFeedUrl;
        return `
            <div class="flex items-center gap-2.5 p-2.5 rounded-xl cursor-pointer transition-all ${
                active ? 'ring-2 ring-accent bg-accent/15 text-main font-semibold shadow-sm' : 'bg-black/10 dark:bg-white/5 hover:bg-black/20 dark:hover:bg-white/10 text-main'
            }" onclick="selectPodcastFeed(${JSON.stringify(f.feed_url).replace(/"/g, '&quot;')})">
                <span class="material-symbols-outlined text-[20px] text-accent flex-shrink-0">podcasts</span>
                <div class="overflow-hidden flex-1 min-w-0">
                    <p class="font-data-sm text-[13px] truncate font-medium">${escapeHtml(f.title)}</p>
                    <p class="font-label-caps text-[10px] text-muted/60 truncate">${f.episode_count} episodios</p>
                </div>
            </div>
        `;
    }).join("");
}

function selectPodcastFeed(feedUrl) {
    podcastSelectedFeedUrl = feedUrl;
    podcastSelected.clear();
    renderPodcastFeeds();
    renderPodcastEpisodes();
    updatePodcastIpodButton();
    updatePodcastSelectUI();
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
    let statusBadge = "";
    if (ep.status === "on_ipod") {
        statusBadge = `<span class="px-2 py-0.5 rounded-md bg-secondary/15 text-secondary text-[10px] font-label-caps flex items-center gap-1"><span class="material-symbols-outlined text-[13px]">check</span> En iPod</span>`;
    } else if (ep.status === "downloaded") {
        statusBadge = `<span class="px-2 py-0.5 rounded-md bg-accent/15 text-accent text-[10px] font-label-caps">Descargado</span>`;
    } else if (ep.status === "downloading") {
        statusBadge = `<span class="px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-400 text-[10px] font-label-caps animate-pulse">Descargando...</span>`;
    } else if (ep.last_error) {
        statusBadge = `<span class="px-2 py-0.5 rounded-md bg-red-500/15 text-red-400 text-[10px] font-label-caps truncate max-w-[120px]" title="${escapeHtml(ep.last_error)}">Error</span>`;
    }
    
    let subtitle = subtitleParts.filter(Boolean).join(" &middot; ");
    let isDownloaded = ep.status === "downloaded";
    let sel = podcastSelected.has(ep.guid);

    let actionOrCheck = '';
    if (isDownloaded) {
        actionOrCheck = `
            <span class="material-symbols-outlined text-[22px] text-accent flex-shrink-0 transition-transform ${sel ? 'scale-110' : 'opacity-60'}">
                ${sel ? 'check_circle' : 'radio_button_unchecked'}
            </span>
        `;
    } else if (ep.status === "not_downloaded") {
        actionOrCheck = `
            <button type="button" onclick="event.stopPropagation();downloadPodcastEpisode(${JSON.stringify(ep.guid).replace(/"/g, '&quot;')})" 
                class="px-3 py-1 rounded-lg bg-btn hover:bg-btn-hover text-main font-label-caps text-[11px] transition-all flex items-center gap-1 hover:brightness-110 flex-shrink-0">
                <span class="material-symbols-outlined text-[14px]">download</span>
                <span>Descargar</span>
            </button>
        `;
    } else {
        actionOrCheck = statusBadge;
    }

    return `
        <div class="flex items-center gap-3 p-2.5 rounded-xl transition-all ${
            isDownloaded ? 'cursor-pointer' : ''
        } ${
            sel ? 'ring-2 ring-accent bg-accent/15 shadow-sm' : 'bg-black/10 dark:bg-white/5 hover:bg-black/20 dark:hover:bg-white/10'
        }" data-guid="${escapeHtml(ep.guid)}" ${isDownloaded ? 'onclick="togglePodcastSelect(this)"' : ''}>
            ${isDownloaded ? actionOrCheck : '<span class="material-symbols-outlined text-[20px] text-muted/40 flex-shrink-0">mic</span>'}
            <div class="overflow-hidden flex-1 min-w-0">
                <p class="font-data-sm text-[13px] font-semibold text-main truncate">${escapeHtml(ep.title)}</p>
                <div class="flex items-center gap-2 mt-0.5">
                    <span class="font-label-caps text-[11px] text-muted/70 truncate">${subtitle}</span>
                    ${!isDownloaded ? statusBadge : ''}
                </div>
            </div>
            ${!isDownloaded ? actionOrCheck : ''}
        </div>
    `;
}

function renderPodcastEpisodes() {
    let listEl = document.getElementById("podcast-episodes-list");
    let titleEl = document.getElementById("podcast-episodes-title");
    if (!listEl) return;
    let feed = _currentPodcastFeed();
    if (!feed) {
        listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40 p-3">' + t("podcasts_pick_feed_hint") + '</p>';
        if (titleEl) titleEl.textContent = "";
        return;
    }
    if (titleEl) titleEl.textContent = feed.title;
    if (feed.episodes.length === 0) {
        listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40 p-3">' + t("podcasts_no_episodes") + '</p>';
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
    await loadPodcastFeeds();
}

function updatePodcastIpodButton() {
    const btn = document.getElementById("podcast-add-ipod-btn");
    if (!btn) return;
    const connected = (typeof ipodState !== "undefined") && ipodState.connected;
    let feed = _currentPodcastFeed();
    const hasEpisodes = feed && feed.episodes && feed.episodes.length > 0;
    btn.classList.toggle("hidden", !(connected && hasEpisodes));
    btn.classList.toggle("inline-flex", (connected && hasEpisodes));
}

function onPodcastIpodButton() {
    let feed = _currentPodcastFeed();
    if (!feed) return;
    
    const downloadedEpisodes = (feed.episodes || []).filter(ep => ep.status === "downloaded");
    if (downloadedEpisodes.length === 0) {
        alert("Primero descarga algún episodio para poder transferirlo al iPod.");
        return;
    }
    
    if (podcastSelected.size === 0) {
        if (downloadedEpisodes.length === 1) {
            podcastSelected.add(downloadedEpisodes[0].guid);
            renderPodcastEpisodes();
            updatePodcastSelectUI();
        } else {
            alert("Por favor selecciona al menos un episodio descargado.");
            return;
        }
    }
    commitPodcastSelectionToIpod();
}

function exitPodcastSelectMode() {
    podcastSelected.clear();
    renderPodcastEpisodes();
    updatePodcastSelectUI();
}

function togglePodcastSelect(el) {
    const guid = el.dataset.guid;
    if (!guid) return;
    const now = !podcastSelected.has(guid);
    if (now) podcastSelected.add(guid); else podcastSelected.delete(guid);
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
    updatePodcastSelectUI();
}

function updatePodcastSelectUI() {
    const label = document.getElementById("podcast-add-ipod-label");
    const selectedCount = podcastSelected.size;

    if (label) {
        label.textContent = selectedCount > 0
            ? `Agregar a iPod (${selectedCount})`
            : `Agregar a iPod`;
    }
}

function commitPodcastSelectionToIpod() {
    if (podcastSelected.size === 0) {
        alert(t("library_select_none"));
        return;
    }
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
            podcast_enclosure_url: ep.audio_url || null,
            podcast_rss_url: feed.feed_url || null,
            guid: ep.guid,
        }));
    const added = (typeof addToSyncBasket === "function") ? addToSyncBasket(items) : 0;
    
    if (typeof closeSubscribePodcastModal === "function") {
        closeSubscribePodcastModal();
    }
    
    exitPodcastSelectMode();
    alert(t("library_added_to_ipod").replace("{n}", added));
    
    if (typeof selectIpodCategory === "function") {
        selectIpodCategory("sync");
    }
}

