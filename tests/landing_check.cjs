// Run: node marketpulse/tests/landing_check.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const web = path.join(__dirname, '../web');
const html = fs.readFileSync(path.join(web, 'index.html'), 'utf8');
assert.equal(html, fs.readFileSync(path.join(web, 'landing.template.html'), 'utf8'));
assert.match(html, /<title>MarketPulse \| Market Intelligence<\/title>/);
for (const [, asset] of html.matchAll(/(?:src|href)="(\/assets\/[^" ]+)"/g)) assert.ok(fs.existsSync(path.join(web, asset)));
for (const [file, hash] of Object.entries({'terminal.html':'abdbc2c06b3e1e80eec66b12f58df3809ebc116e54c81dafdf8f06eec4a2a56f','terminal.template.html':'a2aa648574de0d97282e2316ca54d9756fc253c11207b343d8129f2a07adf001'})) {
  assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(web,file))).digest('hex'),hash,`${file} changed from the preserved dashboard`);
}
console.log('PASS: MarketPulse build assets, generator template, and unchanged dashboard.');
