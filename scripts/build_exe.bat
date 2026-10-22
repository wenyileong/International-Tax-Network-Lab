@echo off
rem Builds dist\taxnetlab.exe on Windows from this source folder, using the hash-locked environment.
rem Requires Python 3.12 (python.org installer, "Add python.exe to PATH" ticked). Run from the project folder.
setlocal
cd /d "%~dp0\.."
python -m venv .build-venv || goto :error
call .build-venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install --require-hashes -r requirements\windows-build.lock || goto :error
python -m pip install --no-deps -e . || goto :error
python scripts\write_build_manifest.py requirements\windows-build.lock || goto :error
pyinstaller --noconfirm --clean packaging\taxnetlab.spec || goto :error
dist\taxnetlab.exe selftest || goto :error
echo.
echo Built and self-tested: %CD%\dist\taxnetlab.exe
rem Optional: the per-user installer, if Inno Setup 6 is installed (https://jrsoftware.org/isinfo.php).
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
for /f %%v in ('python -c "import taxnetlab; print(taxnetlab.__version__)"') do set "APPVER=%%v"
if not exist "%ISCC%" goto :noinstaller
"%ISCC%" /DAppVersion=%APPVER% packaging\installer.iss || goto :error
echo Installer: %CD%\dist\taxnetlab-setup-%APPVER%.exe
goto :done
:noinstaller
echo Inno Setup not found: the installer was not built. The portable executable is ready.
:done
pause
exit /b 0
:error
echo.
echo Build failed. See the messages above.
pause
exit /b 1
