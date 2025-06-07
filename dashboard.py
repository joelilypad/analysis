# dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO
import re
from clean_gusto_multi import process_gusto_upload
from quickbooks_parser import process_quickbooks_upload, generate_revenue_summary, generate_evaluation_counts, generate_service_bundle_analysis
import numpy as np

# ========== PAGE CONFIG ==========
st.set_page_config(
    page_title="🧠 Lilypad Analytics",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== CUSTOM CSS ==========
st.markdown("""
<style>
    /* Modern color scheme */
    :root {
        --primary: #2563eb;
        --primary-dark: #1d4ed8;
        --background: #ffffff;
        --card: #f8fafc;
        --card-foreground: #0f172a;
        --popover: #ffffff;
        --popover-foreground: #0f172a;
        --muted: #f1f5f9;
        --muted-foreground: #64748b;
        --border: #e2e8f0;
        --radius: 0.5rem;
    }

    /* Card-like containers */
    [data-testid="stMetric"] {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1rem;
        box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
    }
    
    /* Metric label styling */
    [data-testid="stMetricLabel"] {
        color: var(--muted-foreground);
        font-size: 0.875rem !important;
        font-weight: 500 !important;
    }
    
    /* Metric value styling */
    [data-testid="stMetricValue"] {
        color: var(--card-foreground);
        font-size: 1.875rem !important;
        font-weight: 600 !important;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1rem;
        border-bottom: 1px solid var(--border);
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.5rem 1rem;
        border-radius: var(--radius);
        font-weight: 500;
    }
    
    .stTabs [data-baseweb="tab-highlight"] {
        background: var(--primary);
    }
    
    /* Button styling */
    .stButton > button {
        border-radius: var(--radius);
        border: 1px solid var(--border);
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        border-color: var(--primary);
        color: var(--primary);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: var(--background);
        border-right: 1px solid var(--border);
    }
    
    /* File uploader styling */
    [data-testid="stFileUploader"] {
        border: 2px dashed var(--border);
        border-radius: var(--radius);
        padding: 1rem;
    }
    
    /* Chart container styling */
    [data-testid="stPlotlyChart"] {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ========== HEADER ==========
st.markdown("""
<div style='padding: 1rem 0; margin-bottom: 2rem;'>
    <h1 style='margin: 0; font-size: 2.25rem; font-weight: 600; color: #0f172a;'>
        🧠 Lilypad Analytics Dashboard
    </h1>
    <p style='margin-top: 0.5rem; color: #64748b; font-size: 1rem;'>
        Analyze operational efficiency and financial performance for Lilypad Learning's evaluation services.
    </p>
</div>
""", unsafe_allow_html=True)

# ========== FILE UPLOADS ==========
st.sidebar.markdown("""
<div style='margin-bottom: 2rem;'>
    <h2 style='font-size: 1.25rem; font-weight: 600; color: #0f172a; margin-bottom: 1rem;'>
        📁 Upload Your Files
    </h2>
</div>
""", unsafe_allow_html=True)

gusto_file = st.sidebar.file_uploader(
    "Gusto Time Tracking Export (CSV)",
    type="csv",
    key="gusto_file",
    help="Upload the raw Gusto contractor hours export"
)

quickbooks_file = st.sidebar.file_uploader(
    "QuickBooks Financial Export (CSV)",
    type="csv",
    key="quickbooks_file",
    help="Upload the QuickBooks sales/revenue export"
)

# ========== DATA PROCESSING ==========
@st.cache_data
def load_and_process_data(gusto_file, quickbooks_file):
    gusto_df = None
    qb_df = None
    
    # Process QuickBooks data if available
    if quickbooks_file:
        try:
            st.info("Processing QuickBooks financial data...")
            qb_df = process_quickbooks_upload(quickbooks_file)
            if qb_df is not None and not qb_df.empty:
                st.success(f"✅ Successfully processed QuickBooks data ({len(qb_df)} records)")
            else:
                st.warning("⚠️ No valid records found in QuickBooks file")
        except Exception as e:
            st.error("❌ Error processing QuickBooks data:")
            st.error(str(e))
    
    # Process Gusto data if available
    if gusto_file:
        try:
            st.info("Processing Gusto time tracking data...")
            gusto_df = process_gusto_upload(gusto_file)
            if gusto_df is not None and not gusto_df.empty:
                st.success(f"✅ Successfully processed Gusto time tracking data ({len(gusto_df)} records)")
            else:
                st.warning("⚠️ No valid records found in Gusto file")
        except Exception as e:
            st.warning("⚠️ Error processing Gusto data:")
            st.warning(str(e))
            
    return qb_df, gusto_df

# Load and process the data
qb_df, gusto_df = load_and_process_data(gusto_file, quickbooks_file)

if qb_df is None and gusto_df is None:
    st.warning("⚠️ Please upload either QuickBooks or Gusto data to begin analysis.")
    st.stop()

# ========== FILTERS ==========
st.sidebar.header("🔎 Filters")

# Date range filter - use QuickBooks dates if available, otherwise Gusto
if qb_df is not None:
    date_df = qb_df
elif gusto_df is not None:
    date_df = gusto_df

date_range = st.sidebar.date_input(
    "Date Range",
    value=(date_df['Date'].min(), date_df['Date'].max()),
    min_value=date_df['Date'].min(),
    max_value=date_df['Date'].max()
)

# District filter - combine districts from both sources if available
districts = []
if qb_df is not None:
    districts.extend(qb_df['District'].dropna().unique())
if gusto_df is not None:
    districts.extend(gusto_df['District'].dropna().unique())
districts = sorted(list(set(districts)))

selected_districts = st.sidebar.multiselect(
    "Districts",
    districts,
    default=districts
)

# Apply filters to both dataframes
if qb_df is not None:
    filtered_qb = qb_df[
        (qb_df['Date'].dt.date >= date_range[0]) &
        (qb_df['Date'].dt.date <= date_range[1]) &
        (qb_df['District'].isin(selected_districts))
    ]

if gusto_df is not None:
    filtered_gusto = gusto_df[
        (gusto_df['Date'].dt.date >= date_range[0]) &
        (gusto_df['Date'].dt.date <= date_range[1]) &
        (gusto_df['District'].isin(selected_districts))
    ]
    
    # Psychologist filter only if Gusto data available
    psychologists = sorted(gusto_df['Psychologist'].dropna().unique())
    selected_psychs = st.sidebar.multiselect(
        "Psychologists",
        psychologists,
        default=psychologists
    )
    filtered_gusto = filtered_gusto[filtered_gusto['Psychologist'].isin(selected_psychs)]

# ========== FINANCIAL METRICS ==========
st.header("💰 Financial Performance")

if qb_df is not None:
    # Calculate financial KPIs from QuickBooks data
    total_revenue = filtered_qb['Amount'].sum()
    
    # Count unique evaluations (excluding add-on services)
    eval_mask = filtered_qb['Service Type'].str.contains('Evaluation', na=False)
    total_evals = filtered_qb[eval_mask]['Student Initials'].nunique()
    
    avg_revenue_per_eval = total_revenue / total_evals if total_evals > 0 else 0
    
    # Calculate costs if Gusto data available
    if gusto_df is not None:
        total_cost = filtered_gusto['Cost'].sum()
        gross_margin = total_revenue - total_cost
        margin_percent = (gross_margin / total_revenue * 100) if total_revenue > 0 else 0
    else:
        total_cost = 0
        gross_margin = 0
        margin_percent = 0
    
    # Display financial KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Revenue", f"${total_revenue:,.2f}")
    col2.metric("Total Evaluations", f"{total_evals:,}")
    col3.metric("Avg Revenue/Eval", f"${avg_revenue_per_eval:,.2f}")
    if gusto_df is not None:
        col4.metric("Gross Margin", f"${gross_margin:,.2f}")
    
    # Service breakdown
    st.subheader("Service Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        # Revenue by service type
        service_revenue = filtered_qb.groupby('Service Type')['Amount'].sum().sort_values(ascending=True)
        
        # Create bar chart
        fig = go.Figure(data=[
            go.Bar(
                x=service_revenue.values,
                y=service_revenue.index,
                orientation='h',
                text=[f"${x:,.0f}" for x in service_revenue.values],
                textposition='auto',
            )
        ])
        
        fig.update_layout(
            title="Revenue by Service Type",
            xaxis_title="Revenue ($)",
            showlegend=False,
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Service bundle analysis
        bundle_revenue = filtered_qb.groupby('Service Bundle')['Amount'].sum().sort_values(ascending=True)
        
        # Create bar chart
        fig = go.Figure(data=[
            go.Bar(
                x=bundle_revenue.values,
                y=bundle_revenue.index,
                orientation='h',
                text=[f"${x:,.0f}" for x in bundle_revenue.values],
                textposition='auto',
            )
        ])
        
        fig.update_layout(
            title="Revenue by Service Bundle",
            xaxis_title="Revenue ($)",
            showlegend=False,
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    # District revenue analysis
    st.subheader("District Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        # Revenue by district
        district_revenue = filtered_qb.groupby('District')['Amount'].sum().sort_values(ascending=True)
        
        # Create bar chart
        fig = go.Figure(data=[
            go.Bar(
                x=district_revenue.values,
                y=district_revenue.index,
                orientation='h',
                text=[f"${x:,.0f}" for x in district_revenue.values],
                textposition='auto',
            )
        ])
        
        fig.update_layout(
            title="Revenue by District",
            xaxis_title="Revenue ($)",
            showlegend=False,
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Evaluations by district
        district_evals = filtered_qb[eval_mask].groupby('District')['Student Initials'].nunique().sort_values(ascending=True)
        
        # Create bar chart
        fig = go.Figure(data=[
            go.Bar(
                x=district_evals.values,
                y=district_evals.index,
                orientation='h',
                text=district_evals.values,
                textposition='auto',
            )
        ])
        
        fig.update_layout(
            title="Evaluations by District",
            xaxis_title="Number of Evaluations",
            showlegend=False,
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    # Monthly trends
    st.subheader("Monthly Trends")
    col1, col2 = st.columns(2)
    
    with col1:
        # Monthly revenue
        monthly_revenue = filtered_qb.groupby('Month')['Amount'].sum()
        
        # Create line chart
        fig = go.Figure(data=[
            go.Scatter(
                x=monthly_revenue.index.astype(str),
                y=monthly_revenue.values,
                mode='lines+markers',
                text=[f"${x:,.0f}" for x in monthly_revenue.values],
                textposition='top center',
            )
        ])
        
        fig.update_layout(
            title="Monthly Revenue",
            xaxis_title="Month",
            yaxis_title="Revenue ($)",
            showlegend=False,
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Monthly evaluations
        monthly_evals = filtered_qb[eval_mask].groupby('Month')['Student Initials'].nunique()
        
        # Create line chart
        fig = go.Figure(data=[
            go.Scatter(
                x=monthly_evals.index.astype(str),
                y=monthly_evals.values,
                mode='lines+markers',
                text=monthly_evals.values,
                textposition='top center',
            )
        ])
        
        fig.update_layout(
            title="Monthly Evaluations",
            xaxis_title="Month",
            yaxis_title="Number of Evaluations",
            showlegend=False,
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("⚠️ Upload QuickBooks data to view financial metrics")

# ========== TIME TRACKING ==========
if gusto_df is not None:
    st.header("⏱️ Time Tracking")
    st.warning("""
    ⚠️ Note: Time tracking data from Gusto may contain inconsistencies due to manual entry errors. 
    The financial metrics above provide more reliable information about completed evaluations.
    """)
    
    # Calculate time-based KPIs
    total_hours = filtered_gusto['Hours'].sum()
    avg_hours_per_eval = total_hours / total_evals if total_evals > 0 else 0
    
    # Display time KPIs
    col1, col2 = st.columns(2)
    col1.metric("Total Hours", f"{total_hours:,.1f}")
    col2.metric("Avg Hours/Eval", f"{avg_hours_per_eval:.1f}")
    
    # Time distribution
    st.subheader("Time Distribution")
    task_hours = filtered_gusto.groupby('Standardized Task')['Hours'].sum().sort_values(ascending=True)
    fig = px.bar(
        task_hours,
        orientation='h',
        title="Hours by Task Type",
        labels={'value': 'Total Hours', 'Standardized Task': 'Task'},
        color_discrete_sequence=CHART_THEME['colorway']
    )
    fig = style_chart(fig)
    st.plotly_chart(fig, use_container_width=True)
    
    # Time trends
    st.subheader("Time Trends")
    monthly_hours = filtered_gusto.groupby([pd.Grouper(key='Date', freq='M'), 'District'])['Hours'].sum().reset_index()
    fig = px.line(
        monthly_hours,
        x='Date',
        y='Hours',
        color='District',
        title="Monthly Hours by District",
        labels={'Date': 'Month', 'Hours': 'Total Hours'},
        color_discrete_sequence=CHART_THEME['colorway']
    )
    fig = style_chart(fig)
    st.plotly_chart(fig, use_container_width=True)

# ========== DOWNLOAD SECTION ==========
st.sidebar.header("📥 Download Data")

if st.sidebar.button("Download Processed Data"):
    # Prepare download data
    output = StringIO()
    
    if qb_df is not None:
        # Merge Gusto and QuickBooks data
        merged_df = pd.merge(
            filtered_gusto,
            filtered_qb,
            on=['District', 'Student Initials', 'Date'],
            how='outer',
            suffixes=('_time', '_revenue')
        )
    else:
        merged_df = filtered_gusto
    
    merged_df.to_csv(output, index=False)
    
    # Create download button
    st.sidebar.download_button(
        label="📥 Download CSV",
        data=output.getvalue(),
        file_name="lilypad_analytics_export.csv",
        mime="text/csv"
    )
