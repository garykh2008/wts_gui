// Lucide Offline Fallback (prevents crashes in offline environments)
if (typeof lucide === 'undefined') {
    window.lucide = {
        createIcons: () => { console.debug("Lucide offline fallback: icons will render as empty tags"); }
    };
}

// Global State
const state = {
    configPath: '',
    configParams: [],
    devices: [],
    xmlTestCases: [],
    xmlTestbeds: [],
    xmlDetails: {},
    exclusions: [],
    tmsParams: [],
    tmsUploadEnabled: false,
    selectedTests: new Set(),
    execStats: {
        total: 0,
        pass: 0,
        fail: 0
    },
    currentTheme: 'dark',
    activeTab: 'config',
    activeLogFolder: '',
    logFolders: [],
    logFiles: [],
    runHistory: [],
    
    // Execution overrides
    overrideFailNtOnly: false,
    overrideIncludeTestbeds: new Set(),
    overrideExcludeTestbeds: new Set()
};

// API Base URL (empty for same host, which is local server)
const API_BASE = '';

// Helper API Fetcher
async function apiFetch(path, options = {}) {
    try {
        const url = `${API_BASE}${path}`;
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (e) {
        console.error(`API Fetch Error (${path}):`, e);
        showNotification(`Error: ${e.message}`, 'red');
        return { error: e.message };
    }
}

// Show Alert Notification (toast-like)
function showNotification(message, type = 'blue') {
    const toast = document.createElement('div');
    toast.className = `toast-alert ${type}`;
    toast.innerHTML = `
        <span class="toast-text">${message}</span>
        <button class="toast-close">&times;</button>
    `;
    document.body.appendChild(toast);
    
    // Auto-remove after 4 seconds
    const timeout = setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
    
    toast.querySelector('.toast-close').addEventListener('click', () => {
        clearTimeout(timeout);
        toast.remove();
    });
}

// Add CSS for Toasts dynamically
const styleSheet = document.createElement("style");
styleSheet.innerText = `
.toast-alert {
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    padding: 1rem 1.5rem;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 1rem;
    z-index: 1000;
    box-shadow: 0 10px 30px var(--shadow-color);
    animation: slideInToast 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
@keyframes slideInToast {
    from { transform: translateY(100px) scale(0.9); opacity: 0; }
    to { transform: translateY(0) scale(1); opacity: 1; }
}
.toast-alert.fade-out {
    opacity: 0;
    transform: translateY(20px) scale(0.9);
    transition: all 0.3s ease;
}
.toast-alert.blue { border-left: 4px solid var(--accent-color); }
.toast-alert.green { border-left: 4px solid var(--status-pass); }
.toast-alert.red { border-left: 4px solid var(--status-fail); }
.toast-alert.orange { border-left: 4px solid var(--status-nt); }
.toast-text { font-size: 0.9rem; font-weight: 500; color: var(--text-primary); }
.toast-close { border: none; background: transparent; color: var(--text-muted); cursor: pointer; font-size: 1.2rem; }
.toast-close:hover { color: var(--text-primary); }
`;
document.head.appendChild(styleSheet);

// ==================== Initialization ====================
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initApp();
    });
} else {
    initApp();
}

async function initApp() {
    // Initialize Lucide Icons
    lucide.createIcons();
    
    // Theme setup
    setupTheme();
    
    // Tab Navigation setup
    setupNavigation();
    
    // Initial fetch of app status & load default config if stored
    await checkBackendStatus();
}

function setupTheme() {
    const themeBtn = document.getElementById('theme-toggle-btn');
    const storedTheme = localStorage.getItem('theme') || 'dark';
    
    if (storedTheme === 'light') {
        document.body.classList.add('light-theme');
        state.currentTheme = 'light';
        themeBtn.innerHTML = '<i data-lucide="moon"></i>';
    } else {
        document.body.classList.remove('light-theme');
        state.currentTheme = 'dark';
        themeBtn.innerHTML = '<i data-lucide="sun"></i>';
    }
    lucide.createIcons();
    
    themeBtn.addEventListener('click', () => {
        if (state.currentTheme === 'dark') {
            document.body.classList.add('light-theme');
            state.currentTheme = 'light';
            themeBtn.innerHTML = '<i data-lucide="moon"></i>';
            localStorage.setItem('theme', 'light');
        } else {
            document.body.classList.remove('light-theme');
            state.currentTheme = 'dark';
            themeBtn.innerHTML = '<i data-lucide="sun"></i>';
            localStorage.setItem('theme', 'dark');
        }
        lucide.createIcons();
    });
}

function setupNavigation() {
    const navItems = document.querySelectorAll('.sidebar-nav .nav-item');
    const tabPanels = document.querySelectorAll('.tab-panel');
    const pageTitle = document.getElementById('page-title');
    
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const tabName = item.getAttribute('data-tab');
            
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            
            tabPanels.forEach(p => p.classList.remove('active'));
            document.getElementById(`tab-${tabName}`).classList.add('active');
            
            state.activeTab = tabName;
            
            // Update Title
            const titleMap = {
                config: 'Configuration Editor',
                execution: 'Test Suite Execution',
                analytics: 'Testing Results Analytics',
                logs: 'Log Directory Browser',
                masterinfo: 'MasterTestInfo XML Specifications',
                tms: 'TMS Connection Settings',
                help: 'WTS User Documentation'
            };
            pageTitle.innerText = titleMap[tabName] || 'WTS GUI Dashboard';
            
            // Tab Specific Load triggers
            if (tabName === 'logs' && state.logFolders.length === 0) {
                loadLogsFolders();
            }
        });
    });
    
    // Help manual link trigger
    document.getElementById('help-btn').addEventListener('click', (e) => {
        e.preventDefault();
        navItems.forEach(i => i.classList.remove('active'));
        tabPanels.forEach(p => p.classList.remove('active'));
        document.getElementById('tab-help').classList.add('active');
        state.activeTab = 'help';
        pageTitle.innerText = 'WTS User Documentation';
        loadUserGuide();
    });
}

async function checkBackendStatus() {
    const res = await apiFetch('/api/status');
    if (res && !res.error) {
        document.getElementById('backend-status-text').innerText = 'Backend Connected';
        document.querySelector('.status-dot').className = 'status-dot green';
        
        // Load path memory: server settings priority, then localStorage fallback
        let loadedPath = '';
        if (res.settings && res.settings.config_path) {
            loadedPath = res.settings.config_path;
        } else {
            loadedPath = localStorage.getItem('wts_config_path');
        }
        
        if (loadedPath) {
            state.configPath = loadedPath;
            document.getElementById('current-config-path').innerText = state.configPath;
            document.getElementById('current-config-path').title = state.configPath;
            
            // Load config details
            await loadConfigDetails();
            await loadXmlSpecs();
        }
        
        if (res.settings) {
            if (res.settings.log_filter_date) {
                document.getElementById('log-date-filter').value = res.settings.log_filter_date;
            } else {
                // Set default to 1 month ago
                const d = new Date();
                d.setMonth(d.getMonth() - 1);
                document.getElementById('log-date-filter').value = d.toISOString().split('T')[0];
            }
            if (res.settings.result_filter_date) {
                document.getElementById('analytics-date-input').value = res.settings.result_filter_date;
            } else {
                // Set default to today
                document.getElementById('analytics-date-input').value = new Date().toISOString().split('T')[0];
            }
        }
        
        // Load default exclusions
        await loadExclusionsRegistry();
        
        // Load TMS Config
        await loadTmsConfig();
        
        // If tests are currently running in backend (e.g. after page refresh), reconnect seamlessly
        if (res.running) {
            document.getElementById('start-testing-btn').disabled = true;
            document.getElementById('stop-testing-btn').disabled = false;
            document.getElementById('exec-checkbox-list').querySelectorAll('input').forEach(i => i.disabled = true);
            
            const term = document.getElementById('terminal-output');
            term.innerHTML = '<div class="terminal-line system-msg">[System] Reconnected to ongoing test execution stream...</div>';
            
            startConsoleOutputSSE();
            syncExecStatsFromLogs();
        }
    } else {
        document.getElementById('backend-status-text').innerText = 'Connection Offline';
        document.querySelector('.status-dot').className = 'status-dot red';
        showNotification('Failed to connect to local WTS API backend!', 'red');
    }
}

// ==================== Config Tab Logic ====================

async function loadConfigDetails() {
    if (!state.configPath) return;
    
    const res = await apiFetch(`/api/config?path=${encodeURIComponent(state.configPath)}`);
    if (res && !res.error) {
        state.configParams = res.parameters || [];
        state.devices = res.devices || [];
        
        // Cache path in browser storage
        localStorage.setItem('wts_config_path', state.configPath);
        
        renderConfigParameters();
        renderDeviceToggles();
        
        // Enable Save/Reload/Raw actions
        document.getElementById('save-config-btn').disabled = false;
        document.getElementById('reload-config-btn').disabled = false;
        document.getElementById('view-raw-config-btn').disabled = false;
        
        // Enable check alive button & trigger check
        document.getElementById('check-alive-btn').disabled = false;
        runCheckAlive();
    }
}

