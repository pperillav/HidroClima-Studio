; Script de instalador Windows (Inno Setup 6) para HidroClima Studio

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

#define AppName "HidroClima Studio"
#define AppExeName "HidroClimaStudio.exe"
#define AppPublisher "HidroClima Studio"
#define AppURL "https://github.com/pperillav/HidroClima-Studio"

[Setup]
AppId={{7B6F8C91-4E5A-4D29-B3C1-98E2F0A145D1}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=HidroClimaStudio-Setup-{#AppVersion}
SetupIconFile=..\hidroclima\static\hidroclima_studio.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} v{#AppVersion}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
VersionInfoDescription=Instalador de HidroClima Studio — Hidrologia IDF, Climatologia y Pavimentos

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\HidroClimaStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Comment: "Hidrología IDF, Balance Hídrico, Climatología Ambiental y Pavimentos"
Name: "{group}\Manual 01 — Información General (PDF)"; Filename: "{app}\docs\manuals\01_Manual_Informacion_General.pdf"
Name: "{group}\Manual 02 — Tutorial y Casos Prácticos (PDF)"; Filename: "{app}\docs\manuals\02_Manual_Tutorial.pdf"
Name: "{group}\Manual 03 — Manual Científico y Fórmulas (PDF)"; Filename: "{app}\docs\manuals\03_Manual_Cientifico.pdf"
Name: "{group}\Manual 04 — Referencia y Verificación (PDF)"; Filename: "{app}\docs\manuals\04_Manual_Referencia_y_Verificacion.pdf"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
