// Run after building: node tests/terminal_check.cjs
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(require('node:path').join(__dirname, '../web/terminal.html'), 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
for (const [, script] of scripts) new vm.Script(script);
const nodes = {};
for (const [, id] of html.matchAll(/id="([^"]+)"/g)) nodes[id] = {
  value: id === 'sentiment-filter' ? 'all' : '', textContent: '', innerHTML: '',
  querySelectorAll: () => [], dataset: {},
};
let candles;
const chartIds = [];
const timers = [];
const context = vm.createContext({URL, Date, console, MutationObserver: class {observe(){}}, location: {protocol: 'http:'}, setTimeout: fn => fn(), setInterval: fn => timers.push(fn), fetch: async () => ({ok: true, json: async () => ({snapshots: {}})}), document: {
  getElementById: id => {assert.ok(nodes[id], `Missing element: ${id}`); return nodes[id];},
  querySelectorAll: () => [],
  addEventListener: () => {},
}, Plotly: {react: (id, traces) => {chartIds.push(id); if(id===nodes['world-map']){assert.equal(traces[0].type,'choropleth');assert.ok(traces[0].locations.length>=140);assert.equal(traces[1].type,'scattergeo')} candles = traces[0];}, relayout: (id, layout) => {assert.equal(id, 'world-map'); assert.equal(layout['geo.projection.scale'], 1);}}});
const app = scripts.find(([, script]) => script.includes('const D='));
vm.runInContext(app[1], context);
assert.equal(nodes['chart-title'].textContent, 'NVDA / PRICE ACTION');
assert.equal(candles.close.length, 90);
vm.runInContext("select('MSFT'); range=252; render()", context);
assert.equal(nodes['chart-title'].textContent, 'MSFT / PRICE ACTION');
assert.equal(candles.close.length, 252);
nodes['sentiment-filter'].value = 'positive';
vm.runInContext('render()', context);
assert.ok(!nodes.news.innerHTML.includes('>NEGATIVE</span>'));
assert.ok(nodes.stats.innerHTML.includes('61,656'));
const live = scripts.find(([, script]) => script.includes('function renderAll'));
vm.runInContext(live[1], context);
assert.match(nodes['chart-title'].textContent, /AUTO ROTATION/);
assert.equal(vm.runInContext('ticker', context), 'ALL');
const firstRotatingTicker = nodes['chart-title'].textContent;
timers.at(-1)();
assert.notEqual(nodes['chart-title'].textContent, firstRotatingTicker);
nodes.search.oninput({target: {value: 'MSFT'}});
assert.equal(nodes['chart-title'].textContent, 'MSFT / PRICE ACTION');
timers.at(-1)();
assert.equal(nodes['chart-title'].textContent, 'MSFT / PRICE ACTION');
nodes.search.oninput({target: {value: ''}});
assert.match(nodes['chart-title'].textContent, /AUTO ROTATION/);
vm.runInContext("renderResearch('MSFT')", context);
assert.ok(nodes['research-summary'].innerHTML.includes('MSFT'));
assert.ok(nodes['metrics-table'].innerHTML.includes('Buy &amp; Hold'));
assert.ok(nodes['event-study-table'].innerHTML.includes('EventDate'));
assert.ok(chartIds.includes('research-metrics-chart'));
assert.ok(chartIds.includes('research-walk-chart'));
assert.ok(chartIds.includes('research-event-chart'));
vm.runInContext("renderArchive('NVDA')", context);
assert.ok(nodes.archive.innerHTML.includes('news-card'));
assert.ok(nodes.archive.innerHTML.includes('sentiment-pill'));
vm.runInContext("updateMarketTable([{Ticker:'NVDA',IEXLast:229.83,YahooClose:230.36,YahooReturn:.0084,YahooAsOf:'2026-09-04',Regime:'High Volatility',RSI:53.68,Momentum:'LONG'}])", context);
assert.ok(nodes['market-table'].innerHTML.includes('<th>Live</th>'));
assert.ok(nodes['market-table'].innerHTML.includes('<th>Close</th>'));
assert.ok(!nodes['market-table'].innerHTML.includes('<th>Yahoo</th>'));
assert.ok(nodes['market-table'].innerHTML.includes('▲ +0.84%'));
console.log('PASS: rotation, ticker freeze, company research, charts, filters, and JavaScript syntax.');
