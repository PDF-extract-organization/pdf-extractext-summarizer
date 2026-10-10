# pdf-extractext-summarizer

Microservicio que genera resúmenes de texto con IA (OpenRouter). Forma parte de
[pdf-extractext](https://github.com/PDF-extract-organization/pdf-extractext), dividido
en microservicios (épica: pdf-extractext#64).

Recibe texto y devuelve un resumen. No conoce PDFs ni base de datos. Es el único
servicio que tiene la API key de OpenRouter.

## Contrato HTTP

Escucha en el puerto `8000`. En el stack completo, Traefik le quita el prefijo
`/summarizer`, así que desde fuera las rutas son `http://pdf.localhost/summarizer/...`.

| Método y ruta | Entrada | Respuesta |
|---|---|---|
| `POST /summarize` | JSON `{"text": "..."}` | `200` `{"summary", "model", "tokens_used"}` |
| `GET /health` | — | `200` `{"status": "healthy" \| "degraded", "service": "summarizer"}` |

`/health` responde `degraded` si no hay API key o si `GET {OPENROUTER_API_URL}/models`
falla en menos de 3 segundos. Siempre devuelve `200`: el proceso está vivo aunque el
proveedor no.

### Errores

Todos devuelven `{"detail": "..."}` en español.

| Código | Cuándo |
|---|---|
| `422` | Falta `text`, o está vacío o solo tiene espacios |
| `429` | OpenRouter ha alcanzado el límite de peticiones. Incluye `Retry-After` si OpenRouter lo envía |
| `502` | OpenRouter falló, no se pudo contactar, o devolvió una respuesta con forma inesperada |
| `503` | Falta `OPENROUTER_API_KEY` |
| `504` | OpenRouter tardó más de `REQUEST_TIMEOUT_SECONDS` |

Los reintentos ante 429 y 5xx aún no están implementados (#3).

## Qué hace con el texto

1. Lo trunca a `MAX_PROMPT_CHARS` caracteres.
2. Lo envía con un prompt de sistema que pide un resumen claro, en el idioma del
   texto, sin añadir información y respondiendo **solo** con el resumen. El prompt
   vive en `app/application/prompts.py`.
3. Descarta de la respuesta los bloques `<think>...</think>` y
   `<reasoning>...</reasoning>` que emiten algunos modelos (#2).

## Configuración

| Variable | Por defecto | Uso |
|---|---|---|
| `OPENROUTER_API_KEY` | — (obligatoria) | Clave de OpenRouter |
| `OPENROUTER_API_URL` | `https://openrouter.ai/api/v1` | Base de la API |
| `OPENROUTER_MODEL` | `openrouter/free` | Modelo |
| `MAX_PROMPT_CHARS` | `12000` | Truncado del texto |
| `MAX_TOKENS` | `1024` | Límite de la respuesta |
| `TEMPERATURE` | `0.3` | Temperatura |
| `REQUEST_TIMEOUT_SECONDS` | `60` | Timeout hacia OpenRouter |

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
| `app/application/interfaces` | Puerto `AIProvider`, `AIResponse` y los errores del puerto |
| `app/application/prompts.py` | El prompt de sistema y el de usuario |
| `app/application/services` | `SummaryService`: trunca, envía y limpia la respuesta |
| `app/infrastructure` | `OpenRouterAIProvider`: el único sitio que importa `httpx` |
| `app/presentation` | Router y schemas de FastAPI |
| `app/dependencies.py` | Cableado desde `Settings`; lo importan el router y `main` |

`OpenRouterAIProvider` recibe toda su configuración por constructor y un `transport`
opcional de httpx, que los tests usan para simular OpenRouter sin red.

## Flujo de trabajo

`main` y `develop` son las ramas principales. Los cambios entran por pull request a
`develop`, con los tests en verde en la CI. Los commits citan el issue (`#1`).