function renderConfigParameters() {
    const searchVal = document.getElementById('config-search').value.toLowerCase();
    const tbody = document.getElementById('config-table-body');
    tbody.innerHTML = '';
    
    const filtered = state.configParams.filter(p => 
        p.key.toLowerCase().includes(searchVal) || p.value.toLowerCase().includes(searchVal)
    );
    
    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-4">No matching parameters found.</td></tr>`;
        return;
    }
    
    filtered.forEach(p => {
        const tr = document.createElement('tr');
        if (p.commented) {
            tr.className = 'row-commented';
        }
        
        const keyDisplay = p.commented ? `[OFF] ${p.key}` : p.key;
        
        let typeBadgeClass = 'badge-blue';
        if (p.type === 'define_kv_pair') typeBadgeClass = 'badge-purple';
        if (p.type === 'ip_port_pair') typeBadgeClass = 'badge-green';
        
        const typeDisplay = p.type.replace('_pair', '').replace('_', ' ').toUpperCase();
        
        tr.innerHTML = `
            <td class="table-cell-key">${keyDisplay}</td>
            <td class="table-cell-value" title="${p.value}">${p.value}</td>
            <td><span class="badge ${typeBadgeClass}">${typeDisplay}</span></td>
            <td class="text-right" style="white-space: nowrap;">
                <button class="action-icon-btn toggle-comment-btn" data-index="${p.index}" style="color: ${p.commented ? 'var(--text-muted)' : 'var(--accent-color)'};" title="${p.commented ? 'Activate (Uncomment)' : 'Comment Out'}">
                    <i data-lucide="${p.commented ? 'toggle-left' : 'toggle-right'}"></i>
                </button>
                <button class="action-icon-btn edit-param-btn" data-index="${p.index}" style="margin-left: 0.25rem;" title="Edit Value">
                    <i data-lucide="edit-3"></i>
                </button>
            </td>
        `;
        
        tbody.appendChild(tr);
    });
    
    // Wire up edit buttons
    tbody.querySelectorAll('.edit-param-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const index = parseInt(btn.getAttribute('data-index'));
            openConfigEditorModal(index);
        });
    });
    
    // Wire up toggle comment buttons
    tbody.querySelectorAll('.toggle-comment-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const index = parseInt(btn.getAttribute('data-index'));
            const param = state.configParams.find(p => p.index === index);
            if (param) {
                param.commented = !param.commented;
                togglePairedParameterInState(param);
                renderConfigParameters();
                showNotification(`Parameter '${param.key}' is now ${param.commented ? 'commented out' : 'active'} in memory. Click Save Config to apply.`, 'blue');
            }
        });
    });
    
    lucide.createIcons();
}

function togglePairedParameterInState(param) {
    let dev = '';
    let ip = '';
    let isAgent = false;
    
    const keyLower = param.key.toLowerCase();
    if (keyLower.startsWith('wfa_control_agent_')) {
        dev = keyLower.replace('wfa_control_agent_', '');
        isAgent = true;
        const match = param.value.match(/ipaddr=([^,]+)/);
        if (match) ip = match[1].trim();
    } else if (keyLower.endsWith('_wireless_ip')) {
        dev = keyLower.replace('$', '').replace('_wireless_ip', '');
        isAgent = false;
        ip = param.value.trim();
    }
    
    if (!dev) return;
    
    // Partner keys can either start with $ or not
    const partnerKeysLower = isAgent ? [ `$${dev}_wireless_ip`.toLowerCase(), `${dev}_wireless_ip`.toLowerCase() ] : [ `wfa_control_agent_${dev}`.toLowerCase() ];
    
    // Find partner parameter using dual matching strategy:
    // 1. Proximity check first
    let partner = state.configParams.find(p => {
        const pKeyLower = p.key.toLowerCase();
        if (!partnerKeysLower.includes(pKeyLower)) return false;
        if (isAgent) {
            return p.index > param.index && p.index <= param.index + 3;
        } else {
            return p.index < param.index && p.index >= param.index - 3;
        }
    });
    
    // 2. IP matching fallback if proximity fails
    if (!partner && ip) {
        partner = state.configParams.find(p => {
            const pKeyLower = p.key.toLowerCase();
            if (!partnerKeysLower.includes(pKeyLower)) return false;
            if (isAgent) {
                return p.value.trim() === ip;
            } else {
                return p.value.includes(`ipaddr=${ip}`);
            }
        });
    }
    
    if (partner) {
        partner.commented = param.commented;
    }
    
    // If activating (uncommenting), disable all other entries of the same device
    if (!param.commented) {
        state.configParams.forEach(p => {
            if (p.index === param.index || (partner && p.index === partner.index)) {
                return; // skip ourselves
            }
            
            const pKeyLower = p.key.toLowerCase();
            // Check other control agents for the same device
            if (pKeyLower === `wfa_control_agent_${dev}`.toLowerCase()) {
                p.commented = true;
            }
            // Check other wireless IPs for the same device
            if (pKeyLower === `$${dev}_wireless_ip`.toLowerCase() || pKeyLower === `${dev}_wireless_ip`.toLowerCase()) {
                p.commented = true;
            }
        });
    }
}

function renderDeviceToggles() {
    const containerAp = document.getElementById('ap-toggles-container');
    const containerSta = document.getElementById('sta-toggles-container');
    
    containerAp.innerHTML = '';
    containerSta.innerHTML = '';
    
    const aps = state.devices.filter(d => d.name.includes('_ap'));
    const stas = state.devices.filter(d => d.name.includes('_sta'));
    
    if (aps.length === 0) containerAp.innerHTML = '<span class="text-muted">No AP platforms found.</span>';
    if (stas.length === 0) containerSta.innerHTML = '<span class="text-muted">No STA platforms found.</span>';
    
    const renderRow = (d, container) => {
        const row = document.createElement('div');
        row.className = 'device-toggle-row';
        const label = d.ip ? `${d.name} (${d.ip})` : d.name;
        row.innerHTML = `
            <span>${label}</span>
            <label class="switch-container">
                <input type="checkbox" class="device-switch" data-index="${d.index}" ${d.enabled ? 'checked' : ''}>
                <span class="switch-slider"></span>
            </label>
        `;
        container.appendChild(row);
        
        // Event listener
        row.querySelector('.device-switch').addEventListener('change', async (e) => {
            const checked = e.target.checked;
            const res = await apiFetch('/api/config/toggle-device', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    path: state.configPath,
                    index: d.index,
                    enabled: checked
                })
            });
            if (res && res.success) {
                showNotification(`${label} ${checked ? 'enabled' : 'disabled'} in config.`, 'green');
                await loadConfigDetails();
                updateTestExecutionChecklist(); // Update execution checkboxes since devices changed
            } else {
                e.target.checked = !checked; // revert
            }
        });
    };
    
    aps.forEach(d => renderRow(d, containerAp));
    stas.forEach(d => renderRow(d, containerSta));
}

async function runCheckAlive() {
    if (!state.configPath) return;
    
    const btn = document.getElementById('check-alive-btn');
    const container = document.getElementById('check-alive-list');
    
    // Set UI to checking state
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="icon-spin" style="width: 14px; height: 14px;"></i>`;
    lucide.createIcons();
    
    // Update existing elements to "checking..."
    const badges = container.querySelectorAll('.badge');
    badges.forEach(badge => {
        badge.className = 'badge badge-checking';
        badge.innerText = 'CHECKING...';
    });
    
    try {
        const res = await apiFetch(`/api/config/check-alive?path=${encodeURIComponent(state.configPath)}`);
        
        if (res && res.results) {
            container.innerHTML = '';
            if (res.results.length === 0) {
                container.innerHTML = '<span class="text-muted">No active devices to check.</span>';
            } else {
                res.results.forEach(item => {
                    const row = document.createElement('div');
                    row.className = 'alive-item';
                    
                    const targetDisplay = item.port ? `${item.ip}:${item.port}` : item.ip;
                    const typeLabel = item.type.toUpperCase();
                    
                    const statusClass = item.status === 'online' ? 'badge-online' : 'badge-offline';
                    const statusText = item.status.toUpperCase();
                    
                    row.innerHTML = `
                        <div class="alive-info">
                            <span class="alive-name" title="${item.key}">${item.key}</span>
                            <span class="alive-target">${targetDisplay} (${typeLabel})</span>
                        </div>
                        <span class="badge ${statusClass}">${statusText}</span>
                    `;
                    container.appendChild(row);
                });
            }
        } else {
            container.innerHTML = '<span class="text-danger">Failed to check status.</span>';
        }
    } catch (e) {
        console.error("Error checking alive status:", e);
        container.innerHTML = '<span class="text-danger">Error checking status.</span>';
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="refresh-cw" style="width: 14px; height: 14px;"></i>`;
        lucide.createIcons();
    }
}

// Modal handling logic
function openModal(modalId) {
    document.getElementById('modal-backdrop').style.display = 'block';
    document.getElementById(modalId).style.display = 'flex';
}

function closeModal(modalId) {
    document.getElementById('modal-backdrop').style.display = 'none';
    document.getElementById(modalId).style.display = 'none';
}

// Wire up close buttons
document.querySelectorAll('.modal-close, [data-modal]').forEach(el => {
    el.addEventListener('click', (e) => {
        e.preventDefault();
        const targetModal = el.getAttribute('data-modal') || el.closest('.modal').id;
        closeModal(targetModal);
    });
});

