@echo off
chcp 65001 >nul 2>&1
title GSC Indexing Manager
color 0B
setlocal enabledelayedexpansion

echo.
echo  ╔════════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║     🔍  GSC Indexing Manager                             ║
echo  ║                                                          ║
echo  ╚════════════════════════════════════════════════════════════╝
echo.

set WEB_DIR=%~dp0

:: ════════════════════════════════════════════
::  Verifica se já está instalado (tem .venv)
:: ════════════════════════════════════════════
if exist "%WEB_DIR%.venv\Scripts\python.exe" (
    goto :iniciar
)

:: ════════════════════════════════════════════
::  PRIMEIRA VEZ — Roda instalação completa
:: ════════════════════════════════════════════
echo  Parece que e a primeira vez que voce abre o sistema.
echo  A instalacao sera feita automaticamente. Aguarde...
echo.
echo  ============================================================
echo.

:: ────────────────────────────────────────────
::  PASSO 1: Verificar Python
:: ────────────────────────────────────────────
echo  [PASSO 1/3] Verificando Python...
echo.

set PYTHON_CMD=
where python >nul 2>&1
if %errorlevel% equ 0 ( set PYTHON_CMD=python & goto :python_found )
where python3 >nul 2>&1
if %errorlevel% equ 0 ( set PYTHON_CMD=python3 & goto :python_found )
where py >nul 2>&1
if %errorlevel% equ 0 ( set PYTHON_CMD=py & goto :python_found )

:: Python não encontrado
echo  ╔════════════════════════════════════════════════════════════╗
echo  ║  ⚠  Python NAO encontrado no seu computador!            ║
echo  ╚════════════════════════════════════════════════════════════╝
echo.
echo  O Python e necessario para rodar o sistema.
echo.
echo  ┌──────────────────────────────────────────────────────────┐
echo  │  Baixe em: https://www.python.org/downloads/            │
echo  │                                                         │
echo  │  IMPORTANTE: Marque "Add Python to PATH" na instalacao! │
echo  └──────────────────────────────────────────────────────────┘
echo.
set /p OPEN_BROWSER="  Deseja abrir o site para download? (S/N): "
if /i "!OPEN_BROWSER!"=="S" start https://www.python.org/downloads/
echo.
echo  Apos instalar o Python, execute este arquivo novamente.
echo.
pause
exit /b 1

:check_python_after_install
set "PATH=%LOCALAPPDATA%\Programs\Python\Python314\;%LOCALAPPDATA%\Programs\Python\Python314\Scripts\;%PATH%"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python313\;%LOCALAPPDATA%\Programs\Python\Python313\Scripts\;%PATH%"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\;%PATH%"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python311\;%LOCALAPPDATA%\Programs\Python\Python311\Scripts\;%PATH%"
where python >nul 2>&1
if %errorlevel% equ 0 ( set PYTHON_CMD=python & goto :python_found )
where py >nul 2>&1
if %errorlevel% equ 0 ( set PYTHON_CMD=py & goto :python_found )
echo  [ERRO] Python ainda nao foi detectado. Instale e tente novamente.
pause
exit /b 1

:python_found
for /f "tokens=*" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VER=%%i
echo  [✓] !PYTHON_VER! encontrado.
echo.

:: ────────────────────────────────────────────
::  PASSO 2: Criar Ambiente Virtual
:: ────────────────────────────────────────────
echo  [PASSO 2/3] Criando ambiente virtual...
echo.

if exist "%WEB_DIR%.venv" rmdir /s /q "%WEB_DIR%.venv"

%PYTHON_CMD% -m venv "%WEB_DIR%.venv"
if %errorlevel% neq 0 (
    echo  [ERRO] Falha ao criar ambiente virtual.
    pause
    exit /b 1
)
echo  [✓] Ambiente virtual criado.
echo.

:: ────────────────────────────────────────────
::  PASSO 3: Instalar Dependências
:: ────────────────────────────────────────────
echo  [PASSO 3/3] Instalando dependencias...
echo.

echo  [*] Atualizando pip...
"%WEB_DIR%.venv\Scripts\python.exe" -m pip install --upgrade pip -q --disable-pip-version-check 2>nul
echo  [✓] pip atualizado.
echo.

set DEPS=pandas google-api-python-client google-auth-oauthlib google-auth-httplib2 openpyxl requests lxml flask
set TOTAL=8
set CURRENT=0

echo  ┌──────────────────────────────────────────────────────────┐
echo  │  Instalando dependencias...                              │
echo  └──────────────────────────────────────────────────────────┘
echo.

for %%P in (%DEPS%) do (
    set /a CURRENT+=1
    set /a PERCENT=!CURRENT!*100/%TOTAL%
    set "BAR="
    set /a FILLED=!PERCENT!/5
    for /L %%B in (1,1,20) do (
        if %%B leq !FILLED! (set "BAR=!BAR!█") else (set "BAR=!BAR!░")
    )
    echo  [!CURRENT!/%TOTAL%] !PERCENT!%%  !BAR!  %%P
    "%WEB_DIR%.venv\Scripts\python.exe" -m pip install %%P -q --disable-pip-version-check 2>nul
    if !errorlevel! neq 0 (
        echo.
        echo  [ERRO] Falha ao instalar %%P. Verifique sua conexao e tente novamente.
        pause
        exit /b 1
    )
)

echo.
echo  [✓] Todas as dependencias instaladas!
echo.

:: Cria atalho na Área de Trabalho
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT_PATH=%DESKTOP%\GSC Indexing Manager.bat
(
    echo @echo off
    echo cd /d "%WEB_DIR%"
    echo call iniciar.bat
) > "%SHORTCUT_PATH%"
if exist "%SHORTCUT_PATH%" (
    echo  [✓] Atalho criado na Area de Trabalho!
    echo.
)

echo  ============================================================
echo  [✓] Instalacao concluida! Iniciando o sistema...
echo  ============================================================
echo.

:: ════════════════════════════════════════════
::  INICIAR SERVIDOR
:: ════════════════════════════════════════════
:iniciar
echo.
echo  ============================================================
echo   Iniciando servidor...
echo   Acesse: http://localhost:5000
echo  ============================================================
echo.
echo  Pressione Ctrl+C para encerrar.
echo.

call "%WEB_DIR%.venv\Scripts\activate.bat"

:: Instala/atualiza dependências silenciosamente
pip install -r "%WEB_DIR%requirements.txt" -q --disable-pip-version-check 2>nul

:: Abre o navegador após 2 segundos
start /b cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:5000"

:: Inicia o servidor
python "%WEB_DIR%app.py"

echo.
echo  Servidor encerrado.
pause
