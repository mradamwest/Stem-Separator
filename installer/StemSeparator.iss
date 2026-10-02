#define MyAppName "Stem Separator"
#define MyAppVersion "0.1.0"
#define MyAppExeName "StemSeparator.exe"
[Setup]
AppId={{D5E4B5D9-741B-4C8A-9C27-FA765F88446A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\Stem Separator
DefaultGroupName=Stem Separator
OutputDir=..\dist-installer
OutputBaseFilename=Stem_Separator_Setup_0.1.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=Stem Separator
Uninstallable=yes
CreateUninstallRegKey=yes
[Files]
Source: "..\dist\StemSeparator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\Stem Separator"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Stem Separator"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\Uninstall Stem Separator"; Filename: "{uninstallexe}"
