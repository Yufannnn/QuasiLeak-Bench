/* Country-level page-view aggregates only. No IPs, cookies, or visitor IDs stored. */
const ROOT = '/QuasiLeak-Bench/';
const PAGES = new Set([ROOT.slice(0, -1), ROOT, ...[
  'index.html', 'explore.html', 'examples.html', 'evaluation.html', 'submit.html', 'run.html', 'compare.html'
].map(page => ROOT + page)]);
const BOTS = /bot|crawler|spider|preview|prerender|headless|slack|discord|telegram|lighthouse|python|curl\/|wget/i;

function response(data, status = 200, origin = '*') {
  return new Response(data === null ? null : JSON.stringify(data), {status, headers: {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff'
  }});
}

// Public upstream counts are shared at the edge for two minutes, not per visitor.
// No GitHub/Hugging Face token or visitor information is sent upstream.
export async function releaseStats(request, cache = globalThis.caches?.default, fetcher = fetch) {
  const key = new Request(new URL('/release', request.url));
  try {
    const hit = await cache?.match(key);
    if (hit) return response(await hit.json());
  } catch { /* A cache outage must not disable the public counters. */ }
  try {
    const load = async url => {
      const result = await fetcher(url, {headers: {'User-Agent': 'QuasiLeak-Bench-public-counters/1.0',
        Accept: 'application/json'}, signal: AbortSignal.timeout(8000)});
      if (!result.ok) throw Error(new URL(url).hostname + ': HTTP ' + result.status);
      return result.json();
    };
    const integer = value => Number.isSafeInteger(value) && value >= 0;
    const [github, hf] = await Promise.allSettled([
      load('https://api.github.com/repos/Yufannnn/QuasiLeak-Bench').then(value => {
        if (!integer(value.stargazers_count) || !integer(value.forks_count)) throw Error('Invalid GitHub counts');
        return {stars: value.stargazers_count, forks: value.forks_count, url: 'https://github.com/Yufannnn/QuasiLeak-Bench'};
      }),
      load('https://huggingface.co/api/datasets/HenryZYF/QuasiLeak-Bench').then(value => {
        if (!integer(value.downloads) || !integer(value.likes)) throw Error('Invalid Hugging Face counts');
        return {downloads: value.downloads, likes: value.likes, url: 'https://huggingface.co/datasets/HenryZYF/QuasiLeak-Bench'};
      })
    ]);
    if (github.status === 'rejected' && hf.status === 'rejected') throw github.reason;
    const data = {status: github.status === 'fulfilled' && hf.status === 'fulfilled' ? 'ok' : 'partial',
      provider: 'cloudflare', generatedAt: new Date().toISOString(),
      refreshSeconds: 120,
      github: github.status === 'fulfilled' ? github.value : null,
      huggingFace: hf.status === 'fulfilled' ? hf.value : null,
      arxiv: {url: 'https://arxiv.org/abs/2610.21333'}};
    try {
      await cache?.put(key, new Response(JSON.stringify(data), {headers: {
        'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=120'
      }}));
    } catch { /* Return fresh data even if the edge cache is temporarily unavailable. */ }
    return response(data);
  } catch (error) {
    const reason = /^(api.github.com|huggingface.co): HTTP \d{3}$/.test(error.message) ? error.message : 'Upstream request failed';
    return response({status: 'unavailable', error: 'Release counters temporarily unavailable', reason}, 503);
  }
}

async function readPage(request) {
  if (!request.body) throw Error('Invalid body');
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > 512) {
      await reader.cancel();
      throw Error('Body too large');
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  const body = JSON.parse(new TextDecoder().decode(bytes));
  if (!PAGES.has(body?.path)) throw Error('Invalid page');
  return body.path === ROOT.slice(0, -1) ? ROOT : body.path;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get('Origin');
    const allowed = env.ALLOWED_ORIGIN || 'https://yufannnn.github.io';
    if (request.method === 'OPTIONS') return response(null, origin === allowed ? 204 : 403, allowed);
    if (url.pathname === '/health' && request.method === 'GET') return response({ok: true, service: 'qlb-visitor-atlas'});
    if (url.pathname === '/release' && request.method === 'GET') return releaseStats(request);
    if (!env.DB) return response({error: 'Analytics unavailable'}, 503);
    try {
      if (url.pathname === '/visit' && request.method === 'POST') {
        if (origin !== allowed) return response({error: 'Origin not permitted'}, 403, allowed);
        if (request.headers.get('DNT') === '1' || request.headers.get('Sec-GPC') === '1' ||
            BOTS.test(request.headers.get('User-Agent') || '')) return response({counted: false}, 200, allowed);
        let path;
        try { path = await readPage(request); } catch { return response({error: 'Invalid page or body'}, 400, allowed); }
        const country = /^[A-Z]{2}$/.test(request.cf?.country || '') ? request.cf.country : 'ZZ';
        const day = new Date().toISOString().slice(0, 10);
        await env.DB.prepare(`INSERT INTO daily_page_views (day, path, country, views) VALUES (?, ?, ?, 1)
          ON CONFLICT(day, path, country) DO UPDATE SET views = views + 1`).bind(day, path, country).run();
        return response({counted: true}, 201, allowed);
      }
      if (url.pathname === '/stats' && request.method === 'GET') {
        const rows = await env.DB.prepare('SELECT path, country, SUM(views) AS views FROM daily_page_views GROUP BY path, country').all();
        const countries = new Map();
        let pageViews = 0, homepageViews = 0;
        for (const row of rows.results || []) {
          const views = Number(row.views);
          pageViews += views;
          if (row.path === ROOT || row.path === ROOT + 'index.html') homepageViews += views;
          if (/^[A-Z]{2}$/.test(row.country) && !['ZZ', 'XX'].includes(row.country)) {
            countries.set(row.country, (countries.get(row.country) || 0) + views);
          }
        }
        return response({status: 'ok', provider: 'cloudflare', generatedAt: new Date().toISOString(),
          collectedSince: env.COLLECTED_SINCE || '2026-10-16', pageViews, visitors: homepageViews,
          metric: 'pageviews', countries: countries.size,
          countryVisits: [...countries].map(([code, visits]) => ({code, name: code, visits})).sort((a, b) => b.visits - a.visits)});
      }
      return response({error: 'Not found'}, 404);
    } catch {
      return response({error: 'Analytics temporarily unavailable'}, 503);
    }
  }
};
