import csv
import yaml
from datetime import datetime, timezone
# 엑셀 색상 스타일링을 위한 라이브러리 임포트
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font

def export_to_csv(file_path, passes_list):
    """🔥 GUI에서 체크박스가 선택된(selected=True) 지상국 패스 결과만 CSV로 저장"""
    selected_passes = [p for p in passes_list if p.get('selected', False)]
    
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f: # 한글 깨짐 방지 utf-8-sig
        writer = csv.writer(f)
        writer.writerow(["Satellite", "Pass_No", "Station", "AOS(UTC)", "LOS(UTC)", "Duration_Sec", "Max_Elevation", "Status"])
        
        for p in selected_passes:
            writer.writerow([
                p['satellite'],
                p['pass_no'],
                p['station'],
                p['aos'].strftime('%Y-%m-%d %H:%M:%S'),
                p['los'].strftime('%Y-%m-%d %H:%M:%S'),
                p['duration'],
                p['max_el'],
                p['status']
            ])

def export_to_yaml(file_path, passes_list):
    """🔥 GUI에서 체크박스가 선택된 지상국 패스 결과만 표준 YAML로 저장"""
    selected_passes = [p for p in passes_list if p.get('selected', False)]
    
    formatted_list = []
    for p in selected_passes:
        formatted_list.append({
            "satellite": p['satellite'],
            "pass_no": int(p['pass_no']),
            "station": p['station'],
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
    """🔥 [신규] 선택된 패스들을 지상국별로 부드러운 파스텔톤 색상을 입혀 진짜 Excel(.xlsx)로 저장합니다."""
    selected_passes = [p for p in passes_list if p.get('selected', False)]
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Pass Schedule"
    
    # 헤더 작성 및 스타일상 스타일링
    headers = ["Satellite", "Pass_No", "Station", "AOS(UTC)", "LOS(UTC)", "Duration_Sec", "Max_Elevation", "Status"]
    ws.append(headers)
    
    header_fill = PatternFill(start_color="333333", end_color="333333", fill_type="solid")
    header_font = Font(name="맑은 고딕", size=11, bold=True, color="FFFFFF")
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font

    # 🔥 지상국별 파스텔톤 색상 지정 딕셔너리 (HEX 코드)
    # 대전: 연한 파랑, 제주: 연한 노랑, 스발바르: 연한 녹색, 세종: 연한 보라 등
    station_colors = {
        "daejeon": "E6F2FF",    # 연한 파랑
        "jeju": "FFFDE6",       # 연한 노랑
        "svalbard": "E6FDE6",   # 연한 녹색
        "king sejong": "F2E6FF" # 연한 보라
    }
    default_color = "FFFFFF"    # 기본 흰색
    
    data_font = Font(name="맑은 고딕", size=10)
    
    # 데이터 행 기입 및 색상 바인딩
    for row_idx, p in enumerate(selected_passes, start=2):
        row_data = [
            p['satellite'],
            f"Pass {p['pass_no']}",
            p['station'],
            p['aos'].strftime('%Y-%m-%d %H:%M:%S'),
            p['los'].strftime('%Y-%m-%d %H:%M:%S'),
            p['duration'],
            p['max_el'],
            p['status']
        ]
        ws.append(row_data)
        
        # 지상국 이름 매칭 (소문자로 변환하여 공백 제거 후 비교)
        st_key = p['station'].lower().strip()
        color_hex = station_colors.get(st_key, default_color)
        row_fill = PatternFill(start_color=color_hex, end_color=color_hex, fill_type="solid")
        
        # 해당 줄 전체 셀에 폰트와 배경색 주입
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_num)
            cell.fill = row_fill
            cell.font = data_font
            
    # 엑셀 열 너비 자동 최적화
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        
    wb.save(file_path)