let currentEditingIndex = null;

function openConfigEditorModal(index) {
    currentEditingIndex = index;
    const param = state.configParams.find(p => p.index === index);
    if (!param) return;
    
    if (param.type === 'ip_port_pair') {
        // IP address and port fields
        let ip = '';
        let port = '';
        const ipMatch = param.value.match(/ipaddr=([^,]+)/);
        const portMatch = param.value.match(/port=(\d+)/);
        
        if (ipMatch) ip = ipMatch[1];
        if (portMatch) port = portMatch[1];
        
        document.getElementById('conn-ip-input').value = ip;
        document.getElementById('conn-port-input').value = port;
        
        openModal('edit-connection-modal');
    } else {
        // Plain text value field
        document.getElementById('edit-value-label').innerText = `Field: ${param.key}`;
        document.getElementById('edit-value-input').value = param.value;
        
        openModal('edit-value-modal');
    }
}

// Save connection modal settings
document.getElementById('save-connection-btn').addEventListener('click', () => {
    if (currentEditingIndex === null) return;
    
    const ip = document.getElementById('conn-ip-input').value.trim();
    const port = document.getElementById('conn-port-input').value.trim();
    
    if (!ip || !port) {
        showNotification('IP and Port cannot be empty!', 'orange');
        return;
    }
    
    const newValue = `ipaddr=${ip},port=${port}`;
    state.configParams.find(p => p.index === currentEditingIndex).value = newValue;
    
    renderConfigParameters();
    closeModal('edit-connection-modal');
    showNotification('Parameter updated locally. Commit changes to save to file.', 'blue');
});

// Save value modal settings
document.getElementById('save-value-btn').addEventListener('click', () => {
    if (currentEditingIndex === null) return;
    
    const val = document.getElementById('edit-value-input').value;
    state.configParams.find(p => p.index === currentEditingIndex).value = val;
    
    renderConfigParameters();
    closeModal('edit-value-modal');
    showNotification('Parameter updated locally. Commit changes to save to file.', 'blue');
});

// Save AllInitConfig back to disk
document.getElementById('save-config-btn').addEventListener('click', async () => {
    const res = await apiFetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            path: state.configPath,
            parameters: state.configParams.map(p => ({
                index: p.index,
                value: p.value,
                commented: p.commented
            }))
        })
    });
    
    if (res && res.success) {
        showNotification('Configuration saved successfully!', 'green');
        await loadConfigDetails();
    }
});

// Reload config
document.getElementById('reload-config-btn').addEventListener('click', async () => {
    await loadConfigDetails();
    showNotification('Configuration reloaded from file.', 'blue');
});

// View raw configuration modal
document.getElementById('check-alive-btn').addEventListener('click', () => {
    runCheckAlive();
});

document.getElementById('view-raw-config-btn').addEventListener('click', async () => {
    const res = await apiFetch(`/api/config?path=${encodeURIComponent(state.configPath)}`);
    if (res && !res.error) {
        // Fetch raw representation from backend or compose it ourselves
        // Let's call the view raw API endpoint if we add it, or compose it
        const rawRes = await apiFetch(`/api/logs/view?folder=.&file=${encodeURIComponent(state.configPath.split(/[\\/]/).pop())}`);
        if (typeof rawRes === 'string') {
            document.getElementById('raw-config-content').value = rawRes;
        } else {
            // Read from logs view endpoint returns file content directly. Wait, the endpoint was wfile.write of log content.
            // If it parsed as json (error), we compose from params:
            const composeText = state.configParams.map(p => {
                const commentPrefix = p.commented ? '# ' : '';
                if (p.type === 'define_kv_pair') return `${commentPrefix}define!${p.key}!${p.value}!\n`;
                return `${commentPrefix}${p.key}!${p.value}!\n`;
            }).join('');
            document.getElementById('raw-config-content').value = composeText;
        }
        openModal('raw-config-modal');
    }
});

// ==================== XML Loader & Specs ====================

async function loadXmlSpecs() {
    if (!state.configPath) return;
    
    const res = await apiFetch(`/api/xml-data?path=${encodeURIComponent(state.configPath)}`);
    if (res && !res.error) {
        state.xmlTestCases = res.testCases || [];
        state.xmlTestbeds = res.testbeds || [];
        state.xmlDetails = res.details || {};
        
        updateTestExecutionChecklist();
        renderXmlTestCaseList();
        renderAdvancedFilterTestbeds();
    }
}

// ==================== Test Execution Tab Logic ====================

function updateTestExecutionChecklist() {
    const searchVal = document.getElementById('exec-search').value.toLowerCase();
    const activeRole = document.querySelector('.role-selector .role-btn.active').getAttribute('data-role');
    const container = document.getElementById('exec-checkbox-list');
    container.innerHTML = '';
    
    // Parse ignore rules
    // Find disabled devices in configuration (disabled only if all of its IP configurations are commented out)
    const allDeviceNames = new Set(state.devices.map(d => d.name.replace('_ap', '').replace('_sta', '')));
    const activeDeviceNames = new Set(state.devices.filter(d => d.enabled).map(d => d.name.replace('_ap', '').replace('_sta', '')));
    const disabledDevices = new Set(Array.from(allDeviceNames).filter(name => !activeDeviceNames.has(name)));
    
    let count = 0;
    
    state.xmlTestCases.forEach(tc => {
        // Role filter: AP = '4.', STA = '5.'
        const suffix = tc.split('-').pop();
        const isAp = suffix.startsWith('4.');
        const isSta = suffix.startsWith('5.');
        
        if (activeRole === 'AP' && !isAp) return;
        if (activeRole === 'STA' && !isSta) return;
        
        // Search filter
        if (searchVal && !tc.toLowerCase().includes(searchVal)) return;
        
        // Excluded list
        if (state.exclusions.includes(tc)) return;
        
        // Check testbeds inclusion/exclusion
        const details = state.xmlDetails[tc] || {};
        const tbListStr = details['TB_LIST'] || '';
        const tbs = tbListStr.split(',').map(t => t.trim()).filter(Boolean);
        
        // Exclude if testcase uses any testbed associated with disabled devices
        const usesDisabledDevice = tbs.some(tb => disabledDevices.has(tb));
        if (usesDisabledDevice) return;
        
        // Override Ignored testbeds
        const usesIgnoredTestbed = tbs.some(tb => state.overrideExcludeTestbeds.has(tb));
        if (usesIgnoredTestbed) return;
        
        // Override Included testbeds (if include list is not empty, test must use at least one included testbed)
        if (state.overrideIncludeTestbeds.size > 0) {
            const usesIncludedTestbed = tbs.some(tb => state.overrideIncludeTestbeds.has(tb));
            if (!usesIncludedTestbed) return;
        }
        
        // Override FAIL/NT cases only
        if (state.overrideFailNtOnly) {
            // Check latest status of this case
            const latestStatus = getTestCaseLatestStatus(tc);
            if (latestStatus === 'PASS') return;
        }
        
        count++;
        
        const row = document.createElement('div');
        row.className = 'checkbox-item-row';
        
        const isChecked = state.selectedTests.has(tc) ? 'checked' : '';
        
        row.innerHTML = `
            <label class="checkbox-container">
                <input type="checkbox" class="test-checkbox" data-test="${tc}" ${isChecked}>
                <span class="checkmark"></span>
                <span class="checkbox-item-label">${tc}</span>
            </label>
        `;
        container.appendChild(row);
        
        // Handle checkbox change
        row.querySelector('.test-checkbox').addEventListener('change', (e) => {
            if (e.target.checked) {
                state.selectedTests.add(tc);
            } else {
                state.selectedTests.delete(tc);
            }
            updateExecStats();
        });
    });
    
    document.getElementById('exec-suite-title').innerText = `Test Suite Selection (${count} Visible)`;
    
    if (count === 0) {
        container.innerHTML = '<div class="text-muted text-center py-5">No test cases match active filters.</div>';
    }
    
    updateExecStats(false);
}

function getTestCaseLatestStatus(tc) {
    // If analytics scanned results exist, check them
    // This requires a mock status check or scanning history
    // We can run a scan dynamically or keep a cached history
    return 'NT'; // Default placeholder until scanned
}

function resetExecStats() {
    state.execStats.pass = 0;
    state.execStats.fail = 0;
    document.getElementById('exec-stat-pass').innerText = 0;
    document.getElementById('exec-stat-fail').innerText = 0;
    
    document.getElementById('exec-progress-bar').style.width = '0%';
    document.getElementById('exec-progress-text').innerText = '0%';
    document.getElementById('exec-progress-bar').style.backgroundColor = 'var(--accent-color)';
}

function updateExecStats(resetResults = true) {
    state.execStats.total = state.selectedTests.size;
    document.getElementById('exec-stat-total').innerText = state.execStats.total;
    
    if (resetResults) {
        resetExecStats();
    }
    
    // Enable run button if any test selected
    document.getElementById('start-testing-btn').disabled = state.selectedTests.size === 0;
}

// Test role selector click
document.querySelectorAll('.role-selector .role-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        const parent = btn.closest('.role-selector');
        parent.querySelectorAll('.role-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        if (parent.id === 'xml-role-selector') {
            renderXmlTestCaseList();
        } else if (parent.id === 'analytics-role-selector') {
            // Handled on scan click
        } else {
            updateTestExecutionChecklist();
        }
    });
});

