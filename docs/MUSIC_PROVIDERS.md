# Cicada — Proveedores de música más allá de Spotify

**Estado (2026-08-28): investigación y diseño completos, cero implementación.**
Diferido a una iteración posterior al release actual — no entra en 1.2.0.

Contexto: Spotify hoy es la única fuente externa de metadata de playlists en
Cicada. Se investigó generalizar ese patrón a otros servicios (YouTube Music,
Deezer, Apple Music, SoundCloud, Bandcamp, Tidal), documentado aquí antes de
tocar código, mismo criterio que el Paquete 8 de podcasts en
`docs/VENDORED.md`.

---

## 0. Cómo funciona Spotify hoy (línea base)

Dos flujos separados, ambos ya implementados, que cualquier proveedor nuevo
debería replicar:

- **Vista "Spotify" (pegar link):** resuelve metadata de un track/álbum/
  playlist/"liked songs" vía la API de Spotify, y **descarga el audio desde
  YouTube** vía yt-dlp (`ytsearch1:{artist} {title} Topic` en
  `download_manager.py`), no desde Spotify — Spotify no permite eso.
- **Vista "Playlists" (replicar):** solo hace fuzzy-matching de la lista de
  tracks contra archivos que **ya existen** en la biblioteca local
  (`/api/library/match`) y genera un `.m3u8`. Cero descarga.

Auth: OAuth2 Authorization Code (`SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET`
en `.env`, refresh_token en `.spotify_token.json`) — necesario porque hoy
Cicada solo lee playlists **privadas/propias** del usuario logueado.

Código aislado en `cicada/core/download_manager.py` (auth + llamadas API +
descarga yt-dlp, mezclados en una sola clase) y `cicada/core/routes/spotify.py`
— buena base para generalizar, pero conviene separar "resolver metadata de
Spotify" de "descargar audio de YouTube" al refactorizar, porque esa segunda
parte ya es compartida en la práctica (ver hallazgo Spotify más abajo).

**Nota sobre AcoustID/fingerprinting:** mecanismo no relacionado (identifica
archivos locales sin metadata). No forma parte de este diseño.

---

## 1. Hallazgo tardío: Spotify también puede evitar el login del usuario

Investigado después de la comparación inicial de los 6 servicios nuevos, pero
aplica retroactivamente a Spotify:

- Todas las llamadas a la Web API de Spotify requieren un access token — no
  existen llamadas anónimas. Pero hay dos flujos de auth distintos:
  - **Authorization Code** (el que Cicada ya implementa): requiere que el
    usuario haga login — único camino para playlists privadas/colaborativas
    y "Canciones que te gustan".
  - **Client Credentials**: la app se autentica con sus propias credenciales
    (`SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET`), sin ningún usuario
    involucrado. Con ese token **sí se puede leer cualquier playlist pública**
    de cualquier usuario (`GET /v1/playlists/{id}`, `.../items`), siempre que
    esté marcada pública en el perfil de su dueño.
- Conclusión: Spotify encaja en `supports_public_playlist_by_id = True`
  (ver §3) para el caso "pegar link de una playlist ajena", igual que
  Deezer/Tidal/YouTube Music — solo que, a diferencia de Deezer, sigue
  exigiendo que la app tenga Client ID/Secret propios (no hay endpoint
  100% anónimo).

**Riesgo colateral encontrado, ya relevante para el código actual — ver nota
en `download_manager.py`:** Spotify restringió el endpoint `audio-features`
(usado hoy para el BPM) a apps creadas **antes** del 27 de noviembre de 2024.
Una app creada después de esa fecha no puede acceder al BPM. El código ya lo
tolera con gracia (`try/except` que omite el campo), pero si un usuario
reconfigura credenciales nuevas y reporta "no me trae el BPM", este es el
motivo — no es un bug.

---

## 2. Tabla comparativa — los 6 servicios evaluados

