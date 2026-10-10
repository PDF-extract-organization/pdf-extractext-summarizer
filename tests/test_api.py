"""Tests de los endpoints HTTP con un proveedor falso. Sin red."""

import pytest
from fastapi.testclient import TestClient

from app.application.interfaces.ai_provider import (
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
    MissingAPIKeyError,
)
from app.application.services.summary_service import SummaryService
from app.dependencies import get_summary_service
from app.main import app
from app.presentation.routers.summarizer import MISSING_API_KEY_DETAIL
from tests.conftest import FakeAIProvider


def client_con(provider: FakeAIProvider) -> TestClient:
    app.dependency_overrides[get_summary_service] = lambda: SummaryService(provider, 100)
    return TestClient(app)


@pytest.fixture(autouse=True)
def limpiar_overrides():
    yield
    app.dependency_overrides.clear()


def resumir(client, text="Un texto que resumir"):
    return client.post("/summarize", json={"text": text})


def test_summarize_devuelve_resumen_modelo_y_tokens():
    response = resumir(client_con(FakeAIProvider()))

    assert response.status_code == 200
    assert response.json() == {
        "summary": "Resumen de prueba",
        "model": "modelo/fake",
        "tokens_used": 42,
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
