// DOM stubs exercise refresh/fallback behavior without a browser or fake visits.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

async function harness(script, kind, initiallyOffline = false, sharedGitHubLimit = false) {
  const fields = {};
  const attribute = kind === 'release' ? 'releaseStat' : 'visitorStat';
  for (const key of kind === 'release' ? ['stars', 'forks', 'downloads', 'likes'] : ['pageViews', 'visitors', 'countries']) {
    fields[key] = {dataset: {[attribute]: key}, textContent: '—'};
  }
  const panel = {dataset: {}, querySelectorAll: selector => selector.includes('stat]') ? Object.values(fields) : []};
  const status = {textContent: '', dataset: {}};
  const events = {}, timers = [], calls = [];
  const document = {
    hidden: false, currentScript: {src: 'https://example.test/assets/' + script},
    querySelector: () => panel,
    getElementById: id => id === 'visitor-atlas' ? panel : status,
    addEventListener: (event, callback) => { events[event] = callback; }
  };
  const live = kind === 'release' ? {
    github: {stars: 4, forks: 1}, huggingFace: {downloads: 9, likes: 2}
  } : {pageViews: 7, visitors: 5, countries: 1, countryVisits: [], daily:[{day:'2026-10-16',views:7}]};
  let fail = initiallyOffline;
  const fetch = async url => {
    url = String(url); calls.push(url);
    if (url.includes('analytics-config.json')) return Response.json({provider: 'cloudflare', endpoint: 'https://counts.workers.dev'});
    if (url.includes('-stats.json')) return Response.json({status: 'ok', ...live, generatedAt: '2026-10-16T05:00:00Z'});
    if (fail) throw Error('Offline');
    if (url.includes('api.github.com')) return Response.json({stargazers_count: 6, forks_count: 2});
    if (url.includes('huggingface.co/api/')) return Response.json({downloads: 9, likes: 2});
    if (sharedGitHubLimit === 'offline-worker') return new Response('', {status: 503});
    if (sharedGitHubLimit && kind === 'release') return Response.json({status: 'partial', provider: 'cloudflare',
      generatedAt: '2026-10-16T05:30:00Z', github: null, huggingFace: live.huggingFace});
    return Response.json({status: 'ok', provider: 'cloudflare', generatedAt: '2026-10-16T05:30:00Z', ...live});
  };
  const window = {addEventListener: (event, callback) => { events[event] = callback; },
    dispatchEvent: event => { events[event.type]?.(event); }};
  const source = await readFile(new URL('../../website/assets/' + script, import.meta.url), 'utf8');
  vm.runInNewContext(source, {document, window, URL, fetch, AbortSignal, Intl,
    CustomEvent: class { constructor(type, options){this.type=type;this.detail=options.detail;} },
    setInterval: (callback, period) => { timers.push({callback, period}); }});
  const settle = async () => { for (let i = 0; i < 8; i++) await new Promise(resolve => setImmediate(resolve)); };
  await settle();
  return {fields, status, panel, document, window, events, timers, calls, settle, fail: () => { fail = true; }};
}

test('Atlas shares daily counts with Activity through its existing refresh, without extra requests', async () => {
  const h = await harness('visitor-atlas.js','visitor');
  assert.equal(h.window.quasiLeakVisitorStats.daily[0].views,7);
  let received;
  h.events['quasileak:activity-stats'] = event => { received=event.detail; };
  const start=h.calls.length;
  h.timers[0].callback(); await h.settle();
  assert.equal(h.calls.length,start+1);
  assert.equal(received.daily[0].views,7);
});

test('shared GitHub rate limits use the direct public API, cached across refreshes', async () => {
  const h = await harness('release-counters.js', 'release', false, true);
  assert.equal(h.fields.stars.textContent, '6');
  assert.equal(h.fields.likes.textContent, '2');
  assert.match(h.status.textContent, /^Live/);
  h.timers[0].callback(); await h.settle();
  assert.equal(h.calls.filter(url => url.includes('api.github.com')).length, 1);
});

test('both direct public APIs can recover a failed Worker release endpoint', async () => {
  const h = await harness('release-counters.js', 'release', false, 'offline-worker');
  assert.equal(h.fields.stars.textContent, '6');
  assert.equal(h.fields.likes.textContent, '2');
  assert.match(h.status.textContent, /^Live/);
});

for (const [script, kind, period] of [['release-counters.js', 'release', 60000], ['visitor-atlas.js', 'visitor', 30000]]) {
  test(script + ': load live values, poll only when visible, refresh on tab return', async () => {
    const h = await harness(script, kind);
    assert.match(h.status.textContent, /^Live/);
    assert.equal(h.fields[kind === 'release' ? 'likes' : 'pageViews'].textContent, kind === 'release' ? '2' : '7');
    assert.equal(h.timers[0].period, period);
    const start = h.calls.length;
    h.document.hidden = true;
    h.timers[0].callback(); await h.settle();
    assert.equal(h.calls.length, start);
    h.document.hidden = false;
    h.events.visibilitychange(); await h.settle();
    assert.equal(h.calls.length, start + 1);
    h.timers[0].callback(); await h.settle();
    assert.equal(h.calls.length, start + 2);
    assert.equal(h.calls.some(url => url.endsWith('/visit')), false);
  });
}

test('a failed release refresh retains the last good values and reports the delay', async () => {
  const h = await harness('release-counters.js', 'release');
  h.fail(); h.timers[0].callback(); await h.settle();
  assert.equal(h.fields.likes.textContent, '2');
  assert.equal(h.status.textContent, 'Refresh delayed');
});

test('a failed Atlas refresh retains the last good values and reports the delay', async () => {
  const h = await harness('visitor-atlas.js', 'visitor');
  h.fail(); h.timers[0].callback(); await h.settle();
  assert.equal(h.fields.pageViews.textContent, '7');
  assert.equal(h.status.textContent, 'Refresh delayed');
});

for (const [script, kind] of [['release-counters.js', 'release'], ['visitor-atlas.js', 'visitor']]) {
  test(script + ': initial outage uses an explicitly labelled static snapshot', async () => {
    const h = await harness(script, kind, true);
    assert.match(h.status.textContent, /^(Snapshot|Updated)/);
    assert.equal(h.fields[kind === 'release' ? 'likes' : 'pageViews'].textContent, kind === 'release' ? '2' : '7');
  });
}
