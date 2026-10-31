"""Tests de los endpoints HTTP con un proveedor falso. Sin red."""

import logging

import pytest
from fastapi.testclient import TestClient

from app.application.interfaces.ai_provider import (
    AIAuthenticationError,
    AIOutOfTokensError,
    AIProviderError,
    AIRateLimitError,
    AIRequestRejectedError,
    AITimeoutError,
    MissingAPIKeyError,
)
from app.application.services.summary_service import SummaryService
from app.dependencies import get_summary_service
from app.main import app
from app.presentation.routers.summarizer import MISSING_API_KEY_DETAIL
from tests.conftest import DEFAULTS, FakeAIProvider, FakeParametersSource

LIMIT = 2000
SECRET = "sk-or-v1-secreta-del-usuario"


def client_con(provider: FakeAIProvider, source: FakeParametersSource | None = None) -> TestClient:
    service = SummaryService(provider, DEFAULTS, source, max_tokens_limit=LIMIT)
    app.dependency_overrides[get_summary_service] = lambda: service
    return TestClient(app)


@pytest.fixture(autouse=True)
def limpiar_overrides():
    yield
    app.dependency_overrides.clear()


def resumir(client, text="Un texto que resumir", **ajustes):
    return client.post("/summarize", json={"text": text, **ajustes})


def test_summarize_devuelve_resumen_modelo_tokens_y_si_se_corto():
    response = resumir(client_con(FakeAIProvider()))

    assert response.status_code == 200
    assert response.json() == {
        "summary": "Resumen de prueba",
        "model": "modelo/env",
        "tokens_used": 42,
        "truncated": False,
    }


@pytest.mark.parametrize("body", [{}, {"text": ""}, {"text": "   "}])
def test_summarize_sin_texto_devuelve_422(body):
    provider = FakeAIProvider()

    response = client_con(provider).post("/summarize", json=body)

    assert response.status_code == 422
    assert provider.calls == []


def test_sin_api_key_devuelve_503_con_el_mensaje_unico():
    response = resumir(client_con(FakeAIProvider(error=MissingAPIKeyError())))

    assert response.status_code == 503
    assert response.json()["detail"] == MISSING_API_KEY_DETAIL


def test_el_mensaje_sin_clave_nombra_las_dos_formas_de_darla():
    assert "Ajustes" in MISSING_API_KEY_DETAIL
    assert "OPENROUTER_API_KEY" in MISSING_API_KEY_DETAIL


def test_rate_limit_devuelve_429_con_retry_after():
    provider = FakeAIProvider(error=AIRateLimitError(retry_after="30"))

    response = resumir(client_con(provider))

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"


def test_rate_limit_sin_retry_after_no_pone_la_cabecera():
    response = resumir(client_con(FakeAIProvider(error=AIRateLimitError())))

    assert response.status_code == 429
    assert "Retry-After" not in response.headers


def test_fallo_del_proveedor_devuelve_502():
    response = resumir(client_con(FakeAIProvider(error=AIProviderError("caído"))))

    assert response.status_code == 502


def test_timeout_del_proveedor_devuelve_504():
    response = resumir(client_con(FakeAIProvider(error=AITimeoutError())))

    assert response.status_code == 504


def test_health_healthy_si_el_proveedor_responde():
    response = client_con(FakeAIProvider(healthy=True)).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "summarizer"}


def test_health_degraded_si_el_proveedor_no_responde():
    response = client_con(FakeAIProvider(healthy=False)).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "service": "summarizer"}


# --- GET /parameters ---


def test_parameters_sin_config_muestra_los_del_env_y_el_tope():
    response = client_con(FakeAIProvider()).get("/parameters")

    assert response.status_code == 200
    assert response.json() == {
        "model": "modelo/env",
        "max_tokens": 1000,
        "max_tokens_limit": LIMIT,
        "temperature": 0.3,
        "max_prompt_chars": 100,
        "config_status": "not_configured",
    }


def test_parameters_muestra_los_valores_de_config_en_cuanto_cambian():
    source = FakeParametersSource({"max_tokens": "5000"})
    client = client_con(FakeAIProvider(), source)

    first = client.get("/parameters").json()
    source.overrides = {"max_tokens": "6000", "model": "modelo/consul"}
    second = client.get("/parameters").json()

    assert (first["max_tokens"], first["config_status"]) == (5000, "ok")
    assert (second["max_tokens"], second["model"]) == (6000, "modelo/consul")


