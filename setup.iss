; setup.iss
[Setup]
AppId={{B5E8E3F2-6F2A-4D1B-8E3A-2F3B5C8D9E1A}}
AppName=Sistema de Gestión de Mantenimiento
AppVersion=1.0
AppPublisher=TuEmpresa
AppPublisherURL=https://tusitio.com
DefaultDirName={pf}\MaintenanceSystem
DefaultGroupName=Sistema de Mantenimiento
UninstallDisplayIcon={app}\logo.ico
Compression=lzma2
SolidCompression=yes
OutputDir=installer\Output
OutputBaseFilename=MaintenanceSystem_Setup
SetupIconFile=logo.ico
PrivilegesRequired=admin
WizardStyle=modern
DisableWelcomePage=no
DisableFinishedPage=no
ShowLanguageDialog=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Archivos de la aplicación (toda la carpeta app)
Source: "app\*"; DestDir: "{app}\app"; Flags: recursesubdirs createallsubdirs
; Archivos raíz
Source: "docker-compose.yml"; DestDir: "{app}"
Source: "Dockerfile"; DestDir: "{app}"
Source: "docker-entrypoint.sh"; DestDir: "{app}"
Source: "requirements.txt"; DestDir: "{app}"
Source: "run.py"; DestDir: "{app}"
Source: "config.py"; DestDir: "{app}"
; Script auxiliar
Source: "installer\setuph.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Sistema de Mantenimiento (Local)"; Filename: "http://localhost:5001"
Name: "{group}\Desinstalar"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Sistema de Mantenimiento (Local)"; Filename: "http://localhost:5001"

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\setuph.ps1"" -InstallDir ""{app}"""; Description: "Configurando el sistema..."; Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\setuph.ps1"" -Uninstall"; Flags: runhidden

[Code]
function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
  ResultCode: Integer;
begin
  Result := True;
  Exec('cmd', '/c docker --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if ResultCode <> 0 then
  begin
    if MsgBox('Docker Desktop no está instalado. ¿Deseas descargarlo?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://www.docker.com/products/docker-desktop/', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
    end;
    MsgBox('Este programa requiere Docker Desktop. Instálalo y vuelve a ejecutar el instalador.', mbError, MB_OK);
    Result := False;
  end;
end;