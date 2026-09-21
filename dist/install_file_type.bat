@echo off
setlocal
set INSTALL_DIR=%~dp0
set INSTALL_DIR=%INSTALL_DIR:~0,-1%

echo Registering .lattice file type...
reg add "HKCU\Software\Classes\.lattice" /ve /d "LatticeArchive" /f
reg add "HKCU\Software\Classes\.lattice" /v "Content Type" /d "application/x-lattice" /f
reg add "HKCU\Software\Classes\LatticeArchive" /ve /d "Lattice Compressed Archive" /f
reg add "HKCU\Software\Classes\LatticeArchive\DefaultIcon" /ve /d "\"%INSTALL_DIR%\\lattice_gui.exe\",0" /f
reg add "HKCU\Software\Classes\LatticeArchive\shell\open" /ve /d "Open with Lattice" /f
reg add "HKCU\Software\Classes\LatticeArchive\shell\open\command" /ve /d "\"%INSTALL_DIR%\\lattice_gui.exe\" \"%%1\"" /f

echo Done! .lattice files will now show the Lattice icon.
echo You may need to restart Explorer or log out and back in.
pause
