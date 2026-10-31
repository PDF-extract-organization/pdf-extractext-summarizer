"""Tests del caso de uso con dobles del proveedor de IA y de la configuración."""

import pytest

from app.application.errors import InvalidAPIKeyError, TokensOverLimitError
from app.application.interfaces.ai_provider import AIAuthenticationError, AIProviderError
from app.application.prompts import SYSTEM_PROMPT
from app.application.services.summary_service import ConfigStatus, SummaryService
from tests.conftest import DEFAULTS, FakeAIProvider, FakeParametersSource


@pytest.fixture
def service(fake_provider) -> SummaryService:
    return SummaryService(fake_provider, DEFAULTS)


async def test_devuelve_el_resumen_el_modelo_y_los_tokens(service):
    result = await service.summarize("Un texto que resumir")

    assert result.summary == "Resumen de prueba"
    assert result.model == "modelo/env"
    assert result.tokens_used == 42


async def test_envia_el_prompt_de_sistema(service, fake_provider):
    await service.summarize("Un texto que resumir")

    assert fake_provider.calls[0].system_prompt == SYSTEM_PROMPT


async def test_el_prompt_de_usuario_incluye_el_texto(service, fake_provider):
    await service.summarize("el contenido del pdf")

    assert "el contenido del pdf" in fake_provider.calls[0].user_prompt


async def test_trunca_el_texto_al_maximo_configurado(service, fake_provider):
    await service.summarize("a" * 100 + "z" * 50)

    assert fake_provider.calls[0].user_prompt.endswith("\n\n" + "a" * 100)


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
    service = SummaryService(FakeAIProvider(content=respuesta), DEFAULTS)

    result = await service.summarize("texto")

    assert result.summary == "El resumen"


async def test_check_health_delega_en_el_proveedor():
    assert await SummaryService(FakeAIProvider(healthy=True), DEFAULTS).check_health() is True
    assert await SummaryService(FakeAIProvider(healthy=False), DEFAULTS).check_health() is False


# --- Parámetros: configuración centralizada con el .env como respaldo ---


async def test_sin_configuracion_centralizada_usa_los_parametros_del_env(service, fake_provider):
    await service.summarize("texto")

    call = fake_provider.calls[0]
    assert (call.model, call.max_tokens, call.temperature) == ("modelo/env", 1000, 0.3)


async def test_los_parametros_centralizados_ganan_al_env(fake_provider):
    source = FakeParametersSource(
        {"model": "modelo/consul", "max_tokens": "5000", "temperature": "0.7"}
    )
    service = SummaryService(fake_provider, DEFAULTS, source)

    result = await service.summarize("texto")

    call = fake_provider.calls[0]
    assert (call.model, call.max_tokens, call.temperature) == ("modelo/consul", 5000, 0.7)
    assert result.model == "modelo/consul"


async def test_max_prompt_chars_centralizado_cambia_el_truncado(fake_provider):
    source = FakeParametersSource({"max_prompt_chars": "3"})
    service = SummaryService(fake_provider, DEFAULTS, source)

    await service.summarize("abcdef")

    assert fake_provider.calls[0].user_prompt.endswith("\n\nabc")


async def test_lee_la_configuracion_en_cada_resumen_sin_reiniciar(fake_provider):
    source = FakeParametersSource({"max_tokens": "1024"})
    service = SummaryService(fake_provider, DEFAULTS, source)

    await service.summarize("texto")
    source.overrides = {"max_tokens": "5000"}
    await service.summarize("texto")

    assert [c.max_tokens for c in fake_provider.calls] == [1024, 5000]


async def test_si_la_configuracion_no_responde_usa_el_env_y_resume_igual(fake_provider):
    service = SummaryService(fake_provider, DEFAULTS, FakeParametersSource(None))

    result = await service.summarize("texto")

    assert result.summary == "Resumen de prueba"
    assert fake_provider.calls[0].max_tokens == DEFAULTS.max_tokens


# --- current_parameters ---


async def test_current_parameters_sin_fuente_es_el_env_y_not_configured(service):
    current = await service.current_parameters()

    assert current.parameters == DEFAULTS
    assert current.config_status == ConfigStatus.NOT_CONFIGURED


