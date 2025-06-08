# dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO
import re
from clean_gusto_multi import process_gusto_upload
from quickbooks_parser import process_quickbooks_upload, generate_revenue_summary, generate_evaluation_counts, generate_service_bundle_analysis
from school_calendar import generate_school_day_analysis
import numpy as np
from datetime import datetime
import hashlib
import os
from pathlib import Path

# ========== PAGE CONFIG ==========
st.set_page_config(
    page_title="🧠 Lilypad Analytics",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== HEADER ==========
st.title("🧠 Lilypad Analytics Dashboard")
st.write("Analyze operational efficiency and financial performance for Lilypad Learning's evaluation services.")

# Simple file storage functions
def save_latest_file(uploaded_file, file_type):
    """Save uploaded file, replacing any previous file of the same type"""
    if uploaded_file is None:
        return
        
    # Create storage directory if it doesn't exist
    storage_dir = Path.home() / ".lilypad_cache"
    storage_dir.mkdir(exist_ok=True)
    
    # Save file with fixed name based on type
    file_path = storage_dir / f"{file_type}_latest.csv"
    
    # Get file content as bytes
    if isinstance(uploaded_file, (str, bytes)):
        content = uploaded_file if isinstance(uploaded_file, bytes) else uploaded_file.encode('utf-8')
    else:
        try:
            content = uploaded_file.read()
            uploaded_file.seek(0)  # Reset file pointer
        except AttributeError:
            content = uploaded_file.getvalue()
    
    with open(file_path, "wb") as f:
        f.write(content)

def load_latest_file(file_type):
    """Load the most recent file of given type if it exists"""
    file_path = Path.home() / ".lilypad_cache" / f"{file_type}_latest.csv"
    if file_path.exists():
        with open(file_path, "rb") as f:
            return f.read()
    return None

def clear_latest_file(file_type):
    """Clear the saved file of given type"""
    file_path = Path.home() / ".lilypad_cache" / f"{file_type}_latest.csv"
    if file_path.exists():
        file_path.unlink()

# ========== FILE UPLOADS ==========
with st.sidebar:
    st.header("📁 Upload Your Files")
    
    # QuickBooks file uploader
    quickbooks_file = st.file_uploader(
        "QuickBooks Financial Export (CSV)",
        type="csv",
        key="quickbooks_file",
        help="Upload the QuickBooks sales/revenue export"
    )
    
    # Gusto file uploader
    gusto_file = st.file_uploader(
        "Gusto Time Tracking Export (Optional, CSV)",
        type="csv",
        key="gusto_file",
        help="Upload the raw Gusto contractor hours export (optional)"
    )

# ========== DATA PROCESSING ==========
@st.cache_data
def load_and_process_data(quickbooks_file, gusto_file):
    qb_df = None
    gusto_df = None
    
    if quickbooks_file is None:
        st.warning("⚠️ Please upload QuickBooks financial data to begin analysis.")
        st.stop()
    
    # Process QuickBooks data
    try:
        st.info("Processing QuickBooks financial data...")
        qb_df = process_quickbooks_upload(quickbooks_file)
        if qb_df is not None and not qb_df.empty:
            st.success(f"✅ Successfully processed QuickBooks data ({len(qb_df)} records)")
        else:
            st.error("❌ No valid records found in QuickBooks file")
            st.stop()
    except Exception as e:
        st.error("❌ Error processing QuickBooks data:")
        st.error(str(e))
        st.stop()
    
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
qb_df, gusto_df = load_and_process_data(quickbooks_file, gusto_file)

# ========== FILTERS ==========
st.sidebar.header("🔎 Filters")

# Date range filter - use service dates
date_range = st.sidebar.date_input(
    "Service Date Range",
    value=(qb_df['Date'].min(), qb_df['Date'].max()),
    min_value=qb_df['Date'].min(),
    max_value=qb_df['Date'].max(),
    help="Filter by when evaluations were actually completed (service date)"
)

# District filter from QuickBooks data
districts = sorted(qb_df['District'].dropna().unique())
selected_districts = st.sidebar.multiselect(
    "Districts",
    districts,
    default=districts
)

# Apply filters to QuickBooks data
filtered_qb = qb_df[
    (qb_df['Date'].dt.date >= date_range[0]) &
    (qb_df['Date'].dt.date <= date_range[1]) &
    (qb_df['District'].isin(selected_districts))
]

# Apply filters to Gusto data if available
if gusto_df is not None:
    filtered_gusto = gusto_df[
        (gusto_df['Date'].dt.date >= date_range[0]) &
        (gusto_df['Date'].dt.date <= date_range[1]) &
        (gusto_df['District'].isin(selected_districts))
    ]
    
    # Psychologist filter only if Gusto data available
    psychologists = sorted(gusto_df['Psychologist'].dropna().unique())
    selected_psychs = st.sidebar.multiselect(
        "Psychologists (Optional)",
        psychologists,
        default=psychologists
    )
    filtered_gusto = filtered_gusto[filtered_gusto['Psychologist'].isin(selected_psychs)]

# ========== FINANCIAL METRICS ==========
st.header("💰 Financial Performance")
st.info("All metrics are based on service dates (when evaluations were completed) rather than invoice dates.")

# Calculate financial KPIs from QuickBooks data
total_revenue = filtered_qb['Amount'].sum()

# Count unique evaluations (excluding add-on services)
eval_mask = (
    ~filtered_qb['Service Type'].str.contains('Academic Testing|IEP Meeting|Setup|Remote', na=False, case=False)
)

# Count evaluations by evaluation number within each district
total_evals = filtered_qb[eval_mask].groupby(['District', 'Evaluation Number'])['Service Type'].count().shape[0]

avg_revenue_per_eval = total_revenue / total_evals if total_evals > 0 else 0

# Display financial KPIs
if gusto_df is not None:
    col1, col2, col3, col4 = st.columns(4)
    total_cost = filtered_gusto['Cost'].sum()
    gross_margin = total_revenue - total_cost
    margin_percent = (gross_margin / total_revenue * 100) if total_revenue > 0 else 0
else:
    col1, col2, col3 = st.columns(3)

col1.metric("Total Revenue", f"${total_revenue:,.2f}")
col2.metric("Total Evaluations", f"{total_evals:,}")
col3.metric("Avg Revenue/Eval", f"${avg_revenue_per_eval:,.2f}")
if gusto_df is not None:
    # Show Gross Profit with percentage without arrow
    col4.container().markdown(f"""
        <div style="padding: 0.5rem 0;">
            <div style="color: rgb(71, 85, 105); font-size: 0.875rem; font-weight: 500;">Gross Profit</div>
            <div style="color: rgb(17, 24, 39); font-size: 1.5rem; font-weight: 600; margin: 0.25rem 0;">${gross_margin:,.2f}</div>
            <div style="color: rgb(21, 128, 61); font-size: 0.875rem; font-weight: 500;">{margin_percent:.1f}%</div>
        </div>
    """, unsafe_allow_html=True)

# Monthly metrics
st.subheader("Monthly Analysis")

# Calculate monthly metrics
monthly_data = pd.DataFrame({
    'Revenue': filtered_qb.groupby('Month')['Amount'].sum(),
    'Evaluations': filtered_qb[eval_mask].groupby(['Month', 'District', 'Evaluation Number'])['Service Type'].count().reset_index().groupby('Month').size(),
})

if gusto_df is not None:
    # Calculate monthly costs and margins
    monthly_costs = filtered_gusto.groupby('Month')['Cost'].sum()
    monthly_data['Cost'] = monthly_costs
    monthly_data['Gross Margin'] = monthly_data['Revenue'] - monthly_data['Cost']
    monthly_data['Gross Margin %'] = (monthly_data['Gross Margin'] / monthly_data['Revenue'] * 100).round(1)

monthly_data['Avg Revenue Per Eval'] = monthly_data['Revenue'] / monthly_data['Evaluations']

# Display monthly metrics
col1, col2 = st.columns(2)

with col1:
    # Monthly revenue by service date
    fig = go.Figure(data=[
        go.Bar(
            x=monthly_data.index.astype(str),
            y=monthly_data['Revenue'],
            name='Revenue',
            text=[f"${x:,.0f}" for x in monthly_data['Revenue']],
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title="Monthly Revenue (by Service Date)",
        xaxis_title="Month",
        yaxis_title="Revenue ($)",
        showlegend=False,
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # Monthly evaluations by service date
    fig = go.Figure(data=[
        go.Bar(
            x=monthly_data.index.astype(str),
            y=monthly_data['Evaluations'],
            name='Evaluations',
            text=monthly_data['Evaluations'],
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title="Monthly Evaluations (by Service Date)",
        xaxis_title="Month",
        yaxis_title="Number of Evaluations",
        showlegend=False,
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

if gusto_df is not None:
    # Add gross margin chart
    fig = go.Figure()
    
    # Add bars for revenue and cost
    fig.add_trace(go.Bar(
        x=monthly_data.index.astype(str),
        y=monthly_data['Revenue'],
        name='Revenue',
        text=[f"${x:,.0f}" for x in monthly_data['Revenue']],
        textposition='auto',
    ))
    
    fig.add_trace(go.Bar(
        x=monthly_data.index.astype(str),
        y=monthly_data['Cost'],
        name='Cost',
        text=[f"${x:,.0f}" for x in monthly_data['Cost']],
        textposition='auto',
    ))
    
    # Add line for margin percentage
    fig.add_trace(go.Scatter(
        x=monthly_data.index.astype(str),
        y=monthly_data['Gross Margin %'],
        name='Gross Margin %',
        yaxis='y2',
        text=[f"{x:.1f}%" for x in monthly_data['Gross Margin %']],
        textposition='top center',
        mode='lines+markers+text',
        line=dict(width=2),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        title="Monthly Revenue, Cost, and Margin",
        xaxis_title="Month",
        yaxis_title="Amount ($)",
        yaxis2=dict(
            title="Margin %",
            overlaying='y',
            side='right',
            range=[0, 100]
        ),
        barmode='group',
        height=500,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)

# School Day Analysis section
st.header("📅 School Day Analysis")
st.info("""
This analysis shows revenue per school day, calculated by dividing each month's total revenue by the number of school days in that month.
This helps normalize revenue across months with different numbers of school days (e.g. February vs March).
""")

# Generate school day analysis
overall_metrics, monthly_school_metrics = generate_school_day_analysis(filtered_qb)

# Display overall metrics
col1, col2 = st.columns(2)

col1.metric(
    "Total Revenue",
    f"${overall_metrics['total_revenue']:,.2f}"
)

# Show Average Revenue per School Day with total days without arrow
col2.container().markdown(f"""
    <div style="padding: 0.5rem 0;">
        <div style="color: rgb(71, 85, 105); font-size: 0.875rem; font-weight: 500;">Average Revenue per School Day</div>
        <div style="color: rgb(17, 24, 39); font-size: 1.5rem; font-weight: 600; margin: 0.25rem 0;">${overall_metrics['avg_revenue_per_school_day']:,.2f}/day</div>
        <div style="color: rgb(21, 128, 61); font-size: 0.875rem; font-weight: 500;">{overall_metrics['total_school_days']} school days</div>
    </div>
""", unsafe_allow_html=True)

# Create monthly breakdown visualization
st.subheader("Monthly Revenue per School Day")

# Bar chart showing revenue per school day by month
fig = go.Figure()

fig.add_trace(go.Bar(
    x=monthly_school_metrics['Month'],
    y=monthly_school_metrics['revenue_per_school_day'],
    name='Revenue per School Day',
    text=[f"${x:,.0f}/day" for x in monthly_school_metrics['revenue_per_school_day']],
    textposition='auto',
))

fig.update_layout(
    title="Revenue per School Day (Normalized by Available School Days)",
    xaxis_title="Month",
    yaxis_title="Revenue per School Day ($)",
    showlegend=False,
    height=400
)

st.plotly_chart(fig, use_container_width=True)

# Display detailed metrics table
st.subheader("Monthly School Day Metrics")
st.write("""
This table shows the monthly breakdown of revenue and school days,
helping identify true monthly performance by accounting for the varying number of school days.
""")

# Format the monthly metrics for display
display_metrics = monthly_school_metrics.copy()
display_metrics['Total Revenue'] = display_metrics['total_revenue'].map('${:,.2f}'.format)
display_metrics['School Days in Month'] = display_metrics['school_days']
display_metrics['Revenue per School Day'] = display_metrics['revenue_per_school_day'].map('${:,.2f}'.format)

# Select and rename columns for display
display_cols = ['Month', 'Total Revenue', 'School Days in Month', 'Revenue per School Day']
st.dataframe(display_metrics[display_cols], use_container_width=True)

# Student-Based Margin Analysis
if gusto_df is not None:
    st.header("📊 Student-Based Margin Analysis")
    st.info("""
    This analysis tracks the full cost of servicing each student across the entire evaluation process:
    1. Initial planning
    2. Student evaluation (billing point)
    3. Report writing
    4. Follow-up meetings
    
    Costs may span multiple months, but are matched to the student's evaluation revenue.
    """)

    # Get evaluation data with student info
    eval_data = filtered_qb[eval_mask].copy()
    
    # Group by student and evaluation number to get total revenue
    student_revenue = (
        eval_data
        .groupby(['Student Initials', 'Evaluation Number'])
        .agg({
            'Amount': 'sum',
            'Date': 'min'  # Use first date as service date
        })
        .reset_index()
        .rename(columns={
            'Amount': 'Revenue',
            'Date': 'Service Date'
        })
    )
    
    # Add month for grouping
    student_revenue['Month'] = student_revenue['Service Date'].dt.to_period('M')
    
    # Ensure Gusto data has matching columns
    if 'Student Initials' not in filtered_gusto.columns:
        st.warning("⚠️ Gusto data is missing student information. Please ensure time entries are tagged with student initials.")
    else:
        # Group costs by student and evaluation
        student_costs = (
            filtered_gusto
            .groupby(['Student Initials'])
            .agg({
                'Cost': 'sum',
                'Hours': 'sum'
            })
            .reset_index()
            .rename(columns={
                'Cost': 'Total Cost',
                'Hours': 'Total Hours'
            })
        )
        
        # Merge revenue and costs
        student_analysis = pd.merge(
            student_revenue,
            student_costs,
            on=['Student Initials'],
            how='left'
        )
        
        # Calculate margins
        student_analysis['Total Cost'] = student_analysis['Total Cost'].fillna(0)
        student_analysis['Margin'] = student_analysis['Revenue'] - student_analysis['Total Cost']
        student_analysis['Margin %'] = (student_analysis['Margin'] / student_analysis['Revenue'] * 100).round(1)
        
        # Calculate monthly aggregates
        monthly_margins = (
            student_analysis
            .groupby('Month')
            .agg({
                'Revenue': 'sum',
                'Total Cost': 'sum',
                'Student Initials': 'nunique',
                'Evaluation Number': 'count'
            })
            .reset_index()
        )
        
        monthly_margins['Margin'] = monthly_margins['Revenue'] - monthly_margins['Total Cost']
        monthly_margins['Margin %'] = (monthly_margins['Margin'] / monthly_margins['Revenue'] * 100).round(1)
        monthly_margins = monthly_margins.rename(columns={
            'Student Initials': 'Unique Students',
            'Evaluation Number': 'Total Evaluations'
        })
        
        # Create visualization
        fig = go.Figure()
        
        # Add bars for revenue and cost
        fig.add_trace(go.Bar(
            x=monthly_margins['Month'].astype(str),
            y=monthly_margins['Revenue'],
            name='Revenue',
            text=[f"${x:,.0f}" for x in monthly_margins['Revenue']],
            textposition='auto',
        ))
        
        fig.add_trace(go.Bar(
            x=monthly_margins['Month'].astype(str),
            y=monthly_margins['Total Cost'],
            name='Total Cost',
            text=[f"${x:,.0f}" for x in monthly_margins['Total Cost']],
            textposition='auto',
        ))
        
        # Add line for margin percentage
        fig.add_trace(go.Scatter(
            x=monthly_margins['Month'].astype(str),
            y=monthly_margins['Margin %'],
            name='Margin %',
            yaxis='y2',
            text=[f"{x:.1f}%" for x in monthly_margins['Margin %']],
            textposition='top center',
            mode='lines+markers+text',
            line=dict(width=2),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title="Monthly Student-Based Revenue, Cost, and Margin",
            xaxis_title="Service Month",
            yaxis_title="Amount ($)",
            yaxis2=dict(
                title="Margin %",
                overlaying='y',
                side='right',
                range=[0, 100]
            ),
            barmode='group',
            height=500,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.write("""
        This table shows the monthly breakdown of student evaluations and their associated costs.
        The margin is calculated by matching each evaluation's revenue with the total cost of servicing that student.
        """)
        
        # Format the table
        display_table = monthly_margins.copy()
        display_table['Month'] = display_table['Month'].astype(str)
        display_table['Revenue'] = display_table['Revenue'].map('${:,.2f}'.format)
        display_table['Total Cost'] = display_table['Total Cost'].map('${:,.2f}'.format)
        display_table['Margin'] = display_table['Margin'].map('${:,.2f}'.format)
        display_table['Margin %'] = display_table['Margin %'].map('{:.1f}%'.format)
        
        st.dataframe(display_table, use_container_width=True)
        
        # Show individual student analysis
        st.subheader("Individual Student Analysis")
        st.write("""
        This table shows each evaluation and its associated costs:
        - Revenue from the evaluation
        - Total hours spent on the student
        - Total cost across all activities
        - Resulting margin for the complete evaluation
        """)
        
        # Format and display student details
        student_details = student_analysis.copy()
        student_details['Service Date'] = student_details['Service Date'].dt.strftime('%Y-%m-%d')
        student_details['Revenue'] = student_details['Revenue'].map('${:,.2f}'.format)
        student_details['Total Cost'] = student_details['Total Cost'].map('${:,.2f}'.format)
        student_details['Margin'] = student_details['Margin'].map('${:,.2f}'.format)
        student_details['Margin %'] = student_details['Margin %'].map('{:.1f}%'.format)
        
        # Reorder columns for display
        display_cols = [
            'Student Initials', 'Evaluation Number', 'Service Date',
            'Revenue', 'Total Hours', 'Total Cost', 'Margin', 'Margin %'
        ]
        st.dataframe(student_details[display_cols].sort_values(['Service Date', 'Student Initials']), use_container_width=True)

# After the main financial metrics, add cost breakdown
if gusto_df is not None and not filtered_gusto.empty:
    st.markdown("### 💰 Cost Breakdown")

    # Calculate costs by psychologist
    psych_costs = (
        filtered_gusto
        .groupby('Psychologist')
        .agg({
            'Hours': 'sum',
            'Cost': 'sum'
        })
        .round(2)
        .sort_values('Cost', ascending=False)
    )

    # Add total row
    total_row = pd.DataFrame({
        'Hours': [psych_costs['Hours'].sum()],
        'Cost': [psych_costs['Cost'].sum()]
    }, index=['Total'])

    psych_costs = pd.concat([psych_costs, total_row])

    # Format for display
    display_costs = psych_costs.copy()
    display_costs['Hours'] = display_costs['Hours'].map('{:,.1f}'.format)
    display_costs['Cost'] = display_costs['Cost'].map('${:,.2f}'.format)
    
    st.dataframe(display_costs, use_container_width=True)
else:
    st.info("Upload Gusto time tracking data to see cost breakdown by psychologist.")
