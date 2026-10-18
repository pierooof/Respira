# Respira

**Calidad del aire y polen por barrio de Valencia.** Mapa con los 19 distritos coloreados según el índice europeo de calidad del aire (EAQI), ficha detallada con polen, previsión y recomendaciones, histórico diario con gráficos y avisos por Telegram.

🌐 Demo: <https://respira.pierooof.dev>

> **Capturas** — _(deja aquí tus imágenes en `docs/` y enlázalas)_
>
> | Mapa | Ficha de barrio | Móvil |
> |---|---|---|
> | `docs/mapa.png` _(pendiente)_ | `docs/ficha.png` _(pendiente)_ | `docs/movil.png` _(pendiente)_ |

## Stack

Python 3.12 · Flask · SQLAlchemy (PyMySQL) · MySQL 8 (utf8mb4) · Flask-Migrate · Flask-Login · Flask-WTF (CSRF) · httpx · APScheduler · python-telegram-bot · Leaflet · Chart.js · gunicorn.

## Funcionalidades

- Seed con los **19 distritos** de Valencia y sus coordenadas.
- **Mapa** (Leaflet) con cada distrito coloreado por el EAQI actual.
- **Ficha de barrio**: valores actuales, contaminante dominante (PM10, PM2.5, NO₂, O₃), polen por tipo (gramíneas, olivo, abedul, aliso, artemisa, ambrosía) con etiquetas _bajo / moderado / alto / muy alto_ y previsión de los próximos días.
- **Recomendaciones** sencillas según el nivel (p. ej. evitar el deporte al aire libre).
- **Histórico diario** guardado por un worker y gráficos de evolución por barrio. En el primer arranque el worker rellena los últimos 30 días con datos reales de Open-Meteo.
- **Usuarios**: registro/login, barrios favoritos y avisos («avísame si el polen de gramíneas será alto mañana en mi barrio») por **Telegram**; la cuenta se vincula con un código de un solo uso desde el bot.
- **Caché** de la API en base de datos y respeto de sus límites: una única petición por hora para los 19 distritos (el plan gratuito permite 600/min y 5000/h) y reintento espaciado si falla.
- **Worker** (planificador) en un proceso separado de la web.

> Datos: [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api) (CAMS/Copernicus, licencia CC BY 4.0, uso no comercial). Resolución ≈ 11 km: los valores entre barrios cercanos son muy parecidos. El polen solo se publica en temporada; fuera de ella la fuente devuelve valores casi nulos. Los umbrales de polen son orientativos (`app/services/levels.py`).

## Estructura

```
app/            Flask: config, modelos, blueprints, servicios (Open-Meteo, niveles, consejos, avisos), plantillas y estáticos
worker/         Planificador APScheduler + bot de Telegram (python -m worker.main)
migrations/     Migraciones Alembic (Flask-Migrate)
tests/          pytest (SQLite en memoria, sin red)
```

## Ejecución en local

