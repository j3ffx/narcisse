# Builds dist/Narcisse-Setup-x.y.z.exe from the wheel in dist/ (npm run build && uv build first):
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
# uv also makes a link named after the minor version: the real folder is the other one.
$found = Get-ChildItem (Join-Path $work 'pythons') -Directory | Where-Object { -not $_.LinkType } | Select-Object -First 1
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

# Compiled now: the first start doesn't wait for it, and no file changes once installed.
& $exe -m compileall -q --invalidation-mode unchecked-hash (Join-Path $python 'Lib')
Remove-Item (Join-Path $python 'Scripts') -Recurse -Force -ErrorAction SilentlyContinue

& $exe -c "import narcisse.cli, narcisse.desktop.tray; from narcisse.modules import discover; print(narcisse.__version__, len(discover()), 'sources')"

$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe' }
& $iscc /Q "/DAppVersion=$version" (Join-Path $root 'packaging/narcisse.iss')
Get-Item (Join-Path $root "dist/Narcisse-Setup-$version.exe") | Select-Object Name, Length
