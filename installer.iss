; Inno Setup betiği. Derleme: ISCC /DMyAppVersion=0.3.0 installer.iss   (build.bat bunu otomatik çalıştırır)
#ifndef MyAppVersion
  #define MyAppVersion "0.3.0"
#endif
[Setup]
AppId={{C3D4FAF8-DA10-49EE-AE0D-D2915F6605D8}
AppName=UUP Studio
AppVersion={#MyAppVersion}
AppPublisher=Bünyamin KAYA
AppPublisherURL=https://bunyaminkaya.com
DefaultDirName={autopf}\UUP Studio
DefaultGroupName=UUP Studio
PrivilegesRequired=admin
OutputDir=dist
OutputBaseFilename=UUP_Studio_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\UUP Studio.exe
ArchitecturesInstallIn64BitMode=x64compatible
[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Files]
Source: "dist\UUP Studio\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "THIRD_PARTY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\UUP Studio"; Filename: "{app}\UUP Studio.exe"
Name: "{autodesktop}\UUP Studio"; Filename: "{app}\UUP Studio.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"
[Run]
Filename: "{app}\UUP Studio.exe"; Description: "{cm:LaunchProgram,UUP Studio}"; Flags: nowait postinstall skipifsilent
