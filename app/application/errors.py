"""Errores del caso de uso que provoca la petición del usuario. La presentación los
traduce a códigos HTTP."""


class TokensOverLimitError(ValueError):
    def __init__(self, limit: int):
        super().__init__(f"El máximo de tokens permitido es {limit}.")
        self.limit = limit


class InvalidAPIKeyError(Exception):
    """El proveedor rechazó la API key que mandó el usuario (no la del servidor)."""
