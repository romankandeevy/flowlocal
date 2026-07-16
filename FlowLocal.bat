@echo off
rem Запуск FlowLocal без окна консоли.
rem Исполняемые строки - только ASCII: bat читается в кодировке cp866,
rem и кириллица в командах превратилась бы в мусор. Путь к pythonw ищем
rem сперва на PATH, при промахе берём известное место установки.
set "PYW=pythonw.exe"
where %PYW% >nul 2>nul || set "PYW=%LOCALAPPDATA%\Python\pythoncore-3.14-64\pythonw.exe"
start "" /d "%~dp0" "%PYW%" app.py
