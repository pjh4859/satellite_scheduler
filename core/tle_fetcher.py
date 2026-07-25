import os
import json
import urllib.request
import urllib.parse
import urllib.error

def search_satellites_from_celestrak(search_query: str) -> tuple[bool, list, str]:
    """
    CelesTrak에서 검색어에 해당되는 위성 목록을 JSON 형태로 먼저 조회합니다.
    - 반환값: (성공 여부, 위성 정보 리스트 [{norad_id, sat_name, int_designator}], 메세지)
    """
    if not search_query or not search_query.strip():
        return False, [], "Query is empty."

    query = search_query.strip()
    
    # CelesTrak GP Query API (JSON 포맷으로 검색 메타데이터 조회)
    if query.isdigit():
        url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={query}&FORMAT=JSON"
    else:
        encoded_query = urllib.parse.quote(query)
        url = f"https://celestrak.org/NORAD/elements/gp.php?NAME={encoded_query}&FORMAT=JSON"

    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )

    try:
        with urllib.request.urlopen(req, timeout=4) as response:
            if response.status == 200:
                raw_data = response.read().decode('utf-8').strip()
                if not raw_data or "No TLE found" in raw_data or "No GP data found" in raw_data:
                    return False, [], f"No satellites found matching '{query}'."
                
                parsed_json = json.loads(raw_data)
                sat_list = []
                
                # 결과가 단일 객체인 경우 리스트로 패킹
                if isinstance(parsed_json, dict):
                    parsed_json = [parsed_json]
                    
                for item in parsed_json:
                    sat_name = item.get("OBJECT_NAME", "UNKNOWN").strip()
                    norad_id = str(item.get("NORAD_CAT_ID", "")).strip()
                    int_des = item.get("OBJECT_ID", "").strip()
                    
                    if norad_id:
                        sat_list.append({
                            "sat_name": sat_name,
                            "norad_id": norad_id,
                            "int_designator": int_des
                        })
                        
                if not sat_list:
                    return False, [], f"No valid satellite records parsed for '{query}'."
                    
                return True, sat_list, f"Found {len(sat_list)} satellite(s)."
            else:
                return False, [], f"Server HTTP status: {response.status}"

    except urllib.error.URLError:
        return False, [], "Network error: Please check your internet connection."
    except Exception as e:
        return False, [], f"Search failed: {str(e)}"


def download_tle_by_norad_id(norad_id: str, file_prefix: str = "", save_dir: str = "tle") -> tuple[bool, str]:
    """
    선택된 위성의 NORAD Catalog ID를 기반으로 최종 TLE 파일(.tle)을 다운로드하여 저장합니다.
    """
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )

    try:
        with urllib.request.urlopen(req, timeout=4) as response:
            if response.status == 200:
                content = response.read().decode('utf-8').strip()
                if not content or "No TLE found" in content:
                    return False, "Failed to download TLE string."

                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)

                # 파일명 생성: 위성명_NORADID.tle 구조로 정갈하게 저장
                clean_prefix = "".join([c for c in file_prefix if c.isalnum() or c in ('-', '_')]).strip().upper()
                if clean_prefix:
                    filename = f"{clean_prefix}_{norad_id}.tle"
                else:
                    filename = f"SAT_{norad_id}.tle"
                    
                file_path = os.path.join(save_dir, filename)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content + "\n")

                return True, file_path
            else:
                return False, f"Server responded with status code: {response.status}"

    except Exception as e:
        return False, f"Download error: {str(e)}"