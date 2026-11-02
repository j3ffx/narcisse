# Builds dist/Narcisse-Setup.exe from the wheel in dist/ (npm run build && uv build first):
# a Python of its own, the locked dependencies and Narcisse installed in it, then Inno Setup.
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$root = Split-Path $PSScriptRoot -Parent
$version = (uv version --short --project $root).Trim()
$wheel = Join-Path $root "dist/narcisse-$version-py3-none-any.whl"
if (-not (Test-Path $wheel)) { throw "No wheel for $version in dist/." }
$work = Join-Path $root 'build/installer'
if (Test-Path $work) { Remove-Item $work -Recurse -Force }
New-Item -ItemType Directory -Force $work | Out-Null

# The Python of .python-version, standalone: nothing of the build machine's stays attached to it.
$wanted = (Get-Content (Join-Path $root '.python-version')).Trim()
uv python install $wanted --install-dir (Join-Path $work 'pythons') --no-bin
# Beside it, uv leaves a link named after the minor version and a temporary folder.
$found = Get-ChildItem (Join-Path $work 'pythons') -Directory |
  Where-Object { -not $_.LinkType -and (Test-Path (Join-Path $_.FullName 'python.exe')) } |
  Select-Object -First 1
$python = Join-Path $work 'python'
Move-Item $found.FullName $python
$exe = Join-Path $python 'python.exe'

# The versions the tests ran on, then Narcisse.
$requirements = Join-Path $work 'requirements.txt'
uv export --project $root --locked --no-dev --no-emit-project --format requirements-txt --output-file $requirements --quiet
uv pip install --python $exe --break-system-packages --require-hashes --requirement $requirements
uv pip install --python $exe --break-system-packages --no-deps $wheel

# Ignores the machine's PYTHON* variables and the user's own packages, which could shadow ours.
$tag = & $exe -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')"
@("python$tag.zip", 'DLLs', 'Lib', 'Lib\site-packages', '.', 'import site') |
  Set-Content (Join-Path $python "python$tag._pth") -Encoding ascii

# What Narcisse never runs.
foreach ($unused in 'BUILD', 'include', 'libs', 'tcl', 'Lib/test', 'Lib/idlelib', 'Lib/tkinter', 'Lib/turtledemo', 'Lib/ensurepip', 'Lib/site-packages/pip', 'DLLs/_tkinter.pyd', 'DLLs/tcl86t.dll', 'DLLs/tk86t.dll') {
  Remove-Item (Join-Path $python $unused) -Recurse -Force -ErrorAction SilentlyContinue
}

# Compiled now: the first start doesn't wait for it, and no file changes once installed.
& $exe -m compileall -q --invalidation-mode unchecked-hash (Join-Path $python 'Lib')
Remove-Item (Join-Path $python 'Scripts') -Recurse -Force -ErrorAction SilentlyContinue

& $exe -c "import narcisse.cli, narcisse.desktop.tray; from narcisse.modules import discover; print(narcisse.__version__, len(discover()), 'sources')"

$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe' }
& $iscc /Q "/DAppVersion=$version" (Join-Path $root 'packaging/narcisse.iss')
Get-Item (Join-Path $root 'dist/Narcisse-Setup.exe') | Select-Object Name, Length
