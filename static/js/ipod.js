// Extraído de cicada/core/main.py — sin cambios de comportamiento. Ver docs/IPOD_INTEGRATION.md
async function scanIpod() {
    try {
        const res = await fetch('/api/ipod/scan');
        const data = await res.json();
        
        const container = document.getElementById("ipod-info-container");
        const noDevice = document.getElementById("ipod-no-device");
        const btnSync = document.getElementById("btn-sync-ipod");
        const btnBackup = document.getElementById("btn-backup-ipod");

        if (data.ipods && data.ipods.length > 0) {
            const ipod = data.ipods[0]; // Usar el primero por ahora
            
            document.getElementById("ipod-name").textContent = ipod.ipod_name || "iPod (Sin Nombre)";
            
            let modelParts = [];
            if (ipod.model_family) modelParts.push(ipod.model_family);
            if (ipod.generation) modelParts.push(ipod.generation);
            if (ipod.color) modelParts.push(ipod.color);
            
            document.getElementById("ipod-model").textContent = "Modelo: " + (modelParts.join(" ") || "Desconocido");
            
            let cap = ipod.capacity || ipod.disk_size_gb;
            document.getElementById("ipod-capacity").textContent = "Capacidad: " + (cap ? cap + " GB" : "Desconocida");
            document.getElementById("ipod-format").textContent = "Formato: " + (ipod.filesystem_type || "Desconocido");
            
            container.classList.remove("hidden");
            noDevice.classList.add("hidden");
            
            btnSync.disabled = false;
            btnSync.classList.remove("opacity-50", "cursor-not-allowed");
            btnBackup.disabled = false;
            btnBackup.classList.remove("opacity-50", "cursor-not-allowed");
        } else {
            container.classList.add("hidden");
            noDevice.classList.remove("hidden");
            
            btnSync.disabled = true;
            btnSync.classList.add("opacity-50", "cursor-not-allowed");
            btnBackup.disabled = true;
            btnBackup.classList.add("opacity-50", "cursor-not-allowed");
        }
    } catch (e) {
        console.error("Error escaneando iPod:", e);
        alert("Ocurrió un error al intentar escanear dispositivos.");
    }
}

async function syncIpod() {
    try {
        const res = await fetch('/api/ipod/sync', { method: 'POST' });
        let data = {};
        try { data = await res.json(); } catch (_) {}
        if (!res.ok) throw new Error(data.detail || t("error_unknown"));
        alert(data.message || "Sincronización completada.");
    } catch (e) {
        alert(t("error_prefix") + e.message);
    }
}

async function backupIpod() {
    try {
        const res = await fetch('/api/ipod/backups', { method: 'POST' });
        let data = {};
        try { data = await res.json(); } catch (_) {}
        if (!res.ok) throw new Error(data.detail || t("error_unknown"));
        alert(data.message || "Backup creado.");
    } catch (e) {
        alert(t("error_prefix") + e.message);
    }
}
