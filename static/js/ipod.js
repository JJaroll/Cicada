// Extraído de cicada/core/main.py — sin cambios de comportamiento. Ver docs/IPOD_INTEGRATION.md
function _setIpodButtons(enabled) {
    for (const id of ["btn-sync-ipod", "btn-backup-ipod"]) {
        const b = document.getElementById(id);
        if (!b) continue;
        b.disabled = !enabled;
        b.classList.toggle("opacity-50", !enabled);
        b.classList.toggle("cursor-not-allowed", !enabled);
    }
}

async function scanIpod() {
    const container = document.getElementById("ipod-info-container");
    const noDevice = document.getElementById("ipod-no-device");
    const noControl = document.getElementById("ipod-no-control");
    const library = document.getElementById("ipod-library");
    try {
        const res = await fetch('/api/ipod/scan');
        const data = await res.json();

        // Tres estados diferenciados.
        if (data.state === "ready" && data.ipods && data.ipods.length > 0) {
            const ipod = data.ipods[0];
            document.getElementById("ipod-name").textContent = ipod.ipod_name || "iPod";

            const modelParts = [ipod.model_family, ipod.generation, ipod.color].filter(Boolean);
            document.getElementById("ipod-model").textContent =
                t("ipod_model_label") + ": " + (modelParts.join(" ") || t("ipod_unknown"));
            document.getElementById("ipod-capacity").textContent =
                t("ipod_capacity_label") + ": " + (ipod.capacity || t("ipod_unknown"));
            // Firma del firmware (HASHAB en Nano 7G): confirma que sabemos leer/verificar.
            document.getElementById("ipod-format").textContent =
                t("ipod_signature_label") + ": " + (ipod.checksum || t("ipod_unknown"));

            container.classList.remove("hidden");
            noDevice.classList.add("hidden");
            noControl.classList.add("hidden");
            _setIpodButtons(true);
            loadIpodLibrary();
        } else if (data.state === "no_ipod_control") {
            container.classList.add("hidden");
            library.classList.add("hidden");
            noDevice.classList.add("hidden");
            noControl.classList.remove("hidden");   // mensaje propio (data-i18n)
            _setIpodButtons(false);
        } else {
            container.classList.add("hidden");
            library.classList.add("hidden");
            noControl.classList.add("hidden");
            noDevice.classList.remove("hidden");
            _setIpodButtons(false);
        }
    } catch (e) {
        console.error("Error escaneando iPod:", e);
        alert(t("ipod_scan_error"));
    }
}

function _escapeHtmlIpod(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, c =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function loadIpodLibrary() {
    const library = document.getElementById("ipod-library");
    const tracksEl = document.getElementById("ipod-tracks-list");
    const plsEl = document.getElementById("ipod-playlists-list");
    const counts = document.getElementById("ipod-library-counts");
    library.classList.remove("hidden");
    tracksEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/60">' + t("ipod_loading") + '</p>';
    plsEl.innerHTML = "";
    try {
        const [tRes, pRes] = await Promise.all([
            fetch('/api/ipod/tracks'), fetch('/api/ipod/playlists'),
        ]);
        const tData = await tRes.json();
        const pData = await pRes.json();
        if (!tRes.ok) throw new Error(tData.detail || t("error_unknown"));
        if (!pRes.ok) throw new Error(pData.detail || t("error_unknown"));

        counts.textContent = (tData.tracks_count || 0) + " " + t("ipod_tracks_count") +
            " · " + (pData.count || 0) + " " + t("ipod_playlists_count");

        plsEl.innerHTML = (pData.playlists || []).map(p =>
            '<div class="flex items-center justify-between px-2 py-1.5 rounded-lg bg-btn">' +
            '<span class="font-data-sm text-[13px] text-main truncate">' +
            (p.is_master ? '<span class="material-symbols-outlined text-[14px] align-middle text-secondary">library_music</span> ' : '') +
            _escapeHtmlIpod(p.title || "—") + '</span>' +
            '<span class="font-data-sm text-[12px] text-muted/60 flex-shrink-0 ml-2">' + p.count + '</span></div>'
        ).join("");

        tracksEl.innerHTML = (tData.tracks || []).map((tr, i) =>
            '<div class="flex items-center gap-3 px-2 py-1.5 rounded-lg hover:bg-btn-hover">' +
            '<span class="font-data-sm text-[12px] text-muted/40 w-6 text-right flex-shrink-0">' + (i + 1) + '</span>' +
            '<div class="flex-1 min-w-0">' +
            '<div class="font-data-sm text-[13px] text-main truncate">' + _escapeHtmlIpod(tr.title || "—") + '</div>' +
            '<div class="font-data-sm text-[12px] text-muted/60 truncate">' +
            _escapeHtmlIpod(tr.artist || "") + (tr.album ? " — " + _escapeHtmlIpod(tr.album) : "") + '</div></div>' +
            '<span class="font-data-sm text-[11px] text-muted/40 flex-shrink-0">' + _escapeHtmlIpod(tr.filetype || "") + '</span></div>'
        ).join("");
    } catch (e) {
        tracksEl.innerHTML = '<p class="font-data-sm text-[13px] text-[#f43f5e]">' + t("error_prefix") + e.message + '</p>';
    }
}

// Extrae el mensaje de error de una respuesta FastAPI (detail = string u {error,code}).
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

// Flujo de escritura: /status (write-safe) -> /tracks -> /plan (dry-run) ->
// gate de consentimiento Music.app -> /apply. Reescribe la base del iPod en el
// formato de Cicada con las pistas actuales. Backup automático + rollback.
async function syncIpod() {
    const btn = document.getElementById("btn-sync-ipod");
    try {
        // 1. Estado del dispositivo: debe ser seguro para escribir.
        const st = await (await fetch("/api/ipod/status")).json();
        const dev = (st.devices || [])[0];
        if (!dev) { alert(t("ipod_write_no_device")); return; }
        if (!dev.guid_is_write_safe) { alert(t("ipod_write_unsafe")); return; }

        // 2. Pistas actuales (fuente de la reescritura).
        const tData = await (await fetch("/api/ipod/tracks")).json();
        const tracks = tData.tracks || [];
        if (!tracks.length) { alert(t("ipod_write_empty")); return; }

        // 3. Plan dry-run (off-device, sin tocar el iPod todavía).
        if (btn) btn.disabled = true;
        const { res: planRes, data: plan } = await _postJson("/api/ipod/plan", { tracks });
        if (!planRes.ok) throw new Error(_ipodErr(plan));

        // 4. Revisión del dry-run.
        if (!confirm(t("ipod_write_review").replace("{n}", plan.tracks_count))) return;

        // 5. Gate de consentimiento Music.app (irreversible) en la primera escritura.
        let consentAck = false;
        if (plan.consent_needed) {
            consentAck = confirm(t("ipod_write_consent"));
            if (!consentAck) return;   // el usuario dice no -> nada se escribe
        }

        // 6. Apply transaccional (backup -> escribir -> verificar -> rollback si falla).
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
