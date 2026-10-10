"""Tests del caso de uso con un proveedor de IA falso."""

import pytest

from app.application.prompts import SYSTEM_PROMPT
from app.application.services.summary_service import SummaryService
from tests.conftest import FakeAIProvider


@pytest.fixture
def service(fake_provider) -> SummaryService:
    return SummaryService(fake_provider, max_prompt_chars=100)


async def test_devuelve_el_resumen_el_modelo_y_los_tokens(service):
    result = await service.summarize("Un texto que resumir")

    assert result.summary == "Resumen de prueba"
    assert result.model == "modelo/fake"
    assert result.tokens_used == 42


async def test_envia_el_prompt_de_sistema(service, fake_provider):
    await service.summarize("Un texto que resumir")

    system_prompt, _ = fake_provider.calls[0]
    assert system_prompt == SYSTEM_PROMPT


async def test_el_prompt_de_usuario_incluye_el_texto(service, fake_provider):
    await service.summarize("el contenido del pdf")

    _, user_prompt = fake_provider.calls[0]
    assert "el contenido del pdf" in user_prompt


async def test_trunca_el_texto_al_maximo_configurado(service, fake_provider):
    await service.summarize("a" * 100 + "b" * 50)

    _, user_prompt = fake_provider.calls[0]
    assert "a" * 100 in user_prompt
    assert "b" not in user_prompt


async def test_el_prompt_de_sistema_pide_responder_solo_con_el_resumen():
    assert "únicamente con el resumen" in SYSTEM_PROMPT


@pytest.mark.parametrize(
    "respuesta",
    [
        "<think>Voy a pensar...</think>El resumen",
        "<think>\nlínea 1\nlínea 2\n</think>\n\nEl resumen",
        "<reasoning>razono</reasoning>El resumen",
    ],
)
async def test_descarta_los_bloques_de_razonamiento(respuesta):
    service = SummaryService(FakeAIProvider(content=respuesta), max_prompt_chars=100)

    result = await service.summarize("texto")

    assert result.summary == "El resumen"


async def test_check_health_delega_en_el_proveedor():
    assert await SummaryService(FakeAIProvider(healthy=True), 100).check_health() is True
    assert await SummaryService(FakeAIProvider(healthy=False), 100).check_health() is False
