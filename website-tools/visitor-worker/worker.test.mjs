import {test} from 'node:test';
import assert from 'node:assert/strict';
import worker, {releaseStats} from './index.mjs';

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

test('release counters fetch public APIs once and reuse the two-minute edge cache', async () => {
  let saved, calls = 0;
  const cache = {
    async match() { return saved?.clone(); },
    async put(key, result) {
      assert.equal(key.url, 'https://example.workers.dev/release');
      assert.equal(result.headers.get('Cache-Control'), 'public, max-age=120');
      saved = result;
    }
  };
  const upstream = async (url, options) => {
    calls++;
    assert.equal('Authorization' in options.headers, false);
    return Response.json(url.includes('github.com') ? {stargazers_count: 3, forks_count: 1} : {downloads: 8, likes: 2});
  };
  const request = new Request('https://example.workers.dev/release?ignored=1');
  const first = await releaseStats(request, cache, upstream);
  assert.equal(first.headers.get('Access-Control-Allow-Origin'), '*');
  assert.equal(first.headers.get('Cache-Control'), 'no-store');
  const stats = await first.json();
  assert.equal(stats.github.stars, 3);
  assert.equal(stats.huggingFace.likes, 2);
  assert.equal(stats.refreshSeconds, 120);
  assert.deepEqual(await (await releaseStats(request, cache, upstream)).json(), stats);
  assert.equal(calls, 2);
});

test('release counters reject upstream errors or malformed counts without caching', async () => {
  const request = new Request('https://example.workers.dev/release');
  const cache = {async match() {}, async put() { assert.fail('Do not cache a failed refresh'); }};
  for (const upstream of [async () => new Response('', {status: 429}), async () => Response.json({likes: -1}),
                          async () => { throw Error('Network failure'); }]) {
    const result = await releaseStats(request, cache, upstream);
    assert.equal(result.status, 503);
    assert.equal((await result.json()).status, 'unavailable');
  }
});

test('a cache failure does not block fresh public release data', async () => {
  const request = new Request('https://example.workers.dev/release');
  const cache = {async match() { throw Error(); }, async put() { throw Error(); }};
  const upstream = async () => Response.json({stargazers_count: 0, forks_count: 0, downloads: 0, likes: 0});
  assert.equal((await releaseStats(request, cache, upstream)).status, 200);
});

test('a rate-limited GitHub API does not freeze Hugging Face counters', async () => {
  const request = new Request('https://example.workers.dev/release');
  const upstream = async url => url.includes('github.com') ? new Response('', {status: 403}) : Response.json({downloads: 3, likes: 1});
  const result = await releaseStats(request, null, upstream);
  assert.equal(result.status, 200);
  const body = await result.json();
  assert.equal(body.status, 'partial');
  assert.equal(body.github, null);
  assert.equal(body.huggingFace.likes, 1);
});
