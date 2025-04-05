; YTune Installer Script
; NSIS Script for creating an installer

!include "MUI2.nsh"

; General settings
Name "YTune"
OutFile "YTune_Setup.exe"
InstallDir "$PROGRAMFILES\YTune"
InstallDirRegKey HKCU "Software\YTune" ""
RequestExecutionLevel admin

; Modern UI settings
!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\icons\music_note.png"
!define MUI_UNICON "..\assets\icons\music_note.png"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Languages
!insertmacro MUI_LANGUAGE "English"

; Installation section
Section "Install"
  SetOutPath "$INSTDIR"
  
  ; Copy application files
  File /r "..\build\dist\*.*"
  
  ; Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  
  ; Create shortcuts
  CreateDirectory "$SMPROGRAMS\YTune"
  CreateShortcut "$SMPROGRAMS\YTune\YTune.lnk" "$INSTDIR\YTune.exe"
  CreateShortcut "$SMPROGRAMS\YTune\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\YTune.lnk" "$INSTDIR\YTune.exe"
  
  ; Write registry keys for uninstall
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YTune" "DisplayName" "YTune"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YTune" "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YTune" "DisplayIcon" "$INSTDIR\YTune.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YTune" "Publisher" "YTune Team"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YTune" "DisplayVersion" "1.0.0"
SectionEnd

; Uninstall section
Section "Uninstall"
  ; Remove application files
  RMDir /r "$INSTDIR"
  
  ; Remove shortcuts
  Delete "$SMPROGRAMS\YTune\YTune.lnk"
  Delete "$SMPROGRAMS\YTune\Uninstall.lnk"
  RMDir "$SMPROGRAMS\YTune"
  Delete "$DESKTOP\YTune.lnk"
  
  ; Remove registry keys
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YTune"
  DeleteRegKey HKCU "Software\YTune"
SectionEnd 