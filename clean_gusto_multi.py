import pandas as pd
import re
from datetime import datetime
import io

# --- Utility Functions ---

def estimate_hours(time_range):
    if pd.isna(time_range) or "-" not in time_range:
        return None
    try:
        start, end = [t.strip() for t in time_range.split("-")]
        fmt = "%I:%M %p" if ":" in start else "%I %p"
        start_dt = datetime.strptime(start, fmt)
        end_dt = datetime.strptime(end, fmt)
        if end_dt < start_dt:
            end_dt = end_dt.replace(day=end_dt.day + 1)
        return round((end_dt - start_dt).seconds / 3600, 3)
    except:
        return None

def split_manual_note_entries(note):
    if pd.isna(note):
        return []
    entries = re.split(r'\n+', note.strip())
    final_entries = []
    for entry in entries:
        parts = re.split(r'(?=\d{1,2}:\d{2}(?:\s?[APMapm]{2})?\s*-\s*\d{1,2}:\d{2})', entry)
        final_entries.extend([p.strip() for p in parts if p.strip()])
    return final_entries

def extract_student_initials(note):
    if pd.isna(note): return None
    parts = re.split(r'>', str(note).strip())

    # Skip time range if it's the first part
    if re.match(r'^\d{1,2}:\d{2}', parts[0]):
        parts = parts[1:]

    # Look in the next block (typically initials)
    if len(parts) >= 2:
        initials_block = parts[1]
    else:
        return None

    # Match 2- or 3-letter uppercase initials (including dotted forms)
    initials = re.findall(r'\b[A-Z]{1,3}\b', initials_block.upper())
    return ", ".join(initials) if initials else None



def extract_task(note):
    if pd.isna(note): return None
    parts = note.split(">")
    if len(parts) >= 3:
        return parts[2].split("-")[0].strip()
    return None

def standardize_task(task):
    if pd.isna(task): return None
    t = task.lower().strip()
    if "report" in t: return "Report Writing"
    elif "testing" in t: return "Testing"
    elif "interview" in t or "observation" in t: return "Interview and Observation"
    elif "eval" in t or "planning" in t: return "Eval Planning"
    elif "scoring" in t or "upload" in t: return "Scoring and Uploading"
    elif "meeting prep" in t: return "Meeting Prep"
    elif "iep" in t: return "IEP Meeting Attendance"
    elif "rating" in t: return "Rating Scales"
    elif "guardian" in t or "parent" in t: return "Guardian Contact"
    elif "teacher" in t: return "Teacher Contact"
    elif "staff" in t: return "School Staff Contact"
    elif "scheduling" in t: return "Scheduling"
    elif "onboarding" in t: return "Onboarding"
    elif "caseload" in t: return "Caseload Organization"
    elif "pd" in t or "development" in t: return "Professional Development"
    elif "email" in t or "communication" in t: return "Internal Communication"
    elif "troubleshoot" in t or "tech" in t: return "Troubleshooting"
    elif "waiting" in t: return "Waiting"
    else: return task.title()

def categorize_task(task):
    eval_tasks = {
        "Eval Planning", "Scheduling", "Guardian Contact", "Teacher Contact", "School Staff Contact",
        "Rating Scales", "Eval Prep", "Waiting", "Testing", "Interview and Observation",
        "Scoring and Uploading", "Report Writing", "Post Eval School Consultation",
        "Meeting Prep", "IEP Meeting Attendance"
    }
    admin_tasks = {
        "Onboarding", "Internal Communication", "Professional Development", "Caseload Organization", "Troubleshooting"
    }
    if task in eval_tasks:
        return "Evaluation"
    elif task in admin_tasks:
        return "Admin"
    return "Uncategorized"

# --- District Cleanup ---

