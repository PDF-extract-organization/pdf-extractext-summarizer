"""Regla de precedencia: la configuración centralizada gana al .env, si es válida."""

import pytest

from app.application.parameters import apply_overrides
from tests.conftest import DEFAULTS


def test_sin_valores_centralizados_quedan_los_del_env():
    assert apply_overrides(DEFAULTS, {}) == DEFAULTS


def test_los_valores_centralizados_ganan_al_env():
    result = apply_overrides(
        DEFAULTS,
        {
            "model": "modelo/consul",
            "max_tokens": "5000",
            "temperature": "0.7",
            "max_prompt_chars": "20000",
        },
    )

    assert result.model == "modelo/consul"
    assert result.max_tokens == 5000
    assert result.temperature == 0.7
    assert result.max_prompt_chars == 20000


def test_solo_cambia_lo_que_viene_de_la_configuracion_centralizada():
    result = apply_overrides(DEFAULTS, {"max_tokens": "5000"})

    assert result.max_tokens == 5000
    assert result.model == DEFAULTS.model
    assert result.temperature == DEFAULTS.temperature
    assert result.max_prompt_chars == DEFAULTS.max_prompt_chars


def test_tolera_espacios_alrededor_de_los_valores():
    result = apply_overrides(DEFAULTS, {"model": "  modelo/consul ", "max_tokens": " 5000 "})

    assert result.model == "modelo/consul"
    assert result.max_tokens == 5000


@pytest.mark.parametrize(
    "name, value",
    [
        ("model", ""),
        ("model", "   "),
        ("max_tokens", "abc"),
        ("max_tokens", "0"),
        ("max_tokens", "-5"),
        ("max_tokens", "12.5"),
        ("temperature", "caliente"),
        ("temperature", "-0.1"),
        ("temperature", "2.1"),
        ("temperature", "nan"),
        ("max_prompt_chars", "0"),
        ("max_prompt_chars", "mucho"),
    ],
)
def test_un_valor_invalido_se_ignora_y_queda_el_del_env(name, value):
    """Una errata en Consul no debe romper los resúmenes."""
    assert apply_overrides(DEFAULTS, {name: value}) == DEFAULTS


def test_un_valor_invalido_no_impide_aplicar_los_validos():
    result = apply_overrides(DEFAULTS, {"max_tokens": "abc", "temperature": "0.9"})

    assert result.max_tokens == DEFAULTS.max_tokens
    assert result.temperature == 0.9


@pytest.mark.parametrize("value", ["0", "2", "1.25"])
def test_acepta_temperaturas_entre_0_y_2(value):
    assert apply_overrides(DEFAULTS, {"temperature": value}).temperature == float(value)


@pytest.mark.parametrize("name", ["api_key", "openrouter_api_key", "otra_cosa", "x/y"])
def test_las_claves_desconocidas_se_ignoran(name):
    """En particular, la API key nunca se lee de la configuración centralizada."""
    assert apply_overrides(DEFAULTS, {name: "valor"}) == DEFAULTS