async def test_current_parameters_con_fuente_aplica_los_valores_y_ok(fake_provider):
    source = FakeParametersSource({"max_tokens": "5000"})
    service = SummaryService(fake_provider, DEFAULTS, source)

    current = await service.current_parameters()

    assert current.parameters.max_tokens == 5000
    assert current.config_status == ConfigStatus.OK


async def test_current_parameters_con_fuente_caida_es_el_env_y_unavailable(fake_provider):
    service = SummaryService(fake_provider, DEFAULTS, FakeParametersSource(None))

    current = await service.current_parameters()

    assert current.parameters == DEFAULTS
    assert current.config_status == ConfigStatus.UNAVAILABLE


async def test_current_parameters_no_llama_a_la_ia(fake_provider):
    service = SummaryService(fake_provider, DEFAULTS, FakeParametersSource({}))

    await service.current_parameters()

    assert fake_provider.calls == []


# --- Ajustes del usuario en la petición (#11) ---


async def test_sin_ajustes_del_usuario_usa_la_clave_del_servidor(service, fake_provider):
    await service.summarize("texto")

    assert fake_provider.calls[0].api_key is None


async def test_los_ajustes_de_la_peticion_ganan_a_consul_y_al_env(fake_provider):
    source = FakeParametersSource({"model": "modelo/consul", "max_tokens": "5000"})
    service = SummaryService(fake_provider, DEFAULTS, source)

    result = await service.summarize(
        "texto", model="modelo/usuario", api_key="sk-usuario", max_tokens=1500
    )

    call = fake_provider.calls[0]
    assert (call.model, call.max_tokens, call.api_key) == ("modelo/usuario", 1500, "sk-usuario")
    assert result.model == "modelo/usuario"


async def test_un_ajuste_parcial_solo_cambia_lo_que_trae(fake_provider):
    source = FakeParametersSource({"model": "modelo/consul", "max_tokens": "5000"})
    service = SummaryService(fake_provider, DEFAULTS, source)

    await service.summarize("texto", max_tokens=1500)

    call = fake_provider.calls[0]
    assert (call.model, call.max_tokens) == ("modelo/consul", 1500)


async def test_max_tokens_de_la_peticion_por_encima_del_tope_se_rechaza(fake_provider):
    service = SummaryService(fake_provider, DEFAULTS, max_tokens_limit=2000)

    with pytest.raises(TokensOverLimitError) as info:
        await service.summarize("texto", max_tokens=2001)

    assert info.value.limit == 2000
    assert fake_provider.calls == []


async def test_max_tokens_igual_al_tope_se_acepta(fake_provider):
    service = SummaryService(fake_provider, DEFAULTS, max_tokens_limit=2000)

    await service.summarize("texto", max_tokens=2000)

    assert fake_provider.calls[0].max_tokens == 2000


async def test_el_tope_no_se_aplica_a_los_valores_del_administrador(fake_provider):
    """Consul y el .env los pone el administrador; el tope es para lo que pida el usuario."""
    source = FakeParametersSource({"max_tokens": "9000"})
    service = SummaryService(fake_provider, DEFAULTS, source, max_tokens_limit=2000)

    await service.summarize("texto")

    assert fake_provider.calls[0].max_tokens == 9000


async def test_max_tokens_limit_es_visible(fake_provider):
    assert SummaryService(fake_provider, DEFAULTS, max_tokens_limit=2000).max_tokens_limit == 2000


async def test_clave_del_usuario_rechazada_es_error_del_usuario():
    service = SummaryService(FakeAIProvider(error=AIAuthenticationError("401")), DEFAULTS)

    with pytest.raises(InvalidAPIKeyError):
        await service.summarize("texto", api_key="sk-mala")


async def test_clave_del_servidor_rechazada_es_error_de_configuracion():
    service = SummaryService(FakeAIProvider(error=AIAuthenticationError("401")), DEFAULTS)

    with pytest.raises(AIProviderError) as info:
        await service.summarize("texto")

    assert not isinstance(info.value, InvalidAPIKeyError)
    assert "servidor" in str(info.value)


@pytest.mark.parametrize("truncated", [True, False])
async def test_indica_si_el_resumen_salio_cortado(truncated):
    service = SummaryService(FakeAIProvider(truncated=truncated), DEFAULTS)

    assert (await service.summarize("texto")).truncated is truncated
