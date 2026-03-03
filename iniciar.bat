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
set REPO_ZIP=https://github.com/diego-anselmo/gsc-indexing-manager/archive/refs/heads/main.zip
set REPO_VERSION_URL=https://raw.githubusercontent.com/diego-anselmo/gsc-indexing-manager/main/version.txt
set LOCAL_VERSION_FILE=%WEB_DIR%version.txt

:: ════════════════════════════════════════════
::  VERIFICAÇÃO DE VERSÃO (rápida, silenciosa)
:: ════════════════════════════════════════════
echo  [*] Verificando atualizacoes...

:: Lê versão local (0 se não existir)
set LOCAL_VER=0
if exist "%LOCAL_VERSION_FILE%" (
    set /p LOCAL_VER=<"%LOCAL_VERSION_FILE%"
    :: Remove espaços/quebras de linha
    for /f "tokens=* delims= " %%v in ("!LOCAL_VER!") do set LOCAL_VER=%%v
)

:: Baixa versão remota via PowerShell (timeout 5s)
set REMOTE_VER=
for /f "delims=" %%v in ('powershell -NoProfile -Command "try { $r=(New-Object Net.WebClient).DownloadString('%REPO_VERSION_URL%').Trim(); Write-Output $r } catch { Write-Output '0' }" 2^>nul') do set REMOTE_VER=%%v

if "!REMOTE_VER!"=="0" (
    echo  [i] Sem conexao - verificacao de atualizacao ignorada.
    goto :checar_instalacao
)
if "!REMOTE_VER!"=="" (
    echo  [i] Nao foi possivel verificar atualizacoes.
    goto :checar_instalacao
)

:: Compara versões (numéricas YYYYMMDD)
if "!LOCAL_VER!"=="!REMOTE_VER!" (
    echo  [✓] Sistema ja esta na versao mais recente ^(!LOCAL_VER!^).
    goto :checar_instalacao
)

:: Nova versão disponível!
echo.
echo  ╔════════════════════════════════════════════════════════════╗
echo  ║  🆕  Atualizacao disponivel!                             ║
echo  ║                                                          ║
echo  ║  Versao atual:  !LOCAL_VER!                              ║
echo  ║  Versao nova:   !REMOTE_VER!                             ║
echo  ╚════════════════════════════════════════════════════════════╝
echo.
set /p ATUALIZAR="  Deseja atualizar agora? (S/N): "
if /i "!ATUALIZAR!" neq "S" goto :checar_instalacao

:: ────────────────────────────────────────────
::  BAIXAR E APLICAR ATUALIZAÇÃO
:: ────────────────────────────────────────────
echo.
echo  [*] Baixando atualizacao !REMOTE_VER!...

set TEMP_ZIP=%TEMP%\gsc_update_%RANDOM%.zip
set TEMP_DIR=%TEMP%\gsc_update_%RANDOM%

powershell -NoProfile -Command "try { $p=New-Object Net.WebClient; $p.Headers.Add('User-Agent','Mozilla/5.0'); $p.DownloadFile('%REPO_ZIP%','%TEMP_ZIP%'); exit 0 } catch { exit 1 }"
if %errorlevel% neq 0 (
    echo  [ERRO] Falha ao baixar atualizacao. Continuando com versao atual.
    if exist "%TEMP_ZIP%" del /f /q "%TEMP_ZIP%"
    goto :checar_instalacao
)

echo  [*] Extraindo arquivos...
powershell -NoProfile -Command "Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%TEMP_DIR%' -Force" >nul 2>&1

set EXTRACTED=%TEMP_DIR%\gsc-indexing-manager-main
if not exist "!EXTRACTED!" (
    echo  [ERRO] Estrutura inesperada no pacote. Continuando com versao atual.
    goto :limpar_temp
)

echo  [*] Aplicando atualizacao (dados e credenciais preservados)...
robocopy "!EXTRACTED!" "%WEB_DIR%" /E /NFL /NDL /NJH /NJS ^
    /XF client_secrets.json token.json *.pickle *.db *.sqlite ^
    /XD .venv data __pycache__ >nul 2>&1

:limpar_temp
if exist "%TEMP_ZIP%" del /f /q "%TEMP_ZIP%" >nul 2>&1
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" >nul 2>&1

echo  [✓] Atualizacao aplicada! Reiniciando...
echo.

:: Reinicia o iniciar.bat atualizado e sai do atual
start "" "%WEB_DIR%iniciar.bat"
exit /b 0

:: ════════════════════════════════════════════
::  INSTALAÇÃO (primeira vez, sem .venv)
:: ════════════════════════════════════════════
:checar_instalacao
echo.
if exist "%WEB_DIR%.venv\Scripts\python.exe" goto :iniciar

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

echo  ╔════════════════════════════════════════════════════════════╗
echo  ║  ⚠  Python NAO encontrado no seu computador!            ║
echo  ╚════════════════════════════════════════════════════════════╝
echo.
echo  ┌──────────────────────────────────────────────────────────┐
echo  │  Baixe em: https://www.python.org/downloads/            │
echo  │  IMPORTANTE: Marque "Add Python to PATH"!               │
echo  └──────────────────────────────────────────────────────────┘
echo.
set /p OPEN_BROWSER="  Deseja abrir o site para download? (S/N): "
if /i "!OPEN_BROWSER!"=="S" start https://www.python.org/downloads/
echo.
echo  Apos instalar o Python, execute este arquivo novamente.
echo.
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
    pause & exit /b 1
)
echo  [✓] Ambiente virtual criado.
echo.

:: ────────────────────────────────────────────
::  PASSO 3: Instalar Dependências
:: ────────────────────────────────────────────
echo  [PASSO 3/3] Instalando dependencias...
echo.

"%WEB_DIR%.venv\Scripts\python.exe" -m pip install --upgrade pip -q --disable-pip-version-check 2>nul

set DEPS=pandas google-api-python-client google-auth-oauthlib google-auth-httplib2 openpyxl requests lxml flask
set TOTAL=8
set CURRENT=0

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
        echo  [ERRO] Falha ao instalar %%P.
        pause & exit /b 1
    )
)

echo.
echo  [✓] Todas as dependencias instaladas!
echo.

:: Cria atalho na Área de Trabalho
set SHORTCUT_PATH=%USERPROFILE%\Desktop\GSC Indexing Manager.bat
(
    echo @echo off
    echo cd /d "%WEB_DIR%"
    echo call iniciar.bat
) > "%SHORTCUT_PATH%"
if exist "%SHORTCUT_PATH%" echo  [✓] Atalho criado na Area de Trabalho!

echo.
echo  ============================================================
echo  [✓] Instalacao concluida! Iniciando...
echo  ============================================================

:: ════════════════════════════════════════════
::  INICIAR SERVIDOR
:: ════════════════════════════════════════════
:iniciar
echo.
echo  ============================================================
echo   Acesse: http://localhost:5000
echo   Pressione Ctrl+C para encerrar.
echo  ============================================================
echo.

call "%WEB_DIR%.venv\Scripts\activate.bat"
pip install -r "%WEB_DIR%requirements.txt" -q --disable-pip-version-check 2>nul
start /b cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:5000"
python "%WEB_DIR%app.py"

echo.
echo  Servidor encerrado.
pause
