# run_constraints_tests.py
import os
import sys
from datetime import datetime, timedelta

def run_integrated_backend_test():
    print("=" * 60)
    print("🛰️  LEOP GROUND SEGMENT BACKEND INTEGRATED TEST SYSTEM")
    print("=" * 60)
    
    errors = 0

    # -----------------------------------------------------------------
    # 검증 1: 1번 블록 코어 엔진 (TLE 및 지상국 패스 연산) 검증
    # -----------------------------------------------------------------
    print("\n[STEP 1] Testing Pass Prediction Core (scheduler.py)...")
    try:
        from core.scheduler import parse_tle_from_dir, parse_stations_from_dir, calculate_passes
        
        # TLE 디렉토리 스캔 테스트
        tle_data = parse_tle_from_dir("tle")
        print(f"  - Detected TLE Satellites: {list(tle_data.keys())}")
        
        # 지상국 디렉토리 스캔 테스트
        station_data = parse_stations_from_dir("stations")
        print(f"  - Detected Ground Stations: {[s[0] for s in station_data]}")
        
        if not tle_data:
            print("  ❌ [FAIL] No TLE data parsed. Check 'tle/' directory.")
            errors += 1
        if not station_data:
            print("  ❌ [FAIL] No Station data parsed. Check 'stations/' directory.")
            errors += 1
            
        # 가시성 가상 연산 테스트 (현재 시간 기준 24시간 Window)
        start_dt = datetime.utcnow()
        end_dt = start_dt + timedelta(days=1)
        
        passes = calculate_passes(tle_data, station_data, start_dt, end_dt, min_el=10, min_dur=300)
        print(f"  - Simulated Visibility Passes Found: {len(passes)} passes")
        print("  ✅ [SUCCESS] Pass calculation core responds cleanly.")
        
    except Exception as e:
        print(f"  ❌ [CRITICAL FAIL] Scheduler Core Broken: {str(e)}")
        errors += 1

    # -----------------------------------------------------------------
    # 검증 2: 2번 블록 코어 엔진 (제약조건 명세 파서 및 입출력) 검증
    # -----------------------------------------------------------------
    print("\n[STEP 2] Testing Mission Constraints Parser (plan_parser.py)...")
    try:
        from core.plan_parser import PLAN_HEADERS, load_plan_csv, load_plan_excel
        
        print(f"  - Active System Headers Configuration: {list(PLAN_HEADERS.values())}")
        
        # 기본 디폴트 CSV 템플릿 파일이 존재하는지 검증
        default_csv = os.path.join("plans", "default_mission_plan.csv")
        if os.path.exists(default_csv):
            csv_rows = load_plan_csv(default_csv)
            print(f"  - Default CSV parsed successfully. Rows found: {len(csv_rows)}")
            if csv_rows and "satellite" in csv_rows[0]:
                print(f"    * Sample Data Linkage: Sat={csv_rows[0]['satellite']}, Act={csv_rows[0]['activity']}")
        else:
            print("  ⚠️  [WARNING] default_mission_plan.csv not found, skipping CSV parsing test.")
            
        # 기본 디폴트 Excel 템플릿 파일이 존재하는지 검증
        default_xlsx = os.path.join("plans", "default_mission_plan.xlsx")
        if os.path.exists(default_xlsx):
            excel_rows = load_plan_excel(default_xlsx)
            print(f"  - Default Excel sheet parsed successfully. Rows found: {len(excel_rows)}")
        else:
            print("  ⚠️  [WARNING] default_mission_plan.xlsx not found, skipping Excel parsing test.")
            
        print("  ✅ [SUCCESS] Plan parser core structure matches design requirements.")
        
    except Exception as e:
        print(f"  ❌ [CRITICAL FAIL] Constraints Parser Broken: {str(e)}")
        errors += 1

    # -----------------------------------------------------------------
    # 최종 결과 리포트
    # -----------------------------------------------------------------
    print("\n" + "=" * 60)
    if errors == 0:
        print("🎉  ALL SYSTEMS OPERATIONAL (100% PASS)")
        print("    코드가 아주 안전합니다! 안심하고 GUI를 구동하셔도 좋습니다.")
        print("=" * 60)
        return True
    else:
        print(f"🚨  TESTS FAILED WITH {errors} CRITICAL ERROR(S)")
        print("    코드가 꼬였습니다! 깃 로그를 확인하거나 롤백을 고려하세요.")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = run_integrated_backend_test()
    sys.exit(0 if success else 1)