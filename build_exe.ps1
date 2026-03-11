Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    py -m venv .venv
}

& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt

if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }

$iconArg = @()
if (Test-Path "assets\app.ico") {
    $iconArg = @("--icon", "assets\app.ico")
}

pyinstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onefile `
  --name RedmineTicketTool `
  --add-data "config.json;." `
  --add-data "README.md;." `
  @iconArg `
  app.py

New-Item -ItemType Directory -Force -Path "dist\RedmineTicketTool" | Out-Null
Copy-Item "config.json" "dist\RedmineTicketTool\config.json" -Force
Copy-Item "README.md" "dist\RedmineTicketTool\README.md" -Force
if (Test-Path "dist\RedmineTicketTool.exe") {
    Move-Item "dist\RedmineTicketTool.exe" "dist\RedmineTicketTool\RedmineTicketTool.exe" -Force
}
New-Item -ItemType Directory -Force -Path "dist\RedmineTicketTool\exports" | Out-Null

Write-Host "Build completed. Output: $PSScriptRoot\dist\RedmineTicketTool"
