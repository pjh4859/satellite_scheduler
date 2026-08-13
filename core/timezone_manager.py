from datetime import timedelta, timezone

class TimezoneManager:
    def __init__(self):
        self._current_tz = "UTC"  # "UTC" or "KST"

    @property
    def current_tz(self):
        return self._current_tz

    def set_timezone(self, tz_str):
        if tz_str in ["UTC", "KST"]:
            self._current_tz = tz_str

    def format_datetime(self, dt):
        """dt(datetime 객체)를 현재 설정된 타임존 문자열로 변환하여 반환"""
        if dt is None:
            return "-"
        
        # dt가 timezone 정보가 없는 naive인 경우 UTC 기준 가정
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
            
        if self._current_tz == "KST":
            kst_dt = dt.astimezone(timezone(timedelta(hours=9)))
            return kst_dt.strftime("%Y-%m-%d %H:%M:%S KST")
        else:
            utc_dt = dt.astimezone(timezone.utc)
            return utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    def convert_dt(self, dt):
        """dt 객체를 현재 타임존 시간대의 datetime 객체로 변환"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
            
        if self._current_tz == "KST":
            return dt.astimezone(timezone(timedelta(hours=9)))
        else:
            return dt.astimezone(timezone.utc)


tz_manager = TimezoneManager()