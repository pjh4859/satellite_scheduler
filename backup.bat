@echo off
:: 터미널 한글 깨짐 방지를 위해 UTF-8 인코딩 코드로 변경
chcp 65001 > nul

echo =========================================
echo  [Vibe Coding] 깃허브 자동 백업 시작...
echo =========================================

:: 1. 기본 브랜치 이름을 안전하게 main으로 통일
git branch -M main

:: 2. 변경된 모든 코드 파일 선택
git add .

:: 3. 현재 날짜와 시간으로 스탬프(커밋) 찍기
set current_time=%date%_%time%
git commit -m "Auto backup: %current_time%"

:: 4. 깃허브 저장소로 전송
git push origin main

echo =========================================
echo  백업 완료! 코드가 안전하게 저장되었습니다.
echo =========================================
pause