; Установщик FlowLocal. Собирается через tools/build.py --installer,
; руками - ISCC.exe tools/installer.iss (нужен Inno Setup 6).
;
; СТАВИМ В ПРОФИЛЬ, А НЕ В PROGRAM FILES, и это не вкусовщина:
;
; 1. Приложение хранит конфиг, историю, лог и модель РЯДОМ С EXE
;    (app_paths._app_dir). В Program Files обычному человеку писать нельзя -
;    приложение сломалось бы при первом же сохранении настройки.
; 2. Профиль не требует прав администратора, а значит нет и окна UAC. Для
;    диктовки, которую ставят «попробовать на пять минут», щит UAC - это уже
;    половина ушедших. Ровно поэтому в плане (6.3) отдельно отмечен Scoop:
;    «ставит без админа и UAC - самый низкий порог».
;
; РАЗДАЁМ ПАПКУ ЦЕЛИКОМ (onedir), а не один .exe: Qt под LGPLv3, §4(d)
; требует оставить возможность подменить библиотеку и перелинковать. Поэтому
; Source берёт dist/cpu/FlowLocal/* рекурсивно, вместе с _internal/ и
; текстами лицензий внутри. Подробности - licenses/README.txt.

#define AppName "FlowLocal"
#define AppVersion "0.1.0"
#define AppPublisher "romankandeevy"
#define AppURL "https://github.com/romankandeevy/flowlocal"
#define AppExe "FlowLocal.exe"
#define SourceDir "..\dist\cpu\FlowLocal"

[Setup]
; AppId менять нельзя никогда: по нему Windows узнаёт, что ставится обновление,
; а не вторая копия рядом.
AppId={{7F3A2C81-4E5D-4B9A-9C21-5D8E6F0A1B32}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
; lowest - никакого UAC. См. шапку.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=FlowLocal-{#AppVersion}-setup
SetupIconFile=..\assets\FlowLocal.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Приложение под Windows 10+: PySide6 и onnxruntime ниже не поедут.
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Ставится приложением на первом запуске, установщик о них не знает - иначе
; останутся навсегда.
Type: files; Name: "{app}\flow.log"
Type: files; Name: "{app}\flow.log.1"
Type: dirifempty; Name: "{app}"

[Code]
// Автозапуск приложение прописывает себе само, галочкой в настройках
// (app_paths.set_autostart). Установщик обязан убрать эту запись за собой:
// иначе после удаления Windows будет вечно пытаться запустить то, чего нет.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ConfigPath: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    RegDeleteValue(HKEY_CURRENT_USER,
      'Software\Microsoft\Windows\CurrentVersion\Run', 'FlowLocal');
  end;

  if CurUninstallStep = usPostUninstall then
  begin
    // Настройки и история - данные человека, а не наши. Молча стирать словарь,
    // замены и все расшифровки нельзя; спросить - можно.
    ConfigPath := ExpandConstant('{app}\config.json');
    if FileExists(ConfigPath) or FileExists(ExpandConstant('{app}\history.jsonl')) then
    begin
      if MsgBox('Удалить также ваши настройки, словарь и историю диктовок?' + #13#10 +
                'Модель (226 МБ) тоже будет удалена.' + #13#10#13#10 +
                'Нет - останутся в папке ' + ExpandConstant('{app}'),
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DeleteFile(ConfigPath);
        DeleteFile(ExpandConstant('{app}\history.jsonl'));
        DeleteFile(ExpandConstant('{app}\history.jsonl.1'));
        DelTree(ExpandConstant('{app}\models'), True, True, True);
        RemoveDir(ExpandConstant('{app}'));
      end;
    end;
  end;
end;
