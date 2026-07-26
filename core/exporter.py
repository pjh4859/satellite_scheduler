import csv
import yaml
import re
from datetime import datetime, timezone
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font

def normalize_sat_name(sat_str):
    if not sat_str: return ""
    clean = str(sat_str).split("(")[0].strip()
    clean = re.sub(r'[^A-Za-z0-9]', '', clean).upper()
    return clean

def export_to_csv(file_path, passes_list):
    selected_passes = [p for p in passes_list if p.get('selected', False)]
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Station", "Satellite", "Pass_No", "AOS(UTC)", "LOS(UTC)", "Duration_Sec", "Max_Elevation", "Status"])
        for p in selected_passes:
            writer.writerow([
                p['station'], p['satellite'], p['pass_no'],
                p['aos'].strftime('%Y-%m-%d %H:%M:%S'), p['los'].strftime('%Y-%m-%d %H:%M:%S'),
                p['duration'], p['max_el'], p['status']
            ])

def export_to_yaml(file_path, passes_list):
    selected_passes = [p for p in passes_list if p.get('selected', False)]
    formatted_list = []
    for p in selected_passes:
        formatted_list.append({
            "station": p['station'], "satellite": p['satellite'], "pass_no": int(p['pass_no']),
            "aos": p['aos'].strftime('%Y-%m-%d %H:%M:%S'), "los": p['los'].strftime('%Y-%m-%d %H:%M:%S'),
            "duration_sec": float(p['duration']), "max_elevation_deg": float(p['max_el']), "status": p['status']
        })
    payload = {
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_passes_count": len(formatted_list),
        "predicted_passes": formatted_list
    }
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

def export_to_excel_with_color(file_path, passes_list):
    selected_passes = [p for p in passes_list if p.get('selected', False)]
    wb = Workbook()
    ws = wb.active
    ws.title = "Pass Schedule"
    
    headers = ["Station", "Satellite", "Pass_No", "AOS(UTC)", "LOS(UTC)", "Duration_Sec", "Max_Elevation", "Status"]
    ws.append(headers)
    
    header_fill = PatternFill(start_color="333333", end_color="333333", fill_type="solid")
    header_font = Font(name="맑은 고딕", size=11, bold=True, color="FFFFFF")
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font

    from core.color_manager import color_manager
    data_font = Font(name="맑은 고딕", size=10)
    
    for row_idx, p in enumerate(selected_passes, start=2):
        row_data = [
            p['station'], p['satellite'], f"Pass {p['pass_no']}",
            p['aos'].strftime('%Y-%m-%d %H:%M:%S'), p['los'].strftime('%Y-%m-%d %H:%M:%S'),
            p['duration'], p['max_el'], p['status']
        ]
        ws.append(row_data)
        
        st_key = p['station'].split("(")[0].strip()
        color_hex, _ = color_manager.get_station_colors(st_key)
        row_fill = PatternFill(start_color=color_hex, end_color=color_hex, fill_type="solid")
        
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_num)
            cell.fill = row_fill
            cell.font = data_font
            
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        
    wb.save(file_path)

# ---------------------------------------------------------------------
# Tab 2 Export Functions
# ---------------------------------------------------------------------
def export_constraints_to_csv(file_path, extracted_plan_list, headers_labels):
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers_labels)
        for data in extracted_plan_list:
            writer.writerow([
                data.get("sat_id", data.get("satellite", "")),
                data.get("main", data.get("activity", "")),
                data.get("sub", ""),
                data.get("min_el", ""),
                data.get("req_cap", data.get("required_cap", data.get("x_band_req", ""))),
                data.get("min_dur", data.get("min_duration", data.get("min_pass_contact", ""))),
                data.get("pre_req_main", data.get("pre_activity_sequence_id", "")),
                data.get("sequence_id", data.get("activity_sequence_id", ""))
            ])

def export_constraints_to_excel_color(file_path, extracted_plan_list, headers_labels):
    wb = Workbook()
    ws = wb.active
    ws.title = "Mission Constraints"
    
    ws.append(headers_labels)
    header_fill = PatternFill(start_color="2A2A2A", end_color="2A2A2A", fill_type="solid")
    header_font = Font(name="맑은 고딕", size=11, bold=True, color="FFFFFF")
    for col_idx in range(1, len(headers_labels) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        
    data_font = Font(name="맑은 고딕", size=10)
    from core.color_manager import color_manager
    
    for row_idx, data in enumerate(extracted_plan_list, start=2):
        row_values = [
            data.get("sat_id", data.get("satellite", "")),
            data.get("main", data.get("activity", "")),
            data.get("sub", ""),
            data.get("min_el", ""),
            data.get("req_cap", data.get("required_cap", data.get("x_band_req", ""))),
            data.get("min_dur", data.get("min_duration", data.get("min_pass_contact", ""))),
            data.get("pre_req_main", data.get("pre_activity_sequence_id", "")),
            data.get("sequence_id", data.get("activity_sequence_id", ""))
        ]
        ws.append(row_values)
        
        sat_raw = data.get("sat_id", data.get("satellite", "")).strip()
        sat_clean = normalize_sat_name(sat_raw)
        color_hex, _ = color_manager.get_colors(sat_clean)
        row_fill = PatternFill(start_color=color_hex, end_color=color_hex, fill_type="solid")
        
        for col_idx in range(1, len(headers_labels) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.fill = row_fill
            cell.font = data_font
            
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 4, 15)
        
    wb.save(file_path)

# ---------------------------------------------------------------------
# Tab 3 Export Functions (정밀 색상 매핑 보완)
# ---------------------------------------------------------------------
def export_final_schedule_to_csv(file_path, final_data):
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Station", "Satellite", "Pass_No", "AOS(UTC)", "LOS(UTC)", "Duration_Sec", "Max_Elevation", "Status", "Mission Activity"])
        for item in final_data:
            writer.writerow([
                item["station"], item["satellite"], item["pass_no"],
                item["aos"], item["los"], item["duration"], item["max_el"],
                item["status"], item["activity"]
            ])

def export_final_schedule_to_excel(file_path, final_data, color_mode):
    from core.color_manager import color_manager
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Final Integrated Schedule"
    
    headers = ["Station", "Satellite", "Pass_No", "AOS(UTC)", "LOS(UTC)", "Duration_Sec", "Max_Elevation", "Status", "Mission Activity"]
    ws.append(headers)
    
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(name="맑은 고딕", size=11, bold=True, color="FFFFFF")
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        
    data_font = Font(name="맑은 고딕", size=10)
    
    for row_idx, item in enumerate(final_data, start=2):
        ws.append([
            item["station"], item["satellite"], item["pass_no"],
            item["aos"], item["los"], item["duration"], item["max_el"],
            item["status"], item["activity"]
        ])
        
        # 🔥 [핵심 수정]: 정규화된 지상국/위성 키로 정확하게 파스텔 색상 매핑
        if color_mode == "STATION":
            st_key = item["station"].split("(")[0].strip()
            color_hex, _ = color_manager.get_station_colors(st_key)
        else:
            sat_raw = item["satellite"]
            sat_clean = normalize_sat_name(sat_raw)
            color_hex, _ = color_manager.get_colors(sat_clean)
            
        row_fill = PatternFill(start_color=color_hex, end_color=color_hex, fill_type="solid")
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.fill = row_fill
            cell.font = data_font
            
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 4, 15)
        
    wb.save(file_path)