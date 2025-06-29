"""FastAPI backend for POCTIFY Usage Intelligence."""
from fastapi import FastAPI
from routes.upload import router as upload_router
from routes.template import router as template_router

app = FastAPI(title="POCTIFY Usage Intelligence")

# register routers
app.include_router(upload_router)
app.include_router(template_router)
