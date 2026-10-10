from fastapi import FastAPI

from app.presentation.routers import summarizer

app = FastAPI(title="pdf-extractext-summarizer")
app.include_router(summarizer.router)