district_aliases = {
    "LHS": "Lawrence", "Lawrence High": "Lawrence", "Lawrence High School": "Lawrence",
    "Kipp": "KIPP",
    "Waltham High": "Waltham", "Waltham Elementary": "Waltham",
    "WSHS": "West Springfield", "W. Springfield": "West Springfield",
    "West Springfield High School": "West Springfield", "west springfield high school": "West Springfield",
    "Bridgewater": "Bridgewater-Raynham", "BMS": "Bridgewater-Raynham", "Raynahm": "Bridgewater-Raynham", "Raynham": "Bridgewater-Raynham",
    "BRHS": "Bridgewater-Raynham", "BRRHS": "Bridgewater-Raynham", "Bridgewater Middle": "Bridgewater-Raynham",
    "Randolph Middle": "Randolph", "Randolph Middle School": "Randolph", "Randolph High": "Randolph",
    "Donovan Elementary": "Randolph", "Donovan": "Randolph", "Donnovan": "Randolph", "Donovan School": "Randolph",
    "Wareham Elementary": "Wareham", "WES": "Wareham",
    "AMS": "Ashland", "AHS": "Ashland", "Ashland Middle": "Ashland",
    "Central Elementary": "Tewksbury", "Central Elementary School": "Tewksbury", "Center School": "Tewksbury", "TWyMS": "Tewksbury",
    "Milton HS": "Milton", "Milton High School": "Milton",
    "Blue hills": "Blue Hills", "Blue Hils": "Blue Hills", "BlueHills": "Blue Hills",
    "Admin": "Lilypad", "LL": "Lilypad", "Lilypad, Greenfield": "Greenfield", "Lilypad/Greenfield": "Greenfield", "Lilypad/Holbrook": "Holbrook",
    "salem": "Salem", "Salem Saltonstall": "Salem", "Saltonstall Elementary": "Salem", "Bentley School": "Salem", "Bentley Elementary": "Salem",
    "HMHS": "Holbrook", "GMS": "Greenfield", "Green Field": "Greenfield",
    "W.Springfield": "West Springfield", "West Springfield HS": "West Springfield", "WSHS- J/G.S.": "West Springfield",
    "Center Elementary": "Tewksbury",
    "Springfield": "West Springfield"
}

approved_districts = {
    "Ashland", "Blue Hills", "Bridgewater-Raynham", "Easthampton", "Greenfield", "Holbrook",
    "KIPP", "Lawrence", "Lynnfield", "Mansfield", "Milton", "Randolph", "Salem", "Tewksbury",
    "Waltham", "Wareham", "Acton-Boxborough", "West Springfield", "Chelsea", "New Heights", "Lilypad"
}

def extract_possible_district_from_note(note):
    if pd.isna(note): return None
    note = str(note).strip()
    note = re.sub(r'^\d{1,2}:\d{2}(?: ?[APMapm]{2})?\s*-\s*\d{1,2}:\d{2}(?: ?[APMapm]{2})?\s*>?', '', note).strip()
    return note.split(">")[0].strip() if ">" in note else note

def standardize_district(raw_text):
    if pd.isna(raw_text): return None
    raw = str(raw_text).strip()
    if re.match(r'^\d{1,2}:\d{2}', raw):
        return None
    lowered = raw.lower()
    for alias, standard in district_aliases.items():
        if alias.lower() in lowered:
            return standard
    return raw if raw in approved_districts else None

# --- Main Parsing Logic ---

def process_block(block_lines, psychologist_name):
    block_str = ''.join(block_lines)
    try:
        df = pd.read_csv(io.StringIO(block_str))
        if "Total hours" in df.columns:
            df["Total hours"] = pd.to_numeric(df["Total hours"], errors="coerce")
            df = df[df["Total hours"] > 0].copy()
        if df.empty:
            return []
    except Exception as e:
        print(f"⚠️ Skipping block for {psychologist_name} due to read error: {e}")
        return []

    results = []

    for _, row in df.iterrows():
        date_raw = row.get("Date", row.get('"Date"'))
        try:
            date = pd.to_datetime(date_raw, errors='coerce')
        except:
            continue
        if pd.isna(date):
            continue

        hours_cols = [col for col in row.index if col.startswith("Hours")]
        notes_cols = [col for col in row.index if col.startswith("Notes")]

        for h_col, n_col in zip(hours_cols, notes_cols):
            h = row[h_col]
            n = row[n_col]
            if not h and not n:
                continue

            est_hours = estimate_hours(h)
            split_notes = split_manual_note_entries(n)
            if not split_notes:
                split_notes = [n]

            for sub_note in split_notes:
                initials = extract_student_initials(sub_note)
                student_list = [s.strip() for s in str(initials).split(",") if s.strip()]
                student_count = len(student_list) if student_list else 1
                split_hours = est_hours / len(split_notes) / student_count if est_hours else 0
                district_raw = extract_possible_district_from_note(sub_note)

                for student in student_list or [None]:
                    task = extract_task(sub_note)
                    std_task = standardize_task(task)

                    try:
                        results.append({
                            "Date": date,
                            "Hours": h,
                            "Note": sub_note,
                            "Estimated Hours": split_hours,
                            "Student Initials": student,
                            "District": standardize_district(district_raw),
                            "Task": task,
                            "Standardized Task": std_task,
                            "Task Category": categorize_task(std_task),
                            "Psychologist": psychologist_name
                        })
                    except Exception as e:
                        print(f"⚠️ Skipping row due to error: {e}")

    return results


