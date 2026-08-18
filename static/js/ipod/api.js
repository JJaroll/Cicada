// static/js/ipod/api.js — Única puerta de entrada a /api/ipod/*: parseo de
// respuesta, extracción de mensajes de error y detección de desconexión
// espontánea del iPod (MOUNT_NOT_FOUND en mitad de una operación, distinta
// del chequeo previo de "no hay dispositivo").

function _ipodErr(data) {
    const d = data && data.detail;
    if (!d) return t("error_unknown");
    return (typeof d === "object" ? (d.error || d.code) : d) || t("error_unknown");
}

async function _ipodFetch(url, options) {
    const res = await fetch(url, options);
    let data = {};
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) {
        const code = data && data.detail && typeof data.detail === "object" ? data.detail.code : null;
        if (res.status === 404 && code === "MOUNT_NOT_FOUND") {
            const err = new Error(t("ipod_disconnected_mid_operation"));
            err.ipodDisconnected = true;
            throw err;
        }
    }
    return { res, data };
}

async function _ipodGet(url) {
    return _ipodFetch(url, { method: "GET" });
}

async function _ipodPost(url, body) {
    return _ipodFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
    });
}

async function ipodFetchScan() { return _ipodGet("/api/ipod/scan"); }
async function ipodFetchStatus() { return _ipodGet("/api/ipod/status"); }
async function ipodFetchTracks() { return _ipodGet("/api/ipod/tracks"); }
async function ipodFetchPlaylists() { return _ipodGet("/api/ipod/playlists"); }
async function ipodFetchPhotos() { return _ipodGet("/api/ipod/photos"); }
async function ipodFetchVideos() { return _ipodGet("/api/ipod/videos"); }
async function ipodFetchPodcasts() { return _ipodGet("/api/ipod/podcasts"); }
async function ipodFetchAudiobooks() { return _ipodGet("/api/ipod/audiobooks"); }

async function ipodMediaSync(payload) { return _ipodPost("/api/ipod/media/sync", payload); }
async function ipodPlaylistSet(payload) { return _ipodPost("/api/ipod/playlist/set", payload); }
async function ipodTrackRemove(payload) { return _ipodPost("/api/ipod/track/remove", payload); }
async function ipodPlaylistsCreate(payload) { return _ipodPost("/api/ipod/playlists/create", payload); }
async function ipodPlaylistsImport(payload) { return _ipodPost("/api/ipod/playlists/import", payload); }
async function ipodEject(payload) { return _ipodPost("/api/ipod/eject", payload); }
async function ipodPlanCreate(payload) { return _ipodPost("/api/ipod/plan", payload); }
async function ipodApplyPlan(payload) { return _ipodPost("/api/ipod/apply", payload); }
async function ipodBackupNow(payload) { return _ipodPost("/api/ipod/backup", payload); }
async function ipodSyncPlayback() { return _ipodPost("/api/ipod/sync/playback", {}); }
