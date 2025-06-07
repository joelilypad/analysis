# dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO
import re
from clean_gusto_multi import process_gusto_upload
from quickbooks_parser import process_quickbooks_upload, generate_revenue_summary, generate_evaluation_counts
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
    if not gusto_file:
        st.warning("⚠️ Please upload the Gusto time tracking export to begin analysis.")
        return None, None
        
    try:
        # Process Gusto data
        st.info("Processing Gusto time tracking data...")
        gusto_df = process_gusto_upload(gusto_file)
        if gusto_df is not None and not gusto_df.empty:
            st.success(f"✅ Successfully processed Gusto time tracking data ({len(gusto_df)} records)")
        else:
            st.error("❌ No valid records found in Gusto file")
            return None, None
        
        # Process QuickBooks data if available
        qb_df = None
        if quickbooks_file:
            st.info("Processing QuickBooks financial data...")
            qb_df = process_quickbooks_upload(quickbooks_file)
            if qb_df is not None and not qb_df.empty:
                st.success(f"✅ Successfully processed QuickBooks data ({len(qb_df)} records)")
            else:
                st.warning("⚠️ No valid records found in QuickBooks file")
            
        return gusto_df, qb_df
        
    except Exception as e:
        import traceback
        st.error("❌ Error processing data:")
        st.error(str(e))
        st.error("Detailed error information:")
        st.code(traceback.format_exc())
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
    "�� Case Details"
])

# ========== CHART STYLING ==========
CHART_THEME = {
    'font_family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    'background_color': '#ffffff',
    'paper_bgcolor': '#ffffff',
    'plot_bgcolor': '#ffffff',
    'font_color': '#0f172a',
    'grid_color': '#e2e8f0',
    'colorway': ['#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe']
}

