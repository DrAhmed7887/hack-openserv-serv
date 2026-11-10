// Runs the mock's real <script> against a minimal stub DOM and reports which step is visible after each action.
// Usage: node tests/mock_harness.js mock/index.html   (prints one JSON object; no network, no browser)
const fs = require("fs");
const vm = require("vm");

const html = fs.readFileSync(process.argv[2], "utf8");
const data = html.match(/<script type="application\/json" id="mock-data">([\s\S]*?)<\/script>/)[1];
const code = html.match(/<script>\s*([\s\S]*?)<\/script>\s*<\/body>/)[1];
const STEPS = ["catalog", "study", "coverage", "repair", "export"];

function element(id) {
  const attrs = {};
  const el = {
    id, innerHTML: "", textContent: id === "mock-data" ? data : "", style: {},
    setAttribute(k, v) { attrs[k] = v; }, removeAttribute(k) { delete attrs[k]; },
    getAttribute(k) { return k in attrs ? attrs[k] : null; },
    querySelector() { return element("child"); },
  };
  return el;
}
const els = {};
const getEl = (id) => (els[id] = els[id] || element(id));
STEPS.forEach((s) => { getEl("step-" + s).style.display = "none"; });

function run(initialHash, actions) {
  const listeners = { click: [], hashchange: [] };
  let hash = initialHash;
  const location = {
    get hash() { return hash; },
    set hash(v) {
      const next = "#" + String(v).replace(/^#/, "");
      if (next !== hash) { hash = next; listeners.hashchange.forEach((f) => f({})); }
    },
  };
  const add = (type, f) => { (listeners[type] = listeners[type] || []).push(f); };
  const sandbox = {
    document: { getElementById: getEl, addEventListener: add },
    window: { scrollTo() {}, addEventListener: add },
    location, history: { pushState() {}, replaceState() {} }, JSON, Object, String, Array, console,
  };
  sandbox.window.location = location;
  vm.runInNewContext(code, sandbox);
  const visible = () => STEPS.filter((s) => getEl("step-" + s).style.display === "block");
  const out = [{ action: "load", hash: location.hash, visible: visible() }];
  actions.forEach((a) => {
    if (a.click) { listeners.click.forEach((f) => f({ target: { getAttribute: (k) => (k === "data-go" ? a.click : null) } })); }
    if (a.hash !== undefined) { location.hash = a.hash; }  // what back/forward or editing the URL does
    out.push({ action: JSON.stringify(a), hash: location.hash, visible: visible() });
  });
  return out;
}

const scenarios = JSON.parse(process.argv[3]);
process.stdout.write(JSON.stringify(scenarios.map((s) => run(s.initial, s.actions))));