def parse_gusto_file(filepath):
    import numpy as np

    cleaned_rows = []

    # Step 1: Read raw Gusto file line by line
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    psychologist = None
    block = []

    # Step 2: Group lines into blocks per psychologist
    for line in lines:
        if "Hours for" in line and "(Contractor)" in line:
            if block:
                try:
                    cleaned_rows += process_block(block, psychologist)
                except Exception as e:
                    print(f"⚠️ Skipping block for {psychologist} due to error: {e}")
                block = []

            match = re.search(r'Hours for (.+?) \(Contractor\)', line)
            psychologist = match.group(1) if match else "Unknown"
        elif line.strip():
            block.append(line)

    # Step 3: Process final block
    if block:
        try:
            cleaned_rows += process_block(block, psychologist)
        except Exception as e:
            print(f"⚠️ Skipping final block for {psychologist} due to error: {e}")

    # Step 4: Deep-clean each row before DataFrame conversion
    safe_rows = []
    for i, row in enumerate(cleaned_rows):
        try:
            for key, value in row.items():
                if isinstance(value, (list, tuple, dict, np.ndarray)):
                    raise ValueError(f"Field '{key}' has unsupported type: {type(value)}")
            safe_rows.append(row)
        except Exception as e:
            print(f"⚠️ Dropping bad row {i} ({row.get('Psychologist', 'Unknown')}): {e}")

    # Step 5: Build DataFrame
    if not safe_rows:
        print("⚠️ No valid rows parsed — returning empty DataFrame")
        return pd.DataFrame()

    df = pd.DataFrame(safe_rows)

    # Step 6: Filter for meaningful work
    if "Estimated Hours" in df.columns:
        df["Estimated Hours"] = pd.to_numeric(df["Estimated Hours"], errors="coerce").fillna(0)
        df = df[df["Estimated Hours"] > 0].copy()

    return df




def generate_monthly_expense_summary(df, output_filename):
    # Ensure date is datetime
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Month"] = df["Date"].dt.to_period("M")

    # Define hourly rates again (used here if not in DataFrame already)
    psychologist_rates = {
        "Nancy": 95, "Kathleen": 95, "David": 95, "Melissa": 95, "Emily": 95, "Tarik": 95,
        "Angela": 70, "Caroline": 70, "Julie": 70, "Lexi": 70, "Shirley": 70
    }

    # Fill in rate/cost if not already in DataFrame
    if "Hourly Rate" not in df.columns:
        df["Psychologist Clean"] = df["Psychologist"].apply(lambda x: x.split()[0] if isinstance(x, str) else x)
        df["Hourly Rate"] = df["Psychologist Clean"].map(psychologist_rates)
    if "Estimated Cost" not in df.columns:
        df["Estimated Cost"] = df["Estimated Hours"] * df["Hourly Rate"]

    # Group by month
    monthly_expense = df.groupby("Month")["Estimated Cost"].sum().reset_index()
    monthly_expense["Month"] = monthly_expense["Month"].astype(str)

    # Save to file
    monthly_expense.to_csv(output_filename, index=False)
    print(f"💵 Monthly psychologist expenses saved to: {output_filename}")



def generate_student_task_breakdown(df, output_filename):
    # Filter out invalid or missing initials
    valid = df[
        df["Student Initials"].notna() & 
        (df["Student Initials"] != "None")
    ]

    # Pivot table: Student, District, Psychologist vs Tasks
    pivot = valid.pivot_table(
        index=["Student Initials", "District", "Psychologist"],
        columns="Standardized Task",
        values="Estimated Hours",
        aggfunc="sum",
        fill_value=0
    )

    # Add total column
    pivot["Total Hours"] = pivot.sum(axis=1)
    pivot_reset = pivot.reset_index()

    # Export to CSV
    pivot_reset.to_csv(output_filename, index=False)
    print(f"📊 Student task breakdown saved to: {output_filename}")

