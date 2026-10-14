param([string]$Executable = '', [string]$ReportDirectory = '')
$ErrorActionPreference = 'Stop'
$taskRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $Executable) { $Executable = Join-Path $taskRoot 'dist\AtlasTrim.exe' }
if (-not $ReportDirectory) { $ReportDirectory = Join-Path $taskRoot '.artifacts\packaged' }
[System.IO.Directory]::CreateDirectory($ReportDirectory) | Out-Null
$taskReport = Join-Path $ReportDirectory 'report.json'
$taskManifest = Join-Path $taskRoot '.artifacts\verification_manifest.json'
$taskOldPath = $env:Path
$taskOldPythonHome = $env:PYTHONHOME
$taskOldPythonPath = $env:PYTHONPATH
try {
    $env:Path = Join-Path $env:SystemRoot 'System32'
    $env:PYTHONHOME = 'Z:\NoInstalledPython'
    $env:PYTHONPATH = ''
    $taskArguments = '--smoke-report "' + $taskReport + '" --verify-manifest "' + $taskManifest + '"'
    $taskProcess = Start-Process -FilePath $Executable -ArgumentList $taskArguments -WindowStyle Hidden -PassThru
    if (-not $taskProcess.WaitForExit(180000)) {
        Stop-Process -Id $taskProcess.Id -Force
        throw 'Packaged verification timed out'
    }
    $taskProcess.Refresh()
    if ($taskProcess.ExitCode -ne 0) { throw ('EXE exited with ' + $taskProcess.ExitCode) }
    $taskText = [System.IO.File]::ReadAllText($taskReport, [System.Text.Encoding]::UTF8)
    $taskResult = ConvertFrom-Json $taskText
    if ($taskResult.status -ne 'passed' -or -not $taskResult.frozen) { throw $taskText }
    [System.Console]::WriteLine($taskText)
} finally {
    $env:Path = $taskOldPath
    $env:PYTHONHOME = $taskOldPythonHome
    $env:PYTHONPATH = $taskOldPythonPath
}
