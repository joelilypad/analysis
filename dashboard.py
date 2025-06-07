# dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO
import re
from clean_gusto_multi import process_gusto_upload
from quickbooks_parser import process_quickbooks_upload, generate_revenue_summary, generate_evaluation_counts

# ========== PAGE CONFIG ==========
st.set_page_config(
    page_title="🧠 Lilypad Analytics",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🧠 Lilypad Analytics Dashboard")
st.markdown("""
This dashboard helps analyze operational efficiency and financial performance for Lilypad Learning's
evaluation services. Upload your Gusto time tracking and QuickBooks financial data to get started.
""")

# ========== FILE UPLOADS ==========
st.sidebar.header("📁 Upload Your Files")

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
    if not gusto_file:
        st.warning("⚠️ Please upload the Gusto time tracking export to begin analysis.")
        return None, None
        
    try:
        # Process Gusto data
        gusto_df = process_gusto_upload(gusto_file)
        st.success("✅ Successfully processed Gusto time tracking data")
        
        # Process QuickBooks data if available
        qb_df = None
        if quickbooks_file:
            qb_df = process_quickbooks_upload(quickbooks_file)
            st.success("✅ Successfully processed QuickBooks financial data")
            
        return gusto_df, qb_df
        
    except Exception as e:
        st.error(f"❌ Error processing data: {str(e)}")
        return None, None

# Load and process the data
gusto_df, qb_df = load_and_process_data(gusto_file, quickbooks_file)

if gusto_df is None:
    st.stop()

# ========== FILTERS ==========
st.sidebar.header("🔎 Filters")

# Date range filter
date_range = st.sidebar.date_input(
    "Date Range",
    value=(gusto_df['Date'].min(), gusto_df['Date'].max()),
    min_value=gusto_df['Date'].min(),
    max_value=gusto_df['Date'].max()
)

# District filter
districts = sorted(gusto_df['District'].dropna().unique())
selected_districts = st.sidebar.multiselect(
    "Districts",
    districts,
    default=districts
)

# Psychologist filter
psychologists = sorted(gusto_df['Psychologist'].dropna().unique())
selected_psychs = st.sidebar.multiselect(
    "Psychologists",
    psychologists,
    default=psychologists
)

# Apply filters
filtered_df = gusto_df[
    (gusto_df['Date'].dt.date >= date_range[0]) &
    (gusto_df['Date'].dt.date <= date_range[1]) &
    (gusto_df['District'].isin(selected_districts)) &
    (gusto_df['Psychologist'].isin(selected_psychs))
]

if qb_df is not None:
    filtered_qb = qb_df[
        (qb_df['Date'].dt.date >= date_range[0]) &
        (qb_df['Date'].dt.date <= date_range[1]) &
        (qb_df['District'].isin(selected_districts))
    ]

# ========== KPI METRICS ==========
st.header("📊 Key Performance Indicators")

# Calculate KPIs
total_hours = filtered_df['Hours'].sum()
total_evals = len(filtered_df[filtered_df['Standardized Task'] == 'Testing']['Student Initials'].unique())
avg_hours_per_eval = total_hours / total_evals if total_evals > 0 else 0

# Financial KPIs if QuickBooks data available
if qb_df is not None:
    total_revenue = filtered_qb['Amount'].sum()
    avg_revenue_per_eval = total_revenue / total_evals if total_evals > 0 else 0
    total_cost = filtered_df['Cost'].sum()
    gross_margin = total_revenue - total_cost
    margin_percent = (gross_margin / total_revenue * 100) if total_revenue > 0 else 0
else:
    total_revenue = 0
    avg_revenue_per_eval = 0
    total_cost = filtered_df['Cost'].sum()
    gross_margin = 0
    margin_percent = 0

# Display KPIs in columns
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Hours", f"{total_hours:,.1f}")
col2.metric("Total Evaluations", f"{total_evals:,}")
col3.metric("Avg Hours/Eval", f"{avg_hours_per_eval:.1f}")
col4.metric("Total Revenue", f"${total_revenue:,.2f}" if qb_df is not None else "No data")
col5.metric("Gross Margin", f"${gross_margin:,.2f}" if qb_df is not None else "No data")

# ========== DETAILED ANALYSIS ==========
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⏱️ Time Analysis",
    "💰 Financial Analysis",
    "📈 Efficiency Metrics",
    "👥 Psychologist Analysis",
    "🔍 Case Details"
])

