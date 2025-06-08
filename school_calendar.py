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
    
    # Get unique dates and check if they're school days
    dates = df['Date'].unique()
    school_day_map = {d: is_school_day(d) for d in dates}
    
    # Add school day indicator
    df['Is School Day'] = df['Date'].map(school_day_map)
    
    # Calculate metrics
    metrics = {
        'total_revenue': df['Amount'].sum(),
        'school_day_revenue': df[df['Is School Day']]['Amount'].sum(),
        'non_school_day_revenue': df[~df['Is School Day']]['Amount'].sum(),
        'total_days': len(dates),
        'school_days': sum(1 for d in dates if school_day_map[d]),
        'non_school_days': sum(1 for d in dates if not school_day_map[d])
    }
    
    # Calculate averages
    metrics['avg_revenue_per_school_day'] = (
        metrics['school_day_revenue'] / metrics['school_days'] 
        if metrics['school_days'] > 0 else 0
    )
    metrics['avg_revenue_per_non_school_day'] = (
        metrics['non_school_day_revenue'] / metrics['non_school_days']
        if metrics['non_school_days'] > 0 else 0
    )
    
    return metrics

def generate_school_day_analysis(df):
    """
    Generate a detailed analysis of revenue by school days vs non-school days.
    Returns both summary metrics and monthly breakdown.
    """
    # Calculate overall metrics
    overall_metrics = calculate_school_day_metrics(df)
    
    # Calculate monthly breakdown
    df['Month'] = df['Date'].dt.to_period('M')
    monthly_data = []
    
    for month in df['Month'].unique():
        month_df = df[df['Month'] == month]
        month_metrics = calculate_school_day_metrics(month_df)
        monthly_data.append({
            'Month': month,
            **month_metrics
        })
    
    monthly_df = pd.DataFrame(monthly_data)
    
    return overall_metrics, monthly_df 