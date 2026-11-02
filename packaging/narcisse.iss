; The Windows installer: a Python of its own and the packages already installed in it, built by
; scripts/build-installer.ps1. A plain Python rather than a frozen app: Narcisse starts itself again
; as `pythonw -m narcisse` and finds its sources by listing a package, and both keep working as is.

#ifndef AppVersion
  #error Give the version: ISCC /DAppVersion=x.y.z
#endif

[Setup]
AppId={{7C1F0B52-6E0A-4E7B-9B55-4A7E8E3D1C20}
AppName=Narcisse
AppVersion={#AppVersion}
AppPublisher=Narcisse
AppPublisherURL=https://github.com/j3ffx/narcisse
AppSupportURL=https://github.com/j3ffx/narcisse/issues
AppUpdatesURL=https://github.com/j3ffx/narcisse/releases
; For this user only: no administrator rights, nothing machine-wide.
PrivilegesRequired=lowest
DefaultDirName={userpf}\Narcisse
DisableDirPage=yes
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\src\narcisse\desktop\narcisse.ico
UninstallDisplayIcon={app}\python\Lib\site-packages\narcisse\desktop\narcisse.ico
UninstallDisplayName=Narcisse
OutputDir=..\dist
OutputBaseFilename=Narcisse-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
fr.OpenNarcisse=Ouvrir Narcisse
en.OpenNarcisse=Open Narcisse

[InstallDelete]
; An update leaves nothing of the previous version's packages.
Type: filesandordirs; Name: "{app}\python"

[Files]
Source: "..\build\installer\python\*"; DestDir: "{app}\python"; Flags: recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"

[Run]
; The Start menu entry Narcisse makes for itself (it files its windows under its own icon).
Filename: "{app}\python\python.exe"; Parameters: "-m narcisse shortcut"; Flags: runhidden
Filename: "{app}\python\pythonw.exe"; Parameters: "-m narcisse open"; Description: "{cm:OpenNarcisse}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: files; Name: "{userprograms}\Narcisse.lnk"
Type: filesandordirs; Name: "{app}\python"

[Registry]
; "Start with Windows", if the user ticked it, goes away with Narcisse. Their data stays.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Narcisse"; Flags: dontcreatekey uninsdeletevalue

[Code]
{ Stops this installation's Narcisse, and no other Python of the machine. }
procedure StopNarcisse();
var
  Code: Integer;
begin
  Exec('powershell.exe',
    '-NoProfile -NonInteractive -Command "Get-CimInstance Win32_Process | ' +
    'Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith(\"' +
    ExpandConstant('{app}') + '\\\", [StringComparison]::OrdinalIgnoreCase) } | ' +
    'ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"',
    '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(1500);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopNarcisse();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopNarcisse();
end;
