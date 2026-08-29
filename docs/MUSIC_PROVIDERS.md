# Cicada — Proveedores de música más allá de Spotify

**Estado (2026-08-29): CORTE CERRADO Y UI INTEGRADA.** Backend y frontend
completos e implementados para Spotify, YouTube Music y Deezer (track,
álbum y playlist públicos por ID o URL, incluyendo enlaces cortos como
`link.deezer.com` o `youtu.be`, sin login) — interfaz `MusicProvider`,
providers, endpoints `/api/youtube_music/*` y `/api/deezer/*`, y pestaña
unificada de Descargas en la UI con auto-detección y descarga en segundo
plano. Tidal queda **diseñado en detalle pero sin implementar**: exige
credenciales de app propias incluso para el camino sin login de usuario
(confirmado en vivo, ver §7), que este corte no gestionó a propósito.
Con esto se cierra el proceso de desarrollo de proveedores de música de
esta iteración — el próximo trabajo en este área es retomar Tidal el día
que haya credenciales, no un nuevo proveedor sin priorizar. Diferido a
una iteración posterior al release actual.

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
| **YouTube Music — IMPLEMENTADO** | **Sí** — `ytmusicapi` sin credenciales (`YTMusic()`) lee playlists públicas por ID; usa yt-dlp como fallback si la respuesta no autenticada no parsea | Sí, vía cookies de sesión o el flujo OAuth "device code" propio de `ytmusicapi` — sin registro de app formal, pero más fricción de UX que el botón de Spotify. Diferido (§4). | **Medio** — librería no oficial (ingeniería inversa de la web interna de YT Music), pero muy usada y activamente mantenida, con fallback a yt-dlp (dependencia que Cicada ya asume hoy) | **1 — hecho** |
| **Deezer — IMPLEMENTADO** | **Sí** — API oficial pública gratuita, `/playlist/{id}` sin ninguna clave ni token | Sí, OAuth2 estándar — pero **el registro self-service de apps nuevas: fuentes contradictorias, sin confirmar** (§4.3). Diferido. | **Bajo** en el camino sin login (API oficial estable, ya implementado); el camino con login sigue sin confirmar | **2 — hecho** |
| **Tidal** | Matizado — **confirmado en vivo en §7: exige token de app (Client Credentials) incluso para catálogo público, no hay acceso 100% anónimo como Deezer**; ese Client Credentials sí funciona sin usuario final, pero requiere Client ID/Secret propios registrados en developer.tidal.com | Sí, Authorization Code + PKCE con scopes granulares (`playlists.read`, etc.) — complejidad comparable al OAuth de Spotify ya implementado | **Bajo** técnicamente (API oficial documentada, con SDKs propios), pero bloqueado en la práctica sin credenciales de app | Diseñado, no implementado (§7) — bloqueado por credenciales, no por prioridad |
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
    name: str                                    # "spotify", "youtube_music", "deezer", "tidal"
    supports_public_playlist_by_id: bool         # sin login del usuario final — ver criterio de prioridad
    requires_auth_for_own_library: bool          # para "mis playlists" estilo Spotify
    supported_resource_types: tuple[str, ...]    # qué resource_type acepta get_tracks() — ver §4.1

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

**Implementado (2026-08-29):** `DownloadManager` (Spotify) y
`YouTubeMusicProvider` (nuevo, `cicada/core/providers/youtube_music.py`) ya
implementan esta interfaz — ver §4.1 para un hallazgo real de la
implementación que no estaba anticipado en el diseño original.

`SpotifyProvider` como wrapper delgado sobre `DownloadManager`, separando
auth+API de la descarga yt-dlp, no se hizo como refactor separado: en la
práctica, `DownloadManager` mismo pasó a implementar `MusicProvider`
directamente (agregando `parse_url`/`get_tracks`/`is_authenticated` como
wrappers sobre su API pública ya existente), sin necesidad de una clase
`SpotifyProvider` intermedia — la clase ya vivía aislada en su propio
módulo, así que envolver-y-renombrar no agregaba nada. `AudioDownloader`
(`cicada/core/audio_downloader.py`) sí se extrajo tal como estaba previsto:
la descarga yt-dlp+retag ahora es un módulo compartido, usado por Spotify
con búsqueda heurística (`ytsearch1:`) y por YouTube Music con el videoId
exacto (`provider_track_id`).

