import pandas as pd
import re
from datetime import datetime
import io

def extract_service_components(description):
    """Extract detailed service components from description."""
    if pd.isna(description):
        return []
    
    description = str(description).lower()
    components = []
    
    # Base evaluation type
    if 'bilingual' in description:
        if 'spanish & haitian creole' in description or 'spanish and haitian creole' in description:
            components.append('Multilingual Evaluation')
        elif 'haitian creole' in description:
            components.append('Haitian Creole Evaluation')
        elif 'spanish' in description:
            components.append('Spanish Evaluation')
        else:
            components.append('Bilingual Evaluation')
    elif any(term in description for term in ['psychoeducational evaluation', 'psychoed eval', 'psychoed evaluation', 'psychological eval', 'psychological evaluation']):
        if 'cognitive only' in description:
            components.append('Cognitive Only')
        elif 'educational only' in description:
            components.append('Educational Only')
        else:
            components.append('Full Evaluation')
    elif 'evaluation' in description and not any(x in description for x in ['academic', 'iep', 'set-up', 'setup']):
        # Catch any other evaluations that don't match the above patterns
        components.append('Full Evaluation')
    
    # Additional components - these are now separate services
    if ('academic' in description and 'assessment' in description) or ('academic' in description and 'testing' in description):
        if not any(c in components for c in ['Full Evaluation', 'Cognitive Only', 'Educational Only', 'Bilingual Evaluation', 'Multilingual Evaluation', 'Haitian Creole Evaluation', 'Spanish Evaluation']):
            components.append('Academic Testing (Add-on)')
    if 'iep' in description and ('meeting' in description or 'presentation' in description):
        if not any(c in components for c in ['Full Evaluation', 'Cognitive Only', 'Educational Only', 'Bilingual Evaluation', 'Multilingual Evaluation', 'Haitian Creole Evaluation', 'Spanish Evaluation']):
            components.append('IEP Meeting (Add-on)')
    if 'rating scales' in description:
        components.append('Rating Scales')
    if 'set-up' in description or 'setup' in description:
        components.append('Remote Setup')
        
    return components

