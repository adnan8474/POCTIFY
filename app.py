import pandas as pd
import numpy as np
import scipy.stats as stats
import streamlit as st
import plotly.express as px
import plotly.io as pio

st.set_page_config(page_title="POCT Barcode Usage Monitor", layout="wide", page_icon="🔎")

st.image("843eb762-d00e-44f5-a84d-0a5bc11089c5.png", width=150)
st.markdown("<h1 style='text-align:center;'>POCT Barcode Sharing Detector</h1>", unsafe_allow_html=True)

st.sidebar.header("⚙️ Controls")
rapid_threshold = st.sidebar.number_input("Rapid test threshold (min)", min_value=0.1, max_value=60.0, value=1.0, step=0.1)
conflict_window = st.sidebar.number_input("Location conflict window (min)", min_value=1, max_value=60, value=5, step=1)
hour_threshold = st.sidebar.number_input("Hourly test threshold", min_value=1, max_value=60, value=8, step=1)
mode = st.sidebar.selectbox("Mode", ["Strict", "Balanced", "Exploratory"])

with st.expander("📁 Upload & Instructions", expanded=True):
    st.write("Upload a CSV or Excel file with these columns:")
    st.code("Timestamp, Operator_ID, Location, Device_ID, Test_Type", language="text")
    with open("POCTIFY_BarcodeSharing_Template.csv", "rb") as f:
        st.download_button("Download CSV Template", f, file_name="POCTIFY_Template.csv", mime="text/csv")
    st.dataframe(pd.read_csv("POCTIFY_BarcodeSharing_Template.csv").head())

uploaded_file = st.file_uploader("Upload POCT Middleware File (.csv or .xlsx)", type=["csv", "xlsx"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    required_cols = ["Timestamp", "Operator_ID", "Location", "Device_ID", "Test_Type"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"Missing columns: {', '.join(missing_cols)}")
        st.stop()

    df["Timestamp"] = pd.to_datetime(
        df["Timestamp"], errors="coerce", infer_datetime_format=True
    )
    if df["Timestamp"].isna().any():
        st.error(
            f"Failed to parse {df['Timestamp'].isna().sum()} timestamps. Example rows below:"
        )
        st.dataframe(df[df["Timestamp"].isna()].head())
        st.stop()

    df = df.sort_values(["Operator_ID", "Timestamp"])
    df['Time_Diff_Min'] = df.groupby('Operator_ID')['Timestamp'].diff().dt.total_seconds() / 60
    df['Prev_Location'] = df.groupby('Operator_ID')['Location'].shift()

    df['Rapid_Test'] = df['Time_Diff_Min'] < rapid_threshold
    df['Location_Conflict'] = (df['Location'] != df['Prev_Location']) & (df['Time_Diff_Min'] <= conflict_window)

    df['Hour'] = df['Timestamp'].dt.hour
    hourly_counts = df.groupby(['Operator_ID', 'Hour']).size().rename('Hour_Count')
    df = df.join(hourly_counts, on=['Operator_ID', 'Hour'])

    hourly_stats = hourly_counts.groupby('Operator_ID').agg(['mean', 'std'])
    hourly_stats.columns = ['Hour_Mean', 'Hour_Std']
    df = df.join(hourly_stats, on='Operator_ID')
    df['Hour_Z'] = (df['Hour_Count'] - df['Hour_Mean']) / df['Hour_Std'].replace({0: np.nan})
    df['High_Hour_Load'] = df['Hour_Count'] > hour_threshold

    df['Reason'] = ''
    df.loc[df['Rapid_Test'], 'Reason'] += 'RAPID+'
    df.loc[df['Location_Conflict'], 'Reason'] += 'LOC+'
    df.loc[df['High_Hour_Load'], 'Reason'] += 'HIGH_HR+'
    df['Reason'] = df['Reason'].str.rstrip('+')

    flagged_rows = df[df['Reason'] != '']

    summary = df.groupby('Operator_ID').agg(
        total_tests=('Operator_ID', 'size'),
        rapid_pct=('Rapid_Test', lambda x: 100 * x.sum() / len(x)),
        loc_pct=('Location_Conflict', lambda x: 100 * x.sum() / len(x)),
        hr_z=('Hour_Z', lambda x: np.nanmean(np.abs(x))),
        unique_devices=('Device_ID', 'nunique')
    )
    peak_hour = (
        df.groupby(['Operator_ID', 'Hour']).size()
        .groupby(level=0)
        .idxmax()
        .apply(lambda x: x[1])
    )
    summary = summary.join(peak_hour.rename('Most_Active_Hour'))
    summary['Suspicion_Score'] = (
        summary['rapid_pct']/100 + summary['loc_pct']/100 + summary['hr_z'].fillna(0) + summary['unique_devices']/summary['total_tests']
    )
    summary = summary.sort_values('Suspicion_Score', ascending=False)

    usage_by_location = df.groupby(['Operator_ID', 'Location']).size().unstack(fill_value=0)

    st.subheader("📄 Raw Data Preview")
    st.dataframe(df.head())

    st.subheader("🚩 Flagged Events")
    st.dataframe(flagged_rows[['Timestamp', 'Operator_ID', 'Location', 'Device_ID', 'Time_Diff_Min', 'Reason']])

    st.subheader("📊 Analytics Dashboard")
    fig_bar = px.bar(df.groupby('Hour').size().reset_index(name='Tests'), x='Hour', y='Tests', title='Tests per Hour')
    st.plotly_chart(fig_bar, use_container_width=True)

    heat = df.pivot_table(index='Operator_ID', columns='Hour', values='Test_Type', aggfunc='count', fill_value=0)
    fig_heat = px.imshow(heat, labels=dict(x="Hour", y="Operator", color="Tests"), title="Operator Usage Heatmap")
    st.plotly_chart(fig_heat, use_container_width=True)

    st.subheader("📋 Usage Report")
    st.dataframe(usage_by_location)
    st.dataframe(summary[['Most_Active_Hour', 'total_tests']])

    st.subheader("⬇️ Export Reports")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button("Flagged Rows CSV", flagged_rows.to_csv(index=False), file_name="flagged_rows.csv", mime="text/csv")
    with col2:
        st.download_button("Operator Summary CSV", summary.to_csv(), file_name="operator_summary.csv", mime="text/csv")
    with col3:
        png = pio.to_image(fig_bar, format='png')
        st.download_button("Download Plot PNG", png, file_name="tests_per_hour.png", mime="image/png")

