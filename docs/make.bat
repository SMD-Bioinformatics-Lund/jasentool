@ECHO OFF
pushd %~dp0
if "%SPHINXBUILD%" == "" (set SPHINXBUILD=sphinx-build)
set SOURCEDIR=source
set BUILDDIR=build
%SPHINXBUILD% >NUL 2>NUL
if errorlevel 9009 (
    echo.
    echo.The 'sphinx-build' command was not found. Make sure you have Sphinx
    echo.installed, then set the SPHINXBUILD environment variable to point
    echo.the full path of the 'sphinx-build' executable.
    exit /b 1
)
%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
goto end
:end
popd
