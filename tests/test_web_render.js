// Regression test: replay the REAL index.html client render pipeline in Node
// against saved API fixtures, and assert the *visible* output contains no
// English leakage ("undefined" / "null"). The collapsed <pre class="hidden">
// raw-data dump is excluded because it intentionally mirrors raw API JSON.
//
// Usage:  node tests/test_web_render.js
// Exits 0 if every fixture renders clean, 1 otherwise.

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const TP = 'templates/index.html';
const FIX = path.join(__dirname, 'fixtures', 'web');

// ---- extract the page <script> body ----
const html = fs.readFileSync(path.join(ROOT, TP), 'utf8');
const start = html.indexOf('<script>') + '<script>'.length;
const end = html.indexOf('</script>');
const body = html.slice(start, end);

// ---- minimal DOM / browser mocks ----
let allHTML = '';
let allText = '';
const elCache = {};
function makeEl(id) {
  const store = { html: '', text: '' };
  const el = {
    _id: id,
    addEventListener() {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    value: '',
    appendChild() {},
  };
  Object.defineProperty(el, 'innerHTML', {
    get() { return store.html; },
    set(v) { store.html += v; allHTML += v; },
  });
  Object.defineProperty(el, 'textContent', {
    get() { return store.text; },
    set(v) { store.text += v; allText += v; },
  });
  return el;
}
const document = {
  getElementById(id) { if (!elCache[id]) elCache[id] = makeEl(id); return elCache[id]; },
  createElement() { return makeEl('dyn'); },
  addEventListener() {},
};
const window = { print() {} };
const fetch = () => Promise.resolve({ json: () => Promise.resolve({}) });

// ---- driver: render each fixture and scan visible output ----
const driver = `
;(function(){
  const files = require('fs').readdirSync(${JSON.stringify(FIX)}).filter(f=>f.endsWith('.json')).sort();
  let bad = 0;
  for (const f of files) {
    allHTML=''; allText='';
    for (const k in elCache) delete elCache[k];
    const data = JSON.parse(require('fs').readFileSync(require('path').join(${JSON.stringify(FIX)}, f), 'utf8')).data;
    currentResult = data;
    try { renderResult(data); } catch (err) { console.log(f + ': ERROR ' + err.message); bad++; continue; }
    let combined = (allHTML + '\\n' + allText);
    // strip collapsed developer raw-data dumps (legitimately contain null)
    combined = combined.replace(/<pre class="hidden">[\\s\\S]*?<\\/pre>/g, '');
    // strip HTML tags so only VISIBLE text is scanned for English leaks
    const textOnly = combined.replace(/<[^>]+>/g, ' ');
    const hits = [...textOnly.matchAll(/undefined|null/g)];
    if (hits.length) {
      bad++;
      const cx = hits.slice(0,5).map(m=>{
        const a=Math.max(0,m.index-25), b=Math.min(combined.length,m.index+25);
        return '   ...' + combined.slice(a,b).replace(/\\s+/g,' ') + '...';
      });
      console.log(f + ': BAD x' + hits.length);
      cx.forEach(c=>console.log(c));
    } else { console.log(f + ': clean(undef/null)'); }
    // English-leak scan on the VISIBLE (JS-rendered) output.
    // Whitelist: (1) common acronyms acceptable in a Chinese UI; (2) open-source
    // library attribution proper nouns (iztro / SylarLong / MIT / Renhuai /
    // ziwei / doushu) — these are REQUIRED credits when publishing to GitHub and
    // are conventionally kept in English. They are NOT user-facing 命理 content.
    const ENG_WHITELIST = /^(pdf|iztro|SylarLong|MIT|Renhuai|ziwei|doushu)$/i;
    const engHits = [...textOnly.matchAll(/[A-Za-z]{2,}/g)]
      .map(m => m[0])
      .filter(w => !ENG_WHITELIST.test(w));
    if (engHits.length) {
      bad++;
      const uniq = [...new Set(engHits)];
      console.log(f + ': ENGLISH-LEAK x' + uniq.length + ' -> ' + uniq.slice(0,12).join(', '));
    } else { console.log(f + ': clean(english)'); }
  }
  if (bad) { console.log('FAIL: ' + bad + ' fixture(s) with English leakage'); process.exit(1); }
  else { console.log('PASS: all fixtures render without undefined/null/english'); process.exit(0); }
})();
`;

// eslint-disable-next-line no-eval
eval(body + driver);
