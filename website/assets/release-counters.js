/* Live public counters via Cloudflare; the Pages snapshot is an offline fallback. */
(() => {
  const panel = document.querySelector('.release-counters');
  const base = new URL('.', document.currentScript.src);
  const count = value => Number.isFinite(value) && value >= 0
    ? Math.floor(value).toLocaleString('en-US') : null;

  const update = stats => {
    if (!panel || !stats || stats.status !== 'ok') return;
    const values = {
      stars: stats.github?.stars,
      forks: stats.github?.forks,
      downloads: stats.huggingFace?.downloads,
      likes: stats.huggingFace?.likes,
    };
    let received = false;
    panel.querySelectorAll('[data-release-stat]').forEach(element => {
      const value = count(values[element.dataset.releaseStat]);
      if (value === null) return;
      element.textContent = value;
      received = true;
    });
    for (const [name, details] of Object.entries({
      github: stats.github,
      huggingFace: stats.huggingFace,
      arxiv: stats.arxiv,
    })) {
      if (typeof details?.url !== 'string') continue;
      panel.querySelectorAll(`[data-release-link="${name}"]`).forEach(link => {
        link.href = details.url;
      });
    }
    if (!received) return;
    const status = document.getElementById('release-counters-status');
    const generated = new Date(stats.generatedAt);
    const live = stats.provider === 'cloudflare';
    status.textContent = (live ? 'Live · ' : 'Snapshot · ') + (Number.isFinite(generated.getTime())
      ? generated.toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit'}) : 'available');
    status.title = (Number.isFinite(generated.getTime()) ? generated.toISOString() + '. ' : '') +
      (live ? 'Checks every minute; upstream counts cached for two minutes. Hugging Face may report downloads with a delay.' : 'Static fallback; live refresh temporarily unavailable.');
    panel.dataset.releaseStats = live ? 'live' : 'snapshot';
  };

  if (panel) {
    const config = fetch(new URL('analytics-config.json', base), {cache: 'no-store'})
      .then(response => response.ok ? response.json() : null).catch(() => null);
    let busy = false;
    async function refresh() {
      if (busy) return;
      busy = true;
      try {
        const settings = await config;
        if (settings?.provider !== 'cloudflare') throw Error('No live endpoint');
        const result = await fetch(new URL('/release', settings.endpoint), {
          cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer', signal: AbortSignal.timeout(12000)
        });
        if (!result.ok) throw Error('Release counters unavailable');
        const stats = await result.json();
        if (stats?.status !== 'ok') throw Error('Invalid counters');
        update(stats);
      } catch {
        // Keep the last successful live values, but do not label them live.
        if (panel.dataset.releaseStats === 'live') {
          document.getElementById('release-counters-status').textContent = 'Refresh delayed';
        } else {
          const fallback = await fetch(new URL('release-stats.json', base), {cache: 'no-store'});
          if (fallback.ok) update({...await fallback.json(), provider: 'snapshot'});
        }
      } finally { busy = false; }
    }
    refresh().catch(() => {});
    setInterval(() => { if (!document.hidden) refresh().catch(() => {}); }, 60000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh().catch(() => {}); });
  }
})();
