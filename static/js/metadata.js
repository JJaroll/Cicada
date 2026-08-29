// Procesamiento y etiquetado de metadatos de la biblioteca de audio.
function fileCardHtml(name, sub) {
    return '<div class="bg-btn border border-theme rounded-lg p-3 flex items-center gap-3">' +
        '<div class="w-8 h-8 rounded bg-accent/20 flex items-center justify-center flex-shrink-0">' +
        '<span class="material-symbols-outlined text-accent text-[18px]">audio_file</span></div>' +
        '<div class="overflow-hidden"><p class="font-data-sm text-[13px] truncate">' + name + '</p>' +
        '<p class="font-label-caps text-[10px] text-muted/40">' + sub + '</p></div></div>';
}

function addFileCard(name, sub) {
    sessionFiles.unshift({name: name, sub: sub});
    if (sessionFiles.length > 24) sessionFiles.pop();
    renderFileGrids();
}

function renderFileGrids() {
    if (sessionFiles.length === 0) return;
    let cardsHtml = sessionFiles.map(function(f) { return fileCardHtml(f.name, f.sub); }).join("");
    if (processFileGrid) processFileGrid.innerHTML = cardsHtml;
}

async function pickFolder(inputId) {
    try {
        let res = await fetch('/api/select_folder');
        let data = await res.json();
        if (data.path) {
            document.getElementById(inputId).value = data.path;
        }
    } catch (e) {
        console.error("Error al seleccionar carpeta:", e);
    }
}

function resetUi() {
    let startBtn = document.getElementById("startBtn");
    if (startBtn) {
        startBtn.disabled = false;
        startBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">play_arrow</span> ' + t("process_start_btn");
        startBtn.classList.remove("opacity-50");
    }
    document.querySelectorAll(".cancel-action").forEach(function(btn) {
        btn.classList.add("hidden");
        btn.disabled = false;
        btn.innerHTML = '<span class="material-symbols-outlined text-[20px]">stop</span> ' + t("process_cancel_btn");
    });
    let downloadBtn = document.getElementById("spotifyDownloadBtn");
    if (downloadBtn) downloadBtn.dataset.busy = "0";
    refreshSpotifyDownloadButton();
}

function startProcess() {
    let input_dir = document.getElementById("input_dir").value;
    let output_dir = document.getElementById("output_dir").value;

    if (!input_dir || !output_dir) {
        alert(t("alert_both_paths_required"));
        return;
    }

    let startBtn = document.getElementById("startBtn");
    startBtn.disabled = true;
    startBtn.innerHTML = '<span class="material-symbols-outlined text-[20px]">sync</span> ' + t("process_connecting_btn");
    startBtn.classList.add("opacity-50");
    document.querySelectorAll(".cancel-action").forEach(function(btn) { btn.classList.remove("hidden"); });

    logContainer.innerHTML = "";
    appendLog(t("log_starting_process"), "info");
    bar.style.width = '0%';
    progressLabel.textContent = "0%";
    statCount.textContent = "0/0";
    statPct.textContent = "0%";
    setStatusPill("process_starting_status", "#06b6d4");
    hasStartedProcessing = true;
    trackTitle.textContent = t("process_starting_track");
    trackSubtitle.textContent = t("process_scanning_library");
    sessionFiles = [];
    if (processFileGrid) processFileGrid.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("process_waiting_first_file") + '</p>';

    let img = document.getElementById("currentCover");
    let placeholder = document.getElementById("coverPlaceholder");
    img.classList.add("hidden");
    placeholder.classList.remove("hidden");

    fetch('/api/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({input_dir: input_dir, output_dir: output_dir})
    }).then(function(r) { return r.json(); }).then(function(d) {
        console.log(d);
    }).catch(function(e) {
        appendLog(t("log_connect_error") + e, "error");
        resetUi();
    });
}

function cancelProcess() {
    document.querySelectorAll(".cancel-action").forEach(function(btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="material-symbols-outlined text-[20px]">sync</span> ' + t("process_cancelling_btn");
    });

    fetch('/api/cancel', {method: 'POST'})
        .then(function(r) { return r.json(); })
        .then(function(d) { console.log(d); })
        .catch(function(e) { console.error("Error al cancelar:", e); });
}

let currentArtworkBase64 = null;

