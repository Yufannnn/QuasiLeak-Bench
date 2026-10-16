import {test} from 'node:test';
import assert from 'node:assert/strict';
import worker from './index.mjs';

function database() {
  const rows = new Map();
  return {prepare() { return {
    bind(day, path, country) { this.row = {day, path, country}; return this; },
    async run() { const key = JSON.stringify(this.row); rows.set(key, (rows.get(key) || 0) + 1); },
    async all() { return {results: [...rows].map(([key, views]) => ({...JSON.parse(key), views}))}; }
  }; }};
}
function visit(path = '/QuasiLeak-Bench/', country = 'SG', headers = {}) {
  return Object.assign(new Request('https://example.workers.dev/visit', {method: 'POST', headers: {
    Origin: 'https://yufannnn.github.io', 'User-Agent': 'Mozilla/5.0', ...headers
  }, body: JSON.stringify({path})}), {cf: {country}});
}
const stats = env => worker.fetch(new Request('https://example.workers.dev/stats'), env).then(r => r.json());

test('only actual recorded page views populate the Atlas', async () => {
  const env = {DB: database()};
  assert.equal((await stats(env)).pageViews, 0);
  assert.equal((await worker.fetch(visit(), env)).status, 201);
  assert.equal((await worker.fetch(visit('/QuasiLeak-Bench/explore.html', 'US'), env)).status, 201);
  const snapshot = await stats(env);
  assert.equal(snapshot.pageViews, 2);
  assert.equal(snapshot.visitors, 1);
  assert.equal(snapshot.countries, 2);
  assert.deepEqual(snapshot.countryVisits.map(c => c.code).sort(), ['SG', 'US']);
  assert.equal('ip' in snapshot, false);
});
test('reject other origins, query strings, and nonpublic pages', async () => {
  const env = {DB: database()};
  assert.equal((await worker.fetch(visit('/QuasiLeak-Bench/', 'SG', {Origin: 'https://other.example'}), env)).status, 403);
  assert.equal((await worker.fetch(visit('/QuasiLeak-Bench/?secret=x'), env)).status, 400);
  assert.equal((await worker.fetch(visit('/review/'), env)).status, 400);
  assert.equal((await stats(env)).pageViews, 0);
});
test('skip Do Not Track, GPC and common bot traffic', async () => {
  const env = {DB: database()};
  for (const headers of [{DNT: '1'}, {'Sec-GPC': '1'}, {'User-Agent': 'curl/8'}]) {
    assert.equal((await worker.fetch(visit('/QuasiLeak-Bench/', 'SG', headers), env)).status, 200);
  }
  assert.equal((await stats(env)).pageViews, 0);
});
test('unknown country still counts a view, but not an additional country', async () => {
  const env = {DB: database()};
  await worker.fetch(visit('/QuasiLeak-Bench/', 'bad'), env);
  const snapshot = await stats(env);
  assert.equal(snapshot.pageViews, 1);
  assert.equal(snapshot.countries, 0);
});
