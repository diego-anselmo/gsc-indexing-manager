# -*- coding: utf-8 -*-
import os
import io
import csv
import json
import time
import datetime
import threading
import requests

# Necessário para aceitar quando o Google retorna escopos ligeiramente diferentes dos solicitados
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
import re
import xml.etree.ElementTree as ET
from typing import List, Set

import pandas as pd
from flask import Flask, redirect, request, session, jsonify, send_from_directory, send_file, url_for
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import database as db

# --- Configuração ---
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.urandom(32)

# Permitir OAuth sem HTTPS em desenvolvimento local
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_PATH = os.path.join(BASE_DIR, 'client_secrets.json')


def has_client_secrets() -> bool:
    """Verifica se o client_secrets.json existe."""
    return os.path.exists(CLIENT_SECRETS_PATH)

SCOPES = [
    'https://www.googleapis.com/auth/webmasters',   # escrita: submeter/deletar sitemaps
    'https://www.googleapis.com/auth/indexing',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

# Limites
MAX_INSPECTION_PER_DAY = 2000
MAX_INDEXING_REQUESTS_PER_DAY = 200
BATCH_SIZE = 50

# Estado global da tarefa em andamento (simplificado para single-user local)
task_state = {
    'running': False,
    'phase': '',
    'progress': 0,
    'total': 0,
    'message': '',
    'exec_id': None,
    'results': [],
    'error': None
}
task_lock = threading.Lock()


# ============================================================
#  AUTENTICAÇÃO OAUTH
# ============================================================

def get_flow():
    """Cria o Flow OAuth com redirect para o callback local."""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_PATH,
        scopes=SCOPES,
        redirect_uri='http://localhost:5000/auth/callback'
    )
    return flow


def get_credentials():
    """Retorna as credenciais do usuário a partir da sessão, ou None."""
    if 'credentials' not in session:
        return None

    creds_data = session['credentials']
    creds = Credentials(
        token=creds_data['token'],
        refresh_token=creds_data.get('refresh_token'),
        token_uri=creds_data['token_uri'],
        client_id=creds_data['client_id'],
        client_secret=creds_data['client_secret'],
        scopes=creds_data['scopes']
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleRequest())
            session['credentials'] = credentials_to_dict(creds)
        except Exception:
            session.pop('credentials', None)
            return None

    return creds


def credentials_to_dict(creds):
    return {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }


# ============================================================
#  ROTAS DE AUTENTICAÇÃO
# ============================================================

@app.route('/auth/login')
def auth_login():
    if not has_client_secrets():
        return redirect('/')
    flow = get_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent'
    )
    session['state'] = state
    return redirect(authorization_url)


@app.route('/auth/callback')
def auth_callback():
    flow = get_flow()
    flow.fetch_token(authorization_response=request.url)

    creds = flow.credentials
    session['credentials'] = credentials_to_dict(creds)

    # Buscar email do usuário
    try:
        user_info_service = build('oauth2', 'v2', credentials=creds)
        user_info = user_info_service.userinfo().get().execute()
        session['user_email'] = user_info.get('email', 'Usuário')
        session['user_name'] = user_info.get('name', '')
        session['user_picture'] = user_info.get('picture', '')
    except Exception:
        session['user_email'] = 'Usuário'

    return redirect('/')


@app.route('/auth/status')
def auth_status():
    if not has_client_secrets():
        return jsonify({'authenticated': False, 'needs_setup': True})
    creds = get_credentials()
    if creds:
        return jsonify({
            'authenticated': True,
            'needs_setup': False,
            'email': session.get('user_email', ''),
            'name': session.get('user_name', ''),
            'picture': session.get('user_picture', '')
        })
    return jsonify({'authenticated': False, 'needs_setup': False})


@app.route('/api/setup/status')
def api_setup_status():
    return jsonify({'configured': has_client_secrets()})