def generate_case_financial_report(df, output_filename):
    # Define psychologist hourly rates
    psychologist_rates = {
        "Nancy": 95, "Kathleen": 95, "David": 95, "Melissa": 95, "Emily": 95, "Tarik": 95,
        "Angela": 70, "Caroline": 70, "Julie": 70, "Lexi": 70, "Shirley": 70
    }

    # Define billing fee per district
    district_fees = {
        "Lawrence": 1000, "Greenfield": 900, "Ashland": 1000, "Blue Hills": 900,
        "Bridgewater-Raynham": 1875, "Easthampton": 1875, "Holbrook": 1500,
        "Milton": 1000, "Randolph": 800, "Salem": 950, "Tewksbury": 1500,
        "Waltham": 1000, "Wareham": 1200, "West Springfield": 800
    }

    # Create Case ID
    df["Case ID"] = df["Student Initials"].fillna("") + " | " + df["District"].fillna("")

    # Normalize psychologist names and map hourly rate
    df["Psychologist Clean"] = df["Psychologist"].apply(lambda x: x.split()[0] if isinstance(x, str) else x)
    df["Hourly Rate"] = df["Psychologist Clean"].map(psychologist_rates)
    df["Estimated Cost"] = df["Estimated Hours"] * df["Hourly Rate"]

    # Group by Case ID and aggregate relevant data
    case_summary = df.groupby("Case ID").agg({
        "Student Initials": "first",
        "District": "first",
        "Estimated Hours": "sum",
        "Estimated Cost": "sum",
        "Psychologist": lambda x: ", ".join(sorted(set(filter(pd.notna, x)))),
        "Date": ["min", "max"]
    })

    # Flatten multi-index from aggregation
    case_summary.columns = ['Student Initials', 'District', 'Estimated Hours', 'Estimated Cost',
                            'Psychologists', 'Start Date', 'End Date']
    case_summary = case_summary.reset_index()

    # Map revenue and compute profit
    case_summary["Revenue"] = case_summary["District"].map(district_fees)
    case_summary["Profit"] = case_summary["Revenue"] - case_summary["Estimated Cost"]

    # Save to CSV
    case_summary.to_csv(output_filename, index=False)
    print(f"💰 Case-level financial report saved to: {output_filename}")


def process_gusto_file(file_content):
    """Process raw Gusto time tracking export with robust handling of its complex structure.
    
    The Gusto export has several challenging characteristics:
    1. Non-tabular format with psychologist blocks
    2. Multiple Hours/Notes column pairs
    3. Semi-structured free text notes
    4. Inconsistent formatting and missing data
    5. Embedded metadata in notes
    """
    try:
        # Step 1: Split into psychologist blocks
        # Format: "Hours for NAME (Contractor)"
        sections = re.split(r'\n\s*"Hours for ([^"]+) \(Contractor\)"\s*\n', file_content)
        
        all_records = []
        current_contractor = None
        processed_blocks = 0
        error_blocks = 0
        
        for i, section in enumerate(sections):
            if i == 0:  # Skip header section
                continue
                
            if i % 2 == 1:  # Contractor name
                current_contractor = section.strip()
                continue
                
            # Step 2: Process each contractor's block
            try:
                # Clean up the section data - remove empty lines and extra whitespace
                cleaned_lines = [line.strip() for line in section.split('\n') if line.strip()]
                cleaned_section = '\n'.join(cleaned_lines)
                
                # Read CSV data
                df = pd.read_csv(io.StringIO(cleaned_section))
                
                # Skip if no data
                if df.empty:
                    continue
                
                # Step 3: Handle date parsing
                date_col = '"Date"' if '"Date"' in df.columns else 'Date'
                if date_col in df.columns:
                    # Try different date formats
                    for date_format in ['%m/%d/%y', '%m/%d/%Y']:
                        try:
                            df['Date'] = pd.to_datetime(df[date_col].str.strip('"'), format=date_format)
                            break
                        except:
                            continue
                    
                    # If specific formats fail, try automatic parsing
                    if 'Date' not in df.columns:
                        df['Date'] = pd.to_datetime(df[date_col].str.strip('"'), errors='coerce')
                    
                    # Drop rows with invalid dates
                    df = df.dropna(subset=['Date'])
                    
                    # Skip if no valid dates
                    if df.empty:
                        continue
                    
                    # Step 4: Process each row and handle multiple Hours/Notes pairs
                    for _, row in df.iterrows():
                        # Find all Hours columns
                        hours_cols = [col for col in row.index if col.startswith('Hours') and not col.startswith('Hours for')]
                        notes_cols = [col for col in row.index if col.startswith('Notes')]
                        
                        # Process each Hours/Notes pair
                        for hours_col, notes_col in zip(hours_cols, notes_cols):
                            if pd.isna(row[hours_col]):
                                continue
                                
                            hours = estimate_hours(row[hours_col])
                            if not hours:
                                continue
                                
                            # Step 5: Parse the semi-structured notes
                            note = row.get(notes_col)
                            district, initials, task = parse_note_format(note)
                            
                            # Create record with all extracted information
                            record = {
                                'Date': row['Date'],
                                'Psychologist': current_contractor,
                                'Hours': hours,
                                'District': district,
                                'Student Initials': initials,
                                'Raw Task': task,
                                'Standardized Task': standardize_task(task),
                                'Time Entry': row[hours_col],
                                'Note': note,
                                'Hours Column': hours_col,  # Track which hours column was used
                                'Notes Column': notes_col   # Track which notes column was used
                            }
                            all_records.append(record)
                
                processed_blocks += 1
                            
            except Exception as e:
                error_blocks += 1
                print(f"Error processing block for {current_contractor}: {str(e)}")
                continue
                
        # Step 6: Validate and create final DataFrame
        if not all_records:
            raise Exception(f"No valid records found in file. Processed blocks: {processed_blocks}, Error blocks: {error_blocks}")
            
        df = pd.DataFrame(all_records)
        
        # Step 7: Add derived columns and calculations
        df['Month'] = df['Date'].dt.to_period('M')
        df['Week'] = df['Date'].dt.to_period('W')
        
        # Calculate costs using psychologist-specific rates
        psychologist_rates = {
            "Nancy": 95, "Kathleen": 95, "David": 95, "Melissa": 95, "Emily": 95, "Tarik": 95,
            "Angela": 70, "Caroline": 70, "Julie": 70, "Lexi": 70, "Shirley": 70
        }
        
        # Extract first name for rate lookup
        df['Psychologist_First_Name'] = df['Psychologist'].apply(lambda x: x.split()[0] if isinstance(x, str) else None)
        df['Rate'] = df['Psychologist_First_Name'].map(psychologist_rates).fillna(100)  # Default to 100 if not found
        df['Cost'] = df['Hours'] * df['Rate']
        
        # Clean up temporary columns
        df = df.drop(columns=['Psychologist_First_Name'])
        
        print(f"Successfully processed {processed_blocks} blocks with {error_blocks} errors")
        print(f"Total records extracted: {len(df)}")
        
        return df
        
    except Exception as e:
        raise Exception(f"Error processing Gusto file: {str(e)}")

