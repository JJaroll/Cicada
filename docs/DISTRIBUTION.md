# Distribución y empaquetado

Decisiones de arquitectura sobre cómo Cicada se compila y distribuye, para no repetir investigaciones ya hechas si alguien retoma una alternativa en el futuro.

## Estado actual: PyInstaller + Inno Setup (Windows), sin Docker

`Cicada.spec` (PyInstaller) genera un ejecutable autocontenido por plataforma; en Windows, `cicada_installer.iss` (Inno Setup) lo empaqueta en un instalador con accesos directos y desinstalador. Ver `.github/workflows/release.yml` para el pipeline de CI que arma los tres instaladores (Windows/macOS/Linux) por tag.

## Docker + smart launcher para Windows — evaluado y descartado (2026-08-28)

**Propuesta evaluada:** usar Docker Desktop (backend WSL2) para manejar la instalación/entorno en Windows, combinado con un "smart launcher" híbrido — mismo patrón que usa Parrot (otro proyecto del autor) para distribuir sus dependencias de IA (PyTorch/Whisper, varios GB).

**Por qué se reconsideró en primer lugar:** la objeción inicial a este patrón era específica al problema que resuelve — evitar que PyInstaller tenga que empaquetar y descomprimir varios GB de dependencias de IA en cada arranque. Cicada no tiene ese problema (sus dependencias nativas, `wasmtime`/`numpy`/`zstandard`, pesan ~81MB en total). Pero "Docker para dependencias nativas en general" (compiladores, versiones de Python) es un ángulo distinto que no se había evaluado — de ahí la reconsideración.

**Motivo del descarte, con evidencia técnica concreta — no es fricción de configuración, es riesgo de que la función central de Cicada deje de funcionar:**

Cicada necesita leer/escribir el iPod montado como volumen de almacenamiento (letra de unidad en Windows, con `iPod_Control/` accesible como filesystem normal). Esto es fundamentalmente distinto de "acceder a un dispositivo USB genérico" (un Arduino, un lector de tarjetas):

- Docker Desktop con backend WSL2 **no expone dispositivos USB a los contenedores de forma nativa**. Requiere `usbipd-win`, una herramienta de terceros aparte, con comandos manuales en PowerShell **con privilegios de administrador** cada vez que se conecta el dispositivo (`usbipd list` → `usbipd bind --busid X` → `usbipd attach --wsl --busid X`).
- Mientras el dispositivo está attachado a WSL2, **Windows deja de verlo** — de la documentación oficial de Microsoft: *"as long as the USB device is attached to WSL, it cannot be used by Windows"*. El iPod desaparecería del Explorador de Windows mientras Cicada lo usa.
- **El hallazgo decisivo:** el kernel de WSL2 no trae soporte de USB mass storage por defecto (`CONFIG_USB_STORAGE` no habilitado). Para que un volumen de almacenamiento USB sea visible como bloque de archivos dentro de WSL2 hace falta **recompilar el kernel de WSL2 a mano** — no es un flag de configuración, es compilar un kernel custom. Y aun haciendo eso correctamente, hay reportes documentados donde el dispositivo aparece en `lsusb` pero **nunca llega a aparecer como bloque montable** (`lsblk`/`blkid` no lo detectan) — ni siquiera recompilar el kernel es garantía de que funcione.

Para el caso específico de Cicada (montar un volumen de almacenamiento, no un dispositivo serie genérico), esto es el peor escenario posible de los que cubre `usbipd-win`: la categoría de dispositivo USB peor soportada por todo el stack Docker Desktop + WSL2.

El punto de acceso a filesystem arbitrario (biblioteca de música, carpetas de audiolibros, ubicación de podcasts — no una carpeta fija conocida) sí se resuelve razonablemente bien: en modo WSL2, Docker Desktop comparte automáticamente todo el filesystem de Windows, sin necesitar que el usuario configure manualmente qué carpetas montar. Ese punto por sí solo no hubiera sido un impedimento — el impedimento real es exclusivamente el acceso al iPod como volumen USB.

**Costo adicional, secundario al motivo técnico principal pero relevante:** Docker Desktop es gratis para uso personal e individual (sin restricción de licencia para el caso de Cicada), pero pesa varios cientos de MB de instalación, requiere WSL2 habilitado (en máquinas sin virtualización activada en BIOS, puede requerir reinicio y cambio de configuración de firmware — fricción que un usuario doméstico promedio no sabe resolver solo). Comparado con los ~81MB de dependencias nativas que Cicada ya tiene, es una herramienta pensada para un problema de otro orden de magnitud (el de Parrot con PyTorch), no el de Cicada.

**Fuentes consultadas:**
- [Connect USB devices — Microsoft Learn](https://learn.microsoft.com/en-us/windows/wsl/connect-usb)
- [usbipd-win Issue #1189 — USB flash drive visible en lsusb pero no en lsblk/blkid tras recompilar el kernel](https://github.com/dorssel/usbipd-win/issues/1189)
- [microsoft/WSL Issue #11193 — Enable USB mass storage in kernel](https://github.com/microsoft/WSL/issues/11193)
- [usbipd-win Issue #352 — USB flash drives are not accessible](https://github.com/dorssel/usbipd-win/issues/352)
- [Sharing local files with containers — Docker Docs](https://docs.docker.com/get-started/docker-concepts/running-containers/sharing-local-files/)
- [Docker Desktop Pricing & License Cost (2026)](https://www.empiricapps.com/zenithal/docker-desktop-license-cost)

**Si se reconsidera en el futuro:** el punto a re-verificar primero es si el soporte de USB mass storage en el kernel de WSL2 cambió (Microsoft lo mantiene activamente, así que es la variable más probable de moverse con el tiempo) — no repetir el resto de la investigación si esa pieza específica sigue igual.

## Lo que sí se adoptó de la arquitectura de Parrot, sin Docker ni launcher híbrido

`SMART_LAUNCHER.txt` (documento de referencia de Parrot, fuera del repo de Cicada) describe además un patrón de launcher "hueco" + entorno virtual instalado en el home del usuario, pensado para evitar que PyInstaller empaquete varios GB. Como Cicada no tiene ese problema (`BUNDLE()` de PyInstaller ya es autocontenido, sin dependencias pesadas de IA), la mayoría de ese documento no aplica — pero dos puntos sí son relevantes independientemente de Docker/launcher híbrido:

- **`--windowed` + `sys.stdout`/`sys.stderr` en `None` (punto P del documento):** sin consola adjunta en Windows, cualquier `print()` suelto lanza una excepción no capturada y aborta el proceso en silencio. Cicada ya detectaba esto (`cicada/core/main.py`, bloque `if getattr(sys, 'frozen', False)`), pero redirigía a `os.devnull` — funcional para evitar el crash, pero sin dejar rastro para diagnosticar. Corregido (2026-08-28): ahora redirige a `launcher.log` en el directorio de datos de la app (`get_app_data_dir()` de `cicada/core/app_paths.py` — mismo directorio que ya usa el resto de Cicada, `%APPDATA%\Cicada` en Windows), mismo patrón que Parrot documenta para su propio log.
- **Inno Setup (punto S):** Cicada ya lo usa (`cicada_installer.iss`) — de hecho es la referencia que Parrot copió, según el propio documento. Nada que traer de vuelta.
- **Detección de GPU (punto Q):** no aplica — Cicada no hace ningún procesamiento que dependa de GPU/CUDA.
