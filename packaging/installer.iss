; Inno Setup script for the per-user Windows installer (plan s 10.2, Phase 9; s 11).
; Build on Windows after dist\taxnetlab.exe exists:
;   iscc /DAppVersion=1.0.0rc1 packaging\installer.iss
; The installer needs no administrator rights: it installs under the user's local application folder,
; adds Start menu shortcuts and an uninstaller, and never touches the user's workspace (Documents\TaxNetLab).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6D2B7C1E-4A53-4E0B-9C1D-5F0B8E7A2C41}
AppName=International Tax Network Lab
AppVersion={#AppVersion}
AppVerName=International Tax Network Lab {#AppVersion}
AppPublisher=Wen Yi Leong
DefaultDirName={localappdata}\Programs\International Tax Network Lab
DefaultGroupName=International Tax Network Lab
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=taxnetlab-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
UninstallDisplayName=International Tax Network Lab {#AppVersion}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\taxnetlab.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion
Source: "..\docs\USER_GUIDE.md"; DestDir: "{app}"; DestName: "USER_GUIDE.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\International Tax Network Lab"; Filename: "{app}\taxnetlab.exe"
Name: "{group}\User guide"; Filename: "{app}\USER_GUIDE.txt"
Name: "{group}\Uninstall International Tax Network Lab"; Filename: "{uninstallexe}"
Name: "{autodesktop}\International Tax Network Lab"; Filename: "{app}\taxnetlab.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\taxnetlab.exe"; Description: "{cm:LaunchProgram,International Tax Network Lab}"; Flags: nowait postinstall skipifsilent
