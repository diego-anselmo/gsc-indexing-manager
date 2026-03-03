@echo off
chcp 65001 >nul 2>&1
title GSC Indexing Manager - Atualizador
color 0B
setlocal enabledelayedexpansion

echo.
echo  ╔════════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║     🔄  GSC Indexing Manager - Atualizador               ║
echo  ║                                                          ║
echo  ╚════════════════════════════════════════════════════════════╝
echo.
echo  Este script vai atualizar o sistema para a versao mais recente.
echo  Seus dados e credenciais serao preservados.
echo.
echo  ============================================================
echo.

:: URL do repositório
set REPO_URL=https://github.com/diego-anselmo/gsc-indexing-manager.git
set WEB_DIR=%~dp0

:: ────────────────────────────────────────────
::  PASSO 1: Verificar Git
:: ────────────────────────────────────────────
echo  [PASSO 1/3] Verificando Git...
echo.

where git >nul 2>&1
if %errorlevel% neq 0 (
    echo  ╔════════════════════════════════════════════════════════════╗
    echo  ║  ⚠  Git NAO encontrado no seu computador!               ║
    echo  ╚════════════════════════════════════════════════════════════╝
    echo.
    echo  O Git e necessario para atualizar o sistema.
    echo.
    echo  ┌──────────────────────────────────────────────────────────┐
    echo  │  Baixe em: https://git-scm.com/download/win             │
    echo  │                                                         │
    echo  │  Apos instalar, execute este atualizador novamente.     │
    echo  └──────────────────────────────────────────────────────────┘
    echo.
    set /p OPEN_GIT="  Deseja abrir o site para download do Git? (S/N): "
    if /i "!OPEN_GIT!"=="S" (
        start https://git-scm.com/download/win
    )
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('git --version') do set GIT_VER=%%i
echo  [✓] !GIT_VER! encontrado.
echo.

:: ────────────────────────────────────────────
::  PASSO 2: Baixar atualização
:: ────────────────────────────────────────────
echo  [PASSO 2/3] Baixando atualizacao...
echo.

:: Verifica se já é um repositório git
if exist "%WEB_DIR%.git" (
    :: Já tem .git — apenas atualiza
    echo  [*] Repositorio git encontrado. Atualizando...
    echo.
    cd /d "%WEB_DIR%"
    git fetch origin >nul 2>&1
    if %errorlevel% neq 0 (
        echo  [ERRO] Nao foi possivel conectar ao repositorio.
        echo  Verifique sua conexao com a internet e tente novamente.
        echo.
        pause
        exit /b 1
    )
    git reset --hard origin/main >nul 2>&1
    if %errorlevel% neq 0 (
        echo  [ERRO] Falha ao aplicar atualizacao.
        echo.
        pause
        exit /b 1
    )
    echo  [✓] Codigo atualizado com sucesso!
) else (
    :: Não tem .git — clona em pasta temp e copia os arquivos
    echo  [*] Primeira atualizacao via Git. Clonando repositorio...
    echo.

    set TEMP_DIR=%WEB_DIR%_temp_update_gsc_
    if exist "!TEMP_DIR!" rmdir /s /q "!TEMP_DIR!"

    git clone --depth=1 "%REPO_URL%" "!TEMP_DIR!"
    if %errorlevel% neq 0 (
        echo.
        echo  [ERRO] Nao foi possivel clonar o repositorio.
        echo  Verifique sua conexao com a internet e tente novamente.
        echo.
        if exist "!TEMP_DIR!" rmdir /s /q "!TEMP_DIR!"
        pause
        exit /b 1
    )

    echo.
    echo  [*] Aplicando atualizacao (preservando dados locais)...
    echo.

    :: Copia arquivos novos, excluindo dados e credenciais sensíveis
    robocopy "!TEMP_DIR!" "%WEB_DIR%" /E /NFL /NDL /NJH /NJS ^
        /XF client_secrets.json token.json *.pickle ^
        /XD .venv data __pycache__ .git instalador >nul 2>&1

    :: Limpa pasta temporária
    rmdir /s /q "!TEMP_DIR!"

    echo  [✓] Arquivos atualizados com sucesso!
)

echo.

:: ────────────────────────────────────────────
::  PASSO 3: Atualizar dependências Python
:: ────────────────────────────────────────────
echo  [PASSO 3/3] Atualizando dependencias Python...
echo.

:: Verifica se o ambiente virtual existe
if not exist "%WEB_DIR%.venv" (
    echo  [!] Ambiente virtual nao encontrado.
    echo  Re-execute o instalador antes de iniciar o sistema.
    echo.
    goto :fim
)

"%WEB_DIR%.venv\Scripts\python.exe" -m pip install -r "%WEB_DIR%requirements.txt" -q --disable-pip-version-check
if %errorlevel% neq 0 (
    echo  [!] Aviso: Falha ao atualizar algumas dependencias.
    echo  O sistema pode funcionar mesmo assim.
) else (
    echo  [✓] Dependencias atualizadas com sucesso!
)

echo.

:: ────────────────────────────────────────────
::  FINALIZADO
:: ────────────────────────────────────────────
:fim
echo.
echo  ╔════════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║  ✅  Sistema atualizado para a versao mais recente!       ║
echo  ║                                                          ║
echo  ╠════════════════════════════════════════════════════════════╣
echo  ║                                                          ║
echo  ║  Seus dados e credenciais foram preservados.             ║
echo  ║                                                          ║
echo  ║  Para iniciar o sistema execute: iniciar.bat             ║
echo  ║                                                          ║
echo  ╚════════════════════════════════════════════════════════════╝
echo.

set /p INICIAR="  Deseja iniciar o sistema agora? (S/N): "
if /i "%INICIAR%"=="S" (
    echo.
    call "%WEB_DIR%iniciar.bat"
)

echo.
pause
