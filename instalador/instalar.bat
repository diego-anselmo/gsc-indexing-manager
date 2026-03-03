@echo off
chcp 65001 >nul 2>&1
title ⚙ Instalador - GSC Indexing Manager
color 0B
setlocal enabledelayedexpansion

echo.
echo  ╔════════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║     ⚙  GSC Indexing Manager - Instalador Completo       ║
echo  ║                                                          ║
echo  ╚════════════════════════════════════════════════════════════╝
echo.
echo  Este instalador vai configurar tudo que voce precisa:
echo.
echo    1. Verificar/Instalar Python
echo    2. Criar ambiente virtual
echo    3. Instalar todas as dependencias
echo    4. Criar atalho para iniciar o sistema
echo.
echo  ============================================================
echo.

:: Diretorio do projeto web (pasta pai do instalador)
set WEB_DIR=%~dp0..

:: ────────────────────────────────────────────
::  PASSO 1: Verificar Python
:: ────────────────────────────────────────────
echo  [PASSO 1/4] Verificando Python...
echo.

:: Tenta encontrar o Python
set PYTHON_CMD=
where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto :python_found
)
where python3 >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python3
    goto :python_found
)
where py >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    goto :python_found
)

:: Python nao encontrado - oferecer download
echo  ╔════════════════════════════════════════════════════════════╗
echo  ║  ⚠  Python NAO encontrado no seu computador!            ║
echo  ╚════════════════════════════════════════════════════════════╝
echo.
echo  O Python e necessario para rodar o sistema.
echo.

:: Verifica se o instalador do Python ja existe na pasta
set PYTHON_INSTALLER=%~dp0python_installer.exe
if exist "%PYTHON_INSTALLER%" (
    echo  [!] Instalador do Python encontrado na pasta.
    echo.
    set /p INSTALL_PYTHON="  Deseja instalar o Python agora? (S/N): "
    if /i "!INSTALL_PYTHON!"=="S" (
        echo.
        echo  [*] Executando instalador do Python...
        echo  [!] IMPORTANTE: Marque "Add Python to PATH" na tela de instalacao!
        echo.
        start /wait "" "%PYTHON_INSTALLER%" /passive InstallAllUsers=0 PrependPath=1 Include_test=0
        goto :check_python_after_install
    )
) else (
    echo  Voce precisa baixar e instalar o Python manualmente.
    echo.
    echo  ┌──────────────────────────────────────────────────────────┐
    echo  │  Link: https://www.python.org/downloads/                │
    echo  │                                                         │
    echo  │  IMPORTANTE: Na tela de instalacao, marque a opcao:     │
    echo  │  [x] "Add Python to PATH"                               │
    echo  └──────────────────────────────────────────────────────────┘
    echo.
    set /p OPEN_BROWSER="  Deseja abrir o site para download? (S/N): "
    if /i "!OPEN_BROWSER!"=="S" (
        start https://www.python.org/downloads/
    )
    echo.
    echo  Apos instalar o Python, execute este instalador novamente.
    echo.
    pause
    exit /b 1
)

:check_python_after_install
:: Atualiza PATH apos instalacao
set "PATH=%LOCALAPPDATA%\Programs\Python\Python314\;%LOCALAPPDATA%\Programs\Python\Python314\Scripts\;%PATH%"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python313\;%LOCALAPPDATA%\Programs\Python\Python313\Scripts\;%PATH%"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\;%PATH%"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python311\;%LOCALAPPDATA%\Programs\Python\Python311\Scripts\;%PATH%"

where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto :python_found
)
where py >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    goto :python_found
)

echo.
echo  [ERRO] Python ainda nao foi detectado.
echo  Feche este terminal, instale o Python e tente novamente.
echo.
pause
exit /b 1

:python_found
:: Mostra versao do Python
for /f "tokens=*" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VER=%%i
echo  [✓] %PYTHON_VER% encontrado.
echo.

:: ────────────────────────────────────────────
::  PASSO 2: Criar Ambiente Virtual
:: ────────────────────────────────────────────
:: Sempre recria o ambiente virtual para garantir compatibilidade
if exist "%WEB_DIR%\.venv" (
    echo  [*] Removendo ambiente virtual anterior...
    rmdir /s /q "%WEB_DIR%\.venv"
)