@app.route('/api/setup/upload', methods=['POST'])
def api_setup_upload():
    """Recebe o upload do client_secrets.json."""
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400

    try:
        content = file.read().decode('utf-8')
        data = json.loads(content)

        # Validar estrutura básica
        if 'installed' not in data and 'web' not in data:
            return jsonify({'error': 'Arquivo JSON inválido. Deve conter chave "installed" ou "web".'}), 400

        # Salvar
        with open(CLIENT_SECRETS_PATH, 'w', encoding='utf-8') as f:
            f.write(content)

        return jsonify({'ok': True, 'message': 'Configuração salva com sucesso!'})
    except json.JSONDecodeError:
        return jsonify({'error': 'O arquivo não é um JSON válido.'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    session.clear()
    return jsonify({'ok': True})


# ============================================================
#  LÓGICA DE SITEMAP E INDEXAÇÃO
# ============================================================

def get_sitemap_urls(sitemap_url: str) -> List[str]:
    """Busca URLs de um sitemap, lidando com sitemap index recursivamente."""
    urls: Set[str] = set()
    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = requests.get(sitemap_url, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

            if 'sitemapindex' in root.tag:
                for sm in root.findall('ns:sitemap', namespaces):
                    loc = sm.find('ns:loc', namespaces)
                    if loc is not None and loc.text:
                        urls.update(get_sitemap_urls(loc.text.strip()))
            elif 'urlset' in root.tag:
                for url_el in root.findall('ns:url', namespaces):
                    loc = url_el.find('ns:loc', namespaces)
                    if loc is not None and loc.text:
                        urls.add(loc.text.strip())
            break  # Sucesso, sai do loop de retry
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))  # Espera progressiva
            continue
        except Exception:
            break  # Outros erros, não tenta novamente

    return list(urls)


# ============================================================
#  UTILS: MULTI-PROPRIEDADE
# ============================================================

def url_matches_property(url: str, site_url: str) -> bool:
    """Verifica se uma URL pode ser enviada via uma propriedade GSC específica."""
    url = url.strip()
    site_url = site_url.strip()

    if site_url.startswith('sc-domain:'):
        # sc-domain cobre qualquer URL do domínio e subdomínios (https/http/www)
        domain = site_url.replace('sc-domain:', '').lower()
        domain = re.sub(r'^www\.', '', domain).split('/')[0]
        url_host = re.sub(r'^https?://', '', url.lower()).split('/')[0].split('?')[0]
        url_host = re.sub(r'^www\.', '', url_host)
        return url_host == domain or url_host.endswith('.' + domain)
    else:
        # Propriedade de prefixo — URL deve começar exatamente com o prefixo
        prefix = site_url.rstrip('/')
        return (
            url == prefix
            or url.startswith(prefix + '/')
            or url.startswith(prefix + '?')
        )


def distribute_urls_to_properties(urls: List[str], site_urls: List[str]) -> dict:
    """
    Distribui URLs entre propriedades GSC para maximizar cobertura única.
    Propriedades mais específicas (com path) são preenchidas primeiro.
    Cada URL é atribuída a exatamente uma propriedade (evita duplicatas).
    Retorna: {site_url: [urls]}
    """
    def specificity(su: str) -> int:
        if su.startswith('sc-domain:'):
            return 0  # menos específico: aceita qualquer URL do domínio
        stripped = re.sub(r'^https?://', '', su).rstrip('/')
        parts = stripped.split('/', 1)
        if len(parts) > 1 and parts[1]:
            return 2 + len(parts[1])  # mais específico: tem path
        return 1  # intermediário: só domínio com schema

    sorted_props = sorted(site_urls, key=specificity, reverse=True)
    assignment: dict = {p: [] for p in site_urls}
    assigned_urls: Set[str] = set()

    for prop in sorted_props:
        quota = MAX_INDEXING_REQUESTS_PER_DAY
        for url in urls:
            if len(assignment[prop]) >= quota:
                break
            if url in assigned_urls:
                continue
            if url_matches_property(url, prop):
                assignment[prop].append(url)
                assigned_urls.add(url)

    return assignment


def run_multi_property_indexing_task(creds_dict, exec_id, property_batches):
    """
    Indexação distribuída em múltiplas propriedades GSC sequencialmente.
    property_batches: list of {'site_url': str, 'urls': list, 'sitemap_urls': list}
    """
    global task_state

    try:
        creds = Credentials(
            token=creds_dict['token'],
            refresh_token=creds_dict.get('refresh_token'),
            token_uri=creds_dict['token_uri'],
            client_id=creds_dict['client_id'],
            client_secret=creds_dict['client_secret'],
            scopes=creds_dict['scopes']
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())

        service_gsc = build('searchconsole', 'v1', credentials=creds)
        service_indexing = build('indexing', 'v3', credentials=creds)

        total_urls = sum(len(b['urls']) for b in property_batches)
        count = 0
        sitemap_count_sent = 0

        with task_lock:
            task_state['phase'] = 'indexing'
            task_state['total'] = total_urls
            task_state['progress'] = 0
            task_state['message'] = (
                f'Iniciando indexação em {len(property_batches)} propriedade(s)...'
            )

        for batch_idx, batch in enumerate(property_batches):
            site_url = batch['site_url']
            urls = batch['urls']
            sitemap_urls = batch.get('sitemap_urls', [])
            prop_label = site_url if len(site_url) <= 45 else site_url[:42] + '...'
            prop_num = f'{batch_idx + 1}/{len(property_batches)}'

            # Fase A: Remover e re-submeter sitemaps desta propriedade
            if sitemap_urls:
                with task_lock:
                    task_state['message'] = (
                        f'[Prop. {prop_num}] Re-submetendo {len(sitemap_urls)} sitemap(s) no GSC...'
                    )
                resubmit_sitemaps(service_gsc, site_url, sitemap_urls)

            # Fase B: Notificar sitemaps via Indexing API
            if sitemap_urls:
                with task_lock:
                    task_state['message'] = (
                        f'[Prop. {prop_num}] Notificando {len(sitemap_urls)} sitemap(s) via Indexing API...'
                    )
                for sm_url in sitemap_urls:
                    try:
                        service_indexing.urlNotifications().publish(
                            body={"url": sm_url, "type": "URL_UPDATED"}
                        ).execute()
                        sitemap_count_sent += 1
                    except Exception:
                        pass

            # Fase B: enviar URLs desta propriedade
            for url in urls[:MAX_INDEXING_REQUESTS_PER_DAY]:
                try:
                    service_indexing.urlNotifications().publish(
                        body={"url": url, "type": "URL_UPDATED"}
                    ).execute()
                    result_msg = "Solicitado com Sucesso"
                except HttpError as e:
                    result_msg = f"Erro API: {e.resp.status}"
                except Exception as e:
                    result_msg = f"Erro: {str(e)}"

                db.update_url_action(exec_id, url, f'Solicitado ({result_msg})', result_msg)
                count += 1

                with task_lock:
                    task_state['progress'] = count
                    task_state['message'] = (
                        f'[Prop. {prop_num}: {prop_label}] {count}/{total_urls} URLs...'
                    )

        db.update_execution(exec_id, requested_count=count, status='completed')

        with task_lock:
            task_state['phase'] = 'done'
            task_state['message'] = (
                f'Concluído! {sitemap_count_sent} sitemap(s) e {count} URL(s) '
                f'em {len(property_batches)} propriedade(s).'
            )

    except Exception as e:
        with task_lock:
            task_state['phase'] = 'error'
            task_state['error'] = str(e)
            task_state['message'] = f'Erro: {str(e)}'
        if task_state.get('exec_id'):
            try:
                db.update_execution(task_state['exec_id'], status='failed')
            except Exception:
                pass
    finally:
        with task_lock:
            task_state['running'] = False


def process_inspection_result(url, response=None, error=None):
    """Processa o resultado da inspeção de uma URL."""
    if error:
        return {
            'URL': url,
            'Status GSC': 'Erro',
            'Veredicto': 'ERROR',
            'Precisa Indexar': False,
            'Motivo': str(error),
            'Ação Tomada': 'Aguardando'
        }

    inspection_res = response.get('inspectionResult', {}) if response else {}
    index_status = inspection_res.get('indexStatusResult', {})

    coverage_state = index_status.get('coverageState', 'Unknown')
    verdict = index_status.get('verdict', 'NEUTRAL')
    robots_txt_state = index_status.get('robotsTxtState', 'UNKNOWN')

    needs_indexing = False
    reason = ""

    if verdict == 'PASS':
        reason = "Já Indexado"
    elif robots_txt_state == 'DISALLOWED':
        reason = "Bloqueado pelo robots.txt"
    else:
        needs_indexing = True
        reason = f"Não Indexado ({coverage_state})"

    if 'Submitted and indexed' in coverage_state or 'Indexed, not submitted in sitemap' in coverage_state:
        needs_indexing = False
        reason = "Já Indexado"

    return {
        'URL': url,
        'Status GSC': coverage_state,
        'Veredicto': verdict,
        'Precisa Indexar': needs_indexing,
        'Motivo': reason,
        'Ação Tomada': 'Aguardando'
    }


def run_inspection_task(creds_dict, site_url, sitemap_urls_list):
    """Executa a tarefa de inspeção em background."""
    global task_state

    try:
        creds = Credentials(
            token=creds_dict['token'],
            refresh_token=creds_dict.get('refresh_token'),
            token_uri=creds_dict['token_uri'],
            client_id=creds_dict['client_id'],
            client_secret=creds_dict['client_secret'],
            scopes=creds_dict['scopes']
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())

        service_gsc = build('searchconsole', 'v1', credentials=creds)
        service_indexing = build('indexing', 'v3', credentials=creds)

        # Fase 1: Extrair URLs dos sitemaps
        with task_lock:
            task_state['phase'] = 'extracting'
            task_state['message'] = 'Extraindo URLs dos sitemaps...'

        all_urls = set()
        for sm_url in sitemap_urls_list:
            urls = get_sitemap_urls(sm_url)
            all_urls.update(urls)

        all_urls = list(all_urls)
        total = len(all_urls)

        if total == 0:
            with task_lock:
                task_state['phase'] = 'done'
                task_state['message'] = 'Nenhuma URL encontrada nos sitemaps.'
            return

        if total > MAX_INSPECTION_PER_DAY:
            all_urls = all_urls[:MAX_INSPECTION_PER_DAY]
            total = MAX_INSPECTION_PER_DAY

        # Criar execução no banco
        exec_id = db.create_execution(site_url, ', '.join(sitemap_urls_list))
        with task_lock:
            task_state['exec_id'] = exec_id

        # Fase 2: Inspeção em lote
        with task_lock:
            task_state['phase'] = 'inspecting'
            task_state['total'] = total
            task_state['progress'] = 0
            task_state['message'] = f'Inspecionando {total} URLs...'

        results = []
        for i in range(0, total, BATCH_SIZE):
            chunk = all_urls[i:i + BATCH_SIZE]
            batch_results = []

            batch = service_gsc.new_batch_http_request()

            def make_callback(url_val):
                def callback(request_id, response, exception):
                    processed = process_inspection_result(url_val, response, exception)
                    batch_results.append(processed)
                return callback

            for j, url in enumerate(chunk):
                req_body = {
                    'inspectionUrl': url,
                    'siteUrl': site_url,
                    'languageCode': 'pt-BR'
                }
                batch.add(
                    service_gsc.urlInspection().index().inspect(body=req_body),
                    request_id=str(j),
                    callback=make_callback(url)
                )

            try:
                batch.execute()
            except Exception as e:
                for url in chunk:
                    if not any(r['URL'] == url for r in batch_results):
                        batch_results.append(process_inspection_result(url, error=e))

            results.extend(batch_results)

            with task_lock:
                task_state['progress'] = min(i + len(chunk), total)
                task_state['message'] = f'Inspecionadas {task_state["progress"]} de {total} URLs...'

        # Salvar resultados no banco
        db.save_url_results(exec_id, results)

        indexed_count = sum(1 for r in results if not r.get('Precisa Indexar'))
        not_indexed_count = sum(1 for r in results if r.get('Precisa Indexar'))

        db.update_execution(exec_id,
            total_urls=total,
            indexed_count=indexed_count,
            not_indexed_count=not_indexed_count,
            status='inspected'
        )

        with task_lock:
            task_state['phase'] = 'inspected'
            task_state['results'] = results
            task_state['message'] = f'Inspeção concluída! {indexed_count} indexadas, {not_indexed_count} precisam de indexação.'

    except Exception as e:
        with task_lock:
            task_state['phase'] = 'error'
            task_state['error'] = str(e)
            task_state['message'] = f'Erro: {str(e)}'
        if task_state.get('exec_id'):
            try:
                db.update_execution(task_state['exec_id'], status='failed')
            except Exception:
                pass
    finally:
        # Garante que running sempre volta para False, mesmo em erros não capturados
        with task_lock:
            task_state['running'] = False

# ============================================================
#  UTILS: SITEMAP RE-SUBMIT
# ============================================================

def resubmit_sitemaps(service_gsc, site_url: str, sitemap_urls: list) -> dict:
    """
    Remove e re-submete cada sitemap no GSC para forçar o Googlebot a re-rastrear.
    Retorna contadores: {'removed': int, 'submitted': int, 'errors': list}
    """
    removed, submitted = 0, 0
    errors = []

    for sm_url in sitemap_urls:
        # 1. Deletar sitemap
        try:
            service_gsc.sitemaps().delete(
                siteUrl=site_url,
                feedpath=sm_url
            ).execute()
            removed += 1
        except HttpError as e:
            if e.resp.status != 404:  # 404 = já não existia, ignora
                errors.append(f'delete {sm_url}: HTTP {e.resp.status}')
        except Exception as e:
            errors.append(f'delete {sm_url}: {str(e)}')

        # 2. Re-submeter sitemap
        try:
            service_gsc.sitemaps().submit(
                siteUrl=site_url,
                feedpath=sm_url
            ).execute()
            submitted += 1
        except HttpError as e:
            errors.append(f'submit {sm_url}: HTTP {e.resp.status}')
        except Exception as e:
            errors.append(f'submit {sm_url}: {str(e)}')

    return {'removed': removed, 'submitted': submitted, 'errors': errors}


def run_indexing_task(creds_dict, exec_id, urls_to_index, sitemap_urls=None, site_url=None):
    """Executa a solicitação de indexação em background."""
    global task_state

    try:
        creds = Credentials(
            token=creds_dict['token'],
            refresh_token=creds_dict.get('refresh_token'),
            token_uri=creds_dict['token_uri'],
            client_id=creds_dict['client_id'],
            client_secret=creds_dict['client_secret'],
            scopes=creds_dict['scopes']
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())

        service_gsc = build('searchconsole', 'v1', credentials=creds)
        service_indexing = build('indexing', 'v3', credentials=creds)

        sitemap_urls = sitemap_urls or []

        # Fase 0A: Remover e re-submeter sitemaps no GSC (força re-rastreamento)
        if sitemap_urls and site_url:
            with task_lock:
                task_state['phase'] = 'indexing'
                task_state['message'] = f'Removendo e re-submetendo {len(sitemap_urls)} sitemap(s) no GSC...'

            resubmit_sitemaps(service_gsc, site_url, sitemap_urls)

        # Fase 0B: Notificar sitemaps via Indexing API
        if sitemap_urls:
            with task_lock:
                task_state['message'] = f'Notificando {len(sitemap_urls)} sitemap(s) via Indexing API...'

            for sm_url in sitemap_urls:
                try:
                    body = {"url": sm_url, "type": "URL_UPDATED"}
                    service_indexing.urlNotifications().publish(body=body).execute()
                except Exception:
                    pass

        total = min(len(urls_to_index), MAX_INDEXING_REQUESTS_PER_DAY)
        count = 0

        with task_lock:
            task_state['phase'] = 'indexing'
            task_state['total'] = total
            task_state['progress'] = 0
            task_state['message'] = f'Solicitando indexação de {total} URLs...'

        for url in urls_to_index[:total]:
            try:
                body = {"url": url, "type": "URL_UPDATED"}
                service_indexing.urlNotifications().publish(body=body).execute()
                result_msg = "Solicitado com Sucesso"
            except HttpError as e:
                result_msg = f"Erro API: {e.resp.status}"
            except Exception as e:
                result_msg = f"Erro: {str(e)}"

            db.update_url_action(exec_id, url, f'Solicitado ({result_msg})', result_msg)
            count += 1

            with task_lock:
                task_state['progress'] = count
                task_state['message'] = f'Indexação: {count} de {total} solicitadas...'

        db.update_execution(exec_id, requested_count=count, status='completed')

        with task_lock:
            task_state['phase'] = 'done'
            task_state['message'] = f'Concluído! {len(sitemap_urls)} sitemap(s) re-submetido(s) e {count} URL(s) enviadas.'

    except Exception as e:
        with task_lock:
            task_state['phase'] = 'error'
            task_state['error'] = str(e)
            task_state['message'] = f'Erro: {str(e)}'
    finally:
        with task_lock:
            task_state['running'] = False


# ============================================================
#  ROTAS DA API
# ============================================================

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')


@app.route('/api/sites')
def api_sites():
    creds = get_credentials()
    if not creds:
        return jsonify({'error': 'Não autenticado'}), 401

    try:
        service = build('searchconsole', 'v1', credentials=creds)
        result = service.sites().list().execute()
        sites = result.get('siteEntry', [])
        return jsonify({'sites': [{'url': s['siteUrl'], 'permission': s.get('permissionLevel', '')} for s in sites]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/sitemaps')
def api_sitemaps():
    creds = get_credentials()
    if not creds:
        return jsonify({'error': 'Não autenticado'}), 401

    site_url = request.args.get('site', '')
    if not site_url:
        return jsonify({'error': 'Parâmetro site é obrigatório'}), 400

    try:
        service = build('searchconsole', 'v1', credentials=creds)
        response = service.sitemaps().list(siteUrl=site_url).execute()
        sitemaps = response.get('sitemap', [])
        return jsonify({'sitemaps': [
            {'path': s.get('path', ''), 'lastSubmitted': s.get('lastSubmitted', 'N/A')}
            for s in sitemaps
        ]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/inspect', methods=['POST'])
def api_inspect():
    global task_state
    creds = get_credentials()
    if not creds:
        return jsonify({'error': 'Não autenticado'}), 401

    with task_lock:
        if task_state['running']:
            return jsonify({'error': 'Já existe uma tarefa em andamento'}), 409

    data = request.get_json()
    site_url = data.get('site_url', '')
    sitemap_urls = data.get('sitemap_urls', [])

    if not site_url or not sitemap_urls:
        return jsonify({'error': 'site_url e sitemap_urls são obrigatórios'}), 400

    with task_lock:
        task_state = {
            'running': True,
            'phase': 'starting',
            'progress': 0,
            'total': 0,
            'message': 'Iniciando...',
            'exec_id': None,
            'results': [],
            'error': None
        }

    creds_dict = session['credentials']
    thread = threading.Thread(target=run_inspection_task, args=(creds_dict, site_url, sitemap_urls))
    thread.daemon = True
    thread.start()

    return jsonify({'ok': True, 'message': 'Inspeção iniciada'})


@app.route('/api/inspect/status')
def api_inspect_status():
    with task_lock:
        return jsonify(task_state)


@app.route('/api/index', methods=['POST'])
def api_index():
    global task_state
    creds = get_credentials()
    if not creds:
        return jsonify({'error': 'Não autenticado'}), 401

    with task_lock:
        if task_state['running']:
            return jsonify({'error': 'Já existe uma tarefa em andamento'}), 409

    data = request.get_json()
    exec_id = data.get('exec_id')
    urls = data.get('urls', [])
    sitemap_urls = data.get('sitemap_urls', [])

    if not exec_id or not urls:
        return jsonify({'error': 'exec_id e urls são obrigatórios'}), 400

    with task_lock:
        task_state = {
            'running': True,
            'phase': 'indexing',
            'progress': 0,
            'total': len(urls),
            'message': 'Iniciando solicitação de indexação...',
            'exec_id': exec_id,
            'results': [],
            'error': None
        }

    # Buscar site_url da execução para re-submeter sitemaps corretamente
    exec_data = db.get_execution(exec_id)
    site_url = exec_data.get('site_url', '') if exec_data else ''

    creds_dict = session['credentials']
    thread = threading.Thread(
        target=run_indexing_task,
        args=(creds_dict, exec_id, urls, sitemap_urls),
        kwargs={'site_url': site_url}
    )
    thread.daemon = True
    thread.start()

    return jsonify({'ok': True, 'message': 'Indexação iniciada'})


@app.route('/api/index/multi', methods=['POST'])
def api_index_multi():
    """Indexação distribuída em múltiplas propriedades GSC."""
    global task_state
    creds = get_credentials()
    if not creds:
        return jsonify({'error': 'Não autenticado'}), 401

    with task_lock:
        if task_state['running']:
            return jsonify({'error': 'Já existe uma tarefa em andamento'}), 409

    data = request.get_json()
    exec_id = data.get('exec_id')
    urls = data.get('urls', [])
    site_urls = data.get('site_urls', [])  # Lista de propriedades GSC selecionadas
    sitemap_urls = data.get('sitemap_urls', [])

    if not exec_id or not urls or not site_urls:
        return jsonify({'error': 'exec_id, urls e site_urls são obrigatórios'}), 400

    # Distribuir URLs entre as propriedades (mais específica primeiro)
    distribution = distribute_urls_to_properties(urls, site_urls)

    # Montar batches (apenas propriedades com URLs atribuídas)
    property_batches = [
        {
            'site_url': su,
            'urls': distribution[su],
            'sitemap_urls': sitemap_urls  # Mesmo conjunto de sitemaps para todas
        }
        for su in site_urls
        if distribution.get(su)
    ]

    if not property_batches:
        return jsonify({'error': 'Nenhuma URL pôde ser atribuída às propriedades selecionadas'}), 400

    total_urls = sum(len(b['urls']) for b in property_batches)

    # Resumo da distribuição para retornar ao frontend
    distribution_summary = {su: len(distribution.get(su, [])) for su in site_urls}

    with task_lock:
        task_state = {
            'running': True,
            'phase': 'indexing',
            'progress': 0,
            'total': total_urls,
            'message': f'Preparando indexação em {len(property_batches)} propriedade(s)...',
            'exec_id': exec_id,
            'results': [],
            'error': None
        }

    creds_dict = session['credentials']
    thread = threading.Thread(
        target=run_multi_property_indexing_task,
        args=(creds_dict, exec_id, property_batches)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'ok': True,
        'message': f'Indexação iniciada em {len(property_batches)} propriedade(s)',
        'distribution': distribution_summary
    })


@app.route('/api/task/reset', methods=['POST'])
def api_task_reset():
    """Força o reset do estado da tarefa — usa se o sistema travar com 'tarefa em andamento'."""
    global task_state
    with task_lock:
        task_state = {
            'running': False,
            'phase': '',
            'progress': 0,
            'total': 0,
            'message': '',
            'exec_id': None,
            'results': [],
            'error': None
        }
    return jsonify({'ok': True, 'message': 'Estado da tarefa resetado com sucesso.'})


@app.route('/api/history')
def api_history():
    executions = db.get_executions()
    return jsonify({'executions': executions})


@app.route('/api/history/<int:exec_id>')
def api_history_detail(exec_id):
    execution = db.get_execution(exec_id)
    if not execution:
        return jsonify({'error': 'Execução não encontrada'}), 404

    only_not_indexed = request.args.get('filter') == 'not_indexed'
    urls = db.get_execution_urls(exec_id, only_not_indexed=only_not_indexed)

    return jsonify({'execution': execution, 'urls': urls})


@app.route('/api/history/<int:exec_id>', methods=['DELETE'])
def api_history_delete(exec_id):
    """Deleta uma execução e seus resultados."""
    execution = db.get_execution(exec_id)
    if not execution:
        return jsonify({'error': 'Execução não encontrada'}), 404

    db.delete_execution(exec_id)
    return jsonify({'ok': True})


@app.route('/api/history/<int:exec_id>/retry', methods=['POST'])
def api_history_retry(exec_id):
    """Re-solicita indexação de URLs não indexadas de uma execução anterior."""
    global task_state
    creds = get_credentials()
    if not creds:
        return jsonify({'error': 'Não autenticado'}), 401

    with task_lock:
        if task_state['running']:
            return jsonify({'error': 'Já existe uma tarefa em andamento'}), 409

    urls_data = db.get_execution_urls(exec_id, only_not_indexed=True)
    urls = [u['url'] for u in urls_data]

    if not urls:
        return jsonify({'error': 'Nenhuma URL para re-indexar'}), 400

    # Criar nova execução baseada na anterior
    execution = db.get_execution(exec_id)
    new_exec_id = db.create_execution(execution['site_url'], execution['sitemap_urls'])

    # Recuperar sitemap_urls da execução original para reenviar ao Google
    saved_sitemaps = execution.get('sitemap_urls', '')
    sitemap_urls = [s.strip() for s in saved_sitemaps.split(',') if s.strip()] if saved_sitemaps else []

    # Copiar as URLs não indexadas para a nova execução
    results_for_db = [
        {
            'URL': u['url'],
            'Status GSC': u['gsc_status'],
            'Veredicto': u['verdict'],
            'Precisa Indexar': True,
            'Motivo': u['reason'],
            'Ação Tomada': 'Aguardando'
        }
        for u in urls_data
    ]
    db.save_url_results(new_exec_id, results_for_db)
    db.update_execution(new_exec_id, total_urls=len(urls), not_indexed_count=len(urls))

    with task_lock:
        task_state = {
            'running': True,
            'phase': 'indexing',
            'progress': 0,
            'total': len(urls),
            'message': 'Re-solicitando indexação...',
            'exec_id': new_exec_id,
            'results': [],
            'error': None
        }

    creds_dict = session['credentials']
    thread = threading.Thread(
        target=run_indexing_task,
        args=(creds_dict, new_exec_id, urls, sitemap_urls),
        kwargs={'site_url': execution.get('site_url', '')}
    )
    thread.daemon = True
    thread.start()

    return jsonify({'ok': True, 'exec_id': new_exec_id, 'count': len(urls)})


@app.route('/api/history/<int:exec_id>/compare')
def api_history_compare(exec_id):
    """Retorna comparação entre a execução atual e a anterior do mesmo site."""
    execution = db.get_execution(exec_id)
    if not execution:
        return jsonify({'error': 'Execução não encontrada'}), 404

    prev = db.get_previous_execution(execution['site_url'], exec_id)
    analytics = db.get_site_analytics(execution['site_url'], limit=10)

    # Inverter para ordem cronológica (mais antiga primeiro)
    analytics_chrono = list(reversed(analytics))

    comparison = None
    if prev:
        delta_total = execution['total_urls'] - prev['total_urls']
        delta_indexed = execution['indexed_count'] - prev['indexed_count']
        delta_not_indexed = execution['not_indexed_count'] - prev['not_indexed_count']

        # Buscar URLs de ambas as execuções para comparação detalhada
        current_urls = db.get_execution_urls(exec_id)
        prev_urls = db.get_execution_urls(prev['id'])

        current_indexed_set = {u['url'] for u in current_urls if not u['needs_indexing']}
        prev_indexed_set = {u['url'] for u in prev_urls if not u['needs_indexing']}
        current_not_indexed_set = {u['url'] for u in current_urls if u['needs_indexing']}
        prev_not_indexed_set = {u['url'] for u in prev_urls if u['needs_indexing']}

        newly_indexed = list(current_indexed_set - prev_indexed_set)
        lost_indexing = list(current_not_indexed_set & prev_indexed_set)

        # Páginas adicionadas/removidas do sitemap
        current_url_set = {u['url'] for u in current_urls}
        prev_url_set = {u['url'] for u in prev_urls}
        pages_added = sorted(list(current_url_set - prev_url_set))
        pages_removed = sorted(list(prev_url_set - current_url_set))

        # Taxa de indexação
        current_rate = round((execution['indexed_count'] / execution['total_urls']) * 100, 1) if execution['total_urls'] > 0 else 0
        prev_rate = round((prev['indexed_count'] / prev['total_urls']) * 100, 1) if prev['total_urls'] > 0 else 0

        comparison = {
            'previous': prev,
            'delta_total': delta_total,
            'delta_indexed': delta_indexed,
            'delta_not_indexed': delta_not_indexed,
            'newly_indexed': newly_indexed[:50],
            'newly_indexed_count': len(newly_indexed),
            'lost_indexing': lost_indexing[:50],
            'lost_indexing_count': len(lost_indexing),
            'pages_added': pages_added[:50],
            'pages_added_count': len(pages_added),
            'pages_removed': pages_removed[:50],
            'pages_removed_count': len(pages_removed),
            'current_rate': current_rate,
            'prev_rate': prev_rate,
            'rate_delta': round(current_rate - prev_rate, 1)
        }

    # Analytics: evolução ao longo do tempo
    analytics_data = [{
        'id': a['id'],
        'date': a['date'],
        'total': a['total_urls'],
        'indexed': a['indexed_count'],
        'not_indexed': a['not_indexed_count'],
        'rate': round((a['indexed_count'] / a['total_urls']) * 100, 1) if a['total_urls'] > 0 else 0
    } for a in analytics_chrono]

    return jsonify({
        'comparison': comparison,
        'analytics': analytics_data,
        'total_executions': len(analytics)
    })


@app.route('/api/inspect/url', methods=['POST'])
def api_inspect_url():
    """Inspeciona uma única URL individualmente e retorna status de indexação."""
    creds = get_credentials()
    if not creds:
        return jsonify({'error': 'Não autenticado'}), 401

    data = request.get_json()
    url = data.get('url', '').strip()
    site_url = data.get('site_url', '').strip()

    if not url or not site_url:
        return jsonify({'error': 'url e site_url são obrigatórios'}), 400

    try:
        service_gsc = build('searchconsole', 'v1', credentials=creds)
        req_body = {
            'inspectionUrl': url,
            'siteUrl': site_url,
            'languageCode': 'pt-BR'
        }
        response = service_gsc.urlInspection().index().inspect(body=req_body).execute()
        inspection_res = response.get('inspectionResult', {})
        index_status = inspection_res.get('indexStatusResult', {})
        mobile_result = inspection_res.get('mobileUsabilityResult', {})

        return jsonify({
            'ok': True,
            'url': url,
            'verdict': index_status.get('verdict', 'NEUTRAL'),
            'coverageState': index_status.get('coverageState', ''),
            'robotsTxtState': index_status.get('robotsTxtState', 'UNKNOWN'),
            'indexingState': index_status.get('indexingState', 'UNKNOWN'),
            'pageFetchState': index_status.get('pageFetchState', 'UNKNOWN'),
            'lastCrawlTime': index_status.get('lastCrawlTime', ''),
            'crawledAs': index_status.get('crawledAs', ''),
            'mobileUsability': mobile_result.get('verdict', ''),
        })
    except HttpError as e:
        return jsonify({'error': f'Erro API: {e.resp.status} - {e._get_reason()}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/index/single', methods=['POST'])
def api_index_single():
    """Solicita indexação de uma única URL."""
    creds = get_credentials()
    if not creds:
        return jsonify({'error': 'Não autenticado'}), 401

    data = request.get_json()
    url = data.get('url', '')
    exec_id = data.get('exec_id')

    if not url:
        return jsonify({'error': 'URL é obrigatória'}), 400

    try:
        service_indexing = build('indexing', 'v3', credentials=creds)
        body = {"url": url, "type": "URL_UPDATED"}
        service_indexing.urlNotifications().publish(body=body).execute()
        result_msg = "Solicitado com Sucesso"

        if exec_id:
            db.update_url_action(exec_id, url, f'Solicitado ({result_msg})', result_msg)

        return jsonify({'ok': True, 'message': result_msg, 'url': url})
    except HttpError as e:
        result_msg = f"Erro API: {e.resp.status}"
        if exec_id:
            db.update_url_action(exec_id, url, f'Erro ({result_msg})', result_msg)
        return jsonify({'error': result_msg}), 500
    except Exception as e:
        result_msg = f"Erro: {str(e)}"
        if exec_id:
            db.update_url_action(exec_id, url, f'Erro ({result_msg})', result_msg)
        return jsonify({'error': result_msg}), 500


@app.route('/api/history/<int:exec_id>/export')
def api_history_export(exec_id):
    """Exporta os dados da execução como arquivo Excel."""
    execution = db.get_execution(exec_id)
    if not execution:
        return jsonify({'error': 'Execução não encontrada'}), 404

    urls = db.get_execution_urls(exec_id)

    # Criar DataFrame de resumo
    summary_data = {
        'Campo': ['Site', 'Data', 'Status', 'Total de URLs', 'Indexadas', 'Não Indexadas', 'Solicitações Enviadas', 'Taxa de Indexação'],
        'Valor': [
            execution['site_url'],
            execution['date'],
            execution['status'],
            execution['total_urls'],
            execution['indexed_count'],
            execution['not_indexed_count'],
            execution['requested_count'],
            f"{round((execution['indexed_count'] / execution['total_urls']) * 100, 1)}%" if execution['total_urls'] > 0 else '0%'
        ]
    }
    df_summary = pd.DataFrame(summary_data)

    # Criar DataFrame de URLs
    urls_data = [{
        'URL': u['url'],
        'Status GSC': u['gsc_status'],
        'Veredicto': u['verdict'],
        'Precisa Indexar': 'Sim' if u['needs_indexing'] else 'Não',
        'Motivo': u['reason'],
        'Ação Tomada': u['action_taken'],
        'Resultado': u['indexing_result'] or '',
        'Data': u['date']
    } for u in urls]
    df_urls = pd.DataFrame(urls_data)

    # Gerar Excel em memória
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_summary.to_excel(writer, sheet_name='Resumo', index=False)
        df_urls.to_excel(writer, sheet_name='URLs', index=False)

        # Auto-ajustar largura das colunas
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    try:
                        if cell.value:
                            max_len = max(max_len, len(str(cell.value)))
                    except:
                        pass
                ws.column_dimensions[col_letter].width = min(max_len + 2, 80)

    output.seek(0)

    site_name = execution['site_url'].replace('sc-domain:', '').replace('https://', '').replace('http://', '').replace('/', '_').replace('.', '_')
    date_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'Relatorio_Indexacao_{site_name}_{date_str}.xlsx'

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


@app.route('/api/history/<int:exec_id>/export/csv')
def api_history_export_csv(exec_id):
    """Exporta os dados da execução como arquivo CSV."""
    execution = db.get_execution(exec_id)
    if not execution:
        return jsonify({'error': 'Execução não encontrada'}), 404

    urls = db.get_execution_urls(exec_id)

    output = io.StringIO()
    writer = csv.writer(output)

    # Cabeçalho
    writer.writerow(['URL', 'Status GSC', 'Veredicto', 'Precisa Indexar', 'Motivo', 'Ação Tomada', 'Resultado', 'Data'])

    for u in urls:
        writer.writerow([
            u['url'],
            u['gsc_status'],
            u['verdict'],
            'Sim' if u['needs_indexing'] else 'Não',
            u['reason'],
            u['action_taken'],
            u['indexing_result'] or '',
            u['date']
        ])

    csv_bytes = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    csv_bytes.seek(0)

    site_name = execution['site_url'].replace('sc-domain:', '').replace('https://', '').replace('http://', '').replace('/', '_').replace('.', '_')
    date_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'Relatorio_Indexacao_{site_name}_{date_str}.csv'

    return send_file(
        csv_bytes,
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )


# ============================================================
#  INICIALIZAÇÃO
# ============================================================

if __name__ == '__main__':
    db.init_db()

    import logging
    logging.basicConfig(level=logging.DEBUG)

    @app.errorhandler(500)
    def internal_error(e):
        import traceback
        tb = traceback.format_exc()
        app.logger.error(f'500 error:\n{tb}')
        return jsonify({'error': 'Erro interno', 'detail': str(e), 'traceback': tb}), 500

    if not has_client_secrets():
        print("=" * 60)
        print("  GSC Indexing Manager - Configuração Inicial")
        print("  Acesse: http://localhost:5000")
        print("  O assistente de configuração irá guiá-lo.")
        print("=" * 60)
    else:
        print("=" * 60)
        print("  GSC Indexing Manager - Interface Web")
        print("  Acesse: http://localhost:5000")
        print("=" * 60)

    app.run(host='localhost', port=5000, debug=False)
