"""Tests del adaptador de OpenRouter.

No hacen peticiones reales: el adaptador recibe un transporte de httpx simulado.
"""

import json

import httpx
import pytest

from app.application.interfaces.ai_provider import (
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
    MissingAPIKeyError,
)
from app.infrastructure.openrouter_provider import OpenRouterAIProvider

BASE_URL = "https://openrouter.test/api/v1"


def build(handler=None, api_key="sk-or-test", requests=None) -> OpenRouterAIProvider:
    """Construye el proveedor con un transporte que registra las peticiones."""

    def capturing(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        return handler(request)

    return OpenRouterAIProvider(
        api_key=api_key,
        base_url=BASE_URL,
        model="modelo/test",
        max_tokens=1024,
        temperature=0.3,
        timeout_seconds=60,
        transport=httpx.MockTransport(capturing) if handler else None,
    )


def ok(content="Un resumen", tokens=123):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"total_tokens": tokens},
            },
        )

    return handler


def status(code, headers=None):
    def handler(request):
        return httpx.Response(code, json={"error": {"message": "x"}}, headers=headers)

    return handler


# --- complete ---


@pytest.mark.parametrize("api_key", ["", "   "])
async def test_sin_api_key_lanza_missing_api_key_error(api_key):
    with pytest.raises(MissingAPIKeyError):
        await build(ok(), api_key=api_key).complete("sistema", "usuario")


async def test_devuelve_el_contenido_el_modelo_y_los_tokens():
    result = await build(ok(content="Este es el resumen", tokens=999)).complete("s", "u")

    assert result.content == "Este es el resumen"
    assert result.model == "modelo/test"
    assert result.tokens_used == 999


async def test_tokens_es_none_si_la_respuesta_no_los_trae():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    assert (await build(handler).complete("s", "u")).tokens_used is None


async def test_envia_la_peticion_esperada():
    requests = []

    await build(ok(), requests=requests).complete("el sistema", "el usuario")

    request = requests[0]
    body = json.loads(request.read())
    assert str(request.url) == f"{BASE_URL}/chat/completions"
    assert request.headers["Authorization"] == "Bearer sk-or-test"
    assert body["model"] == "modelo/test"
    assert body["max_tokens"] == 1024
    assert body["temperature"] == 0.3
    assert body["messages"] == [
        {"role": "system", "content": "el sistema"},
        {"role": "user", "content": "el usuario"},
    ]


async def test_un_429_lanza_rate_limit_con_retry_after():
    with pytest.raises(AIRateLimitError) as info:
        await build(status(429, {"Retry-After": "30"})).complete("s", "u")

    assert info.value.retry_after == "30"


async def test_un_429_sin_retry_after_deja_retry_after_en_none():
    with pytest.raises(AIRateLimitError) as info:
        await build(status(429)).complete("s", "u")

    assert info.value.retry_after is None


@pytest.mark.parametrize("code", [400, 401, 402, 500, 503])
async def test_otros_errores_http_lanzan_ai_provider_error(code):
    with pytest.raises(AIProviderError):
        await build(status(code)).complete("s", "u")


async def test_un_timeout_lanza_ai_timeout_error():
    def handler(request):
        raise httpx.ReadTimeout("lento", request=request)

    with pytest.raises(AITimeoutError):
        await build(handler).complete("s", "u")


async def test_si_no_se_puede_conectar_lanza_ai_provider_error():
    def handler(request):
        raise httpx.ConnectError("sin red", request=request)

    with pytest.raises(AIProviderError):
        await build(handler).complete("s", "u")


async def test_un_error_en_el_cuerpo_lanza_ai_provider_error_con_su_mensaje():
    def handler(request):
        return httpx.Response(200, json={"error": {"message": "Sin saldo"}})

    with pytest.raises(AIProviderError, match="Sin saldo"):
        await build(handler).complete("s", "u")


@pytest.mark.parametrize(
    "body",
    [
        {"algo": "inesperado"},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": None}}]},
    ],
)
async def test_una_respuesta_con_forma_inesperada_lanza_ai_provider_error(body):
    def handler(request):
        return httpx.Response(200, json=body)

    with pytest.raises(AIProviderError):
        await build(handler).complete("s", "u")


# --- health_check ---


async def test_health_es_false_sin_api_key():
    requests = []

    assert await build(ok(), api_key="", requests=requests).health_check() is False
    assert requests == []


async def test_health_es_true_si_models_responde_200():
    requests = []

    def handler(request):
        return httpx.Response(200, json={"data": []})

    assert await build(handler, requests=requests).health_check() is True
    assert str(requests[0].url) == f"{BASE_URL}/models"


async def test_health_es_false_si_models_falla():
    assert await build(status(503)).health_check() is False


async def test_health_es_false_si_no_se_puede_conectar():
    def handler(request):
        raise httpx.ConnectError("sin red", request=request)

    assert await build(handler).health_check() is False
