"""El HEALTHCHECK de la imagen no puede depender de OpenRouter (#20)."""

from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parent.parent / "Dockerfile"


def test_el_healthcheck_usa_live_y_no_health():
    healthcheck = DOCKERFILE.read_text(encoding="utf-8").split("HEALTHCHECK", 1)[1]
    command = healthcheck.split("\n\n", 1)[0]

    assert "localhost:8000/live" in command
    assert "/health" not in command