with tab1:
    st.subheader("Time Distribution")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Task breakdown
        task_hours = filtered_df.groupby('Standardized Task')['Hours'].sum().sort_values(ascending=True)
        fig = px.bar(
            task_hours,
            orientation='h',
            title="Hours by Task Type",
            labels={'value': 'Total Hours', 'Standardized Task': 'Task'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # District breakdown
        district_hours = filtered_df.groupby('District')['Hours'].sum().sort_values(ascending=True)
        fig = px.bar(
            district_hours,
            orientation='h',
            title="Hours by District",
            labels={'value': 'Total Hours', 'District': 'District'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Time trends
    st.subheader("Time Trends")
    monthly_hours = filtered_df.groupby([pd.Grouper(key='Date', freq='M'), 'District'])['Hours'].sum().reset_index()
    fig = px.line(
        monthly_hours,
        x='Date',
        y='Hours',
        color='District',
        title="Monthly Hours by District"
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    if qb_df is not None:
        st.subheader("Financial Performance")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Revenue by district
            district_revenue = filtered_qb.groupby('District')['Amount'].sum().sort_values(ascending=True)
            fig = px.bar(
                district_revenue,
                orientation='h',
                title="Revenue by District",
                labels={'value': 'Revenue ($)', 'District': 'District'}
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Revenue by service type
            service_revenue = filtered_qb.groupby('Service Type')['Amount'].sum().sort_values(ascending=True)
            fig = px.bar(
                service_revenue,
                orientation='h',
                title="Revenue by Service Type",
                labels={'value': 'Revenue ($)', 'Service Type': 'Service Type'}
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Revenue trends
        st.subheader("Revenue Trends")
        monthly_revenue = filtered_qb.groupby([pd.Grouper(key='Date', freq='M'), 'District'])['Amount'].sum().reset_index()
        fig = px.line(
            monthly_revenue,
            x='Date',
            y='Amount',
            color='District',
            title="Monthly Revenue by District"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Margin analysis
        st.subheader("Margin Analysis")
        
        # Merge Gusto and QuickBooks data
        margin_df = pd.DataFrame({
            'District': filtered_qb.groupby('District')['Amount'].sum().index,
            'Revenue': filtered_qb.groupby('District')['Amount'].sum().values,
            'Cost': filtered_df.groupby('District')['Cost'].sum()
        }).fillna(0)
        
        margin_df['Margin'] = margin_df['Revenue'] - margin_df['Cost']
        margin_df['Margin %'] = (margin_df['Margin'] / margin_df['Revenue'] * 100).round(1)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Revenue',
            y=margin_df['District'],
            x=margin_df['Revenue'],
            orientation='h'
        ))
        fig.add_trace(go.Bar(
            name='Cost',
            y=margin_df['District'],
            x=margin_df['Cost'],
            orientation='h'
        ))
        fig.update_layout(
            barmode='overlay',
            title="Revenue vs Cost by District",
            xaxis_title="Amount ($)",
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Display margin table
        st.dataframe(
            margin_df.sort_values('Margin', ascending=False),
            hide_index=True
        )
    else:
        st.info("📝 Upload QuickBooks data to view financial analysis")

with tab3:
    st.subheader("Efficiency Metrics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Hours per evaluation by district
        eval_hours = filtered_df[filtered_df['Standardized Task'] == 'Testing'].groupby('District')['Hours'].sum()
        eval_counts = filtered_df[filtered_df['Standardized Task'] == 'Testing'].groupby('District')['Student Initials'].nunique()
        hours_per_eval = (eval_hours / eval_counts).sort_values(ascending=True)
        
        fig = px.bar(
            hours_per_eval,
            orientation='h',
            title="Average Hours per Evaluation by District",
            labels={'value': 'Hours per Evaluation', 'District': 'District'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Task distribution within evaluations
        eval_tasks = filtered_df[filtered_df['Student Initials'].notna()]
        task_dist = eval_tasks.groupby('Standardized Task')['Hours'].sum()
        fig = px.pie(
            values=task_dist.values,
            names=task_dist.index,
            title="Time Distribution Across Evaluation Tasks"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Efficiency trends
    monthly_efficiency = (
        filtered_df[filtered_df['Standardized Task'] == 'Testing']
        .groupby([pd.Grouper(key='Date', freq='M'), 'District'])
        .agg(
            Hours=('Hours', 'sum'),
            Evaluations=('Student Initials', 'nunique')
        )
        .reset_index()
    )
    monthly_efficiency['Hours per Eval'] = monthly_efficiency['Hours'] / monthly_efficiency['Evaluations']
    
    fig = px.line(
        monthly_efficiency,
        x='Date',
        y='Hours per Eval',
        color='District',
        title="Evaluation Efficiency Trends by District"
    )
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("Psychologist Performance")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Hours by psychologist
        psych_hours = filtered_df.groupby('Psychologist')['Hours'].sum().sort_values(ascending=True)
        fig = px.bar(
            psych_hours,
            orientation='h',
            title="Total Hours by Psychologist",
            labels={'value': 'Total Hours', 'Psychologist': 'Psychologist'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Evaluations by psychologist
        psych_evals = filtered_df[filtered_df['Standardized Task'] == 'Testing'].groupby('Psychologist')['Student Initials'].nunique()
        fig = px.bar(
            psych_evals,
            orientation='h',
            title="Total Evaluations by Psychologist",
            labels={'value': 'Number of Evaluations', 'Psychologist': 'Psychologist'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Efficiency comparison
    psych_efficiency = pd.DataFrame({
        'Hours': psych_hours,
        'Evaluations': psych_evals
    }).fillna(0)
    psych_efficiency['Hours per Eval'] = psych_efficiency['Hours'] / psych_efficiency['Evaluations']
    psych_efficiency = psych_efficiency.sort_values('Hours per Eval')
    
    fig = px.bar(
        psych_efficiency,
        y=psych_efficiency.index,
        x='Hours per Eval',
        title="Average Hours per Evaluation by Psychologist",
        labels={'Hours per Eval': 'Hours per Evaluation', 'index': 'Psychologist'}
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Task distribution by psychologist
    task_dist = pd.crosstab(
        filtered_df['Psychologist'],
        filtered_df['Standardized Task'],
        values=filtered_df['Hours'],
        aggfunc='sum'
    ).fillna(0)
    
    fig = px.imshow(
        task_dist,
        title="Task Distribution Heat Map",
        labels={'x': 'Task', 'y': 'Psychologist', 'color': 'Hours'}
    )
    st.plotly_chart(fig, use_container_width=True)

with tab5:
    st.subheader("Case-Level Details")
    
    # Case selector
    cases = filtered_df['Student Initials'].dropna().unique()
    selected_case = st.selectbox("Select Student Case", cases)
    
    if selected_case:
        case_data = filtered_df[filtered_df['Student Initials'] == selected_case]
        
        # Case summary
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Hours", f"{case_data['Hours'].sum():.1f}")
        col2.metric("District", case_data['District'].iloc[0])
        col3.metric("Psychologist", case_data['Psychologist'].iloc[0])
        
        if qb_df is not None:
            case_revenue = filtered_qb[filtered_qb['Student Initials'] == selected_case]['Amount'].sum()
            col4.metric("Revenue", f"${case_revenue:,.2f}")
        
        # Task breakdown
        st.write("Task Breakdown")
        task_breakdown = case_data.groupby('Standardized Task')['Hours'].sum().reset_index()
        fig = px.pie(
            task_breakdown,
            values='Hours',
            names='Standardized Task',
            title="Hours by Task Type"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Detailed timeline
        st.write("Timeline")
        st.dataframe(
            case_data[['Date', 'Standardized Task', 'Hours', 'Note']]
            .sort_values('Date'),
            hide_index=True
        )

# ========== DOWNLOAD SECTION ==========
st.sidebar.header("📥 Download Data")

if st.sidebar.button("Download Processed Data"):
    # Prepare download data
    output = StringIO()
    
    if qb_df is not None:
        # Merge Gusto and QuickBooks data
        merged_df = pd.merge(
            filtered_df,
            filtered_qb,
            on=['District', 'Student Initials', 'Date'],
            how='outer',
            suffixes=('_time', '_revenue')
        )
    else:
        merged_df = filtered_df
    
    merged_df.to_csv(output, index=False)
    
    # Create download button
    st.sidebar.download_button(
        label="📥 Download CSV",
        data=output.getvalue(),
        file_name="lilypad_analytics_export.csv",
        mime="text/csv"
    )