Requisitos: Python 3.12+ y MySQL 8 (por ejemplo con `docker compose up -d`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # y edítalo; export $(grep -v '^#' .env | xargs)  o usa tu gestor de .env
export FLASK_APP=wsgi.py
flask db upgrade                # crea las tablas
flask seed                      # distritos + usuario demo
flask run --port 8000           # web  →  http://localhost:8000
python -m worker.main           # (otra terminal) refresca datos, histórico y bot
pytest                          # tests
```

La app carga solo variables de entorno (no lee `.env` por sí misma). Con `APP_ENV=development` funciona por http; con `APP_ENV=production` fuerza https, cookies `Secure` y HSTS.

### Credenciales demo

| Correo | Contraseña |
|---|---|
| `demo@respira.app` | `demo1234` |

El usuario demo tiene dos favoritos y un aviso de ejemplo. **En un despliegue público cambia o elimina esta cuenta si no quieres que sea accesible.**

## Variables de entorno

| Variable | Descripción |
|---|---|
| `APP_ENV` | `development` o `production` |
| `APP_URL` | URL pública, p. ej. `https://respira.pierooof.dev` (enlaces de los avisos y del bot) |
| `SECRET_KEY` | Clave de sesión/CSRF (obligatoria en producción) |
| `PORT` | Puerto (Railway lo inyecta); la app escucha en `0.0.0.0` |
| `TRUSTED_PROXIES` | Nº de proxies de confianza (por defecto `1`). Si existe `CF-Connecting-IP`, se usa como IP real |
| `MYSQL_URL` | `mysql://usuario:clave@host:puerto/bd`, o bien `MYSQLHOST`, `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, `MYSQLDATABASE` |
| `TELEGRAM_TOKEN` | Token del bot (de @BotFather). **Solo en el worker**; sin él, bot y avisos quedan desactivados |
| `TELEGRAM_BOT_USERNAME` | Usuario del bot sin `@`. **En la web** (activa «Generar código» y el enlace al bot); no es secreto |
| `CACHE_TTL_SECONDS` / `REFRESH_MINUTES` / `ALERT_HOUR` | Caché (3600), refresco del worker (60) y hora de los avisos (19) |

## Despliegue en Railway (paso a paso)

Son **tres servicios** en un mismo proyecto: MySQL, `web` y `worker` (ambos desde este repositorio).

1. **Sube el repo a GitHub.**
2. En [railway.com](https://railway.com): **New Project → Deploy from GitHub repo** y elige el repositorio. Railway lee el `Procfile` y crea solo dos servicios, **`web`** y **`worker`**.
3. **Añade MySQL**: *+ New → Database → Add MySQL*.
4. **Variables del servicio `web`** (pestaña *Variables*). Referencia las de MySQL con la sintaxis `${{ ... }}` (cambia `MySQL` por el nombre real del servicio):
   - `MYSQL_URL` = `${{MySQL.MYSQL_URL}}`
   - `APP_ENV` = `production`
   - `APP_URL` = `https://respira.pierooof.dev`
   - `SECRET_KEY` = una cadena aleatoria larga (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
   - `TRUSTED_PROXIES` = `2` (Cloudflare + Railway; ver nota de proxies más abajo)
   - `TELEGRAM_TOKEN` y `TELEGRAM_BOT_USERNAME`
5. El servicio `web` usa `railway.json`: al arrancar ejecuta `flask db upgrade && flask seed` y luego gunicorn; el healthcheck es `/health`.
6. **Servicio `worker`** (ya creado por Railway): en *Settings → Config-as-code* pon la ruta **`/railway.worker.json`** (arranca `python -m worker.main`, sin healthcheck ni dominio; si no, usaría el `railway.json` del web). Dale las **mismas variables** que a `web` (*Raw Editor* → pegar). Usa **una sola réplica**.
   > Railway marca Config-as-code como obsoleto (los ficheros siguen funcionando hasta el 2026-12-01). Después, define en cada servicio, en *Settings → Deploy*, el _Start Command_ (`Procfile`) y el _Healthcheck Path_ `/health` en `web`.
7. **Genera un dominio** en `web` (*Settings → Networking → Generate Domain*) para comprobar que funciona, y después añade el dominio propio (siguiente sección).
8. Comprueba: `https://<dominio>/health` devuelve `{"status":"ok"}` y en los logs del worker aparece `refresh: caché actualizada`.

Las migraciones se aplican en el arranque del servicio `web`; el worker espera a que existan los distritos. Comando manual si lo necesitas: `flask --app wsgi db upgrade`.

### Bot de Telegram

1. En Telegram habla con **@BotFather** → `/newbot` y copia el token a `TELEGRAM_TOKEN`; el usuario del bot a `TELEGRAM_BOT_USERNAME`.
2. El worker usa _long polling_: no hace falta webhook ni abrir puertos. **Ejecuta una sola instancia del worker.**
3. Flujo del usuario: web → *Mi cuenta* → *Generar código* → enviar `/vincular CÓDIGO` al bot. Comandos: `/start`, `/vincular`, `/estado`, `/desvincular`. El worker envía a las 19:00 (hora de Madrid) los avisos cuya condición se cumple **para el día siguiente**, una vez por aviso y día. Para una prueba puntual de entrega (consola del worker en Railway): `flask --app wsgi simulate-alert` envía un aviso de polen simulado «para mañana» al primer usuario vinculado, sin guardar nada.

## Conectar un subdominio de Cloudflare a Railway

Para servir la app en `respira.pierooof.dev` (dominio gestionado en Cloudflare):

1. En Railway: servicio `web` → *Settings → Networking → Custom Domain* → escribe `respira.pierooof.dev`. Railway te muestra un valor **CNAME** (algo como `xxxxx.up.railway.app`) y, a veces, un registro **TXT** de verificación.
2. En Cloudflare: *pierooof.dev → DNS → Records → Add record*:
   - Tipo `CNAME`, nombre `respira`, destino = el valor que dio Railway.
   - Si Railway pide el `TXT` (p. ej. `_railway-verify.respira`), añádelo tal cual.
   - Railway también ofrece "One-click DNS Setup" con Cloudflare (pide permisos OAuth); aquí se hizo a mano.
   - Estado del proxy: **Proxied (nube naranja)** funciona; si la verificación tarda, ponlo en _DNS only_ (gris) hasta que Railway marque el dominio como verificado y vuelve a activarlo.
3. En Cloudflare → *SSL/TLS → Overview*: modo **Full** (o *Full (strict)*). No uses *Flexible* (provocaría bucles de redirección).
4. Espera a que Railway emita el certificado (unos minutos) y abre <https://respira.pierooof.dev>.
5. Variables: `APP_URL=https://respira.pierooof.dev` y `APP_ENV=production` (ya puestas en el paso 4 del despliegue).

**Proxies.** La app va detrás de Cloudflare y del proxy de Railway. `ProxyFix` respeta `X-Forwarded-Proto` (del último proxy), `X-Forwarded-For` y `X-Forwarded-Host`; `TRUSTED_PROXIES` indica cuántos saltos de `X-Forwarded-For` se consideran de confianza (por defecto 1; con Cloudflare + Railway prueba `2`). Si llega `CF-Connecting-IP`, esa es la IP del cliente. Las URLs, redirecciones y cookies usan https en producción.

## Seguridad

Contraseñas con hash (Werkzeug/scrypt), validación de entradas, consultas parametrizadas (SQLAlchemy), protección CSRF en todos los formularios, cookies `HttpOnly` + `SameSite=Lax` (+ `Secure` en producción), redirección post-login solo a rutas internas, y cabeceras `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` y HSTS (producción).

## Mejoras futuras

- Límite de intentos de login (rate limiting con Redis) y verificación de correo / recuperación de contraseña.
- Polígonos reales de distritos/barrios en el mapa (GeoJSON del Ajuntament) y los ~88 barrios, con interpolación entre celdas del modelo.
- Alertas por hora concreta, por contaminantes y con histórico de avisos enviados; avisos por correo o notificaciones push.
- Umbrales de polen calibrados con la red aerobiológica local y datos de estaciones oficiales para contrastar el modelo.
- Webhook de Telegram en lugar de polling si se escala el worker.
