"""Endpoints for template file download."""
import io
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

TEMPLATE_PATH = "POCTIFY_BarcodeSharing_Template.csv"


@router.get("/template/download")
async def download_template():
    """Return a minimal CSV template for uploads."""
    with open(TEMPLATE_PATH, "rb") as f:
        data = f.read()
    headers = {
        "Content-Disposition": "attachment; filename=POCTIFY_BarcodeSharing_Template.csv"
    }
    return StreamingResponse(io.BytesIO(data), media_type="text/csv", headers=headers)
