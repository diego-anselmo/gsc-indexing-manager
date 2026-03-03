// ================================================
// GSC Indexing Manager - Frontend Logic
// ================================================

let selectedSite = '';
let selectedSitemaps = [];
let currentExecId = null;
let currentExecIdForHistory = null;
let allResults = [];
let pollingInterval = null;
let allSites = [];          // Todas as propriedades GSC do usuário
let additionalProperties = []; // Propriedades extras selecionadas para multiplicar cota

// ------------------------------------------------
// Init
// ------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
});

async function checkAuth() {
    try {
        const res = await fetch('/auth/status');
        const data = await res.json();

        if (data.needs_setup) {
            showScreen('setup');
        } else if (data.authenticated) {
            showScreen('dashboard');
            document.getElementById('user-email').textContent = data.email;
            if (data.picture) {
                document.getElementById('user-avatar').src = data.picture;
                document.getElementById('user-avatar').style.display = 'block';
            }
            loadSites();
        } else {
            showScreen('login');
        }
    } catch (e) {
        showScreen('login');
    }
}

function showScreen(name) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById('screen-' + name).classList.add('active');
}

async function logout() {
    await fetch('/auth/logout', { method: 'POST' });
    showScreen('login');
}

// ------------------------------------------------
// Tab Navigation
// ------------------------------------------------
function switchTab(tab) {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.nav-btn[data-tab="${tab}"]`).classList.add('active');
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + tab).classList.add('active');

    if (tab === 'history') {
        loadHistory();
    }
}

// ------------------------------------------------
// Step 1: Sites
// ------------------------------------------------
async function loadSites() {
    const loading = document.getElementById('sites-loading');
    const list = document.getElementById('sites-list');
    loading.style.display = 'flex';
    list.style.display = 'none';

    try {
        const res = await fetch('/api/sites');
        const data = await res.json();

        loading.style.display = 'none';
        list.style.display = 'flex';

        allSites = data.sites || []; // Armazena todas as propriedades

        if (data.sites && data.sites.length > 0) {
            let html = '';
            data.sites.forEach((site, i) => {
                html += `
                    <label class="radio-label">
                        <input type="radio" name="site" value="${site.url}" onchange="selectSite('${site.url}')">
                        <span>${site.url}</span>
                    </label>
                `;
            });
            html += `
                <label class="radio-label">
                    <input type="radio" name="site" value="__manual__" onchange="showManualSite()">
                    <span>Digitar URL manualmente</span>
                </label>
            `;
            list.innerHTML = html;
        } else {
            list.innerHTML = '';
            document.getElementById('site-manual-group').style.display = 'block';
            const input = document.getElementById('site-manual');
            input.addEventListener('input', () => {
                if (input.value.trim()) {
                    selectSite(input.value.trim());
                }
            });
        }
    } catch (e) {
        loading.style.display = 'none';
        list.style.display = 'flex';
        list.innerHTML = '<p style="color: var(--error);">Erro ao carregar propriedades. Tente fazer login novamente.</p>';
    }
}

function showManualSite() {
    document.getElementById('site-manual-group').style.display = 'block';
    const input = document.getElementById('site-manual');
    input.focus();
    input.addEventListener('input', () => {
        if (input.value.trim()) {
            selectSite(input.value.trim());
        }
    });
}

function selectSite(url) {
    selectedSite = url;
    document.getElementById('step-sitemap').classList.remove('disabled');
    loadSitemaps(url);
    showRelatedProperties(url); // Detectar propriedades relacionadas
}

// ------------------------------------------------
// Multi-Property: cota multiplicada
// ------------------------------------------------
function extractRootDomain(siteUrl) {
    let d = siteUrl.replace('sc-domain:', '');
    d = d.replace(/^https?:\/\//, '');
    d = d.replace(/^www\./, '');
    return d.split('/')[0].toLowerCase().split(':')[0];
}

function showRelatedProperties(primaryUrl) {
    const panel = document.getElementById('related-properties-panel');
    const list = document.getElementById('related-props-list');

    const primaryDomain = extractRootDomain(primaryUrl);
    const related = allSites.filter(s =>
        s.url !== primaryUrl && extractRootDomain(s.url) === primaryDomain
    );

    additionalProperties = [];
    updateQuotaBadge();

    if (related.length === 0) {
        panel.style.display = 'none';
        return;
    }

    list.innerHTML = related.map(s => `
        <label class="checkbox-label">
            <input type="checkbox" class="related-prop-cb" value="${s.url}"
                   onchange="updateAdditionalProperties()">
            <span>${s.url}</span>
        </label>
    `).join('');

    panel.style.display = 'block';
}

function updateAdditionalProperties() {
    additionalProperties = [];
    document.querySelectorAll('.related-prop-cb:checked').forEach(cb => {
        additionalProperties.push(cb.value);
    });
    updateQuotaBadge();
}

function updateQuotaBadge() {
    const totalProps = 1 + additionalProperties.length;
    const totalQuota = totalProps * 200;
    const badge = document.getElementById('related-props-quota');
    if (badge) {
        badge.textContent = totalProps > 1
            ? `${totalProps} prop. × 200 = ${totalQuota} URLs/dia`
            : '200 URLs/dia';
        badge.className = 'quota-badge' + (additionalProperties.length > 0 ? ' quota-badge-active' : '');
    }
}

function toggleRelatedProperties() {
    const body = document.getElementById('related-props-body');
    const chevron = document.querySelector('#related-properties-panel .rp-chevron');
    const isOpen = body.style.display !== 'none';
    body.style.display = isOpen ? 'none' : 'block';
    if (chevron) chevron.classList.toggle('rotated', !isOpen);
}

// ------------------------------------------------
// Step 2: Sitemaps
// ------------------------------------------------
async function loadSitemaps(siteUrl) {
    const loading = document.getElementById('sitemaps-loading');
    const list = document.getElementById('sitemaps-list');
    loading.style.display = 'flex';
    list.innerHTML = '';
    selectedSitemaps = [];

    try {
        const res = await fetch('/api/sitemaps?site=' + encodeURIComponent(siteUrl));
        const data = await res.json();

        loading.style.display = 'none';

        if (data.sitemaps && data.sitemaps.length > 0) {
            let html = `
                <label class="checkbox-label">
                    <input type="checkbox" id="sitemaps-all" onchange="toggleAllSitemaps()">
                    <span><strong>Selecionar todos (${data.sitemaps.length})</strong></span>
                </label>
            `;
            data.sitemaps.forEach((sm, i) => {
                html += `
                    <label class="checkbox-label">
                        <input type="checkbox" class="sitemap-cb" value="${sm.path}" onchange="updateSitemapSelection()">
                        <span>${sm.path}<br><small style="color:var(--text-muted)">Último envio: ${sm.lastSubmitted}</small></span>
                    </label>
                `;
            });
            list.innerHTML = html;
        } else {
            list.innerHTML = '<p style="color:var(--text-secondary);font-size:0.85rem;">Nenhum sitemap cadastrado. Use a opção manual abaixo.</p>';
        }
    } catch (e) {
        loading.style.display = 'none';
        list.innerHTML = '<p style="color: var(--error);">Erro ao carregar sitemaps.</p>';
    }
}

function toggleAllSitemaps() {
    const allChecked = document.getElementById('sitemaps-all').checked;
    document.querySelectorAll('.sitemap-cb').forEach(cb => { cb.checked = allChecked; });
    updateSitemapSelection();
}

function updateSitemapSelection() {
    selectedSitemaps = [];
    document.querySelectorAll('.sitemap-cb:checked').forEach(cb => {
        selectedSitemaps.push(cb.value);
    });
    updateActionStep();
}

function toggleManualSitemap() {
    const input = document.getElementById('sitemap-manual');
    const checked = document.getElementById('sitemap-manual-check').checked;
    input.style.display = checked ? 'block' : 'none';
    if (checked) input.focus();
    input.addEventListener('input', () => updateActionStep());
    updateActionStep();
}

function updateActionStep() {
    const manualUrl = document.getElementById('sitemap-manual-check').checked
        ? document.getElementById('sitemap-manual').value.trim()
        : '';

    const allSelected = [...selectedSitemaps];
    if (manualUrl) allSelected.push(manualUrl);

    const stepAction = document.getElementById('step-action');
    const btnStart = document.getElementById('btn-start');
    const summary = document.getElementById('action-summary');

    if (allSelected.length > 0) {
        stepAction.classList.remove('disabled');
        btnStart.disabled = false;
        summary.innerHTML = `
            <strong>Site:</strong> ${selectedSite}<br>
            <strong>Sitemaps:</strong> ${allSelected.length} selecionado(s)
        `;
    } else {
        stepAction.classList.add('disabled');
        btnStart.disabled = true;
    }
}

// ------------------------------------------------
// Step 3: Start Inspection
// ------------------------------------------------
async function startInspection() {
    const manualUrl = document.getElementById('sitemap-manual-check').checked
        ? document.getElementById('sitemap-manual').value.trim()
        : '';

    const sitemaps = [...selectedSitemaps];
    if (manualUrl) sitemaps.push(manualUrl);

    if (!selectedSite || sitemaps.length === 0) return;

    // Show progress modal
    showProgressModal('Verificando indexação...');

    try {
        const res = await fetch('/api/inspect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ site_url: selectedSite, sitemap_urls: sitemaps })
        });

        const data = await res.json();
        if (data.error) {
            alert('Erro: ' + data.error);
            hideProgressModal();
            return;
        }

        // Start polling
        startPolling();
    } catch (e) {
        alert('Erro de conexão: ' + e.message);
        hideProgressModal();
    }
}

// ------------------------------------------------
// Progress Polling
// ------------------------------------------------
function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(pollStatus, 1000);
}

async function pollStatus() {
    try {
        const res = await fetch('/api/inspect/status');
        const state = await res.json();

        const pct = state.total > 0
            ? Math.round((state.progress / state.total) * 100)
            : 0;

        document.getElementById('progress-bar').style.width = pct + '%';
        document.getElementById('progress-text').textContent = state.message;

        if (state.phase === 'extracting') {
            document.getElementById('progress-title').textContent = 'Extraindo URLs dos sitemaps...';
            document.getElementById('progress-detail').textContent = '';
        } else if (state.phase === 'inspecting') {
            document.getElementById('progress-title').textContent = 'Verificando indexação...';
            document.getElementById('progress-detail').textContent = `${state.progress} de ${state.total} URLs`;
        } else if (state.phase === 'indexing') {
            document.getElementById('progress-title').textContent = 'Solicitando indexação...';
            document.getElementById('progress-detail').textContent = `${state.progress} de ${state.total} URLs`;
        }

        if (!state.running) {
            clearInterval(pollingInterval);
            pollingInterval = null;

            if (state.phase === 'error') {
                hideProgressModal();
                alert('Erro: ' + state.error);
            } else if (state.phase === 'inspected') {
                hideProgressModal();
                currentExecId = state.exec_id;
                allResults = state.results || [];
                showResultsModal(allResults, state.exec_id);
            } else if (state.phase === 'done') {
                hideProgressModal();
                alert(state.message);
                loadHistory();
                switchTab('history');
            }
        }
    } catch (e) {
        // ignore polling errors
    }
}

// ------------------------------------------------
// Progress Modal
// ------------------------------------------------
function showProgressModal(title) {
    document.getElementById('progress-title').textContent = title;
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-text').textContent = 'Iniciando...';
    document.getElementById('progress-detail').textContent = '';
    document.getElementById('modal-progress').style.display = 'flex';
}

function hideProgressModal() {
    document.getElementById('modal-progress').style.display = 'none';
}

async function forceResetTask() {
    try {
        await fetch('/api/task/reset', { method: 'POST' });
        hideProgressModal();
        if (pollingInterval) { clearInterval(pollingInterval); pollingInterval = null; }
        alert('Tarefa resetada. Você pode iniciar uma nova verificação.');
    } catch (e) {
        alert('Erro ao resetar: ' + e.message);
    }
}

// ------------------------------------------------
// Results Modal
// ------------------------------------------------
function showResultsModal(results, execId) {
    const indexed = results.filter(r => !r['Precisa Indexar']);
    const notIndexed = results.filter(r => r['Precisa Indexar']);

    // Summary
    document.getElementById('results-summary').innerHTML = `
        <div class="stat-card stat-total">
            <div class="stat-value">${results.length}</div>
            <div class="stat-label">Total</div>
        </div>
        <div class="stat-card stat-indexed">
            <div class="stat-value">${indexed.length}</div>
            <div class="stat-label">Indexadas</div>
        </div>
        <div class="stat-card stat-not-indexed">
            <div class="stat-value">${notIndexed.length}</div>
            <div class="stat-label">Não Indexadas</div>
        </div>
    `;

    // Render table
    renderResultsTable('results-tbody', results, execId);

    // Load insights & show export
    loadInsights(execId, 'results-insights');
    const exportBtn = document.getElementById('btn-export-results');
    exportBtn.style.display = 'inline-flex';
    exportBtn.onclick = () => exportExcel(execId);
    const exportCsvBtn = document.getElementById('btn-export-results-csv');
    exportCsvBtn.style.display = 'inline-flex';
    exportCsvBtn.onclick = () => exportCSV(execId);

    // Footer
    const footer = document.getElementById('results-footer');
    if (notIndexed.length > 0) {
        const totalProps = 1 + additionalProperties.length;
        const totalQuota = totalProps * 200;
        const quotaInfo = additionalProperties.length > 0
            ? `<span class="quota-badge quota-badge-active" style="margin-left:0.5rem;">${totalProps} prop. × 200 = ${totalQuota} URLs/dia</span>`
            : `(limite: 200/dia)`;
        footer.innerHTML = `
            <span style="color:var(--text-secondary);font-size:0.85rem;">
                ${notIndexed.length} URL(s) precisam de indexação ${quotaInfo}
            </span>
            <button class="btn btn-success" onclick="requestIndexing(${execId})">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                Solicitar Indexação (${Math.min(notIndexed.length, totalQuota)})
            </button>
        `;
    } else {
        footer.innerHTML = `
            <span style="color:var(--success);font-size:0.9rem;font-weight:500;">
                ✓ Todas as URLs já estão indexadas!
            </span>
            <button class="btn btn-ghost" onclick="closeResults()">Fechar</button>
        `;
    }

    document.getElementById('modal-results').style.display = 'flex';
}

function renderResultsTable(tbodyId, results, execId) {
    const tbody = document.getElementById(tbodyId);
    const effectiveExecId = execId || currentExecId || currentExecIdForHistory;
    tbody.innerHTML = results.map(r => {
        const needsIndexing = r['Precisa Indexar'] || r['needs_indexing'];
        const badgeClass = needsIndexing ? 'badge-warning' : 'badge-success';
        const badgeText = needsIndexing ? 'Não Indexada' : 'Indexada';
        const reason = r['Motivo'] || r['reason'] || '';
        const action = r['Ação Tomada'] || r['action_taken'] || 'Aguardando';
        const url = r['URL'] || r['url'] || '';
        const escapedUrl = url.replace(/'/g, "\\'").replace(/"/g, '&quot;');

        const resendBtn = needsIndexing
            ? `<button class="btn-resend" onclick="requestSingleIndexing(${effectiveExecId}, '${escapedUrl}', this)" title="Reenviar esta URL">
                 <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
               </button>`
            : '<span class="text-muted">—</span>';

        return `
            <tr>
                <td title="${url}">${url}</td>
                <td><span class="badge ${badgeClass}">${badgeText}</span></td>
                <td>${reason}</td>
                <td>${action}</td>
                <td class="td-actions">${resendBtn}</td>
            </tr>
        `;
    }).join('');
}

function filterResults(filter) {
    document.querySelectorAll('#modal-results .filter-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`#modal-results .filter-btn[data-filter="${filter}"]`).classList.add('active');

    let filtered = allResults;
    if (filter === 'not-indexed') {
        filtered = allResults.filter(r => r['Precisa Indexar']);
    } else if (filter === 'indexed') {
        filtered = allResults.filter(r => !r['Precisa Indexar']);
    }
    renderResultsTable('results-tbody', filtered, currentExecId);
}

