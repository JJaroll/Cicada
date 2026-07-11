; ============================================================================
; cicada_installer.iss
; Script de Inno Setup para empaquetar el ejecutable de Cicada generado por
; PyInstaller (dist\Cicada.exe) en un instalador clásico de Windows.
;
; Compilar con:
;   iscc cicada_installer.iss
;
; Requiere que PyInstaller ya haya generado: dist\Cicada.exe
; ============================================================================

#define MyAppName "Cicada"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "JJaroll"
#define MyAppURL "https://github.com/JJaroll"
#define MyAppExeName "Cicada.exe"
#define MyAppIcon "static\logos\cicada_logo.ico"

[Setup]
AppId={{B6C6C9C1-6E1B-4C6E-9C2A-3C1E6E7E9A11}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; El instalador final que consume el workflow de GitHub Actions
OutputDir=dist_installer
OutputBaseFilename=Cicada_Setup_Windows
SetupIconFile={#MyAppIcon}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Ejecutable "onefile" producido por PyInstaller (Cicada.spec)
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Ícono oficial embebido para accesos directos
Source: "{#MyAppIcon}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Menú Inicio
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\cicada_logo.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
; Escritorio (opcional, según el Task marcado por el usuario)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\cicada_logo.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