// Search input keyup
document.getElementById('exec-search').addEventListener('input', () => {
    updateTestExecutionChecklist();
});
document.getElementById('config-search').addEventListener('input', () => {
    renderConfigParameters();
});
document.getElementById('xml-search').addEventListener('input', () => {
    renderXmlTestCaseList();
});

// Select All / Clear Selection
document.getElementById('exec-select-all').addEventListener('click', () => {
    document.querySelectorAll('#exec-checkbox-list .test-checkbox').forEach(cb => {
        cb.checked = true;
        state.selectedTests.add(cb.getAttribute('data-test'));
    });
    updateExecStats();
});
document.getElementById('exec-clear-all').addEventListener('click', () => {
    document.querySelectorAll('#exec-checkbox-list .test-checkbox').forEach(cb => {
        cb.checked = false;
        state.selectedTests.delete(cb.getAttribute('data-test'));
    });
    updateExecStats();
});

// Advanced Overrides Modal opening
document.getElementById('exec-adv-btn').addEventListener('click', () => {
    openModal('adv-filter-modal');
});

// Exclusions Modal opening
document.getElementById('exec-exclusions-btn').addEventListener('click', () => {
    renderExclusionsModalCheckboxes();
    openModal('exclusions-modal');
});

function renderAdvancedFilterTestbeds() {
    const listInc = document.getElementById('adv-include-testbeds-list');
    const listExc = document.getElementById('adv-exclude-testbeds-list');
    
    listInc.innerHTML = '';
    listExc.innerHTML = '';
    
    // Find disabled devices in configuration (disabled only if all of its IP configurations are commented out)
    const allDeviceNames = new Set(state.devices.map(d => d.name.replace('_ap', '').replace('_sta', '')));
    const activeDeviceNames = new Set(state.devices.filter(d => d.enabled).map(d => d.name.replace('_ap', '').replace('_sta', '')));
    const disabledDevices = new Set(Array.from(allDeviceNames).filter(name => !activeDeviceNames.has(name)));
    
    state.xmlTestbeds.forEach(tb => {
        const isDeviceOff = disabledDevices.has(tb);
        const deviceSuffix = isDeviceOff ? ' (OFF)' : '';
        
        // Include List Checkbox
        const rowInc = document.createElement('div');
        rowInc.className = 'checkbox-item-row px-2';
        rowInc.innerHTML = `
            <label class="checkbox-container">
                <input type="checkbox" class="tb-include-switch" data-tb="${tb}" ${isDeviceOff ? 'disabled' : ''}>
                <span class="checkmark"></span>
                <span>${tb}${deviceSuffix}</span>
            </label>
        `;
        listInc.appendChild(rowInc);
        
        rowInc.querySelector('.tb-include-switch').addEventListener('change', (e) => {
            if (e.target.checked) state.overrideIncludeTestbeds.add(tb);
            else state.overrideIncludeTestbeds.delete(tb);
            updateTestExecutionChecklist();
        });
        
        // Exclude List Checkbox
        const rowExc = document.createElement('div');
        rowExc.className = 'checkbox-item-row px-2';
        const isChecked = state.overrideExcludeTestbeds.has(tb) || isDeviceOff ? 'checked' : '';
        rowExc.innerHTML = `
            <label class="checkbox-container">
                <input type="checkbox" class="tb-exclude-switch" data-tb="${tb}" ${isDeviceOff ? 'disabled' : ''} ${isChecked}>
                <span class="checkmark"></span>
                <span>${tb}${deviceSuffix}</span>
            </label>
        `;
        listExc.appendChild(rowExc);
        
        rowExc.querySelector('.tb-exclude-switch').addEventListener('change', (e) => {
            if (e.target.checked) state.overrideExcludeTestbeds.add(tb);
            else state.overrideExcludeTestbeds.delete(tb);
            updateTestExecutionChecklist();
        });
    });
}

document.getElementById('exec-notpass-only').addEventListener('change', (e) => {
    state.overrideFailNtOnly = e.target.checked;
    updateTestExecutionChecklist();
});

// ==================== Exclusions Registry Logic ====================

async function loadExclusionsRegistry() {
    const res = await apiFetch('/api/exclude');
    if (res && !res.error) {
        state.exclusions = res.exclusions || [];
    }
}

function renderExclusionsModalCheckboxes() {
    const container = document.getElementById('exclusions-checkbox-list');
    container.innerHTML = '';
    
    state.xmlTestCases.forEach(tc => {
        const row = document.createElement('div');
        row.className = 'checkbox-item-row';
        
        const isChecked = state.exclusions.includes(tc) ? 'checked' : '';
        
        row.innerHTML = `
            <label class="checkbox-container">
                <input type="checkbox" class="ex-registry-checkbox" data-test="${tc}" ${isChecked}>
                <span class="checkmark"></span>
                <span>${tc}</span>
            </label>
        `;
        container.appendChild(row);
    });
    
    // Select All
    document.getElementById('ex-select-all-btn').onclick = () => {
        container.querySelectorAll('.ex-registry-checkbox').forEach(cb => cb.checked = true);
    };
    // Clear All
    document.getElementById('ex-clear-all-btn').onclick = () => {
        container.querySelectorAll('.ex-registry-checkbox').forEach(cb => cb.checked = false);
    };
}

// Save Exclusions
document.getElementById('ex-save-btn').addEventListener('click', async () => {
    const list = [];
    document.querySelectorAll('#exclusions-checkbox-list .ex-registry-checkbox').forEach(cb => {
        if (cb.checked) {
            list.push(cb.getAttribute('data-test'));
        }
    });
    
    const res = await apiFetch('/api/exclude/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exclusions: list })
    });
    
    if (res && res.success) {
        state.exclusions = list;
        showNotification('Exclusion list registry saved successfully.', 'green');
        closeModal('exclusions-modal');
        updateTestExecutionChecklist(); // Reload visible list
    }
});

// Export exclusions list as JSON
document.getElementById('ex-export-btn').addEventListener('click', () => {
    const list = [];
    document.querySelectorAll('#exclusions-checkbox-list .ex-registry-checkbox').forEach(cb => {
        if (cb.checked) list.push(cb.getAttribute('data-test'));
    });
    
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(list, null, 4));
    const dlAnchorElem = document.createElement('a');
    dlAnchorElem.setAttribute("href",     dataStr     );
    dlAnchorElem.setAttribute("download", "wts_not_support.json");
    dlAnchorElem.click();
});

// Import exclusions list JSON file
document.getElementById('ex-import-btn').addEventListener('click', () => {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.json';
    fileInput.onchange = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = (evt) => {
            try {
                const list = JSON.parse(evt.target.result);
                if (Array.isArray(list)) {
                    document.querySelectorAll('#exclusions-checkbox-list .ex-registry-checkbox').forEach(cb => {
                        const tc = cb.getAttribute('data-test');
                        cb.checked = list.includes(tc);
                    });
                    showNotification('Imported exclusions successfully. Click Save to apply.', 'blue');
                } else {
                    showNotification('Invalid JSON file format!', 'red');
                }
            } catch (err) {
                showNotification('Error parsing exclusions file!', 'red');
            }
        };
        reader.readAsText(file);
    };
    fileInput.click();
});

// ==================== Test Runner Subprocess Logic ====================

let testRunEventSource = null;

document.getElementById('start-testing-btn').addEventListener('click', async () => {
    const tests = Array.from(state.selectedTests);
    if (tests.length === 0) return;
    
    // Prompt confirmation
    if (!confirm(`Start batch run of ${tests.length} tests?`)) {
        return;
    }
    
    // Reset Stats
    state.execStats.pass = 0;
    state.execStats.fail = 0;
    document.getElementById('exec-stat-pass').innerText = 0;
    document.getElementById('exec-stat-fail').innerText = 0;
    
    // Set progress bar
    document.getElementById('exec-progress-bar').style.width = '0%';
    document.getElementById('exec-progress-text').innerText = '0%';
    document.getElementById('exec-progress-bar').style.backgroundColor = 'var(--accent-color)';
    
    // Disable elements
    document.getElementById('start-testing-btn').disabled = true;
    document.getElementById('stop-testing-btn').disabled = false;
    document.getElementById('exec-checkbox-list').querySelectorAll('input').forEach(i => i.disabled = true);
    
    // Clear terminal log view
    const term = document.getElementById('terminal-output');
    term.innerHTML = '<div class="terminal-line system-msg">[System] Initiating testing process...</div>';
    
    // Call trigger endpoint
    const res = await apiFetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            configPath: state.configPath,
            tests: tests
        })
    });
    
    if (res && res.success) {
        // Start streaming output
        startConsoleOutputSSE();
    } else {
        term.innerHTML += `<div class="terminal-line fail-msg">[Error] ${res.error || 'Failed to start subprocess'}</div>`;
        document.getElementById('start-testing-btn').disabled = false;
        document.getElementById('stop-testing-btn').disabled = true;
        document.getElementById('exec-checkbox-list').querySelectorAll('input').forEach(i => i.disabled = false);
    }
});

