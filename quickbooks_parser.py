import pandas as pd
import re
from datetime import datetime
import io

def extract_student_info(description):
    """Extract student initials and service type from description."""
    if pd.isna(description):
        return None, None, None
        
    description = str(description).strip()
    
    # Extract evaluation number
    eval_num_match = re.search(r'Evaluation #?\s*(\d+)', description)
    eval_num = eval_num_match.group(1) if eval_num_match else None
    
    # Extract student initials (in parentheses)
    initials_match = re.search(r'\(([A-Z]{2,3})\)', description)
    initials = initials_match.group(1) if initials_match else None
    
    # Determine service type
    service_type = None
    desc_lower = description.lower()
    
    if 'bilingual' in desc_lower:
        if 'low-incidence' in desc_lower:
            service_type = 'Low-Incidence Bilingual Evaluation'
        else:
            service_type = 'Bilingual Evaluation'
    elif 'psychoeducational evaluation' in desc_lower:
        if 'cognitive only' in desc_lower:
            service_type = 'Cognitive Only'
        elif 'educational only' in desc_lower:
            service_type = 'Educational Only'
        else:
            service_type = 'Full Evaluation'
    elif 'academic achievement' in desc_lower:
        service_type = 'Academic Testing'
    elif 'iep meeting' in desc_lower:
        service_type = 'IEP Meeting'
    elif 'set-up' in desc_lower:
        service_type = 'Setup Fee'
    
    return initials, eval_num, service_type

def clean_amount(amount_str):
    """Clean amount string to numeric value."""
    if pd.isna(amount_str):
        return 0
    if isinstance(amount_str, (int, float)):
        return float(amount_str)
    
    # Remove currency symbols and commas
    cleaned = str(amount_str).replace('$', '').replace(',', '')
    try:
        return float(cleaned)
    except:
        return 0

def process_quickbooks_file(file_content):
    """Process raw QuickBooks sales export."""
    try:
        # Skip header rows and find start of data
        lines = file_content.split('\n')
        start_idx = 0
        for i, line in enumerate(lines):
            if 'Transaction date,Transaction type' in line:
                start_idx = i
                break
        
        # Read CSV starting from data rows
        df = pd.read_csv(io.StringIO('\n'.join(lines[start_idx:])))
        
        # Clean column names
        df.columns = [col.strip() for col in df.columns]
        
        # Initialize lists for records
        records = []
        current_customer = None
        
        # Process each row
        for _, row in df.iterrows():
            # Update current customer if not empty
            if not pd.isna(row.iloc[0]) and row.iloc[0].strip():
                current_customer = row.iloc[0].strip()
                continue
            
            # Skip total rows
            if str(row.iloc[0]).startswith('Total for'):
                continue
            
            # Process transaction row
            if pd.notna(row['Transaction date']):
                try:
                    # Extract student info
                    initials, eval_num, service_type = extract_student_info(row['Line description'])
                    
                    record = {
                        'Date': pd.to_datetime(row['Transaction date']),
                        'Customer': current_customer,
                        'Invoice': row['Num'],
                        'Service': row['Product/Service full name'],
                        'Description': row['Line description'],
                        'Student Initials': initials,
                        'Evaluation Number': eval_num,
                        'Service Type': service_type,
                        'Amount': clean_amount(row['Amount']),
                        'Quantity': clean_amount(row['Quantity']),
                        'Unit Price': clean_amount(row['Sales price'])
                    }
                    records.append(record)
                    
                except Exception as e:
                    print(f"Error processing row: {str(e)}")
                    continue
        
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Add derived columns
        df['Month'] = df['Date'].dt.to_period('M')
        df['Week'] = df['Date'].dt.to_period('W')
        
        # Standardize district names to match Gusto data
        district_map = {
            'Ashland Public Schools': 'Ashland',
            'Blue Hills Regional Technical School': 'Blue Hills',
            'Bridgewater-Raynham Regional School District': 'Bridgewater-Raynham',
            'Chelsea Public Schools': 'Chelsea',
            'Greenfield Public Schools': 'Greenfield',
            'Holbrook Public Schools': 'Holbrook',
            'KIPP Academy Lynn Charter School': 'KIPP',
            'Lawrence Public Schools': 'Lawrence',
            'Lynnfield Public Schools': 'Lynnfield',
            'Mansfield Public Schools': 'Mansfield',
            'Milton Public Schools': 'Milton',
            'Randolph Public Schools': 'Randolph',
            'Salem Public Schools': 'Salem',
            'Tewksbury Public Schools': 'Tewksbury',
            'Waltham Public Schools': 'Waltham',
            'Wareham Public Schools': 'Wareham',
            'West Springfield Public Schools': 'West Springfield'
        }
        df['District'] = df['Customer'].map(district_map).fillna(df['Customer'])
        
        return df
        
    except Exception as e:
        raise Exception(f"Error processing QuickBooks file: {str(e)}")

def process_quickbooks_upload(uploaded_file):
    """Process uploaded QuickBooks file and return cleaned DataFrame."""
    try:
        # Read the uploaded file
        content = uploaded_file.getvalue().decode('utf-8')
        
        # Process the data
        df = process_quickbooks_file(content)
        
        return df
        
    except Exception as e:
        raise Exception(f"Error processing QuickBooks file: {str(e)}")

def generate_revenue_summary(df, group_by='District'):
    """Generate revenue summary by specified grouping."""
    summary = df.groupby([group_by, 'Month'])['Amount'].sum().unstack(fill_value=0)
    summary.loc['Total'] = summary.sum()
    return summary

def generate_evaluation_counts(df, group_by='District'):
    """Generate evaluation counts by specified grouping."""
    evals = df[df['Service Type'].str.contains('Evaluation', na=False)]
    counts = evals.groupby([group_by, 'Month'])['Evaluation Number'].nunique().unstack(fill_value=0)
    counts.loc['Total'] = counts.sum()
    return counts 