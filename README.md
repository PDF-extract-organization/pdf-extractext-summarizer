# pdf-extractext-summarizer

Microservicio que genera resúmenes de texto con IA (OpenRouter). Forma parte de
[pdf-extractext](https://github.com/PDF-extract-organization/pdf-extractext), dividido
en microservicios (épica: pdf-extractext#64).

Recibe texto y devuelve un resumen. No conoce PDFs ni base de datos. Es el único
servicio que tiene la API key de OpenRouter del servidor; los usuarios pueden mandar la
suya en cada petición (página Ajustes, épica pdf-extractext#72).

## Contrato HTTP

Escucha en el puerto `8000`. En el stack completo, Traefik le quita el prefijo
`/summarizer`, así que desde fuera las rutas son `http://pdf.localhost/summarizer/...`.

| Método y ruta | Entrada | Respuesta |
|---|---|---|
| `POST /summarize` | JSON `{"text", "model"?, "api_key"?, "max_tokens"?}` | `200` `{"summary", "model", "tokens_used", "truncated"}` |
| `GET /parameters` | — | `200` `{"model", "max_tokens", "max_tokens_limit", "temperature", "max_prompt_chars", "config_status"}` |
| `GET /health` | — | `200` `{"status": "healthy" \| "degraded", "service": "summarizer"}` |

- `model`, `api_key` y `max_tokens` son los **ajustes del usuario**: valen solo para esa
  petición, no se guardan y ganan a los valores del servidor (ver "Parámetros").
  `max_tokens` no puede pasar de `max_tokens_limit`.
- **`truncated: true`** significa que el modelo paró por `max_tokens`: el resumen está
  **incompleto** y quien lo muestre debe avisar. Pasa sobre todo con modelos de
  razonamiento, que gastan del mismo límite pensando (#2).
- `/parameters` devuelve los parámetros que usaría un resumen sin ajustes del usuario,
  nunca la API key. `config_status` es `ok`, `unavailable` (config no respondió:
  valores del `.env`) o `not_configured` (sin `CONFIG_URL`).

`/health` responde `degraded` si no hay API key o si `GET {OPENROUTER_API_URL}/models`
falla en menos de 3 segundos. Siempre devuelve `200`: el proceso está vivo aunque el
proveedor no.

### Errores

Todos devuelven `{"detail": "..."}` en español.

| Código | Cuándo |
|---|---|
| `400` | `max_tokens` pasa de `MAX_TOKENS_LIMIT`, u OpenRouter rechazó la petición (por ejemplo, un modelo que no existe); el detalle trae su motivo |
| `401` | OpenRouter rechazó la API key **que mandó el usuario** |
| `422` | Falta `text`, está vacío, o un ajuste tiene mal formato (`max_tokens` menor que 1, `model` o `api_key` en blanco). No devuelve lo recibido, para no reflejar la clave |
| `429` | OpenRouter ha alcanzado el límite de peticiones. Incluye `Retry-After` si OpenRouter lo envía |
| `502` | OpenRouter falló o no se pudo contactar; rechazó la API key **del servidor**; o el modelo agotó los tokens sin escribir nada (el detalle sugiere subir el máximo o cambiar de modelo) |
| `503` | No hay clave ni en la petición ni en `OPENROUTER_API_KEY`. El detalle nombra las dos formas de darla |
| `504` | OpenRouter tardó más de `REQUEST_TIMEOUT_SECONDS` |

La API key del usuario nunca aparece en una respuesta, un mensaje de error ni un log.

Los reintentos ante 429 y 5xx aún no están implementados (#3).

## Qué hace con el texto

1. Lee los parámetros (modelo, tokens, temperatura, truncado): ver "Parámetros".
2. Trunca el texto a `max_prompt_chars` caracteres.
3. Lo envía con un prompt de sistema que pide un resumen claro, en el idioma del
   texto, sin añadir información y respondiendo **solo** con el resumen. El prompt
   vive en `app/application/prompts.py`.
4. Descarta de la respuesta los bloques `<think>...</think>` y
   `<reasoning>...</reasoning>` que emiten algunos modelos (#2).

## Parámetros

Cada valor se resuelve en tres niveles; gana el primero que exista:

```
1. La petición               (ajustes del usuario: model, api_key, max_tokens)   #11
2. Configuración centralizada (Consul, a través del servicio config)            #13
3. .env
```

En **cada resumen** se leen los parámetros de la configuración centralizada (Consul,
a través del servicio [config](https://github.com/PDF-extract-organization/pdf-extractext-config)),
con el `.env` como respaldo (épica pdf-extractext#74):

| Campo de la petición | Clave en config | Variable del `.env` | Válido si |
|---|---|---|---|
| `model` | `summarizer/model` | `OPENROUTER_MODEL` | Texto no vacío |
| `max_tokens` | `summarizer/max_tokens` | `MAX_TOKENS` | Entero mayor que 0 (en la petición, además, como mucho `MAX_TOKENS_LIMIT`) |
| — | `summarizer/temperature` | `TEMPERATURE` | Número entre 0 y 2 |
| — | `summarizer/max_prompt_chars` | `MAX_PROMPT_CHARS` | Entero mayor que 0 |
| `api_key` | — (nunca) | `OPENROUTER_API_KEY` | Texto no vacío |

El tope `MAX_TOKENS_LIMIT` solo se aplica a lo que pide la petición: protege la cuota de
la clave del servidor frente a cualquier visitante. Los valores de config y del `.env`
los pone el administrador y no se limitan.

- Un cambio en config vale en el siguiente resumen, **sin reiniciar**.
- Un valor inválido o una clave desconocida se ignoran: se usa el `.env`.
- Si config no responde, tarda más de `CONFIG_TIMEOUT_SECONDS` o devuelve algo
  inesperado, se usa el `.env` y se registra un aviso. El resumen no falla por eso.
- Sin `CONFIG_URL`, todo sale del `.env`.
- **La API key nunca se lee de config**: solo del `.env`.

Para ver qué valores se están usando: `GET /parameters`.

## Configuración

| Variable | Por defecto | Uso |
|---|---|---|
| `OPENROUTER_API_KEY` | vacío | Clave del servidor. Sin ella, solo resumen los usuarios que manden la suya |
| `OPENROUTER_API_URL` | `https://openrouter.ai/api/v1` | Base de la API |
| `OPENROUTER_MODEL` | `openrouter/free` | Modelo |
| `MAX_PROMPT_CHARS` | `12000` | Truncado del texto |
| `MAX_TOKENS` | `5000` | Límite de la respuesta, razonamiento del modelo incluido |
| `MAX_TOKENS_LIMIT` | `8000` | Máximo `max_tokens` que acepta la petición |
| `TEMPERATURE` | `0.3` | Temperatura |
| `REQUEST_TIMEOUT_SECONDS` | `60` | Timeout hacia OpenRouter |
| `CONFIG_URL` | vacío | URL del servicio config. Vacío: solo el `.env` |
| `CONFIG_TIMEOUT_SECONDS` | `2` | Espera máxima a config antes de usar el `.env` |

`OPENROUTER_MODEL`, `MAX_PROMPT_CHARS`, `MAX_TOKENS` y `TEMPERATURE` son los valores
por defecto: config los puede sustituir (ver "Parámetros").

Ver `.env.example`. El `.env` real nunca se commitea.

## Desarrollo

```bash
uv sync --group dev
uv run pytest                   # unitarios: sin red ni API key
uv run pytest -m integration    # contra OpenRouter real; se salta sin API key
uv run uvicorn app.main:app --reload
```

## Docker

```bash
docker build -t pdf-extractext-summarizer .
docker run -p 8000:8000 --env-file .env pdf-extractext-summarizer

curl -H "Content-Type: application/json" -d '{"text": "Texto a resumir"}' \
  http://localhost:8000/summarize
```

En Windows, si el texto lleva acentos, envíalo desde un archivo en UTF-8
(`--data-binary @cuerpo.json`): la terminal puede mandarlo en otra codificación y el
servicio responde `400`.

La imagen corre con un usuario sin privilegios y declara un `HEALTHCHECK`. Al integrar
en `main`, la CI la publica en `ghcr.io/pdf-extract-organization/pdf-extractext-summarizer`.

## Arquitectura

| Capa | Contiene |
|---|---|
| `app/application/interfaces` | Puertos `AIProvider` (con `AIResponse` y sus errores) y `ParametersSource` |
| `app/application/parameters.py` | `SummaryParameters` y la regla de precedencia y validación |
| `app/application/errors.py` | Errores que provoca la petición del usuario: tope de tokens y clave rechazada |
| `app/application/prompts.py` | El prompt de sistema y el de usuario |
| `app/application/services` | `SummaryService`: lee los parámetros, trunca, envía y limpia la respuesta |
| `app/infrastructure` | `OpenRouterAIProvider` y `ConfigServiceParametersSource`: los únicos que importan `httpx` |
| `app/presentation` | Router, schemas y el `422` que no devuelve lo recibido (para no reflejar la clave) |
| `app/dependencies.py` | Cableado desde `Settings`; lo importan el router y `main` |

`OpenRouterAIProvider` recibe por constructor solo la clave del servidor, la URL y el
timeout; el modelo, los tokens, la temperatura y la clave del usuario (si la hay) llegan
en cada llamada. Los dos adaptadores aceptan
un `transport` opcional de httpx, que los tests usan para simular la red.

## Flujo de trabajo

`main` y `develop` son las ramas principales. Los cambios entran por pull request a
`develop`, con los tests en verde en la CI. Los commits citan el issue (`#1`).