function closeResults() {
    document.getElementById('modal-results').style.display = 'none';
}

// ------------------------------------------------
// Request Indexing
// ------------------------------------------------
async function requestIndexing(execId) {
    const notIndexed = allResults.filter(r => r['Precisa Indexar']);
    const urls = notIndexed.map(r => r['URL']);

    if (urls.length === 0) return;

    // Sitemaps selecionados
    const manualUrl = document.getElementById('sitemap-manual-check').checked
        ? document.getElementById('sitemap-manual').value.trim()
        : '';
    const sitemaps = [...selectedSitemaps];
    if (manualUrl) sitemaps.push(manualUrl);

    closeResults();
    showProgressModal('Solicitando indexação...');

    // Se há propriedades adicionais, usar rota multi-property
    const useMulti = additionalProperties.length > 0;
    const endpoint = useMulti ? '/api/index/multi' : '/api/index';
    const bodyData = useMulti
        ? { exec_id: execId, urls, site_urls: [selectedSite, ...additionalProperties], sitemap_urls: sitemaps }
        : { exec_id: execId, urls, sitemap_urls: sitemaps };

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bodyData)
        });

        const data = await res.json();
        if (data.error) {
            hideProgressModal();
            alert('Erro: ' + data.error);
            return;
        }

        // Se multi, mostrar distribuição no título
        if (data.distribution) {
            const parts = Object.entries(data.distribution)
                .filter(([, count]) => count > 0)
                .map(([su, count]) => `${count} via ${su.length > 40 ? su.slice(0, 37) + '...' : su}`);
            document.getElementById('progress-text').textContent = parts.join(' | ');
        }

        startPolling();
    } catch (e) {
        hideProgressModal();
        alert('Erro: ' + e.message);
    }
}

