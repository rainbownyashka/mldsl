#define AppName "MLDSL"
#define AppVersion "0.1.0"
#define AppPublisher "rainbownyashka"
#define AppExeName "mldsl.exe"

; Prepared by: packaging/prepare_installer_payload.py
#define BuildDir "..\\dist\\payload\\app"
#define AssetsDir "..\\dist\\payload\\assets"
#define SeedOutDir "..\\dist\\payload\\seed_out"
#define VsixPath "..\\dist\\payload\\mldsl-helper.vsix"

[Setup]
AppId={{D0E2D9AF-5A7D-4F19-9B89-0A1B9A1A8E23}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\\{#AppName}
DisableProgramGroupPage=yes
OutputDir=..\\dist\\release
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "addpath"; Description: "Добавить MLDSL в PATH (чтобы команда `mldsl` работала в любой папке)"; GroupDescription: "Интеграция"; Flags: checkedonce
Name: "contextmenu"; Description: "Добавить пункт в контекстное меню для .mldsl (компиляция в plan.json)"; GroupDescription: "Интеграция"; Flags: checkedonce
Name: "vscodeext"; Description: "Установить расширение VS Code (если VS Code найден)"; GroupDescription: "Интеграция"; Flags: checkedonce

[Files]
; App (Nuitka standalone folder)
Source: "{#BuildDir}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Static assets used by the compiler (read-only)
Source: "{#AssetsDir}\\*"; DestDir: "{app}\\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

; Seed generated out/ so user doesn't need python/repo. Goes to %LOCALAPPDATA%\MLDSL\out
Source: "{#SeedOutDir}\\*"; DestDir: "{localappdata}\\MLDSL\\out"; Flags: ignoreversion recursesubdirs createallsubdirs

; Optional VS Code extension
#ifexist "{#VsixPath}"
Source: "{#VsixPath}"; DestDir: "{tmp}"; DestName: "mldsl-helper.vsix"; Flags: ignoreversion deleteafterinstall; Tasks: vscodeext
#endif

[Icons]
Name: "{autoprograms}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"

[Registry]
; PATH
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addpath; Check: NeedsAddPath(ExpandConstant('{app}'))

; Context menu: compile current .mldsl into %APPDATA%\.minecraft\plan.json
Root: HKCU; Subkey: "Software\\Classes\\SystemFileAssociations\\.mldsl\\shell\\MLDSL_CompileToPlan"; ValueType: string; ValueName: ""; ValueData: "MLDSL: скомпилировать в plan.json"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\\Classes\\SystemFileAssociations\\.mldsl\\shell\\MLDSL_CompileToPlan\\command"; ValueType: string; ValueName: ""; ValueData: """{app}\\{#AppExeName}"" compile ""%%1"" --plan ""{userappdata}\\.minecraft\\plan.json"""; Tasks: contextmenu

[Code]
function NeedsAddPath(Dir: string): Boolean;
var
  Paths: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Paths) then
    Paths := '';
  Result := Pos(';' + Dir + ';', ';' + Paths + ';') = 0;
end;

function FindVSCodeExe(): string;
var
  P: string;
begin
  Result := '';
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\App Paths\Code.exe', '', P) then
    if FileExists(P) then begin Result := P; exit; end;

  if RegQueryStringValue(HKLM, 'Software\Microsoft\Windows\CurrentVersion\App Paths\Code.exe', '', P) then
    if FileExists(P) then begin Result := P; exit; end;

  // common per-user install
  P := ExpandConstant('{localappdata}\Programs\Microsoft VS Code\Code.exe');
  if FileExists(P) then begin Result := P; exit; end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  CodeExe: string;
  Vsix: string;
  ResultCode: Integer;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('vscodeext') then begin
    CodeExe := FindVSCodeExe();
    Vsix := ExpandConstant('{tmp}\mldsl-helper.vsix');
    if (CodeExe = '') then begin
      MsgBox('VS Code не найден. Расширение не установлено.'#13#10 +
        'Можно установить вручную: Extensions -> Install from VSIX.', mbInformation, MB_OK);
      exit;
    end;
    if not FileExists(Vsix) then begin
      MsgBox('VSIX не найден рядом с инсталлером (mldsl-helper.vsix). Расширение не установлено.', mbInformation, MB_OK);
      exit;
    end;
    Exec(CodeExe, '--install-extension "' + Vsix + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
