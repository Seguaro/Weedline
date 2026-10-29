; Inno Setup script for Weed Lines
; Build the program first with PyInstaller (from the project folder):
;   py -m PyInstaller --onedir --noconsole --icon=weedlines.ico --splash=splash.png weedlines.py
; Then open this file in Inno Setup and press Compile (or run: iscc installer\weedlines.iss).
; The finished installer lands in installer\Output\.
;
; When you release a new version, change MyAppVersion (and MyAppNumericVersion) below.

#define MyAppName "Weed Lines"
#define MyAppVersion "0.1.0-beta"
#define MyAppNumericVersion "0.1.0.0"
#define MyAppPublisher "Studio 57 Design"
#define MyAppURL "https://studio57design.com"
; Change this to your GitHub page once the project is up, e.g. https://github.com/yourname/weedlines
#define MyAppSupportURL "https://studio57design.com"
#define MyAppExeName "weedlines.exe"

[Setup]
; AppId identifies this program to Windows across versions. Never change it.
AppId={{F5B001C4-3F6B-473C-9168-86F3BBE4D7DF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppSupportURL}
AppUpdatesURL={#MyAppSupportURL}
AppCopyright=Copyright (c) 2026 George Sladic, Studio 57 Design
VersionInfoVersion={#MyAppNumericVersion}
VersionInfoDescription={#MyAppName} Setup

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; No admin rights needed by default; the user can choose "install for all users" instead.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; PyInstaller builds a 64-bit program when built with 64-bit Python.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

LicenseFile=..\LICENSE
SetupIconFile=..\weedlines.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
WizardStyle=modern
OutputDir=Output
OutputBaseFilename=WeedLines-{#MyAppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "contextmenu"; Description: "Add ""Add weed lines"" to the right-click menu for SVG files"; GroupDescription: "Shortcuts:"

[Files]
; The whole PyInstaller output folder: weedlines.exe plus its _internal folder.
Source: "..\dist\weedlines\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} License"; Filename: "{app}\LICENSE.txt"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Right-click an SVG in Explorer -> "Add weed lines". On Windows 11 it appears under "Show more options".
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.svg\shell\WeedLines"; ValueType: string; ValueName: ""; ValueData: "Add weed lines"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.svg\shell\WeedLines"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"",0"; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.svg\shell\WeedLines\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: contextmenu

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