function startConsoleOutputSSE() {
    const term = document.getElementById('terminal-output');
    
    if (testRunEventSource) {
        testRunEventSource.close();
    }
    
    testRunEventSource = new EventSource(`${API_BASE}/api/run/stream`);
    
    testRunEventSource.onmessage = (event) => {
        // Parse incoming lines
        const line = JSON.parse(event.data);
        appendTerminalLine(line);
    };
    
    testRunEventSource.addEventListener('finished', (event) => {
        appendTerminalLine('\n--- FINISHED ---', 'system-msg');
        testRunEventSource.close();
        testRunEventSource = null;
        
        // Re-enable actions
        document.getElementById('start-testing-btn').disabled = false;
        document.getElementById('stop-testing-btn').disabled = true;
        document.getElementById('exec-checkbox-list').querySelectorAll('input').forEach(i => i.disabled = false);
        
        // Scan results automatically to update latest status indicators
        scanAnalyticsData(true); // silent scan
        syncExecStatsFromLogs();
    });
    
    testRunEventSource.onerror = (err) => {
        console.error('SSE Stream Error:', err);
        // Do not display error since EventSource automatically tries to reconnect,
        // unless the stream ended.
    };
}

async function syncExecStatsFromLogs() {
    if (!state.configPath || state.selectedTests.size === 0) return;
    
    const role = document.querySelector('#analytics-role-selector .role-btn.active')?.getAttribute('data-role') || 'All';
    const url = `/api/results?role=${role}&currentRunOnly=true&path=${encodeURIComponent(state.configPath)}`;
    
    const res = await apiFetch(url);
    if (!res || !res.results) return;
    
    const selectedSet = state.selectedTests;
    let passCount = 0;
    let failCount = 0;
    
    res.results.forEach(item => {
        if (selectedSet.has(item.case)) {
            if (item.status === 'PASS') passCount++;
            else if (item.status === 'FAIL') failCount++;
        }
    });
    
    state.execStats.pass = passCount;
    state.execStats.fail = failCount;
    
    document.getElementById('exec-stat-pass').innerText = passCount;
    document.getElementById('exec-stat-fail').innerText = failCount;
    updateProgressMetrics();
}

function appendTerminalLine(text, customClass = '') {
    const term = document.getElementById('terminal-output');
    
    const line = document.createElement('div');
    line.className = 'terminal-line';
    
    // Parse formatting / classes based on ANSI color codes or content
    const PASS_RESULT_RE = /final test result\s*--->\s*pass/i;
    const FAIL_RESULT_RE = /final test result\s*--->\s*fail/i;

    if (customClass) {
        line.classList.add(customClass);
    } else if (PASS_RESULT_RE.test(text)) {
        // Definitive PASS result line
        line.classList.add('pass-msg');
        syncExecStatsFromLogs();
    } else if (FAIL_RESULT_RE.test(text)) {
        // Definitive FAIL result line
        line.classList.add('fail-msg');
        syncExecStatsFromLogs();
    } else if (text.includes('---')) {
        line.classList.add('header-msg');
    }
    
    // Also trigger log sync when WTS outputs 'Update Finished..' (end of single testcase)
    if (text.includes('Update Finished..') || text.includes('Stopping FTP server')) {
        syncExecStatsFromLogs();
    }
    
    line.innerText = text;
    term.appendChild(line);
    
    // Scroll to bottom
    term.scrollTop = term.scrollHeight;
}

function updateProgressMetrics() {
    const total = state.execStats.total;
    const completed = state.execStats.pass + state.execStats.fail;
    
    if (total === 0) return;
    
    const percentage = Math.min(100, Math.round((completed / total) * 100));
    
    document.getElementById('exec-progress-bar').style.width = `${percentage}%`;
    document.getElementById('exec-progress-text').innerText = `${percentage}%`;
    
    if (state.execStats.fail > 0) {
        // Red glow or color shift for failed runs
        document.getElementById('exec-progress-bar').style.backgroundColor = 'var(--status-fail)';
    } else {
        document.getElementById('exec-progress-bar').style.backgroundColor = 'var(--accent-color)';
    }
}

// Abort Tests Execution
document.getElementById('stop-testing-btn').addEventListener('click', async () => {
    const res = await apiFetch('/api/stop', { method: 'POST' });
    if (res && res.success) {
        appendTerminalLine('\n[System] ABORT REQUEST SENT.', 'fail-msg');
    }
});

// Clear/Copy Terminal Output
document.getElementById('clear-terminal-btn').addEventListener('click', () => {
    document.getElementById('terminal-output').innerHTML = '';
});

document.getElementById('copy-terminal-btn').addEventListener('click', () => {
    const lines = Array.from(document.querySelectorAll('#terminal-output .terminal-line'))
        .map(el => el.innerText)
        .join('\n');
        
    navigator.clipboard.writeText(lines).then(() => {
        showNotification('Console logs copied to clipboard.', 'green');
    }).catch(err => {
        showNotification('Failed to copy clipboard.', 'red');
    });
});

// ==================== Analytics Tab Logic ====================

// Click Scan
document.getElementById('scan-results-btn').addEventListener('click', () => {
    scanAnalyticsData();
});

async function scanAnalyticsData(silent = false) {
    if (!state.configPath) {
        showNotification('Please load an AllInitConfig first.', 'orange');
        return;
    }
    
    const role = document.querySelector('#analytics-role-selector .role-btn.active').getAttribute('data-role');
    const startDate = document.getElementById('analytics-date-input').value;
    
    // Store in session settings
    await apiFetch('/api/status', {
        method: 'GET' // wait, saving session is triggered by server during api/results call
    });
    
    const url = `/api/results?role=${role}&startDate=${startDate}&path=${encodeURIComponent(state.configPath)}`;
    
    if (!silent) showNotification('Scanning results in log folders...', 'blue');
    
    const res = await apiFetch(url);
    if (res && !res.error) {
        renderAnalyticsTable(res.results || []);
        if (!silent) showNotification('Scan completed.', 'green');
    }
}

function renderAnalyticsTable(results) {
    const hideNt = document.getElementById('hide-nt-checkbox').checked;
    const hideNs = document.getElementById('hide-excluded-checkbox').checked;
    const tbody = document.getElementById('analytics-table-body');
    tbody.innerHTML = '';
    
    let passCount = 0;
    let failCount = 0;
    let ntCount = 0;
    let nsCount = 0;
    let totalVisible = 0;
    
    results.forEach(item => {
        // Counts
        if (item.status === 'PASS') passCount++;
        else if (item.status === 'FAIL') failCount++;
        else if (item.status === 'NT') ntCount++;
        else if (item.status === 'Not Support') nsCount++;
        
        // Hide rules
        if (hideNt && item.status === 'NT') return;
        if (hideNs && item.status === 'Not Support') return;
        
        totalVisible++;
        
        const tr = document.createElement('tr');
        
        // Status pill styling
        const statusClass = item.status.toLowerCase().replace(' ', '');
        const logFolderDisplay = item.logFolder || '<span class="text-muted">-</span>';
        
        tr.innerHTML = `
            <td class="font-semibold">${item.case}</td>
            <td style="text-align: center;">
                <span class="status-pill ${statusClass}">${item.status}</span>
            </td>
            <td class="font-mono text-muted" style="font-size: 0.8rem;">${logFolderDisplay}</td>
            <td class="text-right">
                <button class="btn btn-secondary btn-xs icon-only view-history-btn" data-case="${item.case}" title="Execution History">
                    <i data-lucide="history"></i>
                </button>
            </td>
        `;
        
        tbody.appendChild(tr);
        
        // Wire up history button
        tr.querySelector('.view-history-btn').addEventListener('click', () => {
            openHistoryModal(item.case, item.history);
        });
    });
    
    document.getElementById('analytics-summary-badge').innerText = 
        `${passCount} PASS, ${failCount} FAIL, ${ntCount} NT, ${nsCount} Excluded`;
        
    if (totalVisible === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-5">No records matching search filters.</td></tr>`;
        document.getElementById('export-results-btn').disabled = true;
    } else {
        document.getElementById('export-results-btn').disabled = false;
    }
    
    lucide.createIcons();
    
    // Cache latest status mapping to execution checklist to screen FAIL/NT only
    // This allows execution tab overrides filter to query the results
}

function openHistoryModal(testCaseName, history) {
    document.getElementById('history-modal-title').innerText = `Historical Records: ${testCaseName}`;
    const tbody = document.getElementById('history-table-body');
    tbody.innerHTML = '';
    
    if (!history || history.length === 0) {
        tbody.innerHTML = `<tr><td colspan="2" class="text-center text-muted py-4">No historical runs recorded.</td></tr>`;
    } else {
        history.forEach(run => {
            const tr = document.createElement('tr');
            const statusClass = run.result.toLowerCase();
            tr.innerHTML = `
                <td style="text-align: center;">
                    <span class="status-pill ${statusClass}">${run.result}</span>
                </td>
                <td class="font-mono text-muted" style="font-size: 0.85rem;">${run.folder}</td>
            `;
            tbody.appendChild(tr);
        });
    }
    
    openModal('history-modal');
}

// Hide toggle change rules
document.getElementById('hide-nt-checkbox').addEventListener('change', () => scanAnalyticsData(true));
document.getElementById('hide-excluded-checkbox').addEventListener('change', () => scanAnalyticsData(true));

