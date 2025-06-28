"""FastAPI backend for analyzing POCT barcode sharing.

This app accepts a CSV upload and flags potential suspicious operator activity.
"""
import pandas as pd
from io import BytesIO
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI app
app = FastAPI(title="POCT Barcode Sharing API")

# Configure CORS so a separate frontend can interact with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_methods=["*"],
    allow_headers=["*"],
)

# Columns that must be present in the uploaded log file
REQUIRED_COLUMNS = ["Timestamp", "Operator_ID", "Location", "Device_ID", "Test_Type"]


@app.get("/")
async def read_root() -> dict:
    """Simple health check endpoint."""
    return {"status": "ok"}


@app.post("/upload/")
async def upload_log(file: UploadFile = File(...)) -> dict:
    """Upload a POCT log CSV file and analyze for barcode sharing."""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    try:
        # Read uploaded bytes into pandas DataFrame
        contents = await file.read()
        df = pd.read_csv(BytesIO(contents))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {exc}")

    # Ensure required columns exist
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(missing_cols)}",
        )

    # Parse timestamps and sort for sequential operations
    try:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error parsing timestamps: {exc}")
    df = df.sort_values(["Operator_ID", "Timestamp"])

    # Compute time difference between tests for each operator
    df["Time_Diff"] = df.groupby("Operator_ID")["Timestamp"].diff().dt.total_seconds()
    df["Prev_Location"] = df.groupby("Operator_ID")["Location"].shift()

    # Flag conditions
    df["Rapid_Flag"] = df["Time_Diff"] < 60
    df["Location_Flag"] = (df["Location"] != df["Prev_Location"]) & (df["Time_Diff"] <= 300)

    flagged = df[df["Rapid_Flag"] | df["Location_Flag"]]

    # Summarize suspicious activity per operator
    summary = (
        flagged.groupby("Operator_ID")
        .agg(
            total_flags=("Operator_ID", "size"),
            rapid_flags=("Rapid_Flag", "sum"),
            location_flags=("Location_Flag", "sum"),
        )
        .reset_index()
        .sort_values("total_flags", ascending=False)
    )

    return {"suspicious_operators": summary.to_dict(orient="records")}
