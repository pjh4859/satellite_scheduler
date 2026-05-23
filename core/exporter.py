import csv
import yaml
from datetime import datetime, timezone
# 엑셀 색상 스타일링을 위한 라이브러리 임포트
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font

def export_to_csv(file_path, passes_list):
    """🔥 GUI 변경 순서 적용: Ground Station, Satellite, Pass_No 순으로 CSV 저장"""
    selected_passes = [p for p in passes_list if p.get('selected', False)]
    
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f: # 한글 깨짐 방지
        writer = csv.writer(f)
        # 헤더 순서 변경
        writer.writerow(["Station", "Satellite", "Pass_No", "AOS(UTC)", "LOS(UTC)", "Duration_Sec", "Max_Elevation", "Status"])
        
        for p in selected_passes:
            writer.writerow([
                p['station'],     # 1. Station
                p['satellite'],   # 2. Satellite
                p['pass_no'],     # 3. Pass_No
                p['aos'].strftime('%Y-%m-%d %H:%M:%S'),
                p['los'].strftime('%Y-%m-%d %H:%M:%S'),
                p['duration'],
                p['max_el'],
                p['status']
            ])

def export_to_yaml(file_path, passes_list):
    """🔥 GUI 변경 순서 적용: 항목 구조 순서를 Station, Satellite, Pass_No 순으로 빌드"""
    selected_passes = [p for p in passes_list if p.get('selected', False)]
    
    formatted_list = []
    for p in selected_passes:
        # 딕셔너리 키 배치 순서 조화
        formatted_list.append({
            "station": p['station'],
            "satellite": p['satellite'],
            "pass_no": int(p['pass_no']),
            "aos": p['aos'].strftime('%Y-%m-%d %H:%M:%S'),
            "los": p['los'].strftime('%Y-%m-%d %H:%M:%S'),
            "duration_sec": float(p['duration']),
            "max_elevation_deg": float(p['max_el']),
            "status": p['status']
        })
        
    payload = {
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_passes_count": len(formatted_list),
        "predicted_passes": formatted_list
    }
    
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

def export_to_excel_with_color(file_path, passes_list):
    """🔥 GUI 변경 순서 적용: Station, Satellite, Pass_No 순으로 유동적 파스텔톤 엑셀 백업"""
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
        
        # 지상국 이름을 매니저에 질의하여 실시간 화면과 동기화된 파스텔 HEX 코드 자동 획득
        st_key = p['station'].strip()
        color_hex, _ = color_manager.get_station_colors(st_key)
        
        # ❌ [기존 코드 제거]: if "Conflict" in p['status']: color_hex = "FFEBEB"
        # 💡 경합(Conflict) 상태인 패스도 오버라이드 없이 고유의 지상국 색상이 그대로 유지됩니다.
            
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

# core/exporter.py 맨 하단에 붙여넣을 내보내기 소스코드

def export_constraints_to_csv(file_path, extracted_plan_list, headers_labels):
    """2번 탭 그리드에서 추가/수정된 액티비티 사양을 표준 CSV로 안전하게 백업"""
    import csv
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers_labels)
        for data in extracted_plan_list:
            writer.writerow([
                data.get("satellite", ""),
                data.get("activity", ""),
                data.get("activity_sequence_id", ""),
                data.get("pre_activity_sequence_id", ""),
                data.get("min_pass_contact", ""),
                data.get("x_band_req", ""),
                data.get("priority", "")
            ])

def export_constraints_to_excel_color(file_path, extracted_plan_list, headers_labels):
    """2번 탭 그리드에서 추가/수정된 액티비티 사양을 위성별 파스텔톤 가로줄을 먹여 진짜 진짜 엑셀 파일로 출력"""
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Mission Constraints"
    
    # 상단 다크그레이 헤더 인젝션
    ws.append(headers_labels)
    header_fill = PatternFill(start_color="2A2A2A", end_color="2A2A2A", fill_type="solid")
    header_font = Font(name="맑은 고딕", size=11, bold=True, color="FFFFFF")
    for col_idx in range(1, len(headers_labels) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        
    sat_colors = {
        "NEONSAT1": "F2F9FF",
        "SPACEEYE-T1": "FFFBF0",
        "DEFAULT": "FFFFFF"
    }
    data_font = Font(name="맑은 고딕", size=10)
    
    for row_idx, data in enumerate(extracted_plan_list, start=2):
        row_values = [
            data.get("satellite", ""),
            data.get("activity", ""),
            data.get("activity_sequence_id", ""),
            data.get("pre_activity_sequence_id", ""),
            data.get("min_pass_contact", ""),
            data.get("x_band_req", ""),
            data.get("priority", "")
        ]
        ws.append(row_values)
        
        sat_name = data.get("satellite", "").upper().strip()
        color_hex = sat_colors.get(sat_name, sat_colors["DEFAULT"])
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