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
