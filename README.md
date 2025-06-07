# Lilypad Analytics Dashboard

A Streamlit-based analytics dashboard for analyzing operational efficiency and financial performance of Lilypad Learning's evaluation services.

## Overview

This dashboard helps track and analyze KPIs across every layer—student, psychologist, district, and time. It processes raw time tracking data from Gusto and financial data from QuickBooks to provide insights into:

- Evaluation efficiency and costs
- Revenue and margin analysis
- Psychologist performance
- District-level trends
- Case-level details

## Features

- **Time Analysis**
  - Task distribution
  - Hours by district
  - Monthly trends

- **Financial Analysis**
  - Revenue by district and service type
  - Revenue trends
  - Margin analysis

- **Efficiency Metrics**
  - Hours per evaluation by district
  - Task distribution
  - Efficiency trends

- **Psychologist Analysis**
  - Hours and evaluations by psychologist
  - Efficiency comparison
  - Task distribution heat map

- **Case Details**
  - Individual case metrics
  - Task breakdown
  - Timeline view

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the dashboard:
   ```bash
   streamlit run dashboard.py
   ```

## Usage

1. Upload your Gusto time tracking export
2. Upload your QuickBooks sales export (optional)
3. Use the filters to select date ranges, districts, and psychologists
4. Explore the various tabs for different analyses
5. Download processed data for further analysis

## File Structure

- `dashboard.py` - Main Streamlit application
- `clean_gusto_multi.py` - Gusto data processing pipeline
- `quickbooks_parser.py` - QuickBooks data processing pipeline
- `requirements.txt` - Python dependencies

## Data Requirements

### Gusto Export
- Time tracking data with contractor hours
- Notes should follow the format: `TIME > DISTRICT > STUDENT > TASK - DETAILS`

### QuickBooks Export
- Sales by Customer Detail report
- Should include transaction details, line items, and customer information 