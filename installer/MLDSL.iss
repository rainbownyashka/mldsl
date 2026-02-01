#define AppName "MLDSL"
#define AppVersion "0.1.0"
#define AppPublisher "rainbownyashka"
#define AppExeName "mldsl.exe"

; Expected build output (adjust if you use another build system)
#define BuildDir "..\\dist\\mldsl"

[Setup]
AppId={{D0E2D9AF-5A7D-4F19-9B89-0A1B9A1A8E23}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\\{#AppName}
DisableProgramGroupPage=yes
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "addpath"; Description: "Добавить MLDSL в PATH (чтобы команда `mldsl` работала в любой папке)"; GroupDescription: "Интеграция"; Flags: checkedonce
Name: "contextmenu"; Description: "Добавить пункт в контекстное меню для .mldsl (компиляция в plan.json)"; GroupDescription: "Интеграция"; Flags: checkedonce

[Files]
; Main executable
Source: "{#BuildDir}\\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Static assets used by the compiler (read-only)
Source: "..\\allactions.txt"; DestDir: "{app}\\assets"; Flags: ignoreversion
Source: "..\\src\\assets\\Aliases.json"; DestDir: "{app}\\assets"; Flags: ignoreversion
Source: "..\\src\\assets\\LangTokens.json"; DestDir: "{app}\\assets"; Flags: ignoreversion

; Optional: ship a default apples.txt if you have it in repo root
; Source: "..\\apples.txt"; DestDir: "{app}\\assets"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"

[Registry]
; PATH
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addpath; Check: NeedsAddPath(ExpandConstant('{app}'))

; Context menu: compile current .mldsl into %APPDATA%\.minecraft\plan.json
Root: HKCU; Subkey: "Software\\Classes\\SystemFileAssociations\\.mldsl\\shell\\MLDSL_CompileToPlan"; ValueType: string; ValueName: ""; ValueData: "MLDSL: скомпилировать в plan.json"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\\Classes\\SystemFileAssociations\\.mldsl\\shell\\MLDSL_CompileToPlan\\command"; ValueType: string; ValueName: ""; ValueData: "\"{app}\\{#AppExeName}\" compile \"%%1\" --plan \"{userappdata}\\.minecraft\\plan.json\""; Tasks: contextmenu

[Code]
function NeedsAddPath(Dir: string): Boolean;
var
  Paths: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Paths) then
    Paths := '';
  Result := Pos(';' + Dir + ';', ';' + Paths + ';') = 0;
end;