def process_gusto_upload(uploaded_file):
    """Process uploaded Gusto file and return cleaned DataFrame."""
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
        df = process_gusto_file(content)
        return df
        
    except Exception as e:
        raise Exception(f"Error processing Gusto file: {str(e)}")

def parse_note_format(note):
    """Parse a note into district, student initials, and task."""
    if pd.isna(note):
        return None, None, None
        
    note = str(note).strip()
    
    # Remove time range if present at the start
    note = re.sub(r'^\d{1,2}:\d{2}(?: ?[APMapm]{2})?\s*-\s*\d{1,2}:\d{2}(?: ?[APMapm]{2})?\s*>?\s*', '', note)
    
    # Split by '>'
    parts = [p.strip() for p in note.split('>')]
    
    # Extract components
    district = standardize_district(parts[0]) if len(parts) > 0 else None
    initials = extract_student_initials(note) if len(parts) > 1 else None
    task = extract_task(note) if len(parts) > 2 else None
    
    return district, initials, task

# --- Script Entry Point ---


if __name__ == "__main__":
    input_file = "gusto_time_tracking.csv"
    output_file = "Cleaned_Multi_Psychologist_Report.csv"
    breakdown_file = "Full_Student_Task_Breakdown_With_Evaluator.csv"
    financial_file = "Case_Level_Financial_Report.csv"

    # Parse and clean the main dataset
    df = parse_gusto_file(input_file)
    df.fillna("", inplace=True)

    # Define psychologist hourly rates
    psychologist_rates = {
        "Nancy": 95, "Kathleen": 95, "David": 95, "Melissa": 95, "Emily": 95, "Tarik": 95,
        "Angela": 70, "Caroline": 70, "Julie": 70, "Lexi": 70, "Shirley": 70
    }

    # Add hourly rate and cost columns to cleaned dataset
    df["Psychologist Clean"] = df["Psychologist"].apply(lambda x: x.split()[0] if isinstance(x, str) else x)
    df["Hourly Rate"] = df["Psychologist Clean"].map(psychologist_rates)
    df["Estimated Cost"] = df["Estimated Hours"] * df["Hourly Rate"]

    # Save the cleaned dataset with cost data
    df.to_csv(output_file, index=False)
    print(f"✅ Cleaned report saved to: {output_file}")

    # Full case-level profitability analysis
    generate_case_financial_report(df, financial_file)

    # Generate monthly expense summary
    monthly_expense_file = "Monthly_Expense_Summary.csv"
    generate_monthly_expense_summary(df, monthly_expense_file)


    # Create student task breakdown summary
    generate_student_task_breakdown(df, breakdown_file)

