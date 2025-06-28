import pandas as pd
import streamlit as st
import io
import matplotlib.pyplot as plt

st.set_page_config(page_title="POCT Barcode Usage Monitor", layout="wide")
# Add logo
st.image("843eb762-d00e-44f5-a84d-0a5bc11089c5.png", width=200)
st.title("🔎 POCT Barcode Sharing Detector")

uploaded_file = st.file_uploader("Upload POCT Middleware CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    st.subheader("📄 Raw Data Preview")
    st.dataframe(df.head())

    df = df.sort_values(by=['Operator_ID', 'Timestamp'])
    df['Time_Diff'] = df.groupby('Operator_ID')['Timestamp'].diff().dt.total_seconds()
    df['Prev_Location'] = df.groupby('Operator_ID')['Location'].shift()
    df['Rapid_Test_Flag'] = df['Time_Diff'] < 60
    df['Location_Conflict'] = (df['Location'] != df['Prev_Location']) & (df['Time_Diff'] < 300)

    st.subheader("🚩 Suspicious Operator Summary")
    summary = df.groupby('Operator_ID')[['Rapid_Test_Flag', 'Location_Conflict']].sum()
    summary['Total_Flags'] = summary['Rapid_Test_Flag'] + summary['Location_Conflict']
    summary = summary.sort_values(by='Total_Flags', ascending=False)
    st.dataframe(summary)

    st.subheader("📊 Test Volume by Hour")
    df['Hour'] = df['Timestamp'].dt.hour
    test_volume = df.groupby('Hour').size()
    fig, ax = plt.subplots()
    test_volume.plot(kind='bar', ax=ax, color='skyblue')
    ax.set_title('Tests per Hour')
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Number of Tests')
    st.pyplot(fig)

    suspicious = df[df['Rapid_Test_Flag']]
    location_conflicts = df[df['Location_Conflict']]

    st.subheader("⬇️ Download Flagged Reports")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Download Rapid Usage Flags", suspicious.to_csv(index=False), file_name="rapid_flags.csv")
    with col2:
        st.download_button("Download Location Conflict Flags", location_conflicts.to_csv(index=False), file_name="location_flags.csv")
