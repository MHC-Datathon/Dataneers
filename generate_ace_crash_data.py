import pandas as pd
import json
from datetime import datetime

def generate_combined_data():

    needed_crash_columns = [
        'CRASH DATE', 'LATITUDE', 'LONGITUDE', 'BOROUGH',
        'NUMBER OF PERSONS INJURED', 'NUMBER OF PERSONS KILLED'
    ]
    
    crashes_df = pd.read_csv("Motor_Crashes_2022_2025.csv", usecols=needed_crash_columns, low_memory=False)
    

    crashes_clean = crashes_df.dropna(subset=['LATITUDE', 'LONGITUDE', 'CRASH DATE']).copy()
    crashes_clean = crashes_clean[
        (crashes_clean['LATITUDE'] >= 40.4) & 
        (crashes_clean['LATITUDE'] <= 40.95) &
        (crashes_clean['LONGITUDE'] >= -74.3) & 
        (crashes_clean['LONGITUDE'] <= -73.7)
    ]
    
    crashes_clean['CRASH_DATE_PARSED'] = pd.to_datetime(crashes_clean['CRASH DATE'], errors='coerce')
    crashes_clean = crashes_clean.dropna(subset=['CRASH_DATE_PARSED'])
    crashes_clean['YEAR_MONTH'] = crashes_clean['CRASH_DATE_PARSED'].dt.strftime('%Y-%m')
    crashes_clean['MONTH_NAME'] = crashes_clean['CRASH_DATE_PARSED'].dt.strftime('%B %Y')
    
    try:

        ace_df = pd.read_csv("ACE.csv", low_memory=False)
        ace_df['First_Occurrence_Date'] = pd.to_datetime(ace_df['First Occurrence'], format='%m/%d/%Y %I:%M:%S %p', errors='coerce')
        ace_clean = ace_df.dropna(subset=['First_Occurrence_Date', 'Bus Stop Latitude', 'Bus Stop Longitude']).copy()
        
        ace_clean['YEAR_MONTH'] = ace_clean['First_Occurrence_Date'].dt.strftime('%Y-%m')
        ace_clean['MONTH_NAME'] = ace_clean['First_Occurrence_Date'].dt.strftime('%B %Y')
        
    except Exception as e:

        ace_clean = pd.DataFrame()
    

    if len(ace_clean) > 0:
        all_months = sorted(set(crashes_clean['YEAR_MONTH'].unique()) | set(ace_clean['YEAR_MONTH'].unique()))

    else:
        all_months = sorted(crashes_clean['YEAR_MONTH'].unique())

    

    monthly_data = {}
    ace_monthly_data = {}
    
    for month in all_months:

        month_crashes = crashes_clean[crashes_clean['YEAR_MONTH'] == month]
        
        crash_features = []
        for idx, row in month_crashes.iterrows():
            crash_features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(row['LONGITUDE'], 4), round(row['LATITUDE'], 4)]
                },
                "properties": {
                    "injured": int(row['NUMBER OF PERSONS INJURED']) if pd.notna(row['NUMBER OF PERSONS INJURED']) else 0,
                    "killed": int(row['NUMBER OF PERSONS KILLED']) if pd.notna(row['NUMBER OF PERSONS KILLED']) else 0,
                    "type": "crash"
                }
            })
        
        monthly_data[month] = {
            "type": "FeatureCollection",
            "features": crash_features
        }
        

        if len(ace_clean) > 0:
            month_ace = ace_clean[ace_clean['YEAR_MONTH'] == month]
            

            ace_locations = month_ace.groupby(['Bus Stop Latitude', 'Bus Stop Longitude']).size().reset_index()
            ace_locations.columns = ['latitude', 'longitude', 'tickets_issued']
            
            # Only include locations with significant enforcement (3+ tickets for better coverage)
            ace_locations = ace_locations[ace_locations['tickets_issued'] >= 3]
            
            ace_features = []
            for idx, row in ace_locations.iterrows():
                ace_features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [round(row['longitude'], 4), round(row['latitude'], 4)]
                    },
                    "properties": {
                        "tickets_issued": int(row['tickets_issued']),
                        "enforcement_level": "high" if row['tickets_issued'] >= 15 else "medium",
                        "type": "ace_enforcement"
                    }
                })
            
            ace_monthly_data[month] = {
                "type": "FeatureCollection", 
                "features": ace_features
            }
    

    month_labels = []
    for month in all_months:
        sample_row = crashes_clean[crashes_clean['YEAR_MONTH'] == month]
        if len(sample_row) > 0:
            month_labels.append(sample_row['MONTH_NAME'].iloc[0])
        else:
            year, mon = month.split('-')
            date_obj = datetime(int(year), int(mon), 1)
            month_labels.append(date_obj.strftime('%B %Y'))
    

    total_crashes = len(crashes_clean)
    total_ace_violations = len(ace_clean) if len(ace_clean) > 0 else 0
    

    combined_data = {
        "crash_data": {
            "monthly_data": monthly_data,
            "month_labels": month_labels,
            "unique_months": all_months,
            "stats": {
                "total_crashes": total_crashes,
                "total_months": len(all_months),
                "date_range": f"{all_months[0]} to {all_months[-1]}"
            }
        },
        "ace_data": {
            "monthly_data": ace_monthly_data,
            "stats": {
                "total_tickets_issued": total_ace_violations,
                "enforcement_locations": len(ace_clean.groupby(['Bus Stop Latitude', 'Bus Stop Longitude'])) if len(ace_clean) > 0 else 0,
                "avg_tickets_per_location": round(total_ace_violations / len(ace_clean.groupby(['Bus Stop Latitude', 'Bus Stop Longitude'])), 1) if len(ace_clean) > 0 else 0
            }
        }
    }
    
    with open('ace_crash_data.json', 'w') as f:
        json.dump(combined_data, f, separators=(',', ':'))
    
    config = {
        "mapbox_token": "pk.eyJ1IjoiY2F1c21pY3MiLCJhIjoiY21mdWJ5MTh3MG83aDJqb2hib25idGdjcyJ9.IJ3M_RSBdZDF-3P_BWghrw",
        "map_center": 
        [-73.9778,40.7358],
        "map_zoom": 4,
        "map_bounds": [
            [-74.5,40.3],
            [-73.4,41.1]
        ],
        "min_zoom": 4,
        "max_zoom": 14
    }
    
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)
    

generate_combined_data()