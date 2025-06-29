"""FastAPI backend for POCTIFY Usage Intelligence."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.upload import router as upload_router
from routes.template import router as template_router

app = FastAPI(title="POCTIFY Usage Intelligence")

# ✅ Add this CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://codesharepoctify.netlify.app",  # your actual Netlify frontend domain
        "https://www.codesharepoctify.netlify.app"  # optional www version
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(upload_router)
app.include_router(template_router)