def extract_student_info(description):
    """Extract student initials and service type from description."""
    if pd.isna(description):
        return None, None, None, []
        
    description = str(description).strip()
    
    # Extract evaluation number - handle more formats
    eval_num = None
    eval_patterns = [
        r'Evaluation #?\s*(\d+)',  # Standard format: "Evaluation #123" or "Evaluation 123"
        r'Eval #?\s*(\d+)',        # Abbreviated: "Eval #123" or "Eval 123"
        r'#\s*(\d+)',              # Just the number: "#123"
        r'\(#(\d+)\)',             # Parenthesized: "(#123)"
        r'(\d{2,})'                # Any 2+ digit number (last resort, might be noisy)
    ]
    
    for pattern in eval_patterns:
        match = re.search(pattern, description)
        if match:
            eval_num = match.group(1)
            break
    
    # Extract student initials (in parentheses)
    initials_match = re.search(r'\(([A-Z]{2,3})\)', description)
    initials = initials_match.group(1) if initials_match else None
    
    # Extract service components
    components = extract_service_components(description)
    
    # Determine primary service type
    service_type = None
    if components:
        if 'Multilingual Evaluation' in components:
            service_type = 'Multilingual Evaluation'
        elif any(c for c in components if 'Bilingual' in c and 'Evaluation' in c):
            service_type = 'Bilingual Evaluation'
        elif 'Cognitive Only' in components:
            service_type = 'Cognitive Only'
        elif 'Educational Only' in components:
            service_type = 'Educational Only'
        elif 'Full Evaluation' in components:
            service_type = 'Full Evaluation'
        elif 'Academic Testing (Add-on)' in components:
            service_type = 'Academic Testing (Add-on)'
        elif 'IEP Meeting (Add-on)' in components:
            service_type = 'IEP Meeting (Add-on)'
        elif 'Remote Setup' in components:
            service_type = 'Setup Fee'
    
    return initials, eval_num, service_type, components

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
        start_idx = None
        current_customer = None
        
        # Find the header row that contains column names
        for i, line in enumerate(lines):
            if 'Transaction date,Transaction type' in line:
                start_idx = i
                break
        
        if start_idx is None:
            raise Exception("Could not find column headers in file")
            
        # Add validation for minimum required columns
        required_columns = [
            'Transaction date', 'Transaction type', 'Num', 'Customer',
            'Product/Service full name', 'Line description', 'Amount',
            'Quantity', 'Sales price'
        ]
        
        # Read CSV starting from data rows
        df = pd.read_csv(io.StringIO('\n'.join(lines[start_idx:])))
        
        # Clean column names and drop empty columns
        df.columns = [col.strip() for col in df.columns]
        df = df.dropna(axis=1, how='all')
        
        # Validate required columns
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise Exception(f"Missing required columns: {', '.join(missing_columns)}")
            
        # Add validation for data quality
        if df.empty:
            raise Exception("No data found in file")
            
        # Check for missing critical values
        critical_nulls = {
            'Transaction date': df['Transaction date'].isnull().sum(),
            'Amount': df['Amount'].isnull().sum(),
            'Customer': df['Customer'].isnull().sum()
        }
        
        if any(critical_nulls.values()):
            warnings = []
            for col, count in critical_nulls.items():
                if count > 0:
                    warnings.append(f"{count} missing values in {col}")
            print("⚠️ Data quality warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        
        # Initialize lists for records
        records = []
        
        # Process each row
        for _, row in df.iterrows():
            # Skip empty rows and total rows
            if pd.isna(row['Transaction date']) or str(row.get('Transaction type', '')).lower().startswith('total'):
                continue
                
            try:
                # Extract student info and service components
                initials, eval_num, service_type, components = extract_student_info(row['Line description'])
                
                # Get customer from the Customer column or use the last known customer
                customer = row['Customer'] if pd.notna(row['Customer']) else current_customer
                if pd.notna(customer):
                    current_customer = customer
                
                # Use service date if available, otherwise fall back to transaction date
                date = pd.to_datetime(row['Service date']) if pd.notna(row.get('Service date')) else pd.to_datetime(row['Transaction date'])
                
                record = {
                    'Date': date,
                    'Invoice Date': pd.to_datetime(row['Transaction date']),
                    'Customer': customer,
                    'Invoice': row['Num'],
                    'Service': row['Product/Service full name'],
                    'Description': row['Line description'],
                    'Student Initials': initials,
                    'Evaluation Number': eval_num,
                    'Service Type': service_type,
                    'Service Components': components,
                    'Amount': clean_amount(row['Amount']),
                    'Quantity': clean_amount(row['Quantity']),
                    'Unit Price': clean_amount(row['Sales price'])
                }
                records.append(record)
                
            except Exception as e:
                print(f"Error processing row: {str(e)}")
                continue
        
        # Validate processed records
        if not records:
            raise Exception("No valid records could be processed from the file")
            
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Add derived columns and calculations
        df['Month'] = df['Date'].dt.to_period('M')
        df['Week'] = df['Date'].dt.to_period('W')
        df['Invoice Month'] = df['Invoice Date'].dt.to_period('M')
        
        # Group related services by invoice and student
        df['Service Bundle'] = df.apply(lambda x: 
            ' + '.join(sorted(set(x['Service Components']))) if isinstance(x['Service Components'], list) else '',
            axis=1
        )
        
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
        
        # Final validation of processed data
        total_amount = df['Amount'].sum()
        if total_amount <= 0:
            raise Exception("Total amount is zero or negative - possible data processing error")
            
        print(f"✅ Successfully processed {len(df)} records")
        print(f"   Total amount: ${total_amount:,.2f}")
        print(f"   Date range: {df['Date'].min().strftime('%Y-%m-%d')} to {df['Date'].max().strftime('%Y-%m-%d')}")
        
        return df
        
    except Exception as e:
        raise Exception(f"Error processing QuickBooks file: {str(e)}")

def process_quickbooks_upload(uploaded_file):
    """Process uploaded QuickBooks file and return cleaned DataFrame."""
    try:
        # Handle both string and bytes input
        if isinstance(uploaded_file, (str, bytes)):
            # If it's already bytes or string content
            content = uploaded_file.decode('utf-8') if isinstance(uploaded_file, bytes) else uploaded_file
        else:
            # If it's a file-like object (e.g. StreamlitUploadedFile)
            try:
                # Try to read directly first
                content = uploaded_file.getvalue()
                if isinstance(content, bytes):
                    content = content.decode('utf-8')
            except:
                try:
                    content = uploaded_file.read()
                    if isinstance(content, bytes):
                        content = content.decode('utf-8')
                except:
                    # If both methods fail, try string conversion
                    content = str(uploaded_file)
            
            # Reset file pointer if possible
            try:
                uploaded_file.seek(0)
            except:
                pass
            
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

def generate_service_bundle_analysis(df):
    """Generate analysis of service bundles and their revenue."""
    bundle_summary = df.groupby(['Service Bundle', 'District']).agg({
        'Amount': ['sum', 'mean', 'count'],
        'Student Initials': 'nunique'
    }).round(2)
    
    bundle_summary.columns = ['Total Revenue', 'Average Revenue', 'Transaction Count', 'Student Count']
    return bundle_summary

def generate_pricing_analysis(df):
    """Generate analysis of pricing patterns by district and service type."""
    pricing = df.groupby(['District', 'Service Type', 'Service Bundle'])['Unit Price'].agg(['min', 'max', 'mean', 'count']).round(2)
    return pricing 