| Servicio | Sin login (playlist pública) | Con login (mis playlists, estilo Spotify) | Riesgo de mantenimiento | Prioridad |
|---|---|---|---|---|
| **YouTube Music** | **Sí** — `ytmusicapi` sin credenciales (`YTMusic()`) lee playlists públicas por ID; usa yt-dlp como fallback si la respuesta no autenticada no parsea | Sí, vía cookies de sesión o el flujo OAuth "device code" propio de `ytmusicapi` — sin registro de app formal, pero más fricción de UX que el botón de Spotify | **Medio** — librería no oficial (ingeniería inversa de la web interna de YT Music), pero muy usada y activamente mantenida, con fallback a yt-dlp (dependencia que Cicada ya asume hoy) | **1** |
| **Deezer** | **Sí** — API oficial pública gratuita, `/playlist/{id}` sin ninguna clave ni token | Sí, OAuth2 estándar — pero **el registro self-service de apps nuevas está cerrado actualmente** ("no es posible registrar una app nueva vía el portal ahora mismo") | **Bajo** en el camino sin login (API oficial estable); el camino con login está bloqueado hoy por causas ajenas al código, no técnicas | **2** |
| **Tidal** | **Sí** — OAuth2 Client Credentials (sin usuario final) da acceso al catálogo público incluyendo playlists; registro de app self-service en developer.tidal.com | Sí, Authorization Code + PKCE con scopes granulares (`playlists.read`, etc.) — complejidad comparable al OAuth de Spotify ya implementado | **Bajo** — API oficial documentada, con SDKs propios | **3** |
| **Apple Music** — **DESCARTADO** | No — el catálogo (incluidas playlists públicas) exige Developer Token firmado igual, sin endpoint anónimo real | Sí, MusicKit/Apple Music API — requiere **Apple Developer Program de pago (99 USD/año, confirmado)**, JWT firmado con clave privada P8 como Developer Token, más User Token real para biblioteca del usuario | Bajo técnicamente (API oficial estable), pero costo de entrada no técnico | — |
| **SoundCloud** — **DESCARTADO** | Técnicamente posible pero frágil: la API real (`api-v2.soundcloud.com`) funciona con solo un `client_id`, pero **el registro oficial está cerrado desde 2017** — el client_id hay que extraerlo inspeccionando el tráfico de red de la web, puede rotar sin aviso | El registro self-service oficial reabrió en 2026, pero **exige una suscripción paga SoundCloud Artist-Pro** — no es gratis ni abierto | **Alto** en el camino sin login (client_id no oficial); costo económico en el camino con login | — |
| **Bandcamp** — **DESCARTADO** | No — Bandcamp cerró su API pública y no planea reabrirla; todo acceso es scraping de HTML (`bandcamp-scraper`, sin actualizaciones en ~4 años) | No aplica | **Muy alto** (scraping puro sobre un dominio que cerró su API deliberadamente) | — |

---

## 3. Descartes explícitos (no diferidos — no se van a implementar)

**Bandcamp — DESCARTADO (2026-08-28), no se va a implementar.**
Motivo doble y suficiente por sí solo cada uno: (1) no existe API viable ni
para el caso simple — Bandcamp cerró su API pública deliberadamente y la
única vía es scraping de HTML no mantenido; (2) más de fondo, Bandcamp **no
tiene el concepto de "playlist" de usuario** que este diseño requiere — son
álbumes/discografías de artista, un modelo de datos distinto que no hay que
forzar a encajar. No es un "todavía no" — no hay camino razonable en ningún
plazo con la forma de servicio que Bandcamp es hoy.

**Apple Music — DESCARTADO (2026-08-28), no se va a implementar por ahora.**
Motivo: la única vía de acceso, aun para el caso "sin login del usuario final"
(playlist pública ajena), exige que Cicada como proyecto tenga una cuenta
Apple Developer Program de pago (99 USD/año) para generar el Developer Token
firmado — no hay ningún endpoint anónimo real. Es una barrera de costo
recurrente para el proyecto, no una barrera técnica superable con más
trabajo de ingeniería. Reevaluable si el proyecto adopta una cuenta de
desarrollador paga por otro motivo en el futuro.

**SoundCloud — DESCARTADO (2026-08-28), no se va a implementar por ahora.**
Motivo: ambos caminos tienen un costo no técnico bloqueante. El camino sin
login depende de un `client_id` no oficial (registro público cerrado desde
2017, hay que extraerlo inspeccionando tráfico de red de la web, puede
rotar sin aviso — riesgo de mantenimiento alto y sin garantías). El camino
con login reabrió en 2026 pero exige que el usuario final de Cicada (no el
proyecto) tenga una suscripción paga SoundCloud Artist-Pro — no es un
requisito que el proyecto pueda satisfacer una sola vez, es un costo
recurrente por usuario. Reevaluable si SoundCloud reabre el registro público
gratuito.

