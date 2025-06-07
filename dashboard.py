# dashboard.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from io import StringIO
import re

st.set_page_config(page_title="Lilypad Analytics", layout="wide")
st.title("🧠 Lilypad Evaluation Dashboard")

# ========== FILE UPLOADS ==========
st.sidebar.header("📁 Upload Your Files")

eval_file = st.sidebar.file_uploader("Cleaned Evaluation CSV", type="csv", key="eval_file")
sales_file = st.sidebar.file_uploader("QuickBooks Sales Export (optional)", type="csv", key="sales_file")

@st.cache_data
def load_csv(file):
    return pd.read_csv(file)

if not eval_file:
    st.warning("Please upload at least the cleaned evaluation CSV.")
    st.stop()

df = load_csv(eval_file)
st.success("✅ Evaluation data loaded.")

sales_df = load_csv(sales_file) if sales_file else None
if sales_df is not None:
    st.success("✅ Sales data loaded.")

# ========== PREPROCESSING ==========
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df["Month"] = df["Date"].dt.to_period("M").astype(str)
df["Case ID"] = df["Student Initials"].fillna("") + " | " + df["District"].fillna("")
df["Initials"] = df["Student Initials"].str.upper().str.strip()

if sales_df is not None:
    sales_df["Date"] = pd.to_datetime(sales_df["Date"], errors="coerce")
    sales_df["Description"] = sales_df["Description"].astype(str)
    sales_df["Initials"] = sales_df["Description"].apply(
        lambda text: re.findall(r'\b[A-Z]{2,3}\b', text)[0] if re.findall(r'\b[A-Z]{2,3}\b', text) else None
    )
    sales_df["Initials"] = sales_df["Initials"].str.upper().str.strip()
    sales_df["Revenue"] = pd.to_numeric(sales_df["Amount"], errors="coerce")

    revenue_map = sales_df.groupby("Initials")["Revenue"].sum()
    df["Revenue"] = df["Initials"].map(revenue_map).fillna(0)
else:
    df["Revenue"] = 0

df["Margin"] = df["Revenue"] - df["Estimated Cost"]

# ========== SIDEBAR FILTERS ==========
st.sidebar.header("🔎 Filters")

months_all = sorted(df["Month"].dropna().unique())
districts_all = sorted(df["District"].dropna().unique())
psychs_all = sorted(df["Psychologist"].dropna().unique())

months = st.sidebar.multiselect("Month", months_all, default=months_all)
districts = st.sidebar.multiselect("District", districts_all, default=districts_all)
psychs = st.sidebar.multiselect("Psychologist", psychs_all, default=psychs_all)

filtered = df[
    df["Month"].isin(months) &
    df["District"].isin(districts) &
    df["Psychologist"].isin(psychs)
]

# ========== KPIs ==========
st.subheader("📊 Key Performance Indicators")
col1, col2, col3 = st.columns(3)
col1.metric("Total Hours", round(filtered["Estimated Hours"].sum(), 1))
col2.metric("Total Revenue", f"${filtered['Revenue'].sum():,.0f}")
col3.metric("Gross Margin", f"${filtered['Margin'].sum():,.0f}")

# ========== VISUALIZATION TABS ==========
tab1, tab2, tab3, tab4 = st.tabs([
    "Efficiency Over Time", "Margins by District", "Case Drilldown", "Efficiency vs Profit"
])

with tab1:
    st.markdown("### ⏳ Average Hours per Case (Monthly)")
    eff = (
        filtered.groupby("Month")
        .agg(Total_Hours=("Estimated Hours", "sum"), Cases=("Case ID", "nunique"))
        .assign(Hours_per_Case=lambda d: d["Total_Hours"] / d["Cases"])
        .reset_index()
    )
    fig, ax = plt.subplots()
    sns.lineplot(data=eff, x="Month", y="Hours_per_Case", marker="o", ax=ax)
    ax.set_ylabel("Hours per Case")
    st.pyplot(fig)

with tab2:
    st.markdown("### 💰 Financials by District & Month")
    monthly = (
        filtered.groupby(["Month", "District"])
        .agg(Revenue=("Revenue", "sum"), Cost=("Estimated Cost", "sum"))
        .assign(Margin=lambda d: d["Revenue"] - d["Cost"])
        .assign(Gross_Margin_Percent=lambda d: (d["Margin"] / d["Revenue"].replace(0, pd.NA)) * 100)
        .reset_index()
    )
    metric = st.selectbox("Choose Metric", ["Revenue", "Cost", "Margin", "Gross_Margin_Percent"])
    fig2, ax2 = plt.subplots(figsize=(12, 5))
    for district in monthly["District"].unique():
        district_data = monthly[monthly["District"] == district]
        ax2.plot(district_data["Month"], district_data[metric], marker="o", label=district)
    ax2.set_title(f"{metric} by District Over Time")
    ax2.legend()
    st.pyplot(fig2)

with tab3:
    st.markdown("### 🔍 Case-Level Data")
    selected_case = st.selectbox("Case ID", sorted(filtered["Case ID"].unique()))
    st.dataframe(filtered[filtered["Case ID"] == selected_case])

with tab4:
    st.markdown("### ⚖️ Hours vs Margin")
    scatter = (
        filtered.groupby("Case ID")
        .agg(Hours=("Estimated Hours", "sum"), Margin=("Margin", "sum"))
        .reset_index()
    )
    fig3, ax3 = plt.subplots()
    ax3.scatter(scatter["Hours"], scatter["Margin"], alpha=0.6)
    ax3.set_xlabel("Hours")
    ax3.set_ylabel("Margin")
    ax3.set_title("Efficiency vs Profitability")
    st.pyplot(fig3)