// Export CSV / Excel results
document.getElementById('export-results-btn').addEventListener('click', () => {
    // Generate CSV data directly in browser
    const rows = [
        ["Test Case Name", "Final Status", "Log Directory"]
    ];
    
    const tableRows = document.querySelectorAll('#analytics-table-body tr');
    tableRows.forEach(tr => {
        const nameNode = tr.querySelector('td:nth-child(1)');
        const statusNode = tr.querySelector('.status-pill');
        const folderNode = tr.querySelector('td:nth-child(3)');
        
        if (nameNode && statusNode && folderNode) {
            rows.push([
                nameNode.innerText.trim(),
                statusNode.innerText.trim(),
                folderNode.innerText.trim() === '-' ? '' : folderNode.innerText.trim()
            ]);
        }
    });
    
    // Format as CSV content
    const csvContent = "data:text/csv;charset=utf-8,\uFEFF" 
        + rows.map(e => e.map(val => `"${val.replace(/"/g, '""')}"`).join(",")).join("\n");
        
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "testing_report.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
});

// ==================== Logs Tab Logic ====================

async function loadLogsFolders() {
    const startDate = document.getElementById('log-date-filter').value;
    const res = await apiFetch(`/api/logs?startDate=${startDate}`);
    
    if (res && !res.error) {
        state.logFolders = res.folders || [];
        renderLogFoldersList();
    }
}

document.getElementById('refresh-logs-btn').addEventListener('click', () => {
    loadLogsFolders();
});

function renderLogFoldersList() {
    const container = document.getElementById('log-folders-list');
    container.innerHTML = '';
    
    // Hide bulk actions bar by default when list is re-rendered
    document.getElementById('folder-bulk-actions').style.display = 'none';
    
    if (state.logFolders.length === 0) {
        container.innerHTML = '<li class="list-group-item text-center text-muted py-5">No log folders found.</li>';
        return;
    }
    
    state.logFolders.forEach(folder => {
        const li = document.createElement('li');
        li.className = 'list-group-item';
        li.setAttribute('data-folder', folder);
        
        if (state.activeLogFolder === folder) {
            li.classList.add('active');
        }
        
        // Parse date from folder string (supports Month-DD-YYYY, YYYY-MM-DD, YYYY_MM_DD, YYYYMMDD)
        let dateLabel = '';
        const m1 = folder.match(/([A-Za-z]{3}-\d{1,2}-\d{4})/);
        if (m1) {
            dateLabel = m1[1];
        } else {
            const m2 = folder.match(/(\d{4}-\d{2}-\d{2})/);
            if (m2) {
                dateLabel = m2[1];
            } else {
                const m3 = folder.match(/(\d{4}_\d{2}_\d{2})/);
                if (m3) {
                    dateLabel = m3[1].replace(/_/g, '-');
                } else {
                    const m4 = folder.match(/(\d{8})/);
                    if (m4) {
                        const d = m4[1];
                        dateLabel = `${d.substring(0,4)}-${d.substring(4,6)}-${d.substring(6,8)}`;
                    }
                }
            }
        }
        
        li.innerHTML = `
            <div class="log-folder-item" style="display: flex; align-items: center; width: 100%; gap: 0.5rem;">
                <input type="checkbox" class="folder-select-checkbox" data-folder="${folder}" style="cursor: pointer; margin-right: 0.25rem;">
                <span class="log-folder-name" style="flex-grow: 1; display: flex; align-items: center; gap: 0.5rem;">
                    <i data-lucide="folder"></i>
                    <span>${folder}</span>
                </span>
                <span class="log-folder-meta">${dateLabel}</span>
            </div>
        `;
        
        container.appendChild(li);
        
        li.addEventListener('click', (e) => {
            // Select folder
            container.querySelectorAll('.list-group-item').forEach(el => el.classList.remove('active'));
            li.classList.add('active');
            state.activeLogFolder = folder;
            loadLogFilesList();
        });

        // Prevent event propagation for checkbox clicks
        const checkbox = li.querySelector('.folder-select-checkbox');
        checkbox.addEventListener('click', (e) => {
            e.stopPropagation();
            updateFolderBulkActionsVisibility();
        });
    });
    
    lucide.createIcons();
}

function updateFolderBulkActionsVisibility() {
    const selected = getSelectedFolders();
    const actions = document.getElementById('folder-bulk-actions');
    if (selected.length > 0) {
        actions.style.display = 'flex';
    } else {
        actions.style.display = 'none';
    }
}

function getSelectedFolders() {
    const checked = [];
    document.querySelectorAll('#log-folders-list .folder-select-checkbox').forEach(cb => {
        if (cb.checked) {
            checked.push(cb.getAttribute('data-folder'));
        }
    });
    return checked;
}

async function loadLogFilesList() {
    if (!state.activeLogFolder) return;
    
    const res = await apiFetch(`/api/logs/files?folder=${encodeURIComponent(state.activeLogFolder)}`);
    if (res && !res.error) {
        state.logFiles = res.files || [];
        renderLogFilesTable();
    }
}

function renderLogFilesTable() {
    const tbody = document.getElementById('log-files-table-body');
    tbody.innerHTML = '';
    
    if (state.logFiles.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted py-5">No log/pcap files found in this directory.</td></tr>`;
        return;
    }
    
    state.logFiles.forEach(file => {
        const tr = document.createElement('tr');
        
        const isPcap = file.name.toLowerCase().includes('pcap');
        const iconName = isPcap ? 'binary' : 'file-text';
        const openTitle = isPcap ? 'Open in Wireshark (Local)' : 'Preview Log';
        
        tr.innerHTML = `
            <td class="font-semibold">
                <div class="flex-row gap-2" style="display:inline-flex; align-items:center;">
                    <i data-lucide="${iconName}" style="width: 16px; height: 16px; color: var(--text-secondary);"></i>
                    <span>${file.name}</span>
                </div>
            </td>
            <td class="text-muted font-mono" style="font-size: 0.8rem;">${file.size}</td>
            <td class="text-right">
                <button class="btn btn-secondary btn-xs open-file-btn" data-file="${file.name}" title="${openTitle}">
                    <i data-lucide="external-link"></i>
                </button>
                <button class="btn btn-danger btn-xs icon-only delete-file-btn ml-1" data-file="${file.name}" title="Delete file">
                    <i data-lucide="trash-2"></i>
                </button>
            </td>
        `;
        
        tbody.appendChild(tr);
        
        // Double click line previews or downloads
        tr.addEventListener('dblclick', () => {
            openLogFileDetails(file.name);
        });
        
        // Wire buttons
        tr.querySelector('.open-file-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            openLogFileDetails(file.name);
        });
        
        tr.querySelector('.delete-file-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteLogFile(file.name);
        });
    });
    
    lucide.createIcons();
}

async function openLogFileDetails(fileName) {
    const isPcap = fileName.toLowerCase().includes('pcap');
    
    if (isPcap) {
        // For pcap files, trigger Wireshark locally via backend call
        showNotification(`Launching Wireshark for ${fileName}...`, 'blue');
        const res = await apiFetch('/api/logs/open-external', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder: state.activeLogFolder,
                file: fileName
            })
        });
        if (res && res.error) {
            // If local launch fails, fallback to download
            window.open(`/api/logs/view?folder=${encodeURIComponent(state.activeLogFolder)}&file=${encodeURIComponent(fileName)}`);
        }
    } else {
        // For log text files, show beautiful preview modal inline
        const url = `/api/logs/view?folder=${encodeURIComponent(state.activeLogFolder)}&file=${encodeURIComponent(fileName)}`;
        const text = await fetch(url).then(res => res.text());
        
        document.getElementById('log-view-title').innerText = `Log Preview: ${state.activeLogFolder}/${fileName}`;
        document.getElementById('log-view-content').innerText = text;
        
        // Reset maximized state when opening
        const logModal = document.getElementById('log-view-modal');
        logModal.classList.remove('maximized');
        const maxBtn = document.getElementById('log-view-maximize-btn');
        if (maxBtn) {
            maxBtn.innerHTML = '<i data-lucide="maximize" class="icon-xs"></i>';
        }
        
        // Apply wrap text state
        const storedWrap = localStorage.getItem('log_wrap_text') === 'true';
        if (storedWrap) {
            document.getElementById('log-view-content').classList.add('wrap-text');
        } else {
            document.getElementById('log-view-content').classList.remove('wrap-text');
        }
        
        // Setup copy button
        document.getElementById('log-view-copy-btn').onclick = () => {
            navigator.clipboard.writeText(text).then(() => {
                showNotification('Logs copied to clipboard.', 'green');
            });
        };
        
        openModal('log-view-modal');
        lucide.createIcons();
    }
}

async function deleteLogFile(fileName) {
    if (!confirm(`Delete log file: ${fileName}?`)) return;
    
    const res = await apiFetch('/api/logs/delete-file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            folder: state.activeLogFolder,
            file: fileName
        })
    });
    
    if (res && res.success) {
        showNotification('File deleted.', 'green');
        await loadLogFilesList();
    }
}

// Folder actions zip/delete (could add context menu or bulk select in UI)
// For simplicity, let's implement basic actions. We can zip or delete folders.

// ==================== XML MasterInfo Tab Logic ====================