---

## 4. Diseño de `MusicProvider` (interfaz genérica)

Alcance real: "listar mis playlists + sus tracks", replicando el patrón que
Spotify ya tiene — no "traer metadata de una URL suelta" nomás. La interfaz
inicial ya cubría esto; el único ajuste fue agregar un flag declarativo, no
una abstracción nueva.

```python
class TrackMeta(TypedDict, total=False):
    title: str
    artist: str
    album: str
    artwork_url: str
    track_number: int
    original_release_date: str
    external_ids: dict          # {"isrc": "..."} — para matching robusto
    bpm: float
    provider_track_id: str      # id nativo del proveedor (descarga exacta si aplica)

class PlaylistMeta(TypedDict, total=False):
    id: str
    name: str
    description: str
    track_count: int
    image_url: str
    is_liked: bool

class MusicProvider(ABC):
    name: str                              # "spotify", "youtube_music", "deezer", "tidal"
    supports_public_playlist_by_id: bool   # sin login del usuario final — ver criterio de prioridad
    requires_auth_for_own_library: bool    # para "mis playlists" estilo Spotify

    def parse_url(self, url: str) -> tuple[str, str]: ...       # (resource_type, resource_id)
    async def get_tracks(self, resource_type: str, resource_id: str) -> list[TrackMeta]: ...
    async def get_user_playlists(self) -> list[PlaylistMeta]: ...   # solo si hay auth
    def is_authenticated(self) -> bool: ...
```

`get_tracks()` cubre tanto "playlist pública por ID sin auth" como "playlist
privada ya autenticada" con la misma firma — no necesita bifurcarse por caso.
La descarga de audio (yt-dlp) queda **fuera** de la interfaz: es un paso
posterior y compartido entre proveedores, no algo que cada uno deba saber
hacer — formaliza lo que ya es cierto hoy para Spotify (que tampoco descarga
"de Spotify").

**Deliberadamente no incluido en la interfaz** (para no sobrediseñar):
- Un `search_track()` genérico — ningún proveedor evaluado lo necesita hoy;
  se agrega si aparece un caso real.
- Cualquier modelo de datos para Bandcamp — descartado (§3), no hay forma de
  datos que adivinar.
- Nada específico de Apple Music/SoundCloud que compense sus barreras de
  costo — quedan fuera de la interfaz mientras estén descartados.

`SpotifyProvider` sería un wrapper delgado sobre el `DownloadManager` actual,
separando su lógica de auth+API (por proveedor) de su lógica de descarga
yt-dlp (compartida, movida a un módulo aparte). `YouTubeMusicProvider` sería
nuevo, usando `ytmusicapi` para `get_tracks`/`get_user_playlists` y
reusando ese mismo módulo compartido de descarga — con el video ID exacto
en vez de la heurística de búsqueda por texto que usa Spotify hoy.

---

## 5. Orden de prioridad confirmado

**YouTube Music → Deezer → Tidal → (Apple Music, SoundCloud, Bandcamp: descartados, no en el orden)**

YouTube Music primero no es "el más sólido en aislamiento" — Deezer y Tidal
tienen API oficial documentada y YouTube Music no. Es el más barato porque
Cicada **ya depende de yt-dlp** para el audio: agregar `ytmusicapi` no
introduce una categoría de riesgo nueva, es una segunda instancia de un
riesgo ya aceptado por el proyecto. Deezer sería "más fácil" en aislamiento
si no fuera porque el registro de apps nuevas está cerrado ahora mismo
(bloquea de facto el camino "con login", aunque el camino sin login público
funciona igual).

---

## 6. Tamaño estimado (cuando se retome)

Estimación dada en la investigación original, sin cambios: **2-3 días de
trabajo** para YouTube Music solo (interfaz + refactor de Spotify + provider
nuevo + UI generalizada + tests) — más que una tarde, menos que una fase
completa tipo iPod/Podcasts. Deezer y Tidal, una vez la interfaz exista,
deberían ser más baratos cada uno (API oficial, sin heurística de búsqueda).
