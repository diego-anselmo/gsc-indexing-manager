# GSC Indexing Manager

Interface web para gerenciamento de indexação no Google Search Console. Analisa sitemaps, verifica status de indexação das páginas e facilita o envio de URLs para indexação via API do Google.

## Funcionalidades

- 📊 Dashboard com estatísticas de indexação
- 🗺️ Análise automática de sitemaps
- 🔍 Verificação de status de indexação por URL
- 📤 Envio em lote para indexação
- 📈 Histórico de análises e comparativos
- 📥 Exportação para Excel e CSV

## Requisitos

- Windows 10 ou superior
- Python 3.9+ ([download](https://www.python.org/downloads/))
- Git ([download](https://git-scm.com/download/win)) — necessário para usar o `atualizar.bat`
- Conta Google com acesso ao Search Console

## Instalação

### Opção 1 — Instalador automático (recomendado)

1. Baixe o projeto (botão **Code → Download ZIP** aqui no GitHub)
2. Extraia o ZIP em qualquer pasta
3. Entre na pasta `instalador/`
4. Execute `instalar.bat` com duplo clique
5. Siga as instruções na tela

### Opção 2 — Via Git (clone)

```bash
git clone https://github.com/diegofornalha/gsc-indexing-manager.git
cd gsc-indexing-manager
```

Depois execute `instalador/instalar.bat`.

## Configuração das Credenciais Google

Antes de usar, você precisa configurar as credenciais OAuth do Google:

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto e ative a API do Search Console
3. Crie credenciais OAuth 2.0 (Aplicativo de desktop)
4. Baixe o arquivo JSON e salve como **`client_secrets.json`** na raiz do projeto

> ⚠️ O arquivo `client_secrets.json` **não está no repositório** por segurança. Cada usuário deve configurar suas próprias credenciais.

## Como usar

Execute `iniciar.bat` com duplo clique. O sistema abrirá automaticamente no navegador em `http://localhost:5000`.

## Atualizando para a versão mais recente

Execute `atualizar.bat` com duplo clique. O script:
- Baixa a versão mais recente do GitHub
- Mantém seus dados e credenciais intactos
- Atualiza as dependências automaticamente

> ℹ️ Requer Git instalado.

## Estrutura do projeto

```
gsc-indexing-manager/
├── app.py              # Servidor Flask principal
├── database.py         # Gerenciamento do banco de dados
├── requirements.txt    # Dependências Python
├── iniciar.bat         # Iniciar o sistema
├── atualizar.bat       # Atualizar para versão mais recente
├── instalador/
│   ├── instalar.bat    # Instalador completo
│   └── LEIA-ME.txt     # Instruções de instalação
├── static/
│   ├── app.js          # Frontend JavaScript
│   └── style.css       # Estilos
└── templates/
    └── index.html      # Interface HTML
```

## Licença

Uso interno — AntiGravity.
