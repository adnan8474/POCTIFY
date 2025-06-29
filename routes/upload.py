"""Routes for file upload and analysis endpoints."""
from __future__ import annotations

import io
import time
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse

from utils.flags import validate_dataframe, compute_flags, build_hourly_matrix
from models.schemas import Event, UsageSummary, OperatorSummary, DeviceSummary, FlagStats

router = APIRouter()

# In-memory storage for last processed dataframe and timestamp
LAST_PROCESSED: dict[str, any] = {
    "df": None,
    "timestamp": None,
    "analysis": None,
}
START_TIME = time.time()
VERSION = "0.1.0"

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


@router.post("/upload", response_model=UsageSummary)
async def upload_file(file: UploadFile = File(...)):
    """Upload middleware export file and return analysis."""
    if file.content_type not in [
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ]:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (>20MB)")

    if file.filename.lower().endswith(".csv"):
        df = pd.read_csv(io.BytesIO(contents))
    else:
        df = pd.read_excel(io.BytesIO(contents))

    errors = validate_dataframe(df)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    df = compute_flags(df)
    LAST_PROCESSED["df"] = df
    LAST_PROCESSED["timestamp"] = datetime.utcnow()

    analysis = build_summary(df)
    LAST_PROCESSED["analysis"] = analysis
    return analysis

def build_summary(df: pd.DataFrame) -> UsageSummary:
    """Compile usage summaries and flag statistics from processed data."""
    flagged_events_preview = []
    for _, row in df[df["FLAGGED"]].head(100).iterrows():
        flagged_events_preview.append(
            Event(
                event_id=int(row["Event_ID"]),
                timestamp=row["Timestamp"],
                operator_id=row["Operator_ID"],
                location=row["Location"],
                device_id=row["Device_ID"],
                test_type=row["Test_Type"],
                rapid=bool(row["RAPID"]),
                loc_conflict=bool(row["LOC_CONFLICT"]),
                device_hop=bool(row["DEVICE_HOP"]),
                shift_viol=bool(row["SHIFT_VIOL"]),
                load_dev=bool(row["LOAD_DEV"]),
                coloc=bool(row["COLOC"]),
                flagged=bool(row["FLAGGED"]),
            )
        )

    operator_summary = []
    insights: dict[str, list[str]] = {}
    for op, group in df.groupby("Operator_ID"):
        rapid_count = int(group["RAPID"].sum())
        loc_conflict_count = int(group["LOC_CONFLICT"].sum())
        device_hop_count = int(group["DEVICE_HOP"].sum())
        shift_viol_count = int(group["SHIFT_VIOL"].sum())
        load_dev_count = int(group["LOAD_DEV"].sum())
        coloc_count = int(group["COLOC"].sum())
        suspicion = (
            rapid_count
            + loc_conflict_count
            + device_hop_count
            + shift_viol_count
            + load_dev_count
            + coloc_count
        ) / len(group)
        operator_summary.append(
            OperatorSummary(
                operator_id=op,
                total_tests=len(group),
                suspicion_score=float(suspicion),
                rapid_count=rapid_count,
                loc_conflict_count=loc_conflict_count,
                device_hop_count=device_hop_count,
                shift_viol_count=shift_viol_count,
                load_dev_count=load_dev_count,
                coloc_count=coloc_count,
            )
        )
        messages = []
        if device_hop_count > 0:
            messages.append(
                f"Tested on {group['Device_ID'].nunique()} devices in {int((group['Timestamp'].max()-group['Timestamp'].min()).total_seconds()/60)} minutes"
            )
        if shift_viol_count > 0:
            messages.append("Barcode used after >14 hours within 24h window")
        if messages:
            insights[op] = messages

    device_summary = []
    for dev, group in df.groupby("Device_ID"):
        device_summary.append(
            DeviceSummary(
                device_id=dev,
                total_tests=len(group),
                unique_users=group["Operator_ID"].nunique(),
                coloc_events=int(group["COLOC"].sum()),
            )
        )

    stats = FlagStats(
        rapid=int(df["RAPID"].sum()),
        loc_conflict=int(df["LOC_CONFLICT"].sum()),
        device_hop=int(df["DEVICE_HOP"].sum()),
        shift_viol=int(df["SHIFT_VIOL"].sum()),
        load_dev=int(df["LOAD_DEV"].sum()),
        coloc=int(df["COLOC"].sum()),
    )

    heatmap = build_hourly_matrix(df)

    return UsageSummary(
        flagged_events_preview=flagged_events_preview,
        operator_summary=operator_summary,
        device_summary=device_summary,
        flag_stats=stats,
        hourly_heatmap_matrix=heatmap,
        insights=insights or None,
    )
@router.get("/export/csv")
async def export_csv():
    """Download flagged events as CSV."""
    if LAST_PROCESSED["df"] is None:
        raise HTTPException(status_code=404, detail="No file processed")
    flagged = LAST_PROCESSED["df"][LAST_PROCESSED["df"]["FLAGGED"]]
    stream = io.StringIO()
    flagged.to_csv(stream, index=False)
    stream.seek(0)
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=flagged_events.csv"})

@router.get("/report/pdf")
async def report_pdf():
    """Generate a simple PDF summary of flagged events."""
    if LAST_PROCESSED["df"] is None:
        raise HTTPException(status_code=404, detail="No file processed")
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="POCTIFY Usage Report", ln=1, align="C")
    pdf.cell(200, 10, txt=f"Generated: {datetime.utcnow().isoformat()}", ln=1, align="L")
    df = LAST_PROCESSED["df"]
    pdf.cell(200, 10, txt=f"Total tests: {len(df)}", ln=1, align="L")
    pdf.cell(200, 10, txt=f"Flagged events: {int(df["FLAGGED"].sum())}", ln=1, align="L")
    stream_pdf = io.BytesIO(pdf.output(dest="S").encode("latin-1"))
    stream_pdf.seek(0)
    return StreamingResponse(stream_pdf, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=usage_report.pdf"})





@router.post("/notes")
async def receive_notes(notes: str = File(...)):
    """Receive audit notes (stored temporarily, not persisted)."""
    LAST_PROCESSED["notes"] = notes
    return {"status": "received"}


@router.get("/summary", response_model=UsageSummary)
async def get_summary():
    """Return summary of last processed file."""
    if LAST_PROCESSED["analysis"] is None:
        raise HTTPException(status_code=404, detail="No file processed")
    return LAST_PROCESSED["analysis"]


@router.get("/status")
async def get_status():
    """Return service status information."""
    uptime = int(time.time() - START_TIME)
    return {
        "version": VERSION,
        "uptime": uptime,
        "last_file_processed": LAST_PROCESSED["timestamp"],
    }
