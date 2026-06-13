[Setup]
AppName=ADB Companion
AppVersion=1.0
DefaultDirName={autopf}\ADB Companion
DefaultGroupName=ADB Companion
UninstallDisplayIcon={app}\ADB_Companion.exe
OutputDir=D:\instalador de apps\dist
OutputBaseFilename=ADB_Companion_Setup
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
PrivilegesRequired=admin

[Files]
Source: "D:\instalador de apps\dist\ADB_Companion\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ADB Companion"; Filename: "{app}\ADB_Companion.exe"
Name: "{autodesktop}\ADB Companion"; Filename: "{app}\ADB_Companion.exe"

[Run]
Filename: "{app}\ADB_Companion.exe"; Description: "Iniciar ADB Companion"; Flags: nowait postinstall skipifsilent
