# -*- coding: utf-8 -*-
import sqlite3
import os
import datetime
from typing import List, Dict, Any, Optional

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'history.db')


def get_connection() -> sqlite3.Connection:
    """Retorna uma conexão com o banco SQLite."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Cria as tabelas se não existirem."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_url TEXT NOT NULL,
            sitemap_urls TEXT NOT NULL,
            date TEXT NOT NULL,
            total_urls INTEGER DEFAULT 0,
            indexed_count INTEGER DEFAULT 0,
            not_indexed_count INTEGER DEFAULT 0,
            requested_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS url_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            gsc_status TEXT,
            verdict TEXT,
            needs_indexing INTEGER DEFAULT 0,
            reason TEXT,
            action_taken TEXT DEFAULT 'Aguardando',
            indexing_result TEXT,
            date TEXT NOT NULL,
            FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_url_results_execution
        ON url_results(execution_id)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_url_results_needs_indexing
        ON url_results(execution_id, needs_indexing)
    ''')

    conn.commit()
    conn.close()


def create_execution(site_url: str, sitemap_urls: str) -> int:
    """Cria um novo registro de execução e retorna o ID."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        'INSERT INTO executions (site_url, sitemap_urls, date, status) VALUES (?, ?, ?, ?)',
        (site_url, sitemap_urls, now, 'running')
    )
    exec_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return exec_id


def update_execution(exec_id: int, **kwargs):
    """Atualiza campos de uma execução."""
    conn = get_connection()
    sets = ', '.join(f'{k} = ?' for k in kwargs.keys())
    values = list(kwargs.values()) + [exec_id]
    conn.execute(f'UPDATE executions SET {sets} WHERE id = ?', values)
    conn.commit()
    conn.close()


def save_url_results(exec_id: int, results: List[Dict[str, Any]]):
    """Salva os resultados de URLs em batch."""
    conn = get_connection()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data = [
        (
            exec_id,
            r.get('URL', ''),
            r.get('Status GSC', ''),
            r.get('Veredicto', ''),
            1 if r.get('Precisa Indexar') else 0,
            r.get('Motivo', ''),
            r.get('Ação Tomada', 'Aguardando'),
            r.get('Resultado Indexação', ''),
            now
        )
        for r in results
    ]
    conn.executemany(
        '''INSERT INTO url_results
           (execution_id, url, gsc_status, verdict, needs_indexing, reason, action_taken, indexing_result, date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        data
    )
    conn.commit()
    conn.close()


def update_url_action(exec_id: int, url: str, action: str, result: str = ''):
    """Atualiza a ação tomada para uma URL específica."""
    conn = get_connection()
    conn.execute(
        'UPDATE url_results SET action_taken = ?, indexing_result = ? WHERE execution_id = ? AND url = ?',
        (action, result, exec_id, url)
    )
    conn.commit()
    conn.close()


def get_executions(limit: int = 50) -> List[Dict[str, Any]]:
    """Retorna as execuções mais recentes."""
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM executions ORDER BY id DESC LIMIT ?', (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_execution(exec_id: int) -> Optional[Dict[str, Any]]:
    """Retorna detalhes de uma execução específica."""
    conn = get_connection()
    row = conn.execute('SELECT * FROM executions WHERE id = ?', (exec_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_execution_urls(exec_id: int, only_not_indexed: bool = False) -> List[Dict[str, Any]]:
    """Retorna as URLs de uma execução."""
    conn = get_connection()
    if only_not_indexed:
        rows = conn.execute(
            'SELECT * FROM url_results WHERE execution_id = ? AND needs_indexing = 1 ORDER BY url',
            (exec_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM url_results WHERE execution_id = ? ORDER BY needs_indexing DESC, url',
            (exec_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_execution(exec_id: int):
    """Deleta uma execução e seus resultados (CASCADE)."""
    conn = get_connection()
    conn.execute('DELETE FROM executions WHERE id = ?', (exec_id,))
    conn.commit()
    conn.close()


def get_previous_execution(site_url: str, current_exec_id: int) -> Optional[Dict[str, Any]]:
    """Retorna a execução anterior mais recente do mesmo site."""
    conn = get_connection()
    row = conn.execute(
        '''SELECT * FROM executions
           WHERE site_url = ? AND id < ? AND status IN ('inspected', 'completed')
           ORDER BY id DESC LIMIT 1''',
        (site_url, current_exec_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_site_analytics(site_url: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Retorna as últimas N execuções completas do mesmo site para analytics."""
    conn = get_connection()
    rows = conn.execute(
        '''SELECT * FROM executions
           WHERE site_url = ? AND status IN ('inspected', 'completed')
           ORDER BY id DESC LIMIT ?''',
        (site_url, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
