/* ================= Common JS - Shared Functions ================= */
// common.js — Shared functions and configuration for all Pretty LLDB visualizers.

// ----- Tokyo Night Color Palette ----- //
const colorPalette = {
  nodeDefault: '#7aa2f7',
  nodeBorder: '#565f89',
  nodeSelected: '#bb9af7',
  nodeSelectedBorder: '#9d7cd8',
  nodeHighlighted: '#e0af68',
  nodeHighlightedBorder: '#c49a61',
  nodeAnimated: '#9ece6a',
  nodeAnimatedBorder: '#73a84c',
  nodeSearchResult: '#f7768e',
  nodeSearchBorder: '#e06b83',
  nodeHover: '#9ece6a',

  edgeDefault: '#565f89',
  edgeSelected: '#bb9af7',
  edgeHighlighted: '#e0af68',

  textDefault: '#ffffffff',

  blue: '#7aa2f7',
  purple: '#bb9af7',
  red: '#f7768e',
  orange: '#e0af68',
  green: '#9ece6a',

  dark: { text: '#c0caf5', surface: '#24283b', border: '#414868' },
  light: { text: '#1a1b26', surface: '#c0caf5', border: '#a9b1d6' },
};

// ----- SVG Icons ----- //
const svgIcons = {
  theme: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`,
  expand: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="12" y1="18" x2="12" y2="12"></line><line x1="9" y1="15" x2="15" y2="15"></line></svg>`,
  collapse: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="9" y1="15" x2="15" y2="15"></line></svg>`,
  center: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"></circle><line x1="12" y1="1" x2="12" y2="4"></line><line x1="12" y1="20" x2="12" y2="23"></line><line x1="4" y1="12" x2="1" y2="12"></line><line x1="23" y1="12" x2="20" y2="12"></line><line x1="19.07" y1="4.93" x2="16.95" y2="7.05"></line><line x1="7.05" y1="16.95" x2="4.93" y2="19.07"></line><line x1="19.07" y1="19.07" x2="16.95" y2="16.95"></line><line x1="7.05" y1="7.05" x2="4.93" y2="4.93"></line></svg>`,
  clear: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 4H8l-7 8 7 8h13a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"></path><line x1="18" y1="9" x2="12" y2="15"></line><line x1="12" y1="9" x2="18" y2="15"></line></svg>`,
  png: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>`,
  json: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>`,
  play: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`,
  pause: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>`,
  stop: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16"></rect></svg>`,
  step: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><polygon points="5 4 15 12 5 20 5 4"></polygon><line x1="19" y1="5" x2="19" y2="19"></line></svg>`,
};

/* ==================== STRUCTURED UI HELPERS ===================== */

/**
 * Returns an HTML string for one stat row: key on the left, value on the right.
 * @param {string} key   - Label for the row.
 * @param {string|number} value - Value to display (may contain inner HTML).
 */
function createStatRow(key, value) {
  return `<div class="stat-row"><span class="stat-key">${key}</span><span class="stat-value">${value}</span></div>`;
}

/**
 * Returns an HTML string for a monospace address chip.
 * @param {string} address - The address string to display.
 */
function createAddressChip(address) {
  return `<span class="address-mono">${address}</span>`;
}

/**
 * Returns an HTML string for a connected-node chip entry.
 * @param {string} arrow   - Direction indicator (e.g. "↑", "↓", "→").
 * @param {string} label   - Node label text.
 * @param {string} [extra] - Optional extra HTML appended after the label.
 */
function createNodeChip(arrow, label, extra) {
  const extraHtml = extra ? ` ${extra}` : '';
  return `<div class="connected-node-item"><span class="rel-arrow">${arrow}</span>${label}${extraHtml}</div>`;
}

/* ======================== ICON INJECTION ======================== */

/**
 * Injects SVG icons into buttons that have a matching `id="btn-<key>"`.
 */
function applyIcons() {
  for (const [key, svg] of Object.entries(svgIcons)) {
    const button = document.getElementById(`btn-${key}`);
    if (button) {
      const originalText = button.textContent.trim();
      button.innerHTML = `<span class="button-icon">${svg}</span> ${originalText}`;
    }
  }
}

/* ========================= THEME TOGGLE ========================= */

function toggleTheme() {
  const body = document.body;
  body.classList.toggle('light-theme');
  const isLight = body.classList.contains('light-theme');
  try {
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
  } catch (e) {
    console.warn('localStorage not available for theme persistence');
  }
  updateThemeButton(isLight);
}

function updateThemeButton(isLight) {
  const btn = document.getElementById('theme-toggle-btn');
  if (btn) {
    const themeName = isLight ? 'Dark' : 'Light';
    btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;
    btn.title = `Switch to ${themeName} theme`;
  }
}

(function () {
  let savedTheme = 'dark';
  try {
    savedTheme = localStorage.getItem('theme') || 'dark';
  } catch (e) {
    console.warn('localStorage not available for theme persistence');
  }
  const isLight = savedTheme === 'light';
  if (isLight) document.body.classList.add('light-theme');

  document.addEventListener('DOMContentLoaded', () => {
    updateThemeButton(isLight);
    applyIcons();
  });
})();

/* ====================== INFO PANEL TOGGLE ======================= */

function toggleInfoBox() {
  const infoBox = document.getElementById('info-box');
  const toggleBtn = document.getElementById('toggle-info-btn');
  if (!infoBox || !toggleBtn) return;

  infoBox.classList.toggle('hidden');
  if (infoBox.classList.contains('hidden')) {
    toggleBtn.classList.remove('info-visible');
    toggleBtn.innerHTML = '⚙';
    toggleBtn.title = 'Show Info Panel';
  } else {
    toggleBtn.classList.add('info-visible');
    toggleBtn.innerHTML = '✕';
    toggleBtn.title = 'Hide Info Panel';
  }
}

/* ======================= EXPORT FUNCTIONS ======================= */

function exportPNG() {
  if (!network || !network.canvas || !network.canvas.frame) {
    console.error('Network canvas not available for PNG export');
    return;
  }
  const canvas = network.canvas.frame.canvas;
  const link = document.createElement('a');
  link.download = 'visualization.png';
  link.href = canvas.toDataURL();
  link.click();
}

function exportJSON(dataToExport, filename = 'data.json') {
  const blob = new Blob([JSON.stringify(dataToExport, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/* ================= VIS.JS INTERACTIONS HELPERS ================== */

function centerView() {
  if (network) network.fit();
}

function clearSelection() {
  if (network) {
    network.unselectAll();
    resetColors();
    hideNodeInfo();
  }
}

function hideNodeInfo() {
  const nodeInfo = document.getElementById('node-info');
  if (nodeInfo) nodeInfo.style.display = 'none';
}

function resetColors() {
  if (!nodes || !edges) return;
  const nodeUpdates = nodes.getIds().map((id) => ({
    id,
    color: {
      background: colorPalette.nodeDefault,
      border: colorPalette.nodeBorder,
    },
  }));
  if (nodeUpdates.length > 0) nodes.update(nodeUpdates);

  const edgeUpdates = edges.getIds().map((id) => ({
    id,
    color: { color: colorPalette.edgeDefault },
  }));
  if (edgeUpdates.length > 0) edges.update(edgeUpdates);
}

function clearHighlights() {
  resetColors();
  const searchInput = document.getElementById('search-input');
  if (searchInput) searchInput.value = '';
}

function searchNodes(query) {
  if (!nodes) return;
  resetColors();
  if (!query.trim()) return;

  const matchingNodes = nodes.get({
    filter: (node) =>
      String(node.label).toLowerCase().includes(query.toLowerCase()) ||
      (node.title && String(node.title).toLowerCase().includes(query.toLowerCase())),
  });

  if (matchingNodes.length > 0) {
    nodes.update(
      matchingNodes.map((node) => ({
        id: node.id,
        color: {
          background: colorPalette.nodeSearchResult,
          border: colorPalette.nodeSearchBorder,
        },
      }))
    );
  }
}

function handleNodeHover(params) {
  if (!params.node || !nodes) return;
  const nodeData = nodes.get(params.node);
  if (!nodeData) return;
  const title = nodeData.title || `Label: ${nodeData.label}`;
  const el = document.getElementById('mynetwork');
  if (el) el.title = `${title}\nClick for details`;
}

function handleNodeBlur() {
  const el = document.getElementById('mynetwork');
  if (el) el.title = '';
}

/* ======================= INITIAL UI STATE ======================= */

document.addEventListener('DOMContentLoaded', () => {
  const infoBox = document.getElementById('info-box');
  const toggleBtn = document.getElementById('toggle-info-btn');
  if (infoBox && toggleBtn) {
    infoBox.classList.add('hidden');
    toggleBtn.classList.remove('info-visible');
    toggleBtn.innerHTML = '⚙';
    toggleBtn.title = 'Show Info Panel';
  }
});
