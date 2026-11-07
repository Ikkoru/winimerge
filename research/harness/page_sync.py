"""Account copy of the eye-check pages' marks (used by eyecheck.py and eyecheck2.py).

The pages keep the marks in the browser's localStorage, which only that browser can read. When a page
is opened on claude.ai or in the Claude app (where it is framed by the artifact viewer), this script
also copies the marks into the artifact's database (the `db` capability) as one document, so that any
Claude session of the same account can read them with the ArtifactData tool:

    ArtifactData action "get", url <the page's artifact URL>, collection "marks", doc_id "round1" / "round2"

On load it merges the browser's marks with the account's (an entry with a later `t` wins; entries
without `t` keep the browser's version; `used` lists are joined), so marks made before this existed
are uploaded the first time the page is opened again in the browser that holds them. After that,
every change is written about 1.5 s after the last click. Opened from disk (index.html) there is no
`window.claude`, and the page keeps working with localStorage only.

Each page defines `marks` (an object), calls `queuePush()` after saving locally, and defines
`afterMerge()` to save and redraw after the merge.
"""

SYNC_JS = r'''
// ---- Account copy of the marks (see harness/page_sync.py) ----
const SYNC = { doc: '__DOC__', page: '__PAGE__', ref: null, last: null, timer: null, busy: false, again: false, retried: false };
function syncNote(t) { const el = document.getElementById('sync'); if (el) el.textContent = t; }
function mergeMarks(local, remote) { const out = Object.assign({}, local);
  for (const [k, v] of Object.entries(remote || {})) { const u = out[k];
    if (u === undefined) { out[k] = v; continue; }
    if (!u || !v || typeof u !== 'object' || typeof v !== 'object') continue;
    const remoteNewer = (u.t || 0) < (v.t || 0);
    const m = remoteNewer ? Object.assign({}, u, v) : Object.assign({}, v, u);
    if (u.used || v.used) m.used = [...new Set([...(u.used || []), ...(v.used || [])])];
    out[k] = m; }
  return out; }
function queuePush() { if (!SYNC.ref || JSON.stringify(marks) === SYNC.last) return;
  clearTimeout(SYNC.timer); SYNC.timer = setTimeout(pushMarks, 1500); }
async function pushMarks() {
  if (SYNC.busy) { SYNC.again = true; return; }
  const j = JSON.stringify(marks); if (j === SYNC.last) return;
  SYNC.busy = true;
  try { await SYNC.ref.set({ page: SYNC.page, updated: new Date().toISOString(), entries: Object.keys(marks).length, marks: JSON.parse(j) });
    SYNC.last = j; SYNC.retried = false;
    syncNote(`Marks are saved in this browser and in your Claude account (${Object.keys(marks).length} entries), where a Claude session can read them.`); }
  catch (e) { const code = (e && e.code) || 'error';
    if (code === 'unavailable' && !SYNC.retried) { SYNC.retried = true; setTimeout(pushMarks, 1000 + Math.random() * 2000); }
    else syncNote(`Marks are saved in this browser; saving them to your Claude account failed (${code}). Use the copy button to send them.`); }
  finally { SYNC.busy = false; if (SYNC.again) { SYNC.again = false; queuePush(); } } }
(async () => {
  if (!window.claude || !window.claude.use) { syncNote('Marks are saved in this browser only (opened outside claude.ai). Use the copy button to send them.'); return; }
  syncNote('Marks are saved in this browser. Connecting to your Claude account…');
  let db = null; try { db = await window.claude.use('db'); } catch (e) { db = null; }
  if (!db) { syncNote('Marks are saved in this browser only (this view has no account storage). Use the copy button to send them.'); return; }
  const ref = db.doc(SYNC.doc);
  let snap;
  try { snap = await Promise.race([ref.get(), new Promise((_, no) => setTimeout(() => no({ code: 'timeout' }), 10000))]); }
  catch (e) { syncNote('Marks are saved in this browser; your Claude account could not be reached. Reload the page later to copy them there.'); return; }
  const remote = snap.exists ? ((snap.data() || {}).marks || {}) : {};
  SYNC.ref = ref; SYNC.last = JSON.stringify(remote);
  marks = mergeMarks(marks, remote);
  const n = Object.keys(marks).length;
  syncNote(JSON.stringify(marks) === SYNC.last
    ? (n ? `Marks are saved in this browser and in your Claude account (${n} entries), where a Claude session can read them.`
         : 'Your marks will be saved in this browser and in your Claude account, where a Claude session can read them.')
    : 'Copying your marks to your Claude account…');
  afterMerge();
})();
'''


def sync_js(doc, page):
    return SYNC_JS.replace('__DOC__', doc).replace('__PAGE__', page)
