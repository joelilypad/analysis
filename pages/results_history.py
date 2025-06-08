import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Results History - Lilypad Analysis",
    page_icon="📊",
    layout="wide"
)

st.title("📚 Analysis Results History")
st.write("This page shows the history of all analyses run in this session.")

# Initialize session state for history if it doesn't exist
if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = []

if not st.session_state.analysis_history:
    st.info("No analysis results available yet. Upload files in the main dashboard to see results here.")
else:
    # Display each analysis result
    for i, result in enumerate(reversed(st.session_state.analysis_history)):
        with st.expander(f"Analysis Run {len(st.session_state.analysis_history) - i}: {result['timestamp']}", expanded=(i == 0)):
            col1, col2 = st.columns(2)
            
            # Financial Metrics
            with col1:
                st.subheader("💰 Financial Overview")
                st.metric("Total Revenue", f"${result['total_revenue']:,.2f}")
                st.metric("Total Cost", f"${result['total_cost']:,.2f}")
                st.metric("Gross Margin", f"${result['gross_margin']:,.2f}")
                st.metric("Margin %", f"{result['margin_percent']:.1f}%")
            
            # Evaluation Metrics
            with col2:
                st.subheader("📊 Evaluation Metrics")
                st.metric("Total Evaluations", str(result['total_evals']))
                st.metric("Avg Revenue/Eval", f"${result['avg_revenue_per_eval']:,.2f}")
                st.metric("Districts Analyzed", str(len(result['districts'])))
                st.metric("Psychologists", str(len(result['psychologists'])))
            
            # Additional Details
            st.subheader("🔍 Analysis Details")
            st.write("Districts:", ", ".join(sorted(result['districts'])))
            st.write("Psychologists:", ", ".join(sorted(result['psychologists'])))
            st.write("Date Range:", f"{result['date_range'][0]} to {result['date_range'][1]}")
            
            # Monthly Data
            if result['monthly_data'] is not None:
                st.subheader("📅 Monthly Breakdown")
                st.dataframe(result['monthly_data']) 