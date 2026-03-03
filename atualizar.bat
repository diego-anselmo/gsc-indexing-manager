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

:: Configurações
set REPO_ZIP=https://github.com/diego-anselmo/gsc-indexing-manager/archive/refs/heads/main.zip
set WEB_DIR=%~dp0
set TEMP_ZIP=%TEMP%\gsc_update_%RANDOM%.zip
set TEMP_DIR=%TEMP%\gsc_update_%RANDOM%

:: ────────────────────────────────────────────
::  PASSO 1: Verificar conexão com internet
:: ────────────────────────────────────────────
echo  [PASSO 1/3] Verificando conexao com a internet...
echo.

powershell -Command "try { (New-Object Net.WebClient).DownloadString('https://github.com') | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% neq 0 (
    echo  ╔════════════════════════════════════════════════════════════╗
    echo  ║  ⚠  Sem conexao com a internet!                         ║
    echo  ╚════════════════════════════════════════════════════════════╝
    echo.
    echo  Verifique sua conexao e tente novamente.
    echo.
    pause
    exit /b 1
)
echo  [✓] Conexao OK.
echo.

:: ────────────────────────────────────────────
::  PASSO 2: Baixar e aplicar atualização
:: ────────────────────────────────────────────
echo  [PASSO 2/3] Baixando atualizacao do GitHub...
echo.

:: Baixa o ZIP usando PowerShell (nativo no Windows)
powershell -Command "try { $p = New-Object System.Net.WebClient; $p.Headers.Add('User-Agent', 'Mozilla/5.0'); $p.DownloadFile('%REPO_ZIP%', '%TEMP_ZIP%'); exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
if %errorlevel% neq 0 (
    echo  [ERRO] Nao foi possivel baixar a atualizacao.
    echo  Tente novamente em alguns instantes.
    echo.
    pause
    exit /b 1
)
echo  [✓] Download concluido.
echo.

echo  [*] Extraindo arquivos...

:: Extrai o ZIP
powershell -Command "try { Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%TEMP_DIR%' -Force; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
if %errorlevel% neq 0 (
    echo  [ERRO] Falha ao extrair o arquivo baixado.
    if exist "%TEMP_ZIP%" del /f /q "%TEMP_ZIP%"
    echo.
    pause
    exit /b 1
)

:: O GitHub extrai numa subpasta com o nome do repo + branch (gsc-indexing-manager-main)
set EXTRACTED=%TEMP_DIR%\gsc-indexing-manager-main

if not exist "%EXTRACTED%" (
    echo  [ERRO] Estrutura do arquivo inesperada.
    if exist "%TEMP_ZIP%" del /f /q "%TEMP_ZIP%"
    if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
    echo.
    pause
    exit /b 1
)

echo  [*] Aplicando atualizacao (preservando dados locais)...
echo.

:: Copia os arquivos, preservando credenciais e dados locais
robocopy "%EXTRACTED%" "%WEB_DIR%" /E /NFL /NDL /NJH /NJS ^
    /XF client_secrets.json token.json *.pickle *.db *.sqlite ^
    /XD .venv data __pycache__ >nul 2>&1

:: Limpa arquivos temporários
del /f /q "%TEMP_ZIP%" >nul 2>&1
rmdir /s /q "%TEMP_DIR%" >nul 2>&1

echo  [✓] Arquivos atualizados com sucesso!
echo.

:: ────────────────────────────────────────────
::  PASSO 3: Atualizar dependências Python
:: ────────────────────────────────────────────
echo  [PASSO 3/3] Atualizando dependencias Python...
echo.

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
