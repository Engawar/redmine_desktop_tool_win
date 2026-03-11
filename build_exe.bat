@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv" (
  py -m venv .venv
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

set ICON_ARG=
if exist "assets\app.ico" set ICON_ARG=--icon assets\app.ico

pyinstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onefile ^
  --name RedmineTicketTool ^
  --add-data "config.json;." ^
  --add-data "README.md;." ^
  %ICON_ARG% ^
  app.py

if not exist "dist\RedmineTicketTool" mkdir "dist\RedmineTicketTool"
copy /Y "config.json" "dist\RedmineTicketTool\config.json" >nul
copy /Y "README.md" "dist\RedmineTicketTool\README.md" >nul
if exist "dist\RedmineTicketTool.exe" move /Y "dist\RedmineTicketTool.exe" "dist\RedmineTicketTool\RedmineTicketTool.exe" >nul
if not exist "dist\RedmineTicketTool\exports" mkdir "dist\RedmineTicketTool\exports"

echo.
echo Build completed.
echo Output: %cd%\dist\RedmineTicketTool
pause
