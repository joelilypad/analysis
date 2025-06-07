# dashboard.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from io import StringIO

st.set_page_config(page_title="Lilypad Dashboard", layout="wide")
st.title("🧠 Lilypad Evaluation Dashboard")

# --- Sidebar File Uploads ---
st.sidebar.header("📁 Upload Your Files")

eval_file = st.sidebar.file_uploader("Upload Cleaned Evaluation CSV", type="csv", key="eval_file")
sales_file = st.sidebar.file_uploader("Upload QuickBooks Sales Export", type="csv", key="sales_file")

@st.cache_data
def load_csv(uploaded_file):
    return pd.read_csv(uploaded_file)

if eval_file:
    df = load_csv(eval_file)
    st.success("✅ Evaluation file loaded!")
else:
    st.warning("⚠️ Please upload the cleaned evaluation CSV.")

if sales_file:
    sales_df = load_csv(sales_file)
    st.success("✅ Sales (revenue) file loaded!")
else:
    st.warning("⚠️ You can optionally upload the revenue (QuickBooks) CSV.")

if not eval_file:
    st.stop()

# --- Preprocess Evaluation Data ---
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df["Month"] = df["Date"].dt.to_period("M").astype(str)
df["Case ID"] = df["Student Initials"].fillna("") + " | " + df["District"].fillna("")

# --- Join Sales Data to Evaluation if Provided ---
if sales_file:
    # Preprocess Sales Data
    sales_df["Date"] = pd.to_datetime(sales_df["Date"], errors="coerce")
    sales_df["Description"] = sales_df["Description"].astype(str)

    # Try to extract initials from sales line items
    def extract_initials(text):
        match = pd.Series(text).str.extract(r'([A-Z]{2,3})')[0]
        return match.str.strip().str.upper()

    sales_df["Initials"] = extract_initials(sales_df["Description"])
    sales_df["Revenue"] = pd.to_numeric(sales_df["Amount"], errors="coerce")

    # Join by Case ID or Initials+District heuristics
    merged_df = df.copy()
    merged_df["Initials"] = merged_df["Student Initials"].str.upper().str.strip()

    revenue_map = sales_df.groupby("Initials")["Revenue"].sum()
    merged_df["Revenue"] = merged_df["Initials"].map(revenue_map)

    # Estimate Margin
    merged_df["Revenue"].fillna(0, inplace=True)
    merged_df["Margin"] = merged_df["Revenue"] - merged_df["Estimated Cost"]
else:
    merged_df = df.copy()
    merged_df["Revenue"] = 0
    merged_df["Margin"] = -merged_df["Estimated Cost"]

# --- Sidebar Filters ---
st.sidebar.markdown("---")
st.sidebar.header("🔎 Filter Dashboard")
months = st.sidebar.multiselect("Select Month", sorted(merged_df["Month"].unique()))
districts = st.sidebar.multiselect("Select District", sorted(merged_df["District"].dropna().unique()))
psychs = st.sidebar.multiselect("Select Psychologist", sorted(merged_df["Psychologist"].dropna().unique()))

filtered = merged_df.copy()
if months: filtered = filtered[filtered["Month"].isin(months)]
if districts: filtered = filtered[filtered["District"].isin(districts)]
if psychs: filtered = filtered[filtered["Psychologist"].isin(psychs)]

# --- KPIs ---
st.subheader("📊 Key Metrics")
col1, col2, col3 = st.columns(3)
col1.metric("Total Hours", round(filtered["Estimated Hours"].sum(), 1))
col2.metric("Total Revenue", f"${filtered['Revenue'].sum():,.0f}")
col3.metric("Gross Margin", f"${filtered['Margin'].sum():,.0f}")

# --- Tabs for Deep Dives ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Efficiency Over Time", "Revenue vs Cost by District", "Case Drilldown", "Scatter & Correlation"
])

with tab1:
    st.markdown("### 📅 Efficiency Over Time")
    eff = (
        filtered.groupby("Month")
        .agg(Total_Hours=("Estimated Hours", "sum"), Cases=("Case ID", "nunique"))
        .assign(Hours_per_Case=lambda d: d["Total_Hours"] / d["Cases"])
        .reset_index()
    )
    fig, ax = plt.subplots()
    ax.plot(eff["Month"], eff["Hours_per_Case"], marker='o')
    ax.set_title("Average Hours per Case")
    st.pyplot(fig)

with tab2:
    st.markdown("### 🏫 Revenue, Cost, Margin by District & Month")
    monthly = (
        filtered.groupby(["Month", "District"])
        .agg(Revenue=("Revenue", "sum"), Cost=("Estimated Cost", "sum"))
        .assign(Margin=lambda d: d["Revenue"] - d["Cost"])
        .assign(Gross_Margin_Percent=lambda d: d["Margin"] / d["Revenue"] * 100)
        .reset_index()
    )
    selected_metric = st.selectbox("Metric", ["Revenue", "Cost", "Margin", "Gross_Margin_Percent"])
    fig2, ax2 = plt.subplots(figsize=(12, 5))
    for district in monthly["District"].unique():
        data = monthly[monthly["District"] == district]
        ax2.plot(data["Month"], data[selected_metric], label=district, marker='o')
    ax2.legend()
    ax2.set_title(f"{selected_metric} by District")
    st.pyplot(fig2)

with tab3:
    st.markdown("### 🔍 Case Drilldown")
    case = st.selectbox("Select Case ID", sorted(filtered["Case ID"].unique()))
    st.dataframe(filtered[filtered["Case ID"] == case])

with tab4:
    st.markdown("### 📉 Efficiency vs Margin")
    scatter = (
        filtered.groupby("Case ID")
        .agg(Hours=("Estimated Hours", "sum"), Margin=("Margin", "sum"))
        .reset_index()
    )
    fig3, ax3 = plt.subplots()
    ax3.scatter(scatter["Hours"], scatter["Margin"], alpha=0.6)
    ax3.set_xlabel("Hours")
    ax3.set_ylabel("Margin")
    ax3.set_title("Case Hours vs Margin")
    st.pyplot(fig3)