function switchTrackInfoTab(tab) {
    document.getElementById('tab-info-details').className = 'font-label-caps text-[12px] ' + (tab === 'details' ? 'text-accent border-b-2 border-accent pb-1' : 'text-muted/60 hover:text-main pb-1');
    document.getElementById('tab-info-artwork').className = 'font-label-caps text-[12px] ' + (tab === 'artwork' ? 'text-accent border-b-2 border-accent pb-1' : 'text-muted/60 hover:text-main pb-1');
    document.getElementById('track-info-details-panel').style.display = tab === 'details' ? 'flex' : 'none';
    document.getElementById('track-info-artwork-panel').style.display = tab === 'artwork' ? 'flex' : 'none';
}

function handleArtworkSelection(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function(e) {
        currentArtworkBase64 = e.target.result;
        const img = document.getElementById("info_artwork_img");
        img.src = currentArtworkBase64;
        img.classList.remove("hidden");
    };
    reader.readAsDataURL(file);
}

async function contextGetInfo() {
    if (!contextMenuTrackPath) return;
    try {
        let res = await fetch('/api/library/track_info?path=' + encodeURIComponent(contextMenuTrackPath));
        let meta = await res.json();
        
        document.getElementById("info_title").value = meta.title || "";
        document.getElementById("info_artist").value = meta.artist || "";
        document.getElementById("info_album").value = meta.album || "";
        document.getElementById("info_album_artist").value = meta.album_artist || "";
        document.getElementById("info_composer").value = meta.composer || "";
        document.getElementById("info_grouping").value = meta.grouping || "";
        document.getElementById("info_genre").value = meta.genre || "";
        document.getElementById("info_year").value = meta.year || "";
        document.getElementById("info_bpm").value = meta.bpm || "";
        document.getElementById("info_track_number").value = meta.track_number || "";
        document.getElementById("info_track_count").value = meta.track_count || "";
        document.getElementById("info_disc_number").value = meta.disc_number || "";
        document.getElementById("info_disc_count").value = meta.disc_count || "";
        document.getElementById("info_compilation").checked = meta.compilation || false;
        document.getElementById("info_comments").value = meta.comments || "";
        
        switchTrackInfoTab('details');
        currentArtworkBase64 = null;
        document.getElementById("info_artwork_input").value = "";
        const img = document.getElementById("info_artwork_img");
        img.onload = function() { img.classList.remove("hidden"); };
        img.onerror = function() { img.classList.add("hidden"); };
        img.src = '/api/library/artwork?path=' + encodeURIComponent(contextMenuTrackPath) + '&_t=' + Date.now();

        document.getElementById("track-info-modal").classList.remove("hidden");
        document.getElementById("track-info-modal").classList.add("flex");
    } catch (e) {
        console.error("Error obteniendo info:", e);
        alert("Error obteniendo info de la pista.");
    }
}

function closeTrackInfoModal() {
    document.getElementById("track-info-modal").classList.remove("flex");
    document.getElementById("track-info-modal").classList.add("hidden");
}

async function saveTrackInfo() {
    if (!contextMenuTrackPath) return;
    const meta = {
        title: document.getElementById("info_title").value,
        artist: document.getElementById("info_artist").value,
        album: document.getElementById("info_album").value,
        album_artist: document.getElementById("info_album_artist").value,
        composer: document.getElementById("info_composer").value,
        grouping: document.getElementById("info_grouping").value,
        genre: document.getElementById("info_genre").value,
        year: document.getElementById("info_year").value,
        bpm: document.getElementById("info_bpm").value,
        track_number: document.getElementById("info_track_number").value,
        track_count: document.getElementById("info_track_count").value,
        disc_number: document.getElementById("info_disc_number").value,
        disc_count: document.getElementById("info_disc_count").value,
        compilation: document.getElementById("info_compilation").checked,
        comments: document.getElementById("info_comments").value
    };
    if (currentArtworkBase64) {
        meta.artwork_base64 = currentArtworkBase64;
    }
    
    try {
        let res = await fetch('/api/library/track_info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: contextMenuTrackPath, metadata: meta })
        });
        if (res.ok) {
            closeTrackInfoModal();
            let libraryDir = document.getElementById("library_dir").value || document.getElementById("input_dir").value;
            if (libraryDir) scanLibrary(libraryDir);
        } else {
            let data = await res.json();
            alert("Error: " + data.detail);
        }
    } catch (e) {
        console.error("Error guardando info:", e);
        alert("Error al guardar información.");
    }
}
