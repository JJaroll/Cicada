// Extraído de cicada/core/main.py — sin cambios de comportamiento. Ver docs/IPOD_INTEGRATION.md
let libraryAudio = document.getElementById("library-audio");

let libraryQueues = {};
let currentQueueKey = null;
let currentQueueIndex = -1;

function playFromQueue(key, index) {
    currentQueueKey = key;
    currentQueueIndex = index;
    playCurrentQueueTrack();
}

function playCurrentQueueTrack() {
    let queue = libraryQueues[currentQueueKey];
    if (!queue || !queue[currentQueueIndex]) return;
    let track = queue[currentQueueIndex];

    hasPlayedTrack = true;
    document.getElementById("playerTrackTitle").textContent = track.title || t("track_untitled");
    document.getElementById("playerTrackArtist").textContent = (track.artist || "") + (track.album ? " · " + track.album : "");

    let cover = document.getElementById("playerCover");
    let placeholder = document.getElementById("playerCoverPlaceholder");
    cover.classList.add("hidden");
    placeholder.classList.remove("hidden");
    cover.onload = function() { cover.classList.remove("hidden"); placeholder.classList.add("hidden"); };
    cover.onerror = function() { cover.classList.add("hidden"); placeholder.classList.remove("hidden"); };
    cover.src = '/api/library/artwork?path=' + encodeURIComponent(track.path);

    libraryAudio.src = '/api/library/stream?path=' + encodeURIComponent(track.path);
    libraryAudio.play().catch(function(e) { console.error("Error reproduciendo:", e); });
    setPlayPauseIcon(true);
}

function togglePlayPause() {
    if (!libraryAudio.src) return;
    if (libraryAudio.paused) {
        libraryAudio.play();
        setPlayPauseIcon(true);
    } else {
        libraryAudio.pause();
        setPlayPauseIcon(false);
    }
}

function setPlayPauseIcon(playing) {
    document.getElementById("playerPlayPauseIcon").textContent = playing ? "pause" : "play_arrow";
}

let isShuffle = false;
let repeatMode = 0;

function toggleShuffle() {
    isShuffle = !isShuffle;
    let btn = document.getElementById("btnShuffle");
    if (isShuffle) {
        btn.classList.remove("text-sidebar/40");
        btn.classList.add("text-accent");
    } else {
        btn.classList.remove("text-accent");
        btn.classList.add("text-sidebar/40");
    }
}

function toggleRepeat() {
    repeatMode = (repeatMode + 1) % 3;
    let btn = document.getElementById("btnRepeat");
    if (repeatMode === 0) {
        btn.classList.remove("text-accent");
        btn.classList.add("text-sidebar/40");
        btn.textContent = "repeat";
    } else if (repeatMode === 1) {
        btn.classList.remove("text-sidebar/40");
        btn.classList.add("text-accent");
        btn.textContent = "repeat";
    } else if (repeatMode === 2) {
        btn.classList.remove("text-sidebar/40");
        btn.classList.add("text-accent");
        btn.textContent = "repeat_one";
    }
}

function playNextTrack(auto = false) {
    let queue = libraryQueues[currentQueueKey];
    if (!queue) return;
    
    if (auto === true && repeatMode === 2) {
        libraryAudio.currentTime = 0;
        libraryAudio.play();
        return;
    }
    
    if (isShuffle) {
        currentQueueIndex = Math.floor(Math.random() * queue.length);
    } else {
        if (currentQueueIndex >= queue.length - 1) {
            if (repeatMode === 1) {
                currentQueueIndex = 0;
            } else {
                if (auto === true) setPlayPauseIcon(false);
                return;
            }
        } else {
            currentQueueIndex += 1;
        }
    }
    playCurrentQueueTrack();
}

function playPrevTrack() {
    let queue = libraryQueues[currentQueueKey];
    if (!queue) return;
    
    if (isShuffle) {
        currentQueueIndex = Math.floor(Math.random() * queue.length);
    } else {
        if (currentQueueIndex <= 0) {
            currentQueueIndex = 0;
        } else {
            currentQueueIndex -= 1;
        }
    }
    playCurrentQueueTrack();
}

function seekPlayer(e) {
    if (!libraryAudio.duration) return;
    let rect = document.getElementById("playerSeekTrack").getBoundingClientRect();
    let ratio = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1);
    libraryAudio.currentTime = ratio * libraryAudio.duration;
}

function setVolumeFromClick(e) {
    let rect = document.getElementById("playerVolumeTrack").getBoundingClientRect();
    let ratio = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1);
    setVolume(ratio);
}

function setVolume(vol) {
    libraryAudio.volume = vol;
}

libraryAudio.addEventListener("volumechange", function() {
    let pct = libraryAudio.volume * 100;
    document.getElementById("playerVolumeFill").style.width = pct + "%";
});

libraryAudio.addEventListener("timeupdate", function() {
    if (!libraryAudio.duration) return;
    let pct = (libraryAudio.currentTime / libraryAudio.duration) * 100;
    document.getElementById("playerSeekFill").style.width = pct + "%";
    document.getElementById("playerCurrentTime").textContent = formatTime(libraryAudio.currentTime);
    document.getElementById("playerDuration").textContent = formatTime(libraryAudio.duration);
});
libraryAudio.addEventListener("ended", function() {
    playNextTrack(true);
});
libraryAudio.addEventListener("pause", function() { setPlayPauseIcon(false); });
libraryAudio.addEventListener("play", function() { setPlayPauseIcon(true); });

// --- Ajustes (modal): credenciales de API, toggle del Plan C, carpetas predeterminadas ---