def test_parameters_con_config_caido_muestra_el_env_y_unavailable():
    body = client_con(FakeAIProvider(), FakeParametersSource(None)).get("/parameters").json()

    assert body["max_tokens"] == DEFAULTS.max_tokens
    assert body["config_status"] == "unavailable"


def test_parameters_nunca_expone_la_api_key():
    body = client_con(FakeAIProvider()).get("/parameters").json()

    assert not any("key" in name for name in body)


def test_el_resumen_usa_los_parametros_de_config():
    provider = FakeAIProvider()

    response = resumir(client_con(provider, FakeParametersSource({"model": "modelo/consul"})))

    assert response.json()["model"] == "modelo/consul"
    assert provider.calls[0].model == "modelo/consul"


# --- Ajustes del usuario en la petición (#11) ---


def test_los_ajustes_de_la_peticion_llegan_al_proveedor():
    provider = FakeAIProvider()

    response = resumir(
        client_con(provider), model="modelo/usuario", api_key=SECRET, max_tokens=1500
    )

    assert response.status_code == 200
    call = provider.calls[0]
    assert (call.model, call.api_key, call.max_tokens) == ("modelo/usuario", SECRET, 1500)
    assert response.json()["model"] == "modelo/usuario"


def test_max_tokens_por_encima_del_tope_devuelve_400_con_el_maximo():
    provider = FakeAIProvider()

    response = resumir(client_con(provider), max_tokens=LIMIT + 1)

    assert response.status_code == 400
    assert str(LIMIT) in response.json()["detail"]
    assert provider.calls == []


@pytest.mark.parametrize(
    "ajustes",
    [{"max_tokens": 0}, {"max_tokens": -1}, {"max_tokens": "muchos"}, {"model": "  "}, {"api_key": ""}],
)
def test_ajustes_mal_formados_devuelven_422(ajustes):
    provider = FakeAIProvider()

    assert resumir(client_con(provider), **ajustes).status_code == 422
    assert provider.calls == []


def test_clave_del_usuario_rechazada_devuelve_401():
    response = resumir(
        client_con(FakeAIProvider(error=AIAuthenticationError("401"))), api_key=SECRET
    )

    assert response.status_code == 401
    assert "API key no es válida" in response.json()["detail"]


def test_clave_del_servidor_rechazada_devuelve_502():
    response = resumir(client_con(FakeAIProvider(error=AIAuthenticationError("401"))))

    assert response.status_code == 502


def test_peticion_rechazada_por_el_proveedor_devuelve_400_con_su_motivo():
    error = AIRequestRejectedError("modelo/raro is not a valid model ID")

    response = resumir(client_con(FakeAIProvider(error=error)), model="modelo/raro")

    assert response.status_code == 400
    assert "not a valid model ID" in response.json()["detail"]


def test_sin_texto_por_falta_de_tokens_devuelve_502_que_lo_explica():
    error = AIOutOfTokensError("El modelo agotó los 1024 tokens razonando.")

    response = resumir(client_con(FakeAIProvider(error=error)))

    assert response.status_code == 502
    assert "tokens" in response.json()["detail"]


def test_un_resumen_cortado_se_devuelve_marcado():
    response = resumir(client_con(FakeAIProvider(truncated=True)))

    assert response.status_code == 200
    assert response.json()["truncated"] is True


# --- La clave del usuario no se filtra ---


@pytest.mark.parametrize(
    "body",
    [
        {"api_key": SECRET},  # falta text
        {"text": "x", "api_key": SECRET, "max_tokens": "muchos"},
        {"text": "x", "api_key": SECRET, "model": "  "},
    ],
)
def test_un_422_no_devuelve_la_clave(body):
    response = client_con(FakeAIProvider()).post("/summarize", json=body)

    assert response.status_code == 422
    assert SECRET not in response.text


@pytest.mark.parametrize(
    "error",
    [
        AIAuthenticationError("401"),
        AIRequestRejectedError("rechazada"),
        AIOutOfTokensError("sin tokens"),
        AIProviderError("caído"),
        AIRateLimitError(),
        AITimeoutError(),
    ],
)
def test_ningun_error_devuelve_ni_registra_la_clave(error, caplog):
    caplog.set_level(logging.DEBUG)

    response = resumir(client_con(FakeAIProvider(error=error)), api_key=SECRET)

    assert SECRET not in response.text
    assert SECRET not in caplog.text