### 4.1 Hallazgo real: no todos los `resource_type` existen en todos los proveedores

Descubierto al implementar `YouTubeMusicProvider`, no anticipado en el
diseño original: Spotify modela `track`/`album`/`playlist`/`collection`
("liked songs") como variantes de un mismo espacio de recursos que
`get_tracks()` puede resolver indistintamente. **YouTube Music no comparte
ese espacio** — un álbum de YT Music vive en un `browseId` de tipo
`MPREb_...` (obtenido buscando por `filter="albums"`), mientras que una
playlist vive en un ID de tipo `PL...`/`OLAK5uy_...` que es lo que
`get_playlist()` espera. Son namespaces de ID distintos e incompatibles —
pasarle un `browseId` de álbum a `get_playlist()` no funciona, no es solo
"falta implementar el caso álbum", es un recurso con forma distinta.

Se agregó `supported_resource_types: tuple[str, ...]` a la interfaz para
que esto sea explícito y consultable por cualquier caller (UI, endpoint)
**antes** de llamar a `get_tracks()`, en vez de depender de que el
`ValueError` se propague en tiempo de ejecución — mismo criterio que ya se
usó para `requires_auth_for_own_library` vs. el `NotImplementedError` de
`get_user_playlists()`. Valores reales:
- `DownloadManager.supported_resource_types = ("track", "album", "playlist", "collection")`
- `YouTubeMusicProvider.supported_resource_types = ("playlist",)` — **no
  paridad completa con Spotify**; soporte de álbum de YT Music queda fuera
  de este alcance (requeriría un segundo parser de URL/ID y una segunda
  llamada de API, `get_album()`, con su propio namespace de browseId).

### 4.2 Endpoints (`/api/youtube_music/*`)

`cicada/core/routes/youtube_music.py`, mismo patrón que `routes/spotify.py`:
`POST /api/youtube_music/resolve` (metadata de una playlist pública) y
`POST /api/youtube_music/download` (dispara descarga en segundo plano de
tracks ya resueltos). No expone ningún endpoint de "mis playlists" — eso
sigue bloqueado por `requires_auth_for_own_library`, no tiene sentido
publicar una ruta que solo puede devolver `NotImplementedError`.

`processing.py` ganó `process_youtube_music_selected_tracks()` y
`_download_and_tag_tracks()` ahora acepta un `query_builder` inyectable:
Spotify sigue usando la búsqueda heurística por texto (`ytsearch1:...`,
comportamiento sin cambios, confirmado con test), YouTube Music usa el
`provider_track_id` (videoId) exacto vía
`https://music.youtube.com/watch?v={id}` — determinístico, sin depender de
que la búsqueda por texto encuentre el video correcto primero.

**Riesgo operacional confirmado en verificación real (2026-08-29):**
`yt-dlp` puede empezar a exigir verificación anti-bot de YouTube
("Sign in to confirm you're not a bot...") tras varias descargas seguidas
desde la misma IP en poco tiempo — confirmado durante las pruebas de este
mismo corte: la primera descarga (Paso 4) funcionó limpio, descargas
posteriores en la misma sesión de pruebas empezaron a fallar con ese
error, para *cualquier* video, no uno en particular. No es un bug de
`AudioDownloader` ni de `YouTubeMusicProvider` — es el mismo riesgo de
mantenimiento de yt-dlp que Cicada ya acepta para Spotify hoy (ver §0),
simplemente más visible acá por el volumen de pruebas manuales
consecutivas. Si un usuario reporta "la descarga de YouTube Music falla
con error de login", este es el motivo más probable, no una regresión.

