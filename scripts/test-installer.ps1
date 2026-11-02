# Tries the installer as a user would, on a machine that has never seen Narcisse: installs it, opens
# it, updates over a running one, uninstalls it, and checks the user's data stays. Demo side only.
$ErrorActionPreference = 'Stop'

$root = Split-Path $PSScriptRoot -Parent
$version = (uv version --short --project $root).Trim()
$setup = Join-Path $root 'dist/Narcisse-Setup.exe'
$app = Join-Path $env:LOCALAPPDATA 'Programs/Narcisse'
$shortcut = Join-Path $env:APPDATA 'Microsoft/Windows/Start Menu/Programs/Narcisse.lnk'
$port = 8796
$info = "http://127.0.0.1:$port/api/info"
$env:NARCISSE_DATA_DIR = Join-Path $env:RUNNER_TEMP 'narcisse-data'

function Install-Narcisse {
  $process = Start-Process $setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait -PassThru
  if ($process.ExitCode -ne 0) { throw "The installer exited with $($process.ExitCode)." }
}

function Start-Narcisse {
  Start-Process (Join-Path $app 'python/pythonw.exe') -ArgumentList '-m', 'narcisse', 'tray', '--demo', '--port', $port
  foreach ($try in 1..60) {
    Start-Sleep 1
    try {
      return Invoke-RestMethod $info -TimeoutSec 2
    } catch {
      continue
    }
  }
  throw 'Narcisse did not answer.'
}

function Assert-Stopped {
  try {
    Invoke-RestMethod $info -TimeoutSec 2 | Out-Null
  } catch {
    return
  }
  throw 'Narcisse still answers.'
}

Install-Narcisse
if (-not (Test-Path $shortcut)) { throw 'No Start menu entry.' }

$answer = Start-Narcisse
if ($answer.version -ne $version) { throw "Version $($answer.version), expected $version." }
if (-not $answer.can_switch) { throw 'The tray should be able to switch sides.' }
$page = Invoke-WebRequest "http://127.0.0.1:$port/" -UseBasicParsing
if ($page.Content -notmatch 'id="root"') { throw 'The interface is not served.' }
Write-Output "Installed: $version, $($page.Content.Length) bytes of page."

# An update over a running Narcisse.
Install-Narcisse
Assert-Stopped
Start-Narcisse | Out-Null
Write-Output 'Updated over a running Narcisse.'

$uninstaller = Join-Path $app 'unins000.exe'
$process = Start-Process $uninstaller -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "The uninstaller exited with $($process.ExitCode)." }
# It copies itself to run from a temporary folder: the removal finishes a little later.
foreach ($try in 1..30) {
  if (-not (Test-Path (Join-Path $app 'python'))) { break }
  Start-Sleep 1
}
Assert-Stopped
if (Test-Path (Join-Path $app 'python')) { throw 'Python is still installed.' }
if (Test-Path $shortcut) { throw 'The Start menu entry is still there.' }
if (-not (Test-Path (Join-Path $env:NARCISSE_DATA_DIR 'narcisse.sqlite3'))) { throw 'The data is gone.' }
Write-Output 'Uninstalled; the data stays.'
