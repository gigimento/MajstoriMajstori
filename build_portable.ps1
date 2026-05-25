$OUTPUT = "SCHEDPRO"
$PYTHON_URL = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip"
$PYTHON_ZIP = "python-embed.zip"

Write-Host "=== SCHED//PRO Portable Build ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: create output folder
if (Test-Path $OUTPUT) { Remove-Item -Path $OUTPUT -Recurse -Force }
New-Item -ItemType Directory -Path $OUTPUT -Force | Out-Null
New-Item -ItemType Directory -Path "$OUTPUT\app" -Force | Out-Null
Write-Host "[1/5] Created $OUTPUT folder" -ForegroundColor Green

# Step 2: download embedded Python
if (-not (Test-Path $PYTHON_ZIP)) {
    Write-Host "[2/5] Downloading embedded Python (35MB)..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -Uri $PYTHON_URL -OutFile $PYTHON_ZIP -ErrorAction Stop
        Write-Host "       Downloaded $PYTHON_ZIP" -ForegroundColor Green
    } catch {
        Write-Host "       Download failed. Make sure you have internet access." -ForegroundColor Red
        Write-Host "       Manual: download $PYTHON_URL and place as $PYTHON_ZIP" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "[2/5] Using cached $PYTHON_ZIP" -ForegroundColor Green
}

# Step 3: extract Python
Write-Host "[3/5] Extracting Python..." -ForegroundColor Yellow
Expand-Archive -Path $PYTHON_ZIP -DestinationPath "$OUTPUT\python" -Force

# Enable pip: edit python._pth
$pthFile = Get-ChildItem -Path "$OUTPUT\python" -Filter "python*._pth" | Select-Object -First 1
if ($pthFile) {
    $content = Get-Content $pthFile.FullName
    $content = $content -replace "#import site", "import site"
    Set-Content -Path $pthFile.FullName -Value $content
    Write-Host "       Enabled pip in $($pthFile.Name)" -ForegroundColor Green
}

# Download get-pip.py
Write-Host "       Installing pip..." -ForegroundColor Yellow
$getpip = "$OUTPUT\get-pip.py"
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip -ErrorAction Stop
& "$OUTPUT\python\python.exe" $getpip --no-warn-script-location | Out-Null
Remove-Item $getpip -Force
Write-Host "       Pip installed" -ForegroundColor Green

# Step 4: install dependencies
Write-Host "[4/5] Installing dependencies..." -ForegroundColor Yellow
$pip = Get-ChildItem -Path "$OUTPUT\python\Scripts" -Filter "pip*.exe" | Select-Object -First 1 -ExpandProperty FullName
if (-not $pip) { $pip = "$OUTPUT\python\pip*.exe" }

& "$OUTPUT\python\python.exe" -m pip install streamlit pandas plotly --quiet --no-warn-script-location 2>&1 | Out-Null
Write-Host "       Dependencies installed" -ForegroundColor Green

# Step 5: copy app files
Write-Host "[5/5] Copying app files..." -ForegroundColor Yellow
Copy-Item -Path "app.py", "models.py", "scheduler.py", "license.py", "requirements.txt" -Destination "$OUTPUT\app" -Force
if (Test-Path "scheduler.db") { Copy-Item -Path "scheduler.db" -Destination "$OUTPUT\app" -Force }
Write-Host "       App files copied" -ForegroundColor Green

# Create run.bat
@"
@echo off
title SCHED//PRO
cd /d "%~dp0"
echo.
echo  ========================================
echo    SCHED//PRO - Production Scheduler
echo  ========================================
echo.
echo  Starting server...
echo  Open browser at: http://localhost:8501
echo.
echo  Close this window to stop the server.
echo.
start "" http://localhost:8501
"%~dp0python\python.exe" -m streamlit run "%~dp0app\app.py" --server.headless=true --server.port=8501
pause
"@ | Out-File -FilePath "$OUTPUT\run.bat" -Encoding ASCII

# Create run-noconsole.bat (minimized)
@"
@echo off
title SCHED//PRO
cd /d "%~dp0"
start /min "" http://localhost:8501
"%~dp0python\python.exe" -m streamlit run "%~dp0app\app.py" --server.headless=true --server.port=8501
"@ | Out-File -FilePath "$OUTPUT\run_quiet.bat" -Encoding ASCII

# Create README
@"
SCHED//PRO - Portable Production Scheduler
==========================================

HOW TO USE:
1. Copy the entire SCHEDPRO folder to your desktop or USB drive
2. Double-click run.bat
3. Browser will open automatically
4. Login: admin / admin

REQUIREMENTS:
- Windows 10 or later (64-bit)
- No Python installation needed
- Internet only on first run (for setup)

FIRST TIME SETUP (if downloaded manually):
Double-click run.bat and wait ~30 seconds for the server to start.
The app will check for dependencies automatically.

PORTS:
Default port: 8501
If port 8501 is busy, the app will try port 8502, 8503, etc.
Check the console window to see which port was assigned.

DATA:
All data is stored in app/scheduler.db
Back up this file to keep your data.
Delete it to reset everything.
"@ | Out-File -FilePath "$OUTPUT\README.txt" -Encoding ASCII

Write-Host ""
Write-Host "=== BUILD COMPLETE ===" -ForegroundColor Cyan
Write-Host "Portable app in: $OUTPUT" -ForegroundColor Green
Write-Host "Size: " -NoNewline
$size = (Get-ChildItem -Path $OUTPUT -Recurse | Measure-Object Length -Sum).Sum / 1MB
Write-Host "$([math]::Round($size, 1)) MB" -ForegroundColor Yellow
Write-Host "Double-click SCHEDPRO\run.bat to start" -ForegroundColor Green
