#define AppName "MLDSL"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppPublisher "rainbownyashka"
#define AppExeName "mldsl.exe"

; Prepared by: packaging/prepare_installer_payload.py
#define BuildDir "..\\dist\\payload\\app"
#define AssetsDir "..\\dist\\payload\\assets"
#define SeedOutDir "..\\dist\\payload\\seed_out"
#define VsixPath "..\\dist\\payload\\mldsl-helper.vsix"

#ifndef NoVsix
  ; Set to 1 to build installer without bundling the VSIX (dev builds).
  #define NoVsix 0
#endif

[Setup]
AppId={{D0E2D9AF-5A7D-4F19-9B89-0A1B9A1A8E23}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\\dist\\release
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "mldslcore"; Description: "Установить MLDSL (компилятор, docs, расширение)"; GroupDescription: "Опции"; Flags: checkedonce
Name: "addpath"; Description: "Добавить MLDSL в PATH (чтобы вызывать `mldsl` из любой папки)"; GroupDescription: "Опции"; Flags: unchecked
Name: "contextmenu"; Description: "Добавить пункт в контекстное меню для .mldsl (компиляция в plan.json)"; GroupDescription: "Опции"; Flags: unchecked
Name: "vscodeext"; Description: "Установить расширение для VS Code (если VS Code найден)"; GroupDescription: "Опции"; Flags: checkedonce
Name: "bettercode"; Description: "Скачать/обновить мод BetterCode в %APPDATA%\.minecraft\mods"; GroupDescription: "Опции"

[Files]
; App (Nuitka standalone folder)
Source: "{#BuildDir}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Tasks: mldslcore

; Static assets used by the compiler (read-only)
Source: "{#AssetsDir}\\*"; DestDir: "{app}\\assets"; Flags: ignoreversion recursesubdirs createallsubdirs; Tasks: mldslcore

; Seed generated out/ so user doesn't need python/repo. Goes to %LOCALAPPDATA%\\MLDSL\\out
Source: "{#SeedOutDir}\\*"; DestDir: "{localappdata}\\MLDSL\\out"; Flags: ignoreversion recursesubdirs createallsubdirs; Tasks: mldslcore

; Optional VS Code extension
#if NoVsix == 0
Source: "{#VsixPath}"; DestDir: "{tmp}"; DestName: "mldsl-helper.vsix"; Flags: ignoreversion deleteafterinstall; Tasks: mldslcore vscodeext
#endif

[Icons]
Name: "{autoprograms}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"; Tasks: mldslcore

[Registry]
; PATH
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: mldslcore addpath; Check: NeedsAddPath(ExpandConstant('{app}'))

; Context menu: compile current .mldsl into %APPDATA%\\.minecraft\\plan.json
Root: HKCU; Subkey: "Software\\Classes\\SystemFileAssociations\\.mldsl\\shell\\MLDSL_CompileToPlan"; ValueType: string; ValueName: ""; ValueData: "MLDSL: Скомпилировать в plan.json"; Tasks: mldslcore contextmenu
Root: HKCU; Subkey: "Software\\Classes\\SystemFileAssociations\\.mldsl\\shell\\MLDSL_CompileToPlan\\command"; ValueType: string; ValueName: ""; ValueData: """{app}\\{#AppExeName}"" compile ""%%1"" --plan ""{userappdata}\\.minecraft\\plan.json"""; Tasks: mldslcore contextmenu

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

function InstallOrUpdateBetterCodeMod(): Boolean;
var
  PsExe: string;
  ScriptPath: string;
  Script: string;
  ResultCode: Integer;
begin
  Result := False;
  PsExe := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  if not FileExists(PsExe) then
    PsExe := 'powershell.exe';

  ScriptPath := ExpandConstant('{tmp}\mldsl_bettercode_update.ps1');
  Script :=
    '$ErrorActionPreference = "Stop"'#13#10 +
    '$repo = "rainbownyashka/mlbettercode"'#13#10 +
    '$api = "https://api.github.com/repos/" + $repo + "/releases/latest"'#13#10 +
    '$release = Invoke-RestMethod -Uri $api -Headers @{ "User-Agent" = "MLDSL-Installer" }'#13#10 +
    '$tag = [string]$release.tag_name'#13#10 +
    '$expected = if ($tag -match "^v") { "bettercode-" + $tag.Substring(1) + ".jar" } else { "bettercode-" + $tag + ".jar" }'#13#10 +
    '$asset = $release.assets | Where-Object { $_.name -ieq $expected } | Select-Object -First 1'#13#10 +
    'if (-not $asset) {'#13#10 +
    '  $asset = $release.assets | Where-Object { $_.name -match "^bettercode-.*\.jar$" } | Sort-Object -Property name -Descending | Select-Object -First 1'#13#10 +
    '}'#13#10 +
    'if (-not $asset) { throw "No BetterCode jar asset found in latest release." }'#13#10 +
    '$mods = Join-Path $env:APPDATA ".minecraft\mods"'#13#10 +
    'New-Item -ItemType Directory -Force -Path $mods | Out-Null'#13#10 +
    'Get-ChildItem -Path $mods -Filter "bettercode-*.jar" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue'#13#10 +
    '$outPath = Join-Path $mods $asset.name'#13#10 +
    'Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $outPath -UseBasicParsing'#13#10 +
    'Write-Output ("Installed: " + $outPath)'#13#10;

  if not SaveStringToFile(ScriptPath, Script, False) then
    exit;

  if not Exec(
    PsExe,
    '-NoProfile -ExecutionPolicy Bypass -File "' + ScriptPath + '"',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) then
    exit;

  Result := (ResultCode = 0);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  CodeExe: string;
  Vsix: string;
  ResultCode: Integer;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('mldslcore') and WizardIsTaskSelected('vscodeext') then begin
    CodeExe := FindVSCodeExe();
    Vsix := ExpandConstant('{tmp}\mldsl-helper.vsix');

    if (CodeExe = '') then begin
      MsgBox(
        'VS Code не найден. Расширение не будет установлено автоматически.'#13#10 +
        'Можно установить вручную: Extensions → Install from VSIX.',
        mbInformation,
        MB_OK
      );
      exit;
    end;

    if not FileExists(Vsix) then begin
      MsgBox(
        'VSIX-файл не найден в установщике (mldsl-helper.vsix).'#13#10 +
        'Расширение не будет установлено автоматически.',
        mbInformation,
        MB_OK
      );
      exit;
    end;

    // Do not block installer on VS Code process lifecycle.
    // On some systems Code.exe may remain running and Setup appears frozen.
    if not Exec(CodeExe, '--install-extension "' + Vsix + '" --force', '', SW_HIDE, ewNoWait, ResultCode) then begin
      MsgBox(
        'Не удалось запустить установку расширения VS Code автоматически.'#13#10 +
        'Можно установить вручную: Extensions → Install from VSIX.',
        mbInformation,
        MB_OK
      );
    end;
  end;

  if (CurStep = ssPostInstall) and WizardIsTaskSelected('bettercode') then begin
    if not InstallOrUpdateBetterCodeMod() then begin
      MsgBox(
        'Не удалось скачать/обновить BetterCode автоматически.'#13#10 +
        'Проверь интернет и попробуй вручную:'#13#10 +
        'https://github.com/rainbownyashka/mlbettercode/releases',
        mbInformation,
        MB_OK
      );
    end else begin
      MsgBox(
        'BetterCode успешно скачан/обновлён в %APPDATA%\.minecraft\mods.',
        mbInformation,
        MB_OK
      );
    end;
  end;
end;