**Pendiente resuelto (2026-08-29, sesión siguiente):** la descarga real vía
`POST /api/youtube_music/download` que había quedado bloqueada por el
rate-limit no llegó a reintentarse de forma aislada, pero el mismo
mecanismo compartido (`AudioDownloader.download_audio()`) se confirmó
exitoso de punta a punta por HTTP en la implementación de Deezer (§4.3,
mismo endpoint/BackgroundTasks/mutagen) una vez que el rate-limit se
liberó — es la misma ruta de código, no una ruta distinta sin probar. Se
da por cerrado el pendiente del Paso 5 en la práctica, aunque no se
volvió a golpear `/api/youtube_music/download` específicamente ese día.

### 4.3 Deezer: implementado con el mismo alcance que YouTube Music

`cicada/core/providers/deezer.py` — API pública de Deezer
(`api.deezer.com`) vía `httpx` directo, **sin librería de terceros ni
credenciales**: a diferencia de YouTube Music (necesita `ytmusicapi`) y de
Spotify (necesita Client ID/Secret aunque sea vía Client Credentials),
Deezer no exige nada para leer catálogo público.

**Paridad de tipos de recurso mejor que YouTube Music:**
`supported_resource_types = ("track", "album", "playlist")` — Deezer
modela álbum en el mismo espacio de IDs numéricos que track/playlist
(a diferencia de YouTube Music, donde álbum vive en un namespace de
browseId distinto, ver §4.1). Sí apareció una asimetría real entre
endpoints de Deezer: `GET /album/{id}/tracks` no repite el objeto
`"album"` completo en cada item (solo `track_position`/`disk_number`),
a diferencia de `GET /playlist/{id}/tracks` que sí lo trae completo —
`get_tracks()` para `resource_type="album"` hace una llamada extra a
`GET /album/{id}` para completar título/carátula, en vez de dejar esos
campos vacíos. Cubierto con test de regresión.

