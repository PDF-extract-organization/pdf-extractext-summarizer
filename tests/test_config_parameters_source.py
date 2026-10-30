"""Tests del adaptador que lee los parámetros del servicio config.

No hacen peticiones reales: el adaptador recibe un transporte de httpx simulado.
"""

import httpx
import pytest

from app.infrastructure.config_parameters_source import ConfigServiceParametersSource

BASE_URL = "http://config.test:8000"


def build(handler, requests=None) -> ConfigServiceParametersSource:
    def capturing(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        return handler(request)

    return ConfigServiceParametersSource(
        base_url=BASE_URL, timeout_seconds=2, transport=httpx.MockTransport(capturing)
    )


def entries(*pairs):
    def handler(request):
        items = [{"key": k, "value": v, "index": i} for i, (k, v) in enumerate(pairs, 1)]
        return httpx.Response(200, json={"entries": items, "total": len(items)})

    return handler


async def test_pide_solo_las_claves_de_summarizer():
    requests = []

    await build(entries(), requests).get_overrides()

    assert requests[0].method == "GET"
    assert requests[0].url.copy_with(query=None) == httpx.URL(f"{BASE_URL}/")
    assert requests[0].url.params["prefix"] == "summarizer/"


async def test_devuelve_los_valores_por_nombre_sin_el_prefijo():
    source = build(entries(("summarizer/max_tokens", "5000"), ("summarizer/model", "m")))

    assert await source.get_overrides() == {"max_tokens": "5000", "model": "m"}


async def test_sin_claves_devuelve_un_diccionario_vacio():
    assert await build(entries()).get_overrides() == {}


@pytest.mark.parametrize("code", [404, 422, 500, 503])
async def test_si_config_responde_con_error_devuelve_none(code):
    assert await build(lambda r: httpx.Response(code, json={"detail": "x"})).get_overrides() is None


@pytest.mark.parametrize(
    "error", [httpx.ConnectError("sin red"), httpx.ReadTimeout("lento")]
)
async def test_si_no_se_puede_hablar_con_config_devuelve_none(error):
    def handler(request):
        error.request = request
        raise error

    assert await build(handler).get_overrides() is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="no es json"),
        httpx.Response(200, json=["una", "lista"]),
        httpx.Response(200, json={"otra": "cosa"}),
        httpx.Response(200, json={"entries": [{"key": "summarizer/x"}]}),
    ],
)
async def test_si_la_respuesta_tiene_forma_inesperada_devuelve_none(response):
    assert await build(lambda r: response).get_overrides() is None


async def test_avisa_en_el_log_cuando_usa_el_respaldo(caplog):
    await build(lambda r: httpx.Response(503)).get_overrides()

    assert "config" in caplog.text
    assert ".env" in caplog.text
