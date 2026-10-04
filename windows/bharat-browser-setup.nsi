; Bharat Browser Setup for Windows 10/11. Bharat Browser is a Linux (GTK + WebKitGTK) app,
; so Setup installs its .deb package into Ubuntu on WSL 2 (setup.ps1 does that part, in a
; window of its own) and adds Windows shortcuts that open it through WSLg.
; Built on Linux by build-windows-installer.sh, which passes the defines below.

Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"

!macro Require NAME
  !ifndef ${NAME}
    !error "${NAME} is not defined: build with build-windows-installer.sh"
  !endif
!macroend
!insertmacro Require VERSION
!insertmacro Require DEB
!insertmacro Require ICON
!insertmacro Require LICENSE
!insertmacro Require OUTFILE

!define APP "Bharat Browser"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\BharatBrowser"
!define SETTINGS_KEY "Software\Bharat Browser"

Name "${APP}"
OutFile "${OUTFILE}"
InstallDir "$PROGRAMFILES64\${APP}"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
BrandingText "${APP} ${VERSION}"

VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "${APP}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "FileDescription" "${APP} Setup"
VIAddVersionKey "LegalCopyright" "MIT License"

!define MUI_ICON "${ICON}"
!define MUI_UNICON "${ICON}"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Install ${APP} ${VERSION}"
!define MUI_WELCOMEPAGE_TEXT "${APP} is a Linux app. On Windows it runs through WSL 2, Microsoft's built-in Linux support, and opens in its own window like any other program.$\r$\n$\r$\nSetup will:$\r$\n  - install or update WSL$\r$\n  - install Ubuntu if you don't have it (about 1 GB to download; you'll create a Linux username and password)$\r$\n  - install ${APP} inside Ubuntu$\r$\n  - add desktop and Start menu shortcuts$\r$\n$\r$\nIt can take 10 minutes or more, and may ask you to restart and run Setup again."
!define MUI_FINISHPAGE_TITLE "${APP} is installed"
!define MUI_FINISHPAGE_TEXT "Open ${APP} from the icon on your desktop or from the Start menu.$\r$\n$\r$\nThe first start after turning on your PC takes a few seconds while WSL starts."

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${LICENSE}"
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Var Distro
Var Launcher

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "${APP} needs 64-bit Windows 10 or 11."
    Abort
  ${EndIf}
  SetRegView 64
FunctionEnd

Function un.onInit
  SetRegView 64
FunctionEnd

Section "Install"
  SetOutPath "$INSTDIR"
  File "/oname=bharat-browser.deb" "${DEB}"
  File "/oname=bharat-browser.ico" "${ICON}"
  File "setup.ps1"
  File "wsl-setup.sh"

  DetailPrint "Setting up WSL, Ubuntu and ${APP} in a separate window. Follow the instructions there."
  ; Setup is a 32-bit program: without this, $SYSDIR is SysWOW64, whose 32-bit PowerShell can't find wsl.exe.
  ${DisableX64FSRedirection}
  ExecWait '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\setup.ps1" -Package "$INSTDIR\bharat-browser.deb" -ResultFile "$INSTDIR\distro.txt"' $0
  ${EnableX64FSRedirection}
  ${If} $0 == 3010
    MessageBox MB_ICONINFORMATION "WSL has been installed. Restart your PC, then run ${APP} Setup again to finish."
    Abort "Restart needed: run Setup again after restarting."
  ${ElseIf} $0 != 0
    Abort "Setup didn't finish (code $0). The PowerShell window showed why."
  ${EndIf}

  FileOpen $1 "$INSTDIR\distro.txt" r
  FileRead $1 $Distro
  FileClose $1
  ; FileRead keeps the line break at the end.
  ${Do}
    StrCpy $2 $Distro 1 -1
    ${If} $2 == "$\n"
    ${OrIf} $2 == "$\r"
      StrCpy $Distro $Distro -1
    ${Else}
      ${ExitDo}
    ${EndIf}
  ${Loop}
  Delete "$INSTDIR\distro.txt"
  Delete "$INSTDIR\bharat-browser.deb"

  ; wslg.exe opens a Linux GUI app without leaving a console window open. Without it
  ; (an old WSL), wsl.exe does the same with a console window, kept minimized.
  StrCpy $Launcher "$PROGRAMFILES64\WSL\wslg.exe"
  ${If} ${FileExists} "$Launcher"
    CreateShortCut "$DESKTOP\${APP}.lnk" "$Launcher" "-d $Distro --cd ~ -- bharat-browser" "$INSTDIR\bharat-browser.ico" 0
    CreateShortCut "$SMPROGRAMS\${APP}.lnk" "$Launcher" "-d $Distro --cd ~ -- bharat-browser" "$INSTDIR\bharat-browser.ico" 0
  ${Else}
    StrCpy $Launcher "$WINDIR\System32\wsl.exe"
    CreateShortCut "$DESKTOP\${APP}.lnk" "$Launcher" "-d $Distro --cd ~ -- bharat-browser" "$INSTDIR\bharat-browser.ico" 0 SW_SHOWMINIMIZED
    CreateShortCut "$SMPROGRAMS\${APP}.lnk" "$Launcher" "-d $Distro --cd ~ -- bharat-browser" "$INSTDIR\bharat-browser.ico" 0 SW_SHOWMINIMIZED
  ${EndIf}

  WriteRegStr HKLM "${SETTINGS_KEY}" "Distro" "$Distro"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayName" "${APP}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "Publisher" "${APP}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "URLInfoAbout" "https://github.com/Sangam1112/bharat-browser"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\bharat-browser.ico"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair" 1
SectionEnd

; Removes the browser and the shortcuts. WSL, Ubuntu and your browser data inside Ubuntu
; (~/.config/bharat-browser) stay, since you may use them for other things.
Section "Uninstall"
  ReadRegStr $Distro HKLM "${SETTINGS_KEY}" "Distro"
  ${If} $Distro != ""
    DetailPrint "Removing ${APP} from $Distro..."
    ${DisableX64FSRedirection}
    nsExec::ExecToLog '"$SYSDIR\wsl.exe" -d $Distro -u root -- apt-get remove -y bharat-browser'
    Pop $0
    ${EnableX64FSRedirection}
  ${EndIf}
  Delete "$DESKTOP\${APP}.lnk"
  Delete "$SMPROGRAMS\${APP}.lnk"
  Delete "$INSTDIR\bharat-browser.ico"
  Delete "$INSTDIR\setup.ps1"
  Delete "$INSTDIR\wsl-setup.sh"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKLM "${UNINSTALL_KEY}"
  DeleteRegKey HKLM "${SETTINGS_KEY}"
SectionEnd
