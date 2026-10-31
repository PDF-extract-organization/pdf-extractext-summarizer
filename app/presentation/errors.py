"""Respuestas de error que no deben devolver lo que mandó el cliente."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# FastAPI devuelve en cada error el `input` recibido; si falta un campo, es el cuerpo
# entero, con la API key del usuario dentro. Solo se devuelve dónde y qué falló.
SAFE_FIELDS = ("type", "loc", "msg")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        details = [{k: e[k] for k in SAFE_FIELDS if k in e} for e in error.errors()]
        return JSONResponse(status_code=422, content={"detail": details})
