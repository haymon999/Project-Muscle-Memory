@echo off
title Critical Ops Offline Mock :8080
cd /d "%~dp0"
echo === Critical Ops offline server ===
echo Mock: tools\proxy\offline_mock.py  (listens 0.0.0.0:8080, TCP+UDP game ports)
echo Log:  logs\offline_mock.log  (every game request lands here)
echo Test:  http://192.168.0.249:8080/status/ping/  should print {"status":"success"}
echo.
if exist "C:\Python314\python.exe" (
  C:\Python314\python.exe tools\proxy\offline_mock.py
) else (
  py -3 tools\proxy\offline_mock.py
)
echo.
echo --- server stopped ---
pause