def style_chart(fig):
    """Apply consistent styling to Plotly charts"""
    fig.update_layout(
        font_family=CHART_THEME['font_family'],
        plot_bgcolor=CHART_THEME['plot_bgcolor'],
        paper_bgcolor=CHART_THEME['paper_bgcolor'],
        font_color=CHART_THEME['font_color'],
        title_font_size=18,
        title_font_color='#0f172a',
        title_font_family=CHART_THEME['font_family'],
        title_x=0,
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='#e2e8f0'
        ),
        margin=dict(t=40, r=20, b=40, l=20)
    )
    
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=CHART_THEME['grid_color'],
        zeroline=False,
        showline=True,
        linewidth=1,
        linecolor='#e2e8f0'
    )
    
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=CHART_THEME['grid_color'],
        zeroline=False,
        showline=True,
        linewidth=1,
        linecolor='#e2e8f0'
    )
    
    return fig

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
            labels={'value': 'Total Hours', 'Standardized Task': 'Task'},
            color_discrete_sequence=CHART_THEME['colorway']
        )
        fig = style_chart(fig)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # District breakdown
        district_hours = filtered_df.groupby('District')['Hours'].sum().sort_values(ascending=True)
        fig = px.bar(
            district_hours,
            orientation='h',
            title="Hours by District",
            labels={'value': 'Total Hours', 'District': 'District'},
            color_discrete_sequence=CHART_THEME['colorway']
        )
        fig = style_chart(fig)
        st.plotly_chart(fig, use_container_width=True)
    
    # Time trends
    st.subheader("Time Trends")
    monthly_hours = filtered_df.groupby([pd.Grouper(key='Date', freq='M'), 'District'])['Hours'].sum().reset_index()
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
        
        # Get all unique districts from both datasets
        all_districts = sorted(set(filtered_qb['District'].unique()) | set(filtered_df['District'].unique()))
        
        # Create revenue and cost series with consistent indices
        revenue_by_district = filtered_qb.groupby('District')['Amount'].sum()
        cost_by_district = filtered_df.groupby('District')['Cost'].sum()
        
        # Create DataFrame with aligned indices
        margin_df = pd.DataFrame(index=all_districts)
        margin_df['Revenue'] = revenue_by_district
        margin_df['Cost'] = cost_by_district
        margin_df = margin_df.fillna(0)
        
        # Calculate margins
        margin_df['Margin'] = margin_df['Revenue'] - margin_df['Cost']
        margin_df['Margin %'] = (margin_df['Margin'] / margin_df['Revenue'] * 100).round(1)
        margin_df = margin_df.replace([np.inf, -np.inf], 0)
        
        # Sort by margin
        margin_df = margin_df.sort_values('Margin', ascending=True)
        
        # Create waterfall chart
        fig = go.Figure()
        
        # Revenue bars
        fig.add_trace(go.Bar(
            name='Revenue',
            y=margin_df.index,
            x=margin_df['Revenue'],
            orientation='h',
            marker_color='rgb(44, 160, 44)'
        ))
        
        # Cost bars
        fig.add_trace(go.Bar(
            name='Cost',
            y=margin_df.index,
            x=-margin_df['Cost'],  # Negative to show on left side
            orientation='h',
            marker_color='rgb(214, 39, 40)'
        ))
        
        # Margin text annotations
        for idx, row in margin_df.iterrows():
            fig.add_annotation(
                y=idx,
                x=max(row['Revenue'], row['Cost']) + 1000,  # Offset from the larger bar
                text=f"Margin: ${row['Margin']:,.0f} ({row['Margin %']:,.1f}%)",
                showarrow=False,
                font=dict(size=10)
            )
        
        fig.update_layout(
            title="Revenue vs Cost by District",
            barmode='overlay',
            bargap=0.1,
            xaxis_title="Amount ($)",
            showlegend=True,
            height=max(400, len(margin_df) * 50)  # Dynamic height based on number of districts
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Download button for margin analysis
        st.download_button(
            "📥 Download Margin Analysis",
            margin_df.to_csv(index=True),
            "margin_analysis.csv",
            "text/csv",
            key='download-margin-csv'
        )
    else:
        st.info("📝 Upload QuickBooks data to view financial analysis")

with tab3:
    st.subheader("Efficiency Metrics")
    
    # Hours per evaluation by district
    eval_efficiency = filtered_df[filtered_df['Standardized Task'] == 'Testing'].groupby('District').agg({
        'Hours': 'sum',
        'Student Initials': 'nunique'
    }).reset_index()
    
    eval_efficiency['Hours per Evaluation'] = (eval_efficiency['Hours'] / eval_efficiency['Student Initials']).round(1)
    eval_efficiency = eval_efficiency.sort_values('Hours per Evaluation', ascending=True)
    
    fig = px.bar(
        eval_efficiency,
        x='Hours per Evaluation',
        y='District',
        orientation='h',
        title="Average Hours per Evaluation by District",
        labels={'Hours per Evaluation': 'Hours', 'District': 'District'}
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Task distribution heatmap
    st.subheader("Task Distribution by District")
    
    task_dist = pd.pivot_table(
        filtered_df,
        values='Hours',
        index='District',
        columns='Standardized Task',
        aggfunc='sum',
        fill_value=0
    )
    
    # Convert to percentages
    task_dist_pct = task_dist.div(task_dist.sum(axis=1), axis=0) * 100
    
    fig = px.imshow(
        task_dist_pct.T,  # Transpose for better visualization
        title="Task Distribution Heat Map (%)",
        labels=dict(x="District", y="Task", color="Percentage"),
        aspect="auto",
        color_continuous_scale="RdYlBu_r"
    )
    
    fig.update_layout(
        height=max(400, len(task_dist_pct.columns) * 30)  # Dynamic height based on number of tasks
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Efficiency trends over time
    st.subheader("Efficiency Trends")
    
    monthly_efficiency = filtered_df[filtered_df['Standardized Task'] == 'Testing'].groupby(
        [pd.Grouper(key='Date', freq='M'), 'District']
    ).agg({
        'Hours': 'sum',
        'Student Initials': 'nunique'
    }).reset_index()
    
    monthly_efficiency['Hours per Evaluation'] = (monthly_efficiency['Hours'] / monthly_efficiency['Student Initials']).round(1)
    
    fig = px.line(
        monthly_efficiency,
        x='Date',
        y='Hours per Evaluation',
        color='District',
        title="Monthly Hours per Evaluation by District"
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Download buttons for efficiency metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            "📥 Download District Efficiency",
            eval_efficiency.to_csv(index=False),
            "district_efficiency.csv",
            "text/csv",
            key='download-efficiency-csv'
        )
    
    with col2:
        st.download_button(
            "📥 Download Task Distribution",
            task_dist.to_csv(index=True),
            "task_distribution.csv",
            "text/csv",
            key='download-taskdist-csv'
        )

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
