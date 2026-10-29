@echo off
rem Smart weed lines for outlined vinyl lettering.
rem Usage: weedlines topper.svg   (or drag an SVG onto this file, or use it from Send To)
if "%~1"=="" (
  echo Usage: weedlines yourfile.svg [--amax 1.0 --emax 1.75 --amin 0.08] [--margin 0.375]
  pause
  exit /b 1
)
python "%~dp0weedlines.py" %*
pause
