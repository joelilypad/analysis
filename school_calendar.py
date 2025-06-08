import pandas as pd
from datetime import datetime, timedelta

def is_school_day(date):
    """
    Determine if a given date is a school day in Massachusetts.
    Based on typical MA public school calendar.
    """
    # Convert to datetime if string
    if isinstance(date, str):
        date = pd.to_datetime(date)
    
    # Weekend check
    if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    # Major holidays and breaks
    holidays = {
        # Labor Day (First Monday in September)
        lambda d: d.month == 9 and d.weekday() == 0 and d.day <= 7,
        
        # Indigenous Peoples Day (Second Monday in October)
        lambda d: d.month == 10 and d.weekday() == 0 and 8 <= d.day <= 14,
        
        # Veterans Day (November 11)
        lambda d: d.month == 11 and d.day == 11,
        
        # Thanksgiving Break (Fourth Thursday in November + Friday)
        lambda d: d.month == 11 and d.weekday() == 3 and d.day >= 22 and d.day <= 28,
        lambda d: d.month == 11 and d.weekday() == 4 and d.day >= 23 and d.day <= 29,
        
        # Winter Break (December 24 - January 1)
        lambda d: (d.month == 12 and d.day >= 24) or (d.month == 1 and d.day <= 1),
        
        # Martin Luther King Jr. Day (Third Monday in January)
        lambda d: d.month == 1 and d.weekday() == 0 and 15 <= d.day <= 21,
        
        # February Break (Third week in February)
        lambda d: d.month == 2 and 15 <= d.day <= 23,
        
        # April Break (Third week in April)
        lambda d: d.month == 4 and 15 <= d.day <= 23,
        
        # Memorial Day (Last Monday in May)
        lambda d: d.month == 5 and d.weekday() == 0 and d.day >= 25,
        
        # Summer Break (Late June through August)
        lambda d: d.month == 6 and d.day >= 20,
        lambda d: d.month == 7,
        lambda d: d.month == 8
    }
    
    # Check if date falls on any holiday
    for holiday_check in holidays:
        if holiday_check(date):
            return False
    
    return True

def get_school_days_in_range(start_date, end_date):
    """
    Get all school days between start_date and end_date (inclusive).
    """
    # Convert to datetime if strings
    if isinstance(start_date, str):
        start_date = pd.to_datetime(start_date)
    if isinstance(end_date, str):
        end_date = pd.to_datetime(end_date)
    
    # Generate all dates in range
    dates = pd.date_range(start=start_date, end=end_date)
    
    # Filter to school days
    school_days = [d for d in dates if is_school_day(d)]
    
    return school_days

def calculate_school_day_metrics(df):
    """
    Calculate metrics based on school days for the given DataFrame.
    Expects a DataFrame with 'Date' column and 'Amount' column.
    """
    # Ensure Date column is datetime
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Get the full range of months in the data
    start_date = df['Date'].min().replace(day=1)
    end_date = df['Date'].max().replace(day=1) + pd.offsets.MonthEnd(1)
    
    # Get all possible dates in range
    all_dates = pd.date_range(start=start_date, end=end_date)
    
    # Create a mapping of dates to school days
    school_day_map = {d: is_school_day(d) for d in all_dates}
    
    # Calculate school days per month
    monthly_school_days = (
        pd.DataFrame(index=all_dates)
        .assign(is_school_day=lambda df: df.index.map(school_day_map))
        .reset_index()
        .rename(columns={'index': 'Date'})
        .assign(Month=lambda df: df['Date'].dt.to_period('M'))
        .groupby('Month')['is_school_day']
        .sum()
    )
    
    # Calculate revenue per month
    monthly_revenue = df.groupby(df['Date'].dt.to_period('M'))['Amount'].sum()
    
    # Combine into metrics
    metrics = pd.DataFrame({
        'total_revenue': monthly_revenue,
        'school_days': monthly_school_days
    }).fillna(0)
    
    # Calculate revenue per school day
    metrics['revenue_per_school_day'] = (
        metrics['total_revenue'] / metrics['school_days'].clip(lower=1)
    )
    
    # Calculate overall metrics
    overall_metrics = {
        'total_revenue': metrics['total_revenue'].sum(),
        'total_school_days': metrics['school_days'].sum(),
        'avg_revenue_per_school_day': (
            metrics['total_revenue'].sum() / metrics['school_days'].sum()
            if metrics['school_days'].sum() > 0 else 0
        )
    }
    
    return overall_metrics, metrics

def generate_school_day_analysis(df):
    """
    Generate a detailed analysis of revenue by school days.
    Returns both summary metrics and monthly breakdown.
    """
    # Calculate metrics
    overall_metrics, monthly_metrics = calculate_school_day_metrics(df)
    
    # Convert monthly metrics to DataFrame with month as column
    monthly_df = monthly_metrics.reset_index()
    monthly_df['Month'] = monthly_df['Month'].astype(str)
    
    return overall_metrics, monthly_df 