@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

:: 1. 사용자 지정 커밋 메시지가 입력되었는지 확인 (%*는 뒤에 온 모든 텍스트)
set "USER_MSG=%~1"

:: 2. 만약 입력된 메시지가 없다면 기본 자동 메시지 생성
if "%USER_MSG%"=="" (
    :: 현재 날짜와 시간 추출 (YYYY-MM-DD HH:MM)
    set "CURR_DATE=%date:~0,10%"
    set "CURR_TIME=%time:~0,5%"
    set "COMMIT_MSG=Auto backup: !CURR_DATE! !CURR_TIME! - Scheduled System Snapshot"
) else (
    set "COMMIT_MSG=%~1"
)

echo.
echo ========================================================
echo 🚀 GitHub 원격 저장소 백업을 시작합니다...
echo 📝 Commit Message: "!COMMIT_MSG!"
echo ========================================================
echo.

:: 3. Git 커밋 및 푸시 실행
git add .
git commit -m "!COMMIT_MSG!"
git push origin main

echo.
echo ========================================================
echo 🎉 백업이 성공적으로 완료되었습니다!
echo ========================================================
echo.
pause