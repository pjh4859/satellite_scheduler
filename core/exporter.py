import csv
import yaml
import re
from datetime import datetime, timezone
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font

# ==============================================================================
# [유틸리티] 위성 이름 정규화 함수
# ==============================================================================
def normalize_sat_name(sat_str):
    """
    위성 이름 정규화 함수
    
    [기능 설명]
    - 'NEONSAT-1A(67614)'와 같은 위성 텍스트에서 괄호 및 특수문자/공백을 제거하여
      'NEONSAT1A' 형태로 정규화합니다.
    - color_manager와 연동 시 위성별 일관된 파스텔 색상을 매핑할 수 있도록 지원합니다.
    """
    if not sat_str: 
        return ""
    clean = str(sat_str).split("(")[0].strip()
    clean = re.sub(r'[^A-Za-z0-9]', '', clean).upper()
    return clean


# ==============================================================================
# Tab 1: 패스 예측 결과 내보내기 함수들 (CSV, YAML, Excel)
# ==============================================================================
def export_to_csv(file_path, passes_list):
    """
    Tab 1 패스 예측 스케줄을 CSV 파일로 내보내기
    
    [기능 설명]
    - 선택(selected=True)된 패스 데이터만 추출하여 한글 깨짐이 없는 'utf-8-sig' 인코딩으로 저장합니다.
    - datetime 및 string 형태의 날짜/시간 데이터를 안전하게 포맷팅합니다.
    """
    selected_passes = [p for p in passes_list if p.get('selected', False)]
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Station", "Satellite", "Pass_No", "AOS(UTC)", "LOS(UTC)", "Duration_Sec", "Max_Elevation", "Status"])
        for p in selected_passes:
            aos_str = p['aos'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(p['aos'], datetime) else str(p['aos'])
            los_str = p['los'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(p['los'], datetime) else str(p['los'])
            writer.writerow([
                p['station'], p['satellite'], p.get('pass_no', 1),
                aos_str, los_str,
                p['duration'], p['max_el'], p.get('status', 'Normal')
            ])


def export_to_yaml(file_path, passes_list, all_passes=None, station_data=None, antenna_overrides=None):
    """
    Tab 1 패스 예측 스케줄을 YAML 파일로 내보내기
    
    [기능 설명]
    - 선택된 패스 목록을 생성 시각 타임스탬프와 함께 정돈된 YAML 규격 문서로 출력합니다.
    - all_passes가 제공될 경우 탈락/충돌 패스를 포함한 전체 후보 풀을 'all_candidate_passes'로 함께 직렬화합니다.
    - 💡 [추가기능 6] station_data가 제공되면, 이 스케줄이 어떤 지상국 용량(RX/TX 안테나 대수) 및
      점검 일정 전제 하에 계산됐는지도 함께 기록합니다. 나중에 이 파일만 봐도 "그때 그 지상국이
      몇 대였는지"를 알 수 있어서, 스케줄을 재현하거나 검토할 때 도움이 됩니다.
    """
    selected_passes = [p for p in passes_list if p.get('selected', False)]
    formatted_list = []
    for p in selected_passes:
        aos_str = p['aos'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(p['aos'], datetime) else str(p['aos'])
        los_str = p['los'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(p['los'], datetime) else str(p['los'])
        
        try: pass_no_val = int(p.get('pass_no', 1))
        except (ValueError, TypeError): pass_no_val = 1
        
        try: dur_val = float(p.get('duration', 0.0))
        except (ValueError, TypeError): dur_val = 0.0
        
        try: el_val = float(p.get('max_el', 0.0))
        except (ValueError, TypeError): el_val = 0.0

        formatted_list.append({
            "station": p['station'], 
            "satellite": p['satellite'], 
            "pass_no": pass_no_val,
            "aos": aos_str, 
            "los": los_str,
            "duration_sec": dur_val, 
            "max_elevation_deg": el_val, 
            "status": p.get('status', 'Normal')
        })
        
    payload = {
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_passes_count": len(formatted_list),
        "predicted_passes": formatted_list
    }

    # 전체 패스 풀이 존재할 경우 함께 직렬화 (Tab 3 Cross-Satellite Swap에 활용)
    if all_passes:
        formatted_all = []
        for p in all_passes:
            aos_str = p['aos'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(p['aos'], datetime) else str(p['aos'])
            los_str = p['los'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(p['los'], datetime) else str(p['los'])
            try: pass_no_val = int(p.get('pass_no', 1))
            except (ValueError, TypeError): pass_no_val = 1
            try: dur_val = float(p.get('duration', 0.0))
            except (ValueError, TypeError): dur_val = 0.0
            try: el_val = float(p.get('max_el', 0.0))
            except (ValueError, TypeError): el_val = 0.0

            formatted_all.append({
                "station": p['station'], 
                "satellite": p['satellite'], 
                "pass_no": pass_no_val,
                "aos": aos_str, 
                "los": los_str,
                "duration_sec": dur_val, 
                "max_elevation_deg": el_val, 
                "selected": p.get('selected', False),
                "status": p.get('status', 'Normal')
            })
        payload["all_candidate_passes"] = formatted_all

    # 💡 [추가기능 6] 지상국별 RX/TX 용량 및 점검 일정(있는 경우) 스냅샷
    if station_data:
        station_capacity_snapshot = []
        for st in station_data:
            st_name = st[0]
            entry = {
                "station": st_name,
                "rx_capacity": int(st[5]) if len(st) > 5 else 1,
                "tx_capacity": int(st[6]) if len(st) > 6 else 1,
            }
            overrides_for_station = [ov for ov in (antenna_overrides or []) if ov.get("station") == st_name]
            if overrides_for_station:
                entry["maintenance_windows"] = [
                    {
                        "start": ov["start_dt"].strftime('%Y-%m-%d %H:%M:%S') if isinstance(ov.get("start_dt"), datetime) else str(ov.get("start_dt")),
                        "end": ov["end_dt"].strftime('%Y-%m-%d %H:%M:%S') if isinstance(ov.get("end_dt"), datetime) else str(ov.get("end_dt")),
                        "rx_capacity": ov.get("rx_capacity"),
                        "tx_capacity": ov.get("tx_capacity"),
                        "reason": ov.get("reason", "")
                    }
                    for ov in overrides_for_station
                ]
            station_capacity_snapshot.append(entry)
        payload["station_capacity_snapshot"] = station_capacity_snapshot

    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ==============================================================================
# 💡 [추가기능 6] Excel에 지상국 용량 정보를 별도 시트로 추가하는 공용 헬퍼
# ------------------------------------------------------------------------------
# Tab1(Pass Prediction)과 Tab3(Final Schedule) 양쪽의 Excel 내보내기에서 공통으로
# 사용합니다. CSV는 다운스트림 도구가 순수 표 형태로 파싱하는 경우가 많아 건드리지
# 않았지만, Excel은 시트를 여러 개 둘 수 있어서 "본 데이터를 해치지 않고" 참고 정보를
# 추가하기에 적합합니다.
# ==============================================================================
def _write_station_capacity_sheet(wb, station_data, antenna_overrides=None):
    if not station_data:
        return
    ws = wb.create_sheet("Station Capacity Info")
    headers = ["Station", "RX Capacity", "TX Capacity", "Maintenance Window", "Override RX", "Override TX", "Reason"]
    ws.append(headers)

    header_fill = PatternFill(start_color="455A64", end_color="455A64", fill_type="solid")
    header_font = Font(name="맑은 고딕", size=11, bold=True, color="FFFFFF")
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font

    data_font = Font(name="맑은 고딕", size=10)
    row_idx = 2
    for st in station_data:
        st_name = st[0]
        base_rx = int(st[5]) if len(st) > 5 else 1
        base_tx = int(st[6]) if len(st) > 6 else 1
        overrides_for_station = [ov for ov in (antenna_overrides or []) if ov.get("station") == st_name]

        if not overrides_for_station:
            ws.append([st_name, base_rx, base_tx, "", "", "", ""])
            for col_idx in range(1, len(headers) + 1):
                ws.cell(row=row_idx, column=col_idx).font = data_font
            row_idx += 1
        else:
            for ov in overrides_for_station:
                start_s = ov["start_dt"].strftime('%Y-%m-%d %H:%M') if isinstance(ov.get("start_dt"), datetime) else str(ov.get("start_dt"))
                end_s = ov["end_dt"].strftime('%Y-%m-%d %H:%M') if isinstance(ov.get("end_dt"), datetime) else str(ov.get("end_dt"))
                ws.append([
                    st_name, base_rx, base_tx, f"{start_s} ~ {end_s}",
                    ov.get("rx_capacity") if ov.get("rx_capacity") is not None else "(No Change)",
                    ov.get("tx_capacity") if ov.get("tx_capacity") is not None else "(No Change)",
                    ov.get("reason", "")
                ])
                for col_idx in range(1, len(headers) + 1):
                    ws.cell(row=row_idx, column=col_idx).font = data_font
                row_idx += 1

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)


def export_to_excel_with_color(file_path, passes_list, station_data=None, antenna_overrides=None):
    """
    Tab 1 패스 예측 스케줄을 파스텔 색상 포함 Excel 파일로 내보내기
    
    [기능 설명]
    - 지상국별 고유 파스텔 배경색을 각 행(Row)에 적용하여 가시성을 높인 엑셀 문서를 만듭니다.
    - 파일이 이미 열려 있어 발생하는 PermissionError 시 친절한 오류 메시지와 성공 여부(True/False)를 반환합니다.
    - 💡 [추가기능 6] station_data가 제공되면 "Station Capacity Info" 시트를 추가로 만듭니다.
    """
    try:
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
            aos_str = p['aos'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(p['aos'], datetime) else str(p['aos'])
            los_str = p['los'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(p['los'], datetime) else str(p['los'])
            
            row_data = [
                p['station'], p['satellite'], f"Pass {p.get('pass_no', 1)}",
                aos_str, los_str,
                p['duration'], p['max_el'], p.get('status', 'Normal')
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

        _write_station_capacity_sheet(wb, station_data, antenna_overrides)

        wb.save(file_path)
        return True, "Success"
    except PermissionError:
        return False, f"Permission Denied: The file '{file_path}' is currently open in Excel. Please close it and try again."
    except Exception as e:
        return False, str(e)


# ==============================================================================
# Tab 2: 미션 제약 조건 내보내기 함수들 (Remark 추가)
# ==============================================================================
def export_constraints_to_csv(file_path, extracted_plan_list, headers_labels):
    """
    Tab 2 제약 조건 목록을 CSV 파일로 내보내기 (Remark 항목 추가)
    """
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers_labels)
        for data in extracted_plan_list:
            writer.writerow([
                data.get("sat_id", data.get("satellite", "")),
                data.get("main", data.get("activity", "")),
                data.get("sub", ""),
                data.get("remark", data.get("remarks", data.get("note", ""))),
                data.get("min_el", ""),
                data.get("req_cap", data.get("required_cap", data.get("x_band_req", ""))),
                data.get("min_dur", data.get("min_duration", data.get("min_pass_contact", ""))),
                data.get("pre_req_main", data.get("pre_activity_sequence_id", "")),
                data.get("sequence_id", data.get("activity_sequence_id", ""))
            ])


def export_constraints_to_excel_color(file_path, extracted_plan_list, headers_labels):
    """
    Tab 2 제약 조건 목록을 위성별 색상이 구분된 Excel 파일로 내보내기 (Remark 항목 추가)
    """
    try:
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
                data.get("remark", data.get("remarks", data.get("note", ""))),
                data.get("min_el", ""),
                data.get("req_cap", data.get("required_cap", data.get("x_band_req", ""))),
                data.get("min_dur", data.get("min_duration", data.get("min_pass_contact", ""))),
                data.get("pre_req_main", data.get("pre_activity_sequence_id", "")),
                data.get("sequence_id", data.get("activity_sequence_id", ""))
            ]
            ws.append(row_values)
            
            sat_raw = str(data.get("sat_id", data.get("satellite", ""))).strip()
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
        return True, "Success"
    except PermissionError:
        return False, f"Permission Denied: The file '{file_path}' is currently open in Excel. Please close it and try again."
    except Exception as e:
        return False, str(e)


# ==============================================================================
# Tab 3: 최종 통합 스케줄 내보내기 함수들 (Remark 항목 추가 & 모드별 색상 구분)
# ==============================================================================
def export_final_schedule_to_csv(file_path, final_data):
    """
    Tab 3 최종 산출 스케줄을 CSV 파일로 내보내기 (Remark 열 추가)
    """
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Station", "Satellite", "Pass_No", "AOS(UTC)", "LOS(UTC)", "Duration_Sec", "Max_Elevation", "Status", "Mission Activity", "Remark"])
        for item in final_data:
            writer.writerow([
                item["station"], item["satellite"], item["pass_no"],
                item["aos"], item["los"], item["duration"], item["max_el"],
                item["status"], item["activity"], item.get("remark", "")
            ])


def export_final_schedule_to_excel(file_path, final_data, color_mode, station_data=None, antenna_overrides=None):
    """
    Tab 3 최종 통합 스케줄을 Excel 파일로 내보내기 (Remark 열 추가)
    💡 [추가기능 6] station_data가 제공되면 "Station Capacity Info" 시트를 추가로 만듭니다.
    """
    try:
        from core.color_manager import color_manager
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Final Integrated Schedule"
        
        headers = ["Station", "Satellite", "Pass_No", "AOS(UTC)", "LOS(UTC)", "Duration_Sec", "Max_Elevation", "Status", "Mission Activity", "Remark"]
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
                item["status"], item["activity"], item.get("remark", "")
            ])
            
            if color_mode == "STATION":
                st_key = str(item["station"]).split("(")[0].strip()
                color_hex, _ = color_manager.get_station_colors(st_key)
            else:
                sat_raw = str(item["satellite"])
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

        _write_station_capacity_sheet(wb, station_data, antenna_overrides)

        wb.save(file_path)
        return True, "Success"
    except PermissionError:
        return False, f"Permission Denied: The file '{file_path}' is currently open in Excel. Please close it and try again."
    except Exception as e:
        return False, str(e)