param([string]$PythonPath = 'python')
# Keep this file UTF-8 with BOM for Windows PowerShell 5.1.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& $PythonPath -I -X utf8 scripts/build_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Icon build failed' }
& $PythonPath -I -X utf8 -m PyInstaller --onefile --windowed --clean --noconfirm --name AtlasTrim --icon assets/atlastrim.ico --add-data 'assets/atlastrim.ico;assets' --distpath dist --workpath build atlas_trim.py
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
Copy-Item -LiteralPath "$PSScriptRoot\使用说明.md" -Destination "$PSScriptRoot\dist\使用说明.md" -Force