// ------------------------------------------------
// History
// ------------------------------------------------

function extractSiteName(siteUrl) {
    // sc-domain:reallimp.net.br → Reallimp
    // https://www.reallimp.net.br/ → Reallimp
    let domain = siteUrl;
    domain = domain.replace('sc-domain:', '');
    domain = domain.replace(/^https?:\/\//, '');
    domain = domain.replace(/^www\./, '');
    domain = domain.replace(/\/.*/g, '');
    // Pega só o nome (antes do primeiro ponto)
    const name = domain.split('.')[0];
    return name.charAt(0).toUpperCase() + name.slice(1);
}

async function loadHistory() {
    const list = document.getElementById('history-list');
    const empty = document.getElementById('history-empty');

    list.innerHTML = '<div class="loading-indicator"><div class="spinner"></div><span>Carregando histórico...</span></div>';
    empty.style.display = 'none';

    try {
        const res = await fetch('/api/history');
        const data = await res.json();

        if (!data.executions || data.executions.length === 0) {
            list.innerHTML = '';
            empty.style.display = 'block';
            return;
        }

        empty.style.display = 'none';

        // Agrupar por site
        const groups = {};
        data.executions.forEach(exec => {
            const siteName = extractSiteName(exec.site_url);
            const key = exec.site_url;
            if (!groups[key]) {
                groups[key] = { siteName, siteUrl: exec.site_url, executions: [] };
            }
            groups[key].executions.push(exec);
        });

        list.innerHTML = Object.values(groups).map(group => {
            const totalExecs = group.executions.length;

            const execItems = group.executions.map(exec => {
                const statusBadge = exec.status === 'completed'
                    ? '<span class="badge badge-success">Concluído</span>'
                    : exec.status === 'inspected'
                        ? '<span class="badge badge-info">Inspecionado</span>'
                        : exec.status === 'failed'
                            ? '<span class="badge badge-error">Erro</span>'
                            : '<span class="badge badge-warning">Em andamento</span>';

                return `
                    <div class="history-item">
                        <div class="history-item-info" onclick="viewExecution(${exec.id})">
                            <div class="history-meta">
                                <span>📅 ${exec.date}</span>
                                <span>${statusBadge}</span>
                            </div>
                        </div>
                        <div class="history-item-stats" onclick="viewExecution(${exec.id})">
                            <div class="history-stat">
                                <div class="hs-value" style="color:var(--info)">${exec.total_urls}</div>
                                <div class="hs-label">Total</div>
                            </div>
                            <div class="history-stat">
                                <div class="hs-value" style="color:var(--success)">${exec.indexed_count}</div>
                                <div class="hs-label">Indexadas</div>
                            </div>
                            <div class="history-stat">
                                <div class="hs-value" style="color:var(--warning)">${exec.not_indexed_count}</div>
                                <div class="hs-label">Não Index.</div>
                            </div>
                            <div class="history-stat">
                                <div class="hs-value" style="color:var(--accent-secondary)">${exec.requested_count}</div>
                                <div class="hs-label">Solicitadas</div>
                            </div>
                        </div>
                        <button class="btn-delete" onclick="event.stopPropagation(); deleteExecution(${exec.id})" title="Excluir">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        </button>
                    </div>
                `;
            }).join('');

            return `
                <div class="history-group">
                    <div class="history-group-header" onclick="toggleGroup(this)">
                        <div class="history-group-title">
                            <svg class="group-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                            <span class="group-name">${group.siteName}</span>
                            <span class="group-url">${group.siteUrl}</span>
                        </div>
                        <span class="group-count">${totalExecs} execuç${totalExecs === 1 ? 'ão' : 'ões'}</span>
                    </div>
                    <div class="history-group-body open">
                        ${execItems}
                    </div>
                </div>
            `;
        }).join('');

    } catch (e) {
        list.innerHTML = '<p style="color:var(--error);">Erro ao carregar histórico.</p>';
    }
}

function toggleGroup(header) {
    const body = header.nextElementSibling;
    const chevron = header.querySelector('.group-chevron');
    body.classList.toggle('open');
    chevron.classList.toggle('rotated');
}

async function deleteExecution(execId) {
    if (!confirm('Tem certeza que deseja excluir essa execução?')) return;

    try {
        const res = await fetch(`/api/history/${execId}`, { method: 'DELETE' });
        const data = await res.json();

        if (data.ok) {
            loadHistory();
        } else {
            alert('Erro ao excluir: ' + (data.error || 'Erro desconhecido'));
        }
    } catch (e) {
        alert('Erro de conexão: ' + e.message);
    }
}

let historyDetailUrls = [];

async function viewExecution(execId) {
    const modal = document.getElementById('modal-history-detail');
    modal.style.display = 'flex';
    currentExecIdForHistory = execId;

    document.getElementById('history-detail-title').textContent = 'Carregando...';
    document.getElementById('history-detail-summary').innerHTML = '';
    document.getElementById('history-detail-tbody').innerHTML = '';
    document.getElementById('history-detail-footer').innerHTML = '';

    try {
        const res = await fetch(`/api/history/${execId}`);
        const data = await res.json();

        const exec = data.execution;
        const urls = data.urls;
        historyDetailUrls = urls;

        document.getElementById('history-detail-title').textContent = exec.site_url;

        document.getElementById('history-detail-summary').innerHTML = `
            <div class="stat-card stat-total">
                <div class="stat-value">${exec.total_urls}</div>
                <div class="stat-label">Total</div>
            </div>
            <div class="stat-card stat-indexed">
                <div class="stat-value">${exec.indexed_count}</div>
                <div class="stat-label">Indexadas</div>
            </div>
            <div class="stat-card stat-not-indexed">
                <div class="stat-value">${exec.not_indexed_count}</div>
                <div class="stat-label">Não Indexadas</div>
            </div>
            <div class="stat-card stat-requested">
                <div class="stat-value">${exec.requested_count}</div>
                <div class="stat-label">Solicitadas</div>
            </div>
        `;

        renderResultsTable('history-detail-tbody', urls, exec.id);

        // Load insights & show export
        loadInsights(exec.id, 'history-insights');
        const exportBtn = document.getElementById('btn-export-history');
        exportBtn.style.display = 'inline-flex';
        exportBtn.onclick = () => exportExcel(exec.id);
        const exportCsvBtn = document.getElementById('btn-export-history-csv');
        exportCsvBtn.style.display = 'inline-flex';
        exportCsvBtn.onclick = () => exportCSV(exec.id);

        const notIndexedCount = urls.filter(u => u.needs_indexing).length;
        const footer = document.getElementById('history-detail-footer');

        if (notIndexedCount > 0) {
            footer.innerHTML = `
                <span style="color:var(--text-secondary);font-size:0.85rem;">
                    ${notIndexedCount} URL(s) não indexadas
                </span>
                <button class="btn btn-success" onclick="retryIndexing(${execId})">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                    Re-solicitar Indexação (${notIndexedCount})
                </button>
            `;
        } else {
            footer.innerHTML = `
                <span style="color:var(--success);font-size:0.85rem;">✓ Todas indexadas!</span>
                <button class="btn btn-ghost" onclick="closeHistoryDetail()">Fechar</button>
            `;
        }

    } catch (e) {
        document.getElementById('history-detail-title').textContent = 'Erro';
        document.getElementById('history-detail-summary').innerHTML = '<p style="color:var(--error);">Erro ao carregar detalhes.</p>';
    }
}

function filterHistoryDetail(filter) {
    document.querySelectorAll('#modal-history-detail .filter-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`#modal-history-detail .filter-btn[data-filter="${filter}"]`).classList.add('active');

    let filtered = historyDetailUrls;
    if (filter === 'not-indexed') {
        filtered = historyDetailUrls.filter(u => u.needs_indexing);
    }
    renderResultsTable('history-detail-tbody', filtered, currentExecIdForHistory);
}

async function retryIndexing(execId) {
    closeHistoryDetail();
    showProgressModal('Re-solicitando indexação...');

    try {
        const res = await fetch(`/api/history/${execId}/retry`, {
            method: 'POST'
        });
        const data = await res.json();

        if (data.error) {
            hideProgressModal();
            alert('Erro: ' + data.error);
            return;
        }

        startPolling();
    } catch (e) {
        hideProgressModal();
        alert('Erro: ' + e.message);
    }
}

function closeHistoryDetail() {
    document.getElementById('modal-history-detail').style.display = 'none';
    currentExecIdForHistory = null;
}

// ------------------------------------------------
// Insights & Analytics
// ------------------------------------------------
async function loadInsights(execId, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = '<div class="loading-indicator" style="padding:0.5rem 0;"><div class="spinner"></div><span>Carregando insights...</span></div>';

    try {
        const res = await fetch(`/api/history/${execId}/compare`);
        const data = await res.json();
        renderInsights(data, container);
    } catch (e) {
        container.innerHTML = '';
    }
}

function renderInsights(data, container) {
    let html = '';

    // Comparison with previous execution
    if (data.comparison) {
        const c = data.comparison;
        const deltaIcon = (val) => {
            if (val > 0) return `<span class="delta delta-up">▲ +${val}</span>`;
            if (val < 0) return `<span class="delta delta-down">▼ ${val}</span>`;
            return `<span class="delta delta-neutral">= 0</span>`;
        };
        const rateIcon = (val) => {
            if (val > 0) return `<span class="delta delta-up">▲ +${val}%</span>`;
            if (val < 0) return `<span class="delta delta-down">▼ ${val}%</span>`;
            return `<span class="delta delta-neutral">= 0%</span>`;
        };

        html += `
            <div class="insights-header">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                <span>Comparação com análise anterior <small>(${c.previous.date})</small></span>
            </div>
            <div class="insights-grid">
                <div class="insight-card">
                    <div class="insight-label">Taxa de Indexação</div>
                    <div class="insight-value">${c.current_rate}%</div>
                    <div class="insight-delta">${rateIcon(c.rate_delta)}</div>
                </div>
                <div class="insight-card">
                    <div class="insight-label">Indexadas</div>
                    <div class="insight-value">${data.comparison.delta_indexed >= 0 ? '+' : ''}${data.comparison.delta_indexed}</div>
                    <div class="insight-delta">${deltaIcon(c.delta_indexed)}</div>
                </div>
                <div class="insight-card">
                    <div class="insight-label">Não Indexadas</div>
                    <div class="insight-value">${Math.abs(c.delta_not_indexed)}</div>
                    <div class="insight-delta">${c.delta_not_indexed < 0
                ? '<span class="delta delta-up">▼ ' + c.delta_not_indexed + '</span>'
                : c.delta_not_indexed > 0
                    ? '<span class="delta delta-down">▲ +' + c.delta_not_indexed + '</span>'
                    : '<span class="delta delta-neutral">= 0</span>'
            }</div>
                </div>
                <div class="insight-card">
                    <div class="insight-label">Novas Indexadas</div>
                    <div class="insight-value" style="color:var(--success)">${c.newly_indexed_count}</div>
                    <div class="insight-delta"><small>URLs que passaram a ser indexadas</small></div>
                </div>
            </div>
        `;

        if (c.lost_indexing_count > 0) {
            html += `
                <div class="insight-warning">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    <span>${c.lost_indexing_count} URL(s) perderam indexação desde a última análise</span>
                </div>
            `;
        }
    } else {
        html += `
            <div class="insights-header insights-first">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                <span>Primeira análise desta propriedade — execute novamente no futuro para ver comparações</span>
            </div>
        `;
    }

    // Pages added/removed
    if (data.comparison && (data.comparison.pages_added_count > 0 || data.comparison.pages_removed_count > 0)) {
        const c = data.comparison;
        html += `<div class="pages-changes-section">`;

        if (c.pages_added_count > 0) {
            html += `
                <div class="pages-change-card pages-added">
                    <div class="pages-change-header" onclick="togglePagesList(this)">
                        <div class="pages-change-info">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            <span><strong>${c.pages_added_count}</strong> página(s) adicionada(s) ao sitemap</span>
                        </div>
                        <svg class="pages-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                    </div>
                    <div class="pages-change-list" style="display:none;">
                        ${c.pages_added.map(u => `<div class="pages-url">${u}</div>`).join('')}
                        ${c.pages_added_count > 50 ? `<div class="pages-url pages-more">...e mais ${c.pages_added_count - 50} URL(s)</div>` : ''}
                    </div>
                </div>
            `;
        }

        if (c.pages_removed_count > 0) {
            html += `
                <div class="pages-change-card pages-removed">
                    <div class="pages-change-header" onclick="togglePagesList(this)">
                        <div class="pages-change-info">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            <span><strong>${c.pages_removed_count}</strong> página(s) removida(s) do sitemap</span>
                        </div>
                        <svg class="pages-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                    </div>
                    <div class="pages-change-list" style="display:none;">
                        ${c.pages_removed.map(u => `<div class="pages-url">${u}</div>`).join('')}
                        ${c.pages_removed_count > 50 ? `<div class="pages-url pages-more">...e mais ${c.pages_removed_count - 50} URL(s)</div>` : ''}
                    </div>
                </div>
            `;
        }

        html += `</div>`;
    }

    // Analytics chart (simple bar representation)
    if (data.analytics && data.analytics.length > 1) {
        const maxTotal = Math.max(...data.analytics.map(a => a.total));
        html += `
            <div class="analytics-section">
                <div class="analytics-title">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                    Evolução (${data.analytics.length} execuções)
                </div>
                <div class="analytics-chart">
                    ${data.analytics.map(a => {
            const pct = maxTotal > 0 ? (a.indexed / maxTotal) * 100 : 0;
            const notPct = maxTotal > 0 ? (a.not_indexed / maxTotal) * 100 : 0;
            const dateShort = a.date.split(' ')[0].split('-').reverse().slice(0, 2).join('/');
            return `
                            <div class="analytics-bar-group" title="${a.date}\nIndexadas: ${a.indexed}\nNão index.: ${a.not_indexed}\nTaxa: ${a.rate}%">
                                <div class="analytics-bar">
                                    <div class="bar-indexed" style="height:${pct}%"></div>
                                    <div class="bar-not-indexed" style="height:${notPct}%"></div>
                                </div>
                                <div class="bar-label">${dateShort}</div>
                                <div class="bar-rate">${a.rate}%</div>
                            </div>
                        `;
        }).join('')}
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
}

// ------------------------------------------------
// Single URL Resubmission
// ------------------------------------------------
async function requestSingleIndexing(execId, url, buttonEl) {
    if (!url || buttonEl.disabled) return;

    buttonEl.disabled = true;
    buttonEl.innerHTML = '<div class="spinner-sm"></div>';
    buttonEl.classList.add('btn-resend-loading');

    try {
        const res = await fetch('/api/index/single', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url, exec_id: execId })
        });

        const data = await res.json();

        if (data.ok) {
            buttonEl.innerHTML = '✓';
            buttonEl.classList.remove('btn-resend-loading');
            buttonEl.classList.add('btn-resend-success');
            // Update the action column in the same row
            const row = buttonEl.closest('tr');
            if (row) {
                const actionCell = row.cells[3];
                actionCell.textContent = 'Solicitado (Solicitado com Sucesso)';
            }
        } else {
            buttonEl.innerHTML = '✕';
            buttonEl.classList.remove('btn-resend-loading');
            buttonEl.classList.add('btn-resend-error');
            buttonEl.title = data.error || 'Erro';
            setTimeout(() => {
                buttonEl.disabled = false;
                buttonEl.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>';
                buttonEl.classList.remove('btn-resend-error');
            }, 3000);
        }
    } catch (e) {
        buttonEl.innerHTML = '✕';
        buttonEl.classList.remove('btn-resend-loading');
        buttonEl.classList.add('btn-resend-error');
        setTimeout(() => {
            buttonEl.disabled = false;
            buttonEl.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>';
            buttonEl.classList.remove('btn-resend-error');
        }, 3000);
    }
}

// ------------------------------------------------
// Excel Export
// ------------------------------------------------
function exportExcel(execId) {
    if (!execId) return;
    window.open(`/api/history/${execId}/export`, '_blank');
}

function exportCSV(execId) {
    if (!execId) return;
    window.open(`/api/history/${execId}/export/csv`, '_blank');
}

// ------------------------------------------------
// Individual URL Inspection
// ------------------------------------------------
async function inspectSingleUrl() {
    const urlInput = document.getElementById('inspect-url-input');
    const url = urlInput ? urlInput.value.trim() : '';

    if (!url) {
        alert('Por favor, insira uma URL para inspecionar.');
        return;
    }

    if (!selectedSite) {
        alert('Selecione um site primeiro (Passo 1).');
        return;
    }

    const btn = document.getElementById('btn-inspect-url');
    const resultEl = document.getElementById('inspect-url-result');

    btn.disabled = true;
    btn.textContent = 'Inspecionando...';
    resultEl.style.display = 'none';
    resultEl.innerHTML = '';

    try {
        const res = await fetch('/api/inspect/url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url, site_url: selectedSite })
        });
        const data = await res.json();

        if (data.error) {
            resultEl.innerHTML = `<div class="inspect-result-error">❌ ${data.error}</div>`;
            resultEl.style.display = 'block';
            return;
        }

        const verdictClass = data.verdict === 'PASS' ? 'badge-success' : data.verdict === 'FAIL' ? 'badge-error' : 'badge-warning';
        const verdictLabel = data.verdict === 'PASS' ? '✓ Indexada' : data.verdict === 'FAIL' ? '✕ Não Indexada' : '⚬ Neutro';
        const crawlTime = data.lastCrawlTime ? new Date(data.lastCrawlTime).toLocaleString('pt-BR') : 'Nunca rastreada';
        const robotsClass = data.robotsTxtState === 'ALLOWED' ? 'text-success' : data.robotsTxtState === 'DISALLOWED' ? 'text-error' : '';
        const mobileLabel = data.mobileUsability === 'PASS' ? '✓ OK' : data.mobileUsability === 'FAIL' ? '✕ Problemas' : '—';

        resultEl.innerHTML = `
            <div class="inspect-result-card">
                <div class="inspect-result-row">
                    <span class="inspect-result-label">Veredicto</span>
                    <span class="badge ${verdictClass}">${verdictLabel}</span>
                </div>
                <div class="inspect-result-row">
                    <span class="inspect-result-label">Estado de Cobertura</span>
                    <span class="inspect-result-value">${data.coverageState || '—'}</span>
                </div>
                <div class="inspect-result-row">
                    <span class="inspect-result-label">Robots.txt</span>
                    <span class="inspect-result-value ${robotsClass}">${data.robotsTxtState}</span>
                </div>
                <div class="inspect-result-row">
                    <span class="inspect-result-label">Estado de Indexação</span>
                    <span class="inspect-result-value">${data.indexingState || '—'}</span>
                </div>
                <div class="inspect-result-row">
                    <span class="inspect-result-label">Fetch da Página</span>
                    <span class="inspect-result-value">${data.pageFetchState || '—'}</span>
                </div>
                <div class="inspect-result-row">
                    <span class="inspect-result-label">Rastreado como</span>
                    <span class="inspect-result-value">${data.crawledAs || '—'}</span>
                </div>
                <div class="inspect-result-row">
                    <span class="inspect-result-label">Último Rastreamento</span>
                    <span class="inspect-result-value">${crawlTime}</span>
                </div>
                <div class="inspect-result-row">
                    <span class="inspect-result-label">Usabilidade Mobile</span>
                    <span class="inspect-result-value">${mobileLabel}</span>
                </div>
            </div>
        `;
        resultEl.style.display = 'block';
    } catch (e) {
        resultEl.innerHTML = `<div class="inspect-result-error">❌ Erro de conexão: ${e.message}</div>`;
        resultEl.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Inspecionar';
    }
}

function togglePagesList(headerEl) {
    const list = headerEl.nextElementSibling;
    const chevron = headerEl.querySelector('.pages-chevron');
    const isOpen = list.style.display !== 'none';
    list.style.display = isOpen ? 'none' : 'block';
    if (chevron) chevron.classList.toggle('rotated', !isOpen);
}

// ------------------------------------------------
// Setup / Onboarding - Upload
// ------------------------------------------------
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('upload-area').classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('upload-area').classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('upload-area').classList.remove('drag-over');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

async function uploadFile(file) {
    const statusDiv = document.getElementById('upload-status');
    statusDiv.style.display = 'block';
    statusDiv.className = 'upload-status';
    statusDiv.textContent = 'Enviando arquivo...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/setup/upload', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();

        if (data.ok) {
            statusDiv.className = 'upload-status success';
            statusDiv.innerHTML = '✓ Configuração salva com sucesso! Redirecionando...';
            setTimeout(() => {
                showScreen('login');
            }, 1500);
        } else {
            statusDiv.className = 'upload-status error';
            statusDiv.textContent = '✕ ' + (data.error || 'Erro ao salvar arquivo.');
        }
    } catch (e) {
        statusDiv.className = 'upload-status error';
        statusDiv.textContent = '✕ Erro de conexão: ' + e.message;
    }
}
