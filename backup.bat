@echo off
echo =========================================
echo  [Vibe Coding] 깃허브 자동 백업 시작...
echo =========================================

# 1. 변경된 모든 코드 파일 선택
git add .

# 2. 현재 날짜와 시간으로 스탬프(커밋) 찍기
set current_time=%date%_%time%
git commit -m "Auto backup: %current_time%"

# 3. 깃허브로 전송
git push origin main

echo =========================================
echo  백업 완료! 코드가 안전하게 저장되었습니다.
echo =========================================
pause