import csv
import yaml
from datetime import datetime

def export_to_csv(file_path, passes):
    """패스 스케쥴 데이터를 CSV로 저장합니다."""
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Satellite", "Pass_No", "GroundStation", "AOS_UTC", "LOS_UTC", "Duration_sec", "MaxElevation_deg", "Selected", "Status"])
        for p in passes:
            writer.writerow([
                p['satellite'], p['pass_no'], p['station'], 
                p['aos'].isoformat() + "Z", p['los'].isoformat() + "Z", 
                p['duration'], p['max_el'], p['selected'], p['status']
            ])

def export_to_yaml(file_path, passes):
    """패스 스케쥴 데이터를 구조화된 YAML로 저장합니다."""
    output_dict = {
        "Generated_At": datetime.utcnow().isoformat() + "Z",
        "Pass_Schedules": []
    }
    for p in passes:
        output_dict["Pass_Schedules"].append({
            "Satellite": p['satellite'],
            "Pass_No": p['pass_no'],
            "GroundStation": p['station'],
            "AOS": p['aos'].isoformat() + "Z",
            "LOS": p['los'].isoformat() + "Z",
            "Duration_sec": p['duration'],
            "Max_Elevation_deg": p['max_el'],
            "Selected": p['selected'],
            "Status": p['status']
        })
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(output_dict, f, default_flow_style=False, sort_keys=False)