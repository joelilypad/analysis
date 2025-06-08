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

# ========== PAGE CONFIG ==========
st.set_page_config(
    page_title="🧠 Lilypad Analytics",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== HEADER ==========
st.title("🧠 Lilypad Analytics Dashboard")
st.write("Analyze operational efficiency and financial performance for Lilypad Learning's evaluation services.")

# ========== FILE UPLOADS ==========
st.sidebar.header("📁 Upload Your Files")

quickbooks_file = st.sidebar.file_uploader(
    "QuickBooks Financial Export (CSV)",
    type="csv",
    key="quickbooks_file",
    help="Upload the QuickBooks sales/revenue export"
)

gusto_file = st.sidebar.file_uploader(
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
    (filtered_qb['Service Type'].isin([
        'Full Evaluation',
        'Cognitive Only',
        'Educational Only',
        'Bilingual Evaluation',
        'Spanish Evaluation',
        'Haitian Creole Evaluation',
        'Multilingual Evaluation'
    ])) |
    (filtered_qb['Service Type'].str.contains('Evaluation', na=False) & 
     ~filtered_qb['Service Type'].str.contains('Academic|IEP|Setup|Remote', na=False))
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
    col4.metric("Gross Margin", f"${gross_margin:,.2f}")

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
        title="Monthly Revenue, Cost, and Gross Margin %",
        xaxis_title="Month",
        yaxis_title="Amount ($)",
        yaxis2=dict(
            title="Gross Margin %",
            overlaying='y',
            side='right',
            range=[0, max(monthly_data['Gross Margin %']) * 1.2]  # Give some headroom
        ),
        height=400,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        barmode='group'
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Student-Based Margin Analysis
if gusto_df is not None:
    st.header("📊 Student-Based Margin Analysis")
    st.info("This analysis tracks the full cost of each evaluation across months, matching revenue with all associated costs even if they span multiple months.")

    # Get evaluation data with student info
    eval_data = filtered_qb[eval_mask].copy()
    
    # Group revenue by student and service date
    student_revenue = eval_data.groupby(['Student Initials', 'Evaluation Number', 'Month'])['Amount'].sum().reset_index()
    student_revenue = student_revenue.rename(columns={'Month': 'Service Month', 'Amount': 'Revenue'})
    
    # Ensure Gusto data has matching columns
    if 'Student Initials' not in filtered_gusto.columns:
        st.warning("⚠️ Gusto data is missing student information. Please ensure time entries are tagged with student initials.")
    else:
        # Group costs by student across all months
        student_costs = filtered_gusto.groupby(['Student Initials', 'Month'])['Cost'].sum().reset_index()
        student_costs = student_costs.rename(columns={'Month': 'Cost Month', 'Cost': 'Monthly Cost'})
        
        # Create a full analysis of students, their revenue, and costs across months
        student_analysis = pd.merge(
            student_revenue,
            student_costs,
            on=['Student Initials'],
            how='left'
        )
        
        # Calculate total cost per student
        total_student_costs = student_costs.groupby('Student Initials')['Monthly Cost'].sum().reset_index()
        total_student_costs = total_student_costs.rename(columns={'Monthly Cost': 'Total Cost'})
        
        # Add total costs to the analysis
        student_analysis = pd.merge(
            student_analysis,
            total_student_costs,
            on=['Student Initials'],
            how='left'
        )
        
        # Calculate margins
        student_analysis['Margin'] = student_analysis['Revenue'] - student_analysis['Total Cost']
        student_analysis['Margin %'] = (student_analysis['Margin'] / student_analysis['Revenue'] * 100).round(1)
        
        # Calculate monthly aggregates based on service month
        monthly_student_margins = student_analysis.groupby('Service Month').agg({
            'Revenue': 'sum',
            'Total Cost': 'sum',
            'Student Initials': 'nunique'
        }).reset_index()
        
        monthly_student_margins['Margin'] = monthly_student_margins['Revenue'] - monthly_student_margins['Total Cost']
        monthly_student_margins['Margin %'] = (monthly_student_margins['Margin'] / monthly_student_margins['Revenue'] * 100).round(1)
        monthly_student_margins = monthly_student_margins.rename(columns={'Student Initials': 'Unique Students'})
        
        # Create visualization
        fig = go.Figure()
        
        # Add bars for revenue and cost
        fig.add_trace(go.Bar(
            x=monthly_student_margins['Service Month'].astype(str),
            y=monthly_student_margins['Revenue'],
            name='Revenue',
            text=[f"${x:,.0f}" for x in monthly_student_margins['Revenue']],
            textposition='auto',
        ))
        
        fig.add_trace(go.Bar(
            x=monthly_student_margins['Service Month'].astype(str),
            y=monthly_student_margins['Total Cost'],
            name='Total Student Cost',
            text=[f"${x:,.0f}" for x in monthly_student_margins['Total Cost']],
            textposition='auto',
        ))
        
        # Add line for margin percentage
        fig.add_trace(go.Scatter(
            x=monthly_student_margins['Service Month'].astype(str),
            y=monthly_student_margins['Margin %'],
            name='True Margin %',
            yaxis='y2',
            text=[f"{x:.1f}%" for x in monthly_student_margins['Margin %']],
            textposition='top center',
            mode='lines+markers+text',
            line=dict(width=2),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title="Monthly Revenue vs Total Student Costs (by Service Date)",
            xaxis_title="Service Month",
            yaxis_title="Amount ($)",
            yaxis2=dict(
                title="Margin %",
                overlaying='y',
                side='right',
                range=[0, max(monthly_student_margins['Margin %']) * 1.2]  # Give some headroom
            ),
            height=400,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            barmode='group'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show detailed monthly breakdown
        st.subheader("Monthly Student-Based Analysis")
        st.write("""
        This table shows margins calculated by matching each student's revenue with their total costs, 
        even if those costs extend into future months. This gives a more accurate picture of true efficiency gains.
        """)
        
        # Format the table
        display_table = monthly_student_margins.copy()
        display_table['Revenue'] = display_table['Revenue'].map('${:,.2f}'.format)
        display_table['Total Cost'] = display_table['Total Cost'].map('${:,.2f}'.format)
        display_table['Margin'] = display_table['Margin'].map('${:,.2f}'.format)
        display_table['Margin %'] = display_table['Margin %'].map('{:.1f}%'.format)
        
        st.dataframe(display_table.set_index('Service Month'), use_container_width=True)
        
        # Show individual student analysis
        st.subheader("Individual Student Analysis")
        st.write("""
        This table shows the breakdown for each student, including their service month and all associated costs.
        This helps identify cases where evaluation work extends beyond the service month.
        """)
        
        # Format and display student details
        student_details = student_analysis.copy()
        student_details['Revenue'] = student_details['Revenue'].map('${:,.2f}'.format)
        student_details['Monthly Cost'] = student_details['Monthly Cost'].map('${:,.2f}'.format)
        student_details['Total Cost'] = student_details['Total Cost'].map('${:,.2f}'.format)
        student_details['Margin'] = student_details['Margin'].map('${:,.2f}'.format)
        student_details['Margin %'] = student_details['Margin %'].map('{:.1f}%'.format)
        
        st.dataframe(student_details.sort_values(['Service Month', 'Student Initials']), use_container_width=True)

# Service type breakdown by month
st.header("📊 Service Analysis")

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

# District Analysis
st.header("📍 District Analysis")

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

# Evaluations by district
district_evals = filtered_qb[eval_mask].groupby(['District', 'Evaluation Number'])['Service Type'].count().reset_index().groupby('District').size().sort_values(ascending=True)

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

# After the District Analysis section, add School Day Analysis
st.header("📅 School Day Analysis")
st.info("This analysis shows revenue per active school day, based on the typical Massachusetts public school calendar.")

# Generate school day analysis
overall_metrics, monthly_school_metrics = generate_school_day_analysis(filtered_qb)

# Display overall metrics
col1, col2 = st.columns(2)

col1.metric(
    "Total School Day Revenue",
    f"${overall_metrics['school_day_revenue']:,.2f}"
)

col2.metric(
    "Average Revenue per School Day",
    f"${overall_metrics['avg_revenue_per_school_day']:,.2f}/day"
)

# Create monthly breakdown visualization
st.subheader("Monthly Revenue per School Day")

# Calculate and display monthly revenue per school day
monthly_per_day = monthly_school_metrics.copy()
monthly_per_day['Revenue per School Day'] = (
    monthly_per_day['school_day_revenue'] / 
    monthly_per_day['school_days'].clip(lower=1)  # Avoid division by zero
)

# Bar chart showing revenue per school day by month
fig = go.Figure()

fig.add_trace(go.Bar(
    x=monthly_per_day['Month'].astype(str),
    y=monthly_per_day['Revenue per School Day'],
    name='Revenue per School Day',
    text=[f"${x:,.0f}/day" for x in monthly_per_day['Revenue per School Day']],
    textposition='auto',
))

fig.update_layout(
    title="Revenue per Active School Day",
    xaxis_title="Month",
    yaxis_title="Revenue per School Day ($)",
    showlegend=False,
    height=400
)

st.plotly_chart(fig, use_container_width=True)

# Display detailed metrics table
st.subheader("Monthly School Day Metrics")
st.write("""
This table shows the monthly breakdown of revenue and active school days,
helping identify which months are most efficient in terms of revenue per school day.
""")

# Format the monthly metrics for display
display_metrics = monthly_per_day.copy()
display_metrics['Month'] = display_metrics['Month'].astype(str)
display_metrics['Total Revenue'] = display_metrics['school_day_revenue'].map('${:,.2f}'.format)
display_metrics['Active School Days'] = display_metrics['school_days']
display_metrics['Revenue per School Day'] = display_metrics['Revenue per School Day'].map('${:,.2f}'.format)

# Select and rename columns for display
display_cols = ['Month', 'Total Revenue', 'Active School Days', 'Revenue per School Day']
st.dataframe(display_metrics[display_cols], use_container_width=True)
