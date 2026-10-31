from fastapi import FastAPI

from app.presentation.errors import register_error_handlers
from app.presentation.routers import summarizer

app = FastAPI(title="pdf-extractext-summarizer")
register_error_handlers(app)
app.include_router(summarizer.router)