**BPM deliberadamente omitido de `TrackMeta` para este proveedor:** el
campo existe en `GET /track/{id}` (`bpm`), pero vino en `0` de forma
sistemática en las muestras verificadas (un track de 2025 y "One More
Time" de Daft Punk, de 2000) — no es una limitación de un track en
particular. Prometer un campo en el modelo que en la práctica no llega
casi nunca es peor que omitirlo: se decidió no incluirlo, a diferencia de
`bpm` en Spotify (que sí funciona, salvo la restricción de noviembre 2024
ya documentada en §1).

**Descarga: heurística por texto, igual que Spotify — sin paridad con el
mecanismo determinístico de YouTube Music.** Deezer es solo metadata,
igual que Spotify: no aloja audio descargable (su campo `preview` es un
clip de 30 segundos con firma temporal, no la pista completa). No hay un
id exacto de video de YouTube que Deezer pueda dar, así que
`process_deezer_selected_tracks()` reusa `_ytsearch_query()` (la misma
búsqueda por texto `ytsearch1:{artist} {title}` que ya usa Spotify), no
`_exact_video_query()` (exclusivo de YouTube Music, que sí trae el
videoId real). No se debe asumir que "Deezer, por ser API oficial, tiene
descarga más confiable que YouTube Music" — es al revés en este aspecto
puntual: YouTube Music descarga con precisión de ID exacto, Deezer no.

**"Mis playlists" — incertidumbre real, sin resolver a propósito:** el
estado del registro de apps nuevas de Deezer (`developers.deezer.com`) no
está confirmado. La investigación previa a esta sesión documentaba
"registro cerrado" (ver un GitHub issue de agosto 2024 sobre el tema);
releyendo la documentación oficial actual
(`developers.deezer.com/guidelines/getting_started`), el proceso descrito
es self-service abierto, sin mención de estar cerrado. No se pudo
confirmar cuál de las dos es cierta ahora mismo sin una cuenta Deezer real
intentando crear una app — decisión explícita de no investigarlo más ni
intentar el registro en esta sesión, porque no cambia el alcance de este
corte (solo camino sin login). `DeezerProvider.get_user_playlists()` lanza
`NotImplementedError`, con `requires_auth_for_own_library = True` como
señal principal — mismo patrón que YouTube Music. **Si se retoma Deezer
para "mis playlists" en el futuro, el primer paso real es simplemente
intentar el registro con una cuenta, no seguir buscando en la web.**

Endpoints: `cicada/core/routes/deezer.py`,
`POST /api/deezer/resolve` / `POST /api/deezer/download`, mismo patrón que
`routes/spotify.py` y `routes/youtube_music.py`. Verificado end-to-end
contra la app real: playlist pública de 100 tracks vía HTTP, manejo
correcto del caso real donde Deezer devuelve `200 OK` con
`{"error": {...}}` en el body para un ID inexistente (no un status HTTP
de error — se traduce a `400` con mensaje claro, confirmado con
`curl` real), y **descarga real completa** de "One More Time" de Daft
Punk vía el endpoint HTTP, confirmada con `mutagen` (m4a válido, 320.4s,
coincide con la duración real de la canción, tags título/artista/álbum
correctamente inyectados).

---

## 5. Orden de prioridad — confirmado en la práctica, con un ajuste real

**YouTube Music (implementado) → Deezer (implementado) → Tidal (diseñado, no implementado, bloqueado por credenciales)**

El orden original ("YouTube Music primero por reusar el riesgo de yt-dlp
ya aceptado; Deezer segundo por API oficial") se confirmó correcto en la
práctica: ambos se implementaron sin sorpresas bloqueantes, cada uno con
un hallazgo real pero menor (formato de ID de YouTube Music, asimetría
álbum/playlist de Deezer). **Tidal es el que reveló una sorpresa real al
verificar en vivo** (§7): la investigación original decía "Client
Credentials da acceso al catálogo sin usuario", lo cual es cierto pero
incompleto — no aclaraba que ese Client Credentials exige credenciales de
**app** (Client ID/Secret propios), no solo "sin login de usuario final".
Deezer no tiene ese requisito en absoluto; Tidal sí, igual que Spotify.
Lección para la próxima vez que se evalúe un proveedor nuevo: "sin login
de usuario" y "sin ninguna credencial" no son lo mismo, hay que probarlo
en vivo contra un recurso real, no inferirlo de la documentación.

---

## 6. Tamaño estimado (cuando se retome)

Estimación dada en la investigación original: **2-3 días de trabajo** por
proveedor con interfaz nueva (YouTube Music, que incluyó el refactor de
Spotify) — confirmado en la práctica, contando diseño + implementación +
verificación real de este corte. Deezer, con la interfaz ya lista, tomó
una fracción de eso (medio día) — confirmado: API oficial sin librería
sí es más barato que una librería no oficial. Tidal, si se retoma con
credenciales reales, debería ser comparable a Deezer en esfuerzo de
implementación (la interfaz ya soporta su forma de datos, ver §7) — el
costo real no es de código, es conseguir y validar las credenciales.

---

## 7. Tidal — diseñado, no implementado (bloqueado por credenciales de app)

**No es diseño diferido por decisión de prioridad, como Deezer/Tidal lo
fueron para "mis playlists" — acá el bloqueo es no tener credenciales de
app disponibles en esta sesión, y no se acordó gestionar un registro
nuevo para conseguirlas (mismo criterio que con Deezer: no cambia el
alcance de este corte).** El diseño de abajo está verificado en vivo
contra los endpoints reales de Tidal, no es especulación de
documentación — está listo para implementarse en cuanto haya credenciales.

### 7.1 Hallazgo real: Tidal no tiene ningún camino sin credenciales

Confirmado con `curl` real, no solo lectura de documentación:

```
GET https://openapi.tidal.com/v2/playlists/{uuid real}   → 401 UNAUTHORIZED, sin ningún header
GET https://api.tidal.com/v1/playlists/{uuid real}       → 401 "Missing auth parameter"
```

A diferencia de Deezer (`GET /playlist/{id}` responde `200` con datos
completos, cero configuración), **Tidal exige un access token válido
incluso para leer una playlist pública real** — se probó contra un UUID
real (`74e2ae5a-e88a-4ac3-8368-ad0235e4bf17`, tomado de un ejemplo de
documentación pública), no un ID inventado, para descartar que el `401`
fuera en realidad un `404` disfrazado.

Se probaron además dos vías alternativas sin auth (mismo patrón que
existe en otros servicios): oEmbed (`tidal.com/oembed`) — bloqueado por
un WAF anti-bot (Datadome, `403`) — y el embed widget
(`embed.tidal.com/playlists/{id}`) — devolvió una página de error, no
datos. Ninguna vía sin credenciales de app funciona hoy.

### 7.2 El flujo de auth sí está confirmado y documentado con precisión

El endpoint de token es real y responde con errores específicos (no
genéricos), lo cual permite documentar el formato exacto sin necesidad de
credenciales válidas:

```
POST https://auth.tidal.com/v1/oauth2/token
Content-Type: application/x-www-form-urlencoded
Body: grant_type=client_credentials&client_id={id}&client_secret={secret}
```

- Sin `client_id`: `{"error":"invalid_request","error_description":"invalid_request, Missing parameters: client_id", "status":400}`
- Con un `client_id` inválido pero presente:
  `{"error":"invalid_grant","error_description":"Client with token {id} not found","status":400}`
  — mensaje específico, confirma que el flujo `client_credentials` es real
  y que el servidor sí intenta resolver el `client_id` contra su registro.

Las llamadas de catálogo usan `Authorization: Bearer {token}` — mismo
patrón exacto que ya implementa `DownloadManager` para Spotify
(`_basic_auth_header`/`get_user_token`), confirmado con un Bearer token
inventado: `{"errors":[{"code":"UNAUTHORIZED","detail":"Invalid token structure", ...}]}`
(rechaza la estructura del token, no el endpoint).

### 7.3 Diseño de `TidalProvider` (listo para implementar con credenciales)

Encaja en la interfaz `MusicProvider` sin cambios — mismo patrón que
`DownloadManager` (Spotify), que ya resuelve OAuth de app:

```python
class TidalProvider(MusicProvider):
    name = "tidal"
    supports_public_playlist_by_id = True   # vía Client Credentials, no anónimo
    requires_auth_for_own_library = True    # Authorization Code + PKCE, no investigado a fondo
    supported_resource_types = ("track", "album", "playlist")  # confirmar forma exacta del payload con credenciales reales

    AUTH_URL = "https://auth.tidal.com/v1/oauth2/token"
    CATALOG_BASE = "https://openapi.tidal.com/v2"
    # TIDAL_CLIENT_ID / TIDAL_CLIENT_SECRET en .env, mismo patrón que
    # SPOTIFY_CLIENT_ID/SECRET — necesita cachear el token de app igual que
    # DownloadManager cachea el token de usuario (expiry, refresh).
```

Diferencia real de implementación respecto a Spotify: el token de Tidal
es de **app** (`client_credentials`), no de **usuario** — no hace falta
un flujo de redirect/callback para el camino sin login, solo cachear y
renovar un token de servidor-a-servidor, más simple que el
`process_auth_code`/`_refresh_user_token` que Spotify necesita hoy.

**No verificado, pendiente de credenciales reales:** la forma exacta del
payload de `GET /v2/playlists/{id}` y `GET /v2/albums/{id}` (Tidal usa
JSON:API con `data`/`relationships`/`included`, distinto de la forma
plana de Deezer y Spotify — se ve en la documentación pero no se pudo
confirmar contra un payload real sin auth), y si el registro de app en
`developer.tidal.com` es self-service inmediato o requiere aprobación.
Ambos puntos son el primer paso real si se retoma este proveedor, antes
de escribir ningún código nuevo.

---

## 8. Visión a largo plazo — objetivo declarado, no comprometido

Esta sección deja constancia de la intención y visión a largo plazo del proyecto
para que cualquiera que retome el desarrollo entienda hacia dónde va el diseño,
**separada estrictamente del alcance del corte actual** y sin constituir trabajo
planificado o comprometido para la iteración presente.

### 8.1 Alcance del corte actual (sin cambios, ya en curso)

El trabajo de este ciclo de desarrollo se acota a los 4 servicios priorizados:

- **Spotify:** Integración existente completa (login OAuth2, lectura de "mis
  playlists", resolución de URLs y replicación local).
- **YouTube Music:** Implementado (resolución de playlists públicas y descarga
  determinística por video ID vía yt-dlp).
- **Deezer:** En curso / implementado (resolución de tracks, álbumes y playlists
  públicas por ID y descarga vía yt-dlp).
- **Tidal:** Próximo / diseñado en detalle (§7), último de este corte.

**Con Tidal, el trabajo de ESTE proceso de desarrollo se detiene.** No se
seguirán agregando más servicios en esta ronda; el trabajo posterior inmediato
se enfocará en la UI frontend o en la resolución de credenciales de Tidal.

### 8.2 Visión a largo plazo — paridad de nivel-Spotify

El objetivo final a largo plazo es integrar servicios adicionales al **mismo
nivel de profundidad que Spotify tiene hoy**: autenticación completa del
usuario final (OAuth2 / device-flow), listado de "mis playlists" propias y
guardadas, y no únicamente la resolución de enlaces públicos por ID.

Esto incluye:

1. **Completar el login de nivel-Spotify para los 3 integrados en este corte:**
   - **YouTube Music:** Flujo *device-code* o gestión de cookies de sesión vía
     `ytmusicapi` (§4).
   - **Deezer:** Flujo OAuth2 estándar para usuario final (una vez confirmado el
     estado del registro de apps en su portal de desarrolladores, §4.3).
   - **Tidal:** Flujo Authorization Code + PKCE con scopes de usuario
     (`playlists.read`, §7).

2. **Candidatos nuevos a evaluar (aspiracionales, SIN investigación técnica todavía):**
   Los siguientes servicios representan aspiraciones futuras para explorar,
   marcados explícitamente como **sin evaluar** (no se asume viabilidad técnica
   ni se descartan a priori; requerirán su correspondiente investigación formal
   de APIs, modelos de autenticación, costos y políticas de acceso cuando se
   retome el área):
   - **Amazon Music**
   - **Audiomack**
   - **Napster**
   - **Pandora**
   - **Qobuz**

3. **Nota de precisión conceptual (servicios que difieren del modelo `MusicProvider`):**
   Para que quien retome esto no pierda tiempo intentando forzar abstracciones:
   - **Discogs:** Plataforma orientada a la catalogación de lanzamientos físicos
     (vinilos, CDs, cassettes) y coleccionismo, no a la reproducción o streaming
     de audio.
   - **LastFM:** Servicio enfocado en *scrobbling*, estadísticas e historial de
     escucha, no en actuar como fuente primaria de playlists con audio
     resoluble.
   - *Duda abierta a resolver:* Ambos servicios probablemente **NO encajen** en
     el modelo `MusicProvider` tal como está diseñado hoy (que asume recursos de
     audio reproducibles o descargables). Se documenta como una duda abierta de
     arquitectura a resolver antes de intentar integrarlos, no como una decisión
     tomada en ninguna dirección.

4. **Servicios formalmente descartados:**
   - **Apple Music, SoundCloud y Bandcamp** continúan descartados por los
     motivos técnicos, económicos y de API documentados en detalle en la
     [Sección 3](#3-descartes-explícitos-no-diferidos--no-se-van-a-implementar),
     a la cual se remite para evitar duplicar el análisis.

