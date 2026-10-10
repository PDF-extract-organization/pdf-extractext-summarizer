"""Cómo se pide un resumen. Es regla de negocio: vive aquí, no en el adaptador HTTP."""

SYSTEM_PROMPT = (
    "Eres un asistente experto en síntesis de información. Resume el texto de "
    "forma clara y concisa, en el mismo idioma en que está escrito. No agregues "
    "información que no esté en el texto original. Responde únicamente con el "
    "resumen, sin explicar tu proceso ni repetir estas instrucciones."
)


def build_user_prompt(text: str) -> str:
    return f"Resume el siguiente documento en un máximo de 500 palabras:\n\n{text}"
