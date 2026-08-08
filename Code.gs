/**
 * GNF CAP Board — Google Sheets backend
 * ---------------------------------------------------------------------------
 * Stores the board's progress in a Google Sheet so every manager sees the same
 * numbers, and keeps a flat, readable CAP_PROGRESS tab that can be filtered,
 * pivoted or exported like any normal spreadsheet.
 *
 * SETUP
 *  1. Create a Google Sheet. Extensions ▸ Apps Script. Paste this file in.
 *  2. Change SHARED_KEY below to something only your team knows.
 *  3. Deploy ▸ New deployment ▸ Web app.
 *       Execute as: Me      Who has access: Anyone
 *  4. Copy the /exec URL. Paste it, with the same key, into the board's
 *     Reports ▸ Google Sheets sync panel, then press "Connect & pull".
 *
 * Re-deploy (Manage deployments ▸ edit ▸ New version) after any edit here.
 * ---------------------------------------------------------------------------
 */

var SHARED_KEY = 'gnf-cap-2026';       // <— change this
var BLOB_SHEET = 'CAP_STATE';          // machine-readable store
var FLAT_SHEET = 'CAP_PROGRESS';       // human-readable mirror
var ROLE_SHEET = 'ORSVAI';             // accountability mirror
var LOG_SHEET  = 'CHANGE_LOG';

/* ------------------------------------------------------------------ read */
function doGet(e) {
  var p = (e && e.parameter) || {};
  var out;
  try {
    if (p.key !== SHARED_KEY) {
      out = { ok: false, error: 'Shared key does not match the one set in Code.gs.' };
    } else {
      out = { ok: true, progress: readState(), updated: readUpdated() };
    }
  } catch (err) {
    out = { ok: false, error: String(err) };
  }
  var json = JSON.stringify(out);
  if (p.callback) {
    return ContentService.createTextOutput(p.callback + '(' + json + ');')
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
  return ContentService.createTextOutput(json).setMimeType(ContentService.MimeType.JSON);
}

/* ------------------------------------------------------------------ write */
function doPost(e) {
  var p = (e && e.parameter) || {};
  try {
    if (p.key !== SHARED_KEY) throw new Error('Shared key does not match.');
    if (p.action !== 'save') throw new Error('Unknown action.');
    var progress = JSON.parse(p.payload || '{}');
    var lock = LockService.getScriptLock();
    lock.waitLock(20000);
    try {
      writeState(progress);
      writeFlat(progress);
      writeRoles(progress);
      log('save', countFindings(progress) + ' findings written');
    } finally {
      lock.releaseLock();
    }
    return ContentService.createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    log('error', String(err));
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/* ------------------------------------------------------------------ state */
function sheet(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function readState() {
  var sh = sheet(BLOB_SHEET);
  var chunks = sh.getRange(2, 2, Math.max(1, sh.getLastRow() - 1), 1).getValues();
  var raw = chunks.map(function (r) { return r[0]; }).join('');
  if (!raw) return null;
  try { return JSON.parse(raw); } catch (err) { return null; }
}

function readUpdated() {
  var sh = sheet(BLOB_SHEET);
  return sh.getRange('B1').getValue() || null;
}

/* A cell holds 50,000 characters, so long payloads are split across rows. */
function writeState(progress) {
  var sh = sheet(BLOB_SHEET);
  sh.clear();
  sh.getRange('A1').setValue('updated');
  sh.getRange('B1').setValue(new Date().toISOString());
  var raw = JSON.stringify(progress);
  var size = 45000, rows = [];
  for (var i = 0; i < raw.length; i += size) rows.push(['chunk', raw.substr(i, size)]);
  if (!rows.length) rows.push(['chunk', '']);
  sh.getRange(2, 1, rows.length, 2).setValues(rows);
  sh.hideSheet();
}

function countFindings(progress) {
  return progress && progress.findings ? Object.keys(progress.findings).length : 0;
}

/* ------------------------------------------------------------------ mirrors */
var GATES = ['g1', 'g2', 'g3', 'g4', 'g5', 'g6', 'g7', 'g8', 'g9', 'g10'];

function writeFlat(progress) {
  var sh = sheet(FLAT_SHEET);
  sh.clear();
  var head = ['Finding ID', 'Status', 'Gates cleared', 'Gates N/A', 'Score',
    'Root cause', 'Corrective action', 'Preventive action', 'Action owner',
    'Budget (BDT)', 'Closed on', 'Remarks'].concat(
    GATES.map(function (g) { return g.toUpperCase(); }));
  var rows = [head];
  var f = (progress && progress.findings) || {};
  Object.keys(f).sort().forEach(function (id) {
    var r = f[id] || {}, g = r.gates || {}, done = 0, na = 0;
    GATES.forEach(function (k) { if (g[k] === 'Y') done++; else if (g[k] === 'NA') na++; });
    var applicable = Math.max(1, GATES.length - na);
    rows.push([id, r.status || 'Not Started', done, na, done / applicable,
      r.rootCause || '', r.corrective || '', r.preventive || '', r.owner || '',
      r.budget || '', r.closed || '', r.remarks || ''
    ].concat(GATES.map(function (k) { return g[k] || ''; })));
  });
  if (rows.length === 1) rows.push(['(no progress recorded yet)']);
  sh.getRange(1, 1, rows.length, rows[0].length).setValues(padRows(rows));
  var hr = sh.getRange(1, 1, 1, head.length);
  hr.setFontWeight('bold').setBackground('#12324F').setFontColor('#FFFFFF');
  sh.setFrozenRows(1);
  if (rows.length > 1) sh.getRange(2, 5, rows.length - 1, 1).setNumberFormat('0%');
}

function writeRoles(progress) {
  var sh = sheet(ROLE_SHEET);
  sh.clear();
  var head = ['Deliverable #', 'Owner', 'Responsible', 'Support', 'Verify', 'Approve', 'Inform'];
  var rows = [head];
  var roles = (progress && progress.roles) || {};
  Object.keys(roles).sort(function (a, b) { return Number(a) - Number(b); }).forEach(function (no) {
    var r = roles[no] || {};
    rows.push([no, r.O || '', r.R || '', r.S || '', r.V || '', r.A || '', r.I || '']);
  });
  if (rows.length === 1) rows.push(['(no roles assigned yet)']);
  sh.getRange(1, 1, rows.length, head.length).setValues(padRows(rows, head.length));
  sh.getRange(1, 1, 1, head.length).setFontWeight('bold').setBackground('#1B6B4A').setFontColor('#FFFFFF');
  sh.setFrozenRows(1);
}

function padRows(rows, width) {
  var w = width || Math.max.apply(null, rows.map(function (r) { return r.length; }));
  return rows.map(function (r) {
    var c = r.slice();
    while (c.length < w) c.push('');
    return c;
  });
}

function log(kind, note) {
  try {
    var sh = sheet(LOG_SHEET);
    if (sh.getLastRow() === 0) {
      sh.appendRow(['Timestamp', 'Event', 'Detail']);
      sh.getRange(1, 1, 1, 3).setFontWeight('bold');
    }
    sh.appendRow([new Date(), kind, note]);
    if (sh.getLastRow() > 800) sh.deleteRows(2, 300);
  } catch (err) { /* logging must never break a save */ }
}

/* ------------------------------------------------------------------ helper */
/** Run once from the editor to confirm the Sheet is writable. */
function testSetup() {
  writeState({ findings: {}, roles: {}, updated: new Date().toISOString() });
  writeFlat({ findings: {} });
  writeRoles({ roles: {} });
  Logger.log('Setup OK. Deploy as a web app and copy the /exec URL.');
}