function renderXmlTestCaseList() {
    const searchVal = document.getElementById('xml-search').value.toLowerCase();
    const activeRole = document.querySelector('#xml-role-selector .role-btn.active').getAttribute('data-role');
    const container = document.getElementById('xml-cases-list');
    container.innerHTML = '';
    
    const filtered = state.xmlTestCases.filter(tc => {
        // Role filter: AP = '4.', STA = '5.'
        const suffix = tc.split('-').pop();
        const isAp = suffix.startsWith('4.');
        const isSta = suffix.startsWith('5.');
        
        if (activeRole === 'AP' && !isAp) return false;
        if (activeRole === 'STA' && !isSta) return false;
        
        // Search
        if (searchVal && !tc.toLowerCase().includes(searchVal)) return false;
        
        return true;
    });
    
    if (filtered.length === 0) {
        container.innerHTML = '<li class="list-group-item text-center text-muted py-5">No matching test definitions found.</li>';
        return;
    }
    
    filtered.forEach(tc => {
        const li = document.createElement('li');
        li.className = 'list-group-item';
        li.innerText = tc;
        
        container.appendChild(li);
        
        li.addEventListener('click', () => {
            container.querySelectorAll('.list-group-item').forEach(el => el.classList.remove('active'));
            li.classList.add('active');
            renderXmlDetails(tc);
        });
    });
}

function renderXmlDetails(testCaseName) {
    const tbody = document.getElementById('xml-details-body');
    tbody.innerHTML = '';
    
    const details = state.xmlDetails[testCaseName] || {};
    const keys = Object.keys(details);
    
    if (keys.length === 0) {
        tbody.innerHTML = `<tr><td colspan="2" class="text-center text-muted py-4">No detailed parameters for this test case.</td></tr>`;
        return;
    }
    
    keys.forEach(k => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="font-semibold" style="width: 250px;">${k}</td>
            <td class="font-mono text-muted" style="font-size: 0.85rem;">${details[k]}</td>
        `;
        tbody.appendChild(tr);
    });
}

// ==================== TMS Config Tab Logic ====================

async function loadTmsConfig() {
    const res = await apiFetch('/api/tms-config');
    if (res && !res.error) {
        state.tmsParams = res.parameters || [];
        state.tmsUploadEnabled = res.tmsUploadEnabled || false;
        
        document.getElementById('tms-upload-toggle').checked = state.tmsUploadEnabled;
        renderTmsTable();
    }
}

function renderTmsTable() {
    const tbody = document.getElementById('tms-table-body');
    tbody.innerHTML = '';
    
    const filtered = state.tmsParams.filter(p => p.type === 'kv_pair');
    
    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted py-4">No configuration values found in TmsClient.conf.</td></tr>`;
        return;
    }
    
    filtered.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="font-semibold">${p.key}</td>
            <td class="font-mono text-muted value-cell" style="font-size: 0.85rem;" title="${p.value}">${p.value}</td>
            <td class="text-right">
                <button class="action-icon-btn edit-tms-btn" data-index="${p.index}" title="Edit Parameter">
                    <i data-lucide="edit-3"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
        
        tr.querySelector('.edit-tms-btn').onclick = () => {
            openTmsEditor(p.index);
        };
    });
    
    lucide.createIcons();
}

let currentEditingTmsIndex = null;

function openTmsEditor(index) {
    currentEditingTmsIndex = index;
    const param = state.tmsParams.find(p => p.index === index);
    if (!param) return;
    
    // We can reuse the value editing modal
    document.getElementById('edit-value-label').innerText = `Update Parameter: ${param.key}`;
    document.getElementById('edit-value-input').value = param.value;
    
    // Override save button handler temporarily
    document.getElementById('save-value-btn').onclick = () => {
        const val = document.getElementById('edit-value-input').value;
        state.tmsParams.find(p => p.index === currentEditingTmsIndex).value = val;
        renderTmsTable();
        closeModal('edit-value-modal');
        showNotification('Parameter updated locally. Click Save Config to save to file.', 'blue');
        
        // Restore default handler
        restoreDefaultSaveHandler();
    };
    
    openModal('edit-value-modal');
}

function restoreDefaultSaveHandler() {
    document.getElementById('save-value-btn').onclick = () => {
        if (currentEditingIndex === null) return;
        const val = document.getElementById('edit-value-input').value;
        state.configParams.find(p => p.index === currentEditingIndex).value = val;
        renderConfigParameters();
        closeModal('edit-value-modal');
        showNotification('Parameter updated locally. Commit changes to save to file.', 'blue');
    };
}

// Toggle upload in TMS Config
document.getElementById('tms-upload-toggle').addEventListener('change', async (e) => {
    const checked = e.target.checked;
    const res = await apiFetch('/api/tms-config/toggle-upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: checked })
    });
    if (res && res.success) {
        showNotification(`TMS Upload Sync ${checked ? 'enabled' : 'disabled'}.`, 'green');
        await loadTmsConfig();
    } else {
        e.target.checked = !checked;
    }
});

document.getElementById('reload-tms-btn').addEventListener('click', async () => {
    await loadTmsConfig();
    showNotification('TMS Configuration reloaded.', 'blue');
});

document.getElementById('save-tms-btn').addEventListener('click', async () => {
    const res = await apiFetch('/api/tms-config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            parameters: state.tmsParams.map(p => ({
                index: p.index,
                value: p.value
            }))
        })
    });
    if (res && res.success) {
        showNotification('TMS config saved successfully!', 'green');
        await loadTmsConfig();
    }
});

// ==================== TMS Portal Link Logic ====================

function openTmsPortal() {
    let eventId = '';
    if (state.tmsParams && state.tmsParams.length > 0) {
        const param = state.tmsParams.find(p => p.key === 'TmsEventId');
        if (param && param.value) {
            eventId = param.value.trim();
        }
    }
    
    if (eventId && eventId !== 'XXXXX') {
        navigator.clipboard.writeText(eventId).then(() => {
            showNotification(`Copied Event ID (${eventId}) to clipboard! Opening TMS Portal...`, 'green');
        }).catch(err => {
            console.error('Failed to copy text: ', err);
            showNotification(`Opening TMS Portal... (Event ID: ${eventId})`, 'blue');
        });
    } else {
        showNotification('Opening TMS Portal...', 'blue');
    }
    
    window.open('https://tms.wi-fi.org/', '_blank');
}

document.getElementById('open-tms-portal-btn').addEventListener('click', openTmsPortal);
document.getElementById('analytics-tms-portal-btn').addEventListener('click', openTmsPortal);


// ==================== User Guide Logic ====================

async function loadUserGuide() {
    const markdownContent = document.getElementById('help-markdown-content');
    
    // Fetch manual file (README.md) content
    const res = await fetch('/api/logs/view?folder=.&file=README.md');
    if (res.ok) {
        const text = await res.text();
        
        // Simple Markdown parser
        markdownContent.innerHTML = parseMarkdownToHTML(text);
    } else {
        markdownContent.innerHTML = '<h2>WTS GUI User Guide</h2><p class="text-muted">Documentation file README.md not found in tool workspace.</p>';
    }
}

