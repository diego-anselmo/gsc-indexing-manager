@echo off
chcp 65001 >nul 2>&1
title GSC Indexing Manager - Iniciando...

echo.
echo ============================================================
echo   GSC Indexing Manager - Interface Web
echo ============================================================
echo.

:: Verifica se Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado!
    echo.
    echo Voce precisa instalar o Python 3.9 ou superior.
    echo Baixe em: https://www.python.org/downloads/
    echo.
    echo IMPORTANTE: Marque a opcao "Add Python to PATH" durante a instalacao!
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python encontrado.

:: Verifica/Cria ambiente virtual
if not exist ".venv" (
    echo.
    echo [*] Criando ambiente virtual...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao criar ambiente virtual.
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado.
)

:: Ativa o ambiente virtual
call .venv\Scripts\activate.bat

:: Instala/Atualiza dependências
echo.
echo [*] Verificando dependencias...
pip install -r requirements.txt -q --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

echo.
echo ============================================================
echo   Iniciando servidor...
echo   Acesse: http://localhost:5000
echo ============================================================
echo.
echo Pressione Ctrl+C para encerrar.
echo.

:: Aguarda 2 segundos e abre o navegador
start /b cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:5000"

:: Inicia o servidor
python app.py

:: Se o servidor parar
echo.
echo Servidor encerrado.
pause