echo  [*] Criando ambiente virtual com %PYTHON_VER%...
%PYTHON_CMD% -m venv "%WEB_DIR%\.venv"
if %errorlevel% neq 0 (
    echo.
    echo  [ERRO] Falha ao criar ambiente virtual.
    echo  Verifique se o Python esta instalado corretamente.
    echo.
    pause
    exit /b 1
)
echo  [✓] Ambiente virtual criado com sucesso.
echo.

:: ────────────────────────────────────────────
::  PASSO 3: Instalar Dependencias
:: ────────────────────────────────────────────
echo  [PASSO 3/4] Instalando dependencias...
echo.

echo  [*] Atualizando pip...
"%WEB_DIR%\.venv\Scripts\python.exe" -m pip install --upgrade pip -q --disable-pip-version-check 2>nul
echo  [✓] pip atualizado.
echo.

:: Lista de dependencias (mesma do requirements.txt)
set DEPS=pandas google-api-python-client google-auth-oauthlib google-auth-httplib2 openpyxl requests lxml flask
set TOTAL=8
set CURRENT=0

echo  ┌──────────────────────────────────────────────────────────┐
echo  │  Instalando %TOTAL% dependencias...                          │
echo  └──────────────────────────────────────────────────────────┘
echo.

for %%P in (%DEPS%) do (
    set /a CURRENT+=1
    set /a PERCENT=!CURRENT!*100/%TOTAL%

    :: Monta barra de progresso visual
    set "BAR="
    set /a FILLED=!PERCENT!/5
    for /L %%B in (1,1,20) do (
        if %%B leq !FILLED! (
            set "BAR=!BAR!█"
        ) else (
            set "BAR=!BAR!░"
        )
    )

    echo  [!CURRENT!/%TOTAL%] !PERCENT!%%  !BAR!  Instalando: %%P
    "%WEB_DIR%\.venv\Scripts\python.exe" -m pip install %%P -q --disable-pip-version-check 2>nul
    if !errorlevel! neq 0 (
        echo.
        echo  [ERRO] Falha ao instalar %%P
        echo  Verifique sua conexao com a internet e tente novamente.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo  [✓] Todas as %TOTAL% dependencias instaladas com sucesso!
echo.

:: ────────────────────────────────────────────
::  PASSO 4: Criar atalho na Area de Trabalho
:: ────────────────────────────────────────────
echo  [PASSO 4/4] Criando atalho na Area de Trabalho...
echo.

set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT_PATH=%DESKTOP%\GSC Indexing Manager.bat

(
    echo @echo off
    echo chcp 65001 ^>nul 2^>^&1
    echo title GSC Indexing Manager
    echo cd /d "%WEB_DIR%"
    echo call .venv\Scripts\activate.bat
    echo echo.
    echo echo  Iniciando GSC Indexing Manager...
    echo echo  Acesse: http://localhost:5000
    echo echo.
    echo start /b cmd /c "timeout /t 2 /nobreak ^>nul ^& start http://localhost:5000"
    echo python app.py
    echo pause
) > "%SHORTCUT_PATH%"

if exist "%SHORTCUT_PATH%" (
    echo  [✓] Atalho criado na Area de Trabalho!
    echo      "%SHORTCUT_PATH%"
) else (
    echo  [!] Nao foi possivel criar o atalho automaticamente.
    echo      Use o arquivo "iniciar.bat" para abrir o sistema.
)
echo.

:: ────────────────────────────────────────────
::  FINALIZADO
:: ────────────────────────────────────────────
echo.
echo  ╔════════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║  ✅  Instalacao concluida com sucesso!                    ║
echo  ║                                                          ║
echo  ╠════════════════════════════════════════════════════════════╣
echo  ║                                                          ║
echo  ║  Para iniciar o sistema:                                 ║
echo  ║                                                          ║
echo  ║    • Clique 2x no atalho "GSC Indexing Manager"          ║
echo  ║      na sua Area de Trabalho                             ║
echo  ║                                                          ║
echo  ║    • Ou execute: iniciar.bat                             ║
echo  ║                                                          ║
echo  ║  O sistema abrira no navegador em:                       ║
echo  ║    http://localhost:5000                                  ║
echo  ║                                                          ║
echo  ╚════════════════════════════════════════════════════════════╝
echo.

set /p INICIAR="  Deseja iniciar o sistema agora? (S/N): "
if /i "%INICIAR%"=="S" (
    echo.
    echo  [*] Iniciando o sistema...
    echo.
    cd /d "%WEB_DIR%"
    start /b cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:5000"
    python app.py
)

echo.
pause