// Micro Markdown Parser (only headers, bullets, code blocks, alerts, and bold text)
function parseMarkdownToHTML(md) {
    let html = md;
    
    // Normalize line endings
    html = html.replace(/\r\n/g, '\n');
    
    // Parse Alerts
    html = html.replace(/>\s*\[!(IMPORTANT|NOTE|WARNING|CAUTION)\]\n>\s*([^\n]+)/g, (match, type, content) => {
        const classMap = {
            NOTE: 'note',
            IMPORTANT: 'important',
            WARNING: 'warning',
            CAUTION: 'caution'
        };
        return `<div class="alert-block ${classMap[type] || 'note'}"><strong>${type}:</strong> ${content}</div>`;
    });
    
    // Headers
    html = html.replace(/^# (.*?)$/gm, '<h2>$1</h2>');
    html = html.replace(/^## (.*?)$/gm, '<h3>$1</h3>');
    html = html.replace(/^### (.*?)$/gm, '<h4>$1</h4>');
    
    // Code blocks
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Bullet points
    html = html.replace(/^\*\s+(.*?)$/gm, '<li>$1</li>');
    html = html.replace(/^\-\s+(.*?)$/gm, '<li>$1</li>');
    // Group bullets into list block
    html = html.replace(/((?:<li>.*?<\/li>\s*)+)/gs, '<ul>$1</ul>');
    
    // Number lists
    html = html.replace(/^\d+\.\s+(.*?)$/gm, '<li>$1</li>');
    html = html.replace(/((?:<li>.*?<\/li>\s*)+)/gs, '<ul>$1</ul>'); // simplified
    
    // Paragraphs
    html = html.replace(/([^\n]+)\n\n/g, '<p>$1</p>');
    
    return html;
}

// Add CSS for alerts dynamically
const alertsStyle = document.createElement("style");
alertsStyle.innerText = `
.alert-block {
    padding: 1rem;
    border-radius: 6px;
    margin: 1rem 0;
    font-size: 0.9rem;
    line-height: 1.5;
}
.alert-block.note { background-color: rgba(56, 189, 248, 0.1); border-left: 4px solid var(--accent-color); }
.alert-block.important { background-color: rgba(99, 102, 241, 0.1); border-left: 4px solid var(--status-ns); }
.alert-block.warning { background-color: rgba(245, 158, 11, 0.1); border-left: 4px solid var(--status-nt); }
.alert-block.caution { background-color: rgba(239, 68, 68, 0.1); border-left: 4px solid var(--status-fail); }
.flex-row { display: flex; align-items: center; }
`;
document.head.appendChild(alertsStyle);

// ==================== Global Helper Events ====================

// Web-native File Browser State
state.fsBrowserCurrentPath = '';
state.fsBrowserSelectedFile = '';

// Load directory contents for File Browser
async function loadFsDirectory(path) {
    const res = await apiFetch(`/api/fs/list?path=${encodeURIComponent(path)}`);
    if (res && !res.error) {
        state.fsBrowserCurrentPath = res.currentPath || '';
        document.getElementById('fs-path-input').value = state.fsBrowserCurrentPath;
        document.getElementById('fs-selected-file-display').innerText = 'No file selected';
        document.getElementById('fs-confirm-btn').disabled = true;
        state.fsBrowserSelectedFile = '';
        
        renderFsEntries(res.drives, res.entries);
    }
}

// Render entries inside File Browser modal
function renderFsEntries(drives, entries) {
    const list = document.getElementById('fs-entries-list');
    list.innerHTML = '';
    
    // Render drives (Windows only)
    if (drives && drives.length > 0) {
        drives.forEach(drv => {
            const li = document.createElement('li');
            li.className = 'list-group-item fs-entry-item';
            li.innerHTML = `
                <div class="fs-entry-name folder">
                    <i data-lucide="hard-drive"></i>
                    <span>Disk Drive (${drv})</span>
                </div>
            `;
            list.appendChild(li);
            
            li.onclick = () => {
                list.querySelectorAll('.fs-entry-item').forEach(el => el.classList.remove('selected'));
                li.classList.add('selected');
                state.fsBrowserSelectedFile = '';
                document.getElementById('fs-selected-file-display').innerText = `Selected Drive: ${drv}`;
            };
            
            li.ondblclick = () => {
                loadFsDirectory(drv);
            };
        });
    }
    
    // Render folders and files
    if (entries && entries.length > 0) {
        entries.forEach(e => {
            const li = document.createElement('li');
            li.className = 'list-group-item fs-entry-item';
            
            const iconName = e.isDir ? 'folder' : 'file';
            const typeClass = e.isDir ? 'folder' : 'file';
            
            li.innerHTML = `
                <div class="fs-entry-name ${typeClass}">
                    <i data-lucide="${iconName}"></i>
                    <span>${e.name}</span>
                </div>
            `;
            list.appendChild(li);
            
            const isWin = state.fsBrowserCurrentPath.includes('\\') || window.navigator.platform.includes('Win');
            const separator = isWin ? '\\' : '/';
            let fullPath = state.fsBrowserCurrentPath;
            if (!fullPath.endsWith(separator)) {
                fullPath += separator;
            }
            fullPath += e.name;
            
            li.onclick = () => {
                list.querySelectorAll('.fs-entry-item').forEach(el => el.classList.remove('selected'));
                li.classList.add('selected');
                
                if (e.isDir) {
                    state.fsBrowserSelectedFile = '';
                    document.getElementById('fs-selected-file-display').innerText = `Selected Folder: ${e.name}`;
                    document.getElementById('fs-confirm-btn').disabled = true;
                } else {
                    state.fsBrowserSelectedFile = fullPath;
                    document.getElementById('fs-selected-file-display').innerText = `Selected File: ${e.name}`;
                    document.getElementById('fs-confirm-btn').disabled = false;
                }
            };
            
            li.ondblclick = () => {
                if (e.isDir) {
                    loadFsDirectory(fullPath);
                } else {
                    state.fsBrowserSelectedFile = fullPath;
                    confirmFsFileSelection();
                }
            };
        });
    }
    
    if ((!drives || drives.length === 0) && (!entries || entries.length === 0)) {
        list.innerHTML = '<li class="list-group-item text-center text-muted py-4">Folder is empty.</li>';
    }
    
    lucide.createIcons();
}

function confirmFsFileSelection() {
    if (!state.fsBrowserSelectedFile) return;
    
    state.configPath = state.fsBrowserSelectedFile;
    document.getElementById('current-config-path').innerText = state.configPath;
    document.getElementById('current-config-path').title = state.configPath;
    
    closeModal('file-browser-modal');
    showNotification(`Selected config path: ${state.configPath}`, 'green');
    
    loadConfigDetails();
    loadXmlSpecs();
}

// Bind custom file browser modal events
document.getElementById('browse-config-btn').addEventListener('click', () => {
    let startDir = '';
    if (state.configPath) {
        const isWin = state.configPath.includes('\\');
        const separator = isWin ? '\\' : '/';
        startDir = state.configPath.substring(0, state.configPath.lastIndexOf(separator));
    }
    loadFsDirectory(startDir);
    openModal('file-browser-modal');
});

// FS Go Up
document.getElementById('fs-go-up-btn').addEventListener('click', () => {
    if (!state.fsBrowserCurrentPath) return;
    const separator = state.fsBrowserCurrentPath.includes('\\') ? '\\' : '/';
    const parts = state.fsBrowserCurrentPath.split(separator);
    
    if (parts.length > 1) {
        parts.pop();
        let parent = parts.join(separator);
        if (parent.endsWith(':')) {
            parent += '\\';
        }
        if (!parent) {
            loadFsDirectory('');
        } else {
            loadFsDirectory(parent);
        }
    } else {
        loadFsDirectory('');
    }
});

// FS path input manual Navigation
document.getElementById('fs-go-btn').addEventListener('click', () => {
    const val = document.getElementById('fs-path-input').value.trim();
    loadFsDirectory(val);
});

document.getElementById('fs-path-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        const val = document.getElementById('fs-path-input').value.trim();
        loadFsDirectory(val);
    }
});

// Confirm selection
document.getElementById('fs-confirm-btn').addEventListener('click', () => {
    confirmFsFileSelection();
});

// Bulk Actions for Log Folders (Zip / Delete)
document.getElementById('bulk-zip-folders').addEventListener('click', async () => {
    const folders = getSelectedFolders();
    if (folders.length === 0) return;
    
    showNotification(`Compressing ${folders.length} folders...`, 'blue');
    
    const res = await apiFetch('/api/logs/zip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            folders: folders,
            outputName: `logs_export_${new Date().toISOString().split('T')[0]}.zip`
        })
    });
    
    if (res && res.success && res.downloadUrl) {
        showNotification('Logs compressed successfully! Downloading...', 'green');
        
        // Trigger browser download by opening the download link
        window.open(res.downloadUrl, '_blank');
        
        // Clear checkboxes
        document.querySelectorAll('#log-folders-list .folder-select-checkbox').forEach(cb => cb.checked = false);
        updateFolderBulkActionsVisibility();
    } else {
        showNotification(res.error || 'Failed to compress log folders.', 'red');
    }
});

document.getElementById('bulk-delete-folders').addEventListener('click', async () => {
    const folders = getSelectedFolders();
    if (folders.length === 0) return;
    
    if (!confirm(`Delete all ${folders.length} selected log directories? This cannot be undone.`)) {
        return;
    }
    
    showNotification(`Deleting ${folders.length} folders...`, 'blue');
    
    const res = await apiFetch('/api/logs/delete-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folders: folders })
    });
    
    if (res && res.success) {
        showNotification('Selected folders deleted.', 'green');
        
        // Reload folder list
        await loadLogsFolders();
        updateFolderBulkActionsVisibility();
        
        // Clear active files list if active folder was deleted
        if (folders.includes(state.activeLogFolder)) {
            state.activeLogFolder = '';
            document.getElementById('log-files-table-body').innerHTML = `<tr><td colspan="3" class="text-center text-muted py-5">Please select a folder.</td></tr>`;
        }
    } else {
        showNotification(res.error || 'Failed to delete folders.', 'red');
    }
});

// Log Preview Line Wrap Toggle
const wrapBtn = document.getElementById('log-view-wrap-btn');
const logContent = document.getElementById('log-view-content');

if (wrapBtn && logContent) {
    // Load preference
    const storedWrap = localStorage.getItem('log_wrap_text') === 'true';
    wrapBtn.checked = storedWrap;
    if (storedWrap) {
        logContent.classList.add('wrap-text');
    }
    
    wrapBtn.addEventListener('change', (e) => {
        const checked = e.target.checked;
        if (checked) {
            logContent.classList.add('wrap-text');
        } else {
            logContent.classList.remove('wrap-text');
        }
        localStorage.setItem('log_wrap_text', checked);
    });
}

// Log Preview Maximize Toggle
const maxBtn = document.getElementById('log-view-maximize-btn');
const logModal = document.getElementById('log-view-modal');

if (maxBtn && logModal) {
    maxBtn.addEventListener('click', () => {
        const isMax = logModal.classList.toggle('maximized');
        maxBtn.innerHTML = isMax 
            ? '<i data-lucide="minimize" class="icon-xs"></i>' 
            : '<i data-lucide="maximize" class="icon-xs"></i>';
        lucide.createIcons();
    });
}

// Start periodic heartbeat ping every 10 seconds to keep server alive
setInterval(() => {
    fetch('/api/status').catch(err => console.debug("Heartbeat ping offline"));
}, 10000);
