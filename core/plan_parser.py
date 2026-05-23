import os
import csv
import yaml
from datetime import datetime, timezone

def create_default_plan_csv(plans_dir):
    """
    plans/ 폴더가 없으면 생성하고, 친절한 한글 가이드와 예시가 포함된 
    기본 CSV 양식을 생성합니다. 엑셀 호환성을 위해 'utf-8-sig' 인코딩을 적용합니다.
    """
    if not os.path.exists(plans_dir):
        os.makedirs(plans_dir)
        
    file_path = os.path.join(plans_dir, "default_mission_plan.csv")
    if not os.path.exists(file_path):
        # utf-8-sig로 저장해야 한글 엑셀에서 더블클릭했을 때 글자가 안 깨집니다.
        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            # 한글 주석 가이드 작성
            f.write("# LEOP 미션 플랜 및 제약조건 설정 템플릿\n")
            f.write("# 우선순위(Priority): High / Medium / Low / (빈칸은 설정 없음 의미)\n")
            f.write("# 지정 지상국 및 패스 번호: 특정 명칭/숫자를 쓰거나 'Any' 입력\n")
            writer.writerow([
                "Satellite", "Activity_ID", "Activity_Name", "Est_Duration", 
                "Min_Contact_Req", "Pre_Requisite_ID", "Min_Gap_Sec", 
                "Target_Station", "Target_Pass_No", "Priority"
            ])
            # 한글이 포함된 샘플 행 데이터 삽입 (지상국 이름 등 한글 대응)
            writer.writerow(["SAT_67614", "101", "TC_히터_온", "60", "120", "None", "0", "Daejeon", "1", "High"])
            writer.writerow(["SAT_67614", "102", "TM_덤프_01", "300", "400", "101", "1800", "Any", "Any", "Medium"])
            writer.writerow(["SAT_67614", "103", "배터리_점검", "30", "60", "102", "3600", "Any", "Any", ""])

def load_plan_csv(file_path):
    """
    사용자가 수정한 CSV 파일을 읽어옵니다.
    윈도우 엑셀 특유의 한글 인코딩(BOM 포함 UTF-8, CP949 등)을 자동으로 판별하여 방어합니다.
    """
    # 1단계: 한국어 환경 엑셀의 다양한 인코딩 충돌을 방지하기 위한 인코딩 후보군 테스트
    encodings = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']
    lines = []
    
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                # '#'으로 시작하는 주석 라인은 제외하고 순수 데이터 라인만 확보
                lines = [line for line in f if not line.strip().startswith("#")]
            # 성공적으로 읽었다면 루프 탈출
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if not lines:
        raise ValueError("CSV 파일을 읽을 수 없거나 지원하지 않는 파일 인코딩 형식입니다.")

    # 2단계: 정제된 라인 스트림을 딕셔너리로 파싱
    parsed_rows = []
    reader = csv.DictReader(lines)
    for row in reader:
        parsed_rows.append({
            "satellite": row.get("Satellite", "").strip() if row.get("Satellite") else "",
            "act_id": row.get("Activity_ID", "").strip() if row.get("Activity_ID") else "",
            "act_name": row.get("Activity_Name", "").strip() if row.get("Activity_Name") else "",
            "est_dur": row.get("Est_Duration", "0").strip() if row.get("Est_Duration") else "0",
            "min_contact": row.get("Min_Contact_Req", "0").strip() if row.get("Min_Contact_Req") else "0",
            "pre_id": row.get("Pre_Requisite_ID", "None").strip() if row.get("Pre_Requisite_ID") else "None",
            "min_gap": row.get("Min_Gap_Sec", "0").strip() if row.get("Min_Gap_Sec") else "0",
            "target_station": row.get("Target_Station", "Any").strip() if row.get("Target_Station") else "Any",
            "target_pass": row.get("Target_Pass_No", "Any").strip() if row.get("Target_Pass_No") else "Any",
            "priority": row.get("Priority", "").strip() if row.get("Priority") else ""
        })
    return parsed_rows

def save_plan_to_yaml(dest_path, plan_data_list):
    """
    GUI 그리드로부터 취합된 최종 미션 제약조건 데이터셋을 정제된 구조의 YAML 파일로 덤프합니다.
    출력 결과물에 한글이 원문 그대로 보이도록 인코딩 옵션을 제어합니다.
    """
    formatted_plans = []
    for item in plan_data_list:
        formatted_plans.append({
            "satellite": str(item["satellite"]),
            "activity_id": int(item["act_id"]) if item["act_id"].isdigit() else item["act_id"],
            "activity_name": str(item["act_name"]),  # 한글 스트링 그대로 전달
            "est_duration_sec": int(item["est_dur"]) if item["est_dur"].isdigit() else 0,
            "min_contact_req_sec": int(item["min_contact"]) if item["min_contact"].isdigit() else 0,
            "pre_requisite_id": int(item["pre_id"]) if item["pre_id"].isdigit() else (None if item["pre_id"].lower() == "none" else item["pre_id"]),
            "min_gap_seconds": int(item["min_gap"]) if item["min_gap"].isdigit() else 0,
            "target_station": "Any" if item["target_station"].lower() == "any" or not item["target_station"] else item["target_station"],
            "target_pass_no": "Any" if str(item["target_pass"]).lower() == "any" or not item["target_pass"] else (int(item["target_pass"]) if str(item["target_pass"]).isdigit() else item["target_pass"]),
            "priority": item["priority"] if item["priority"] in ["High", "Medium", "Low"] else "None"
        })
        
    payload = {
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_constraints_count": len(formatted_plans),
        "mission_constraints": formatted_plans
    }
    
    # allow_unicode=True 를 설정해야 YAML 파일 내부에 한글이 유니코드 깨짐 없이 문자 그대로 찍힙니다.
    with open(dest_path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)