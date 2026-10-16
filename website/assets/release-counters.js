/* Live public counters via Cloudflare; the Pages snapshot is an offline fallback. */
(() => {
  const panel = document.querySelector('.release-counters');
  const base = new URL('.', document.currentScript.src);
  const count = value => Number.isFinite(value) && value >= 0
    ? Math.floor(value).toLocaleString('en-US') : null;

  const update = stats => {
    if (!panel || !stats || !['ok', 'partial'].includes(stats.status)) return;
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
    status.textContent = (live ? (stats.status === 'partial' ? 'Partial · ' : 'Live · ') : 'Snapshot · ') + (Number.isFinite(generated.getTime())
      ? generated.toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit'}) : 'available');
    status.title = (Number.isFinite(generated.getTime()) ? generated.toISOString() + '. ' : '') +
      (live ? (stats.status === 'partial' ? 'Some sources unavailable; missing values retain their previous snapshot. ' : '') +
        'Checks every minute; upstream counts cached for two minutes. Hugging Face may report downloads with a delay.' : 'Static fallback; live refresh temporarily unavailable.');
    panel.dataset.releaseStats = live ? (stats.status === 'partial' ? 'partial' : 'live') : 'snapshot';
  };

  if (panel) {
    const config = fetch(new URL('analytics-config.json', base), {cache: 'no-store'})
      .then(response => response.ok ? response.json() : null).catch(() => null);
    let busy = false;
    const directCache = {};
    async function fillMissing(stats) {
      // Shared Cloudflare egress can hit GitHub's unauthenticated rate limit.
      // Fall back to the reader's public API access, never an account token.
      await Promise.all(Object.entries({
        github: 'https://api.github.com/repos/Yufannnn/QuasiLeak-Bench',
        huggingFace: 'https://huggingface.co/api/datasets/HenryZYF/QuasiLeak-Bench'
      }).map(async ([name, url]) => {
        if (stats[name]) return;
        const cached = directCache[name];
        if (cached && Date.now() - cached.time < 120000) { stats[name] = cached.value; return; }
        try {
          const result = await fetch(url, {credentials: 'omit', referrerPolicy: 'no-referrer', signal: AbortSignal.timeout(8000)});
          if (!result.ok) return;
          const value = await result.json();
          const mapped = name === 'github' ? {stars: value.stargazers_count, forks: value.forks_count}
            : {downloads: value.downloads, likes: value.likes};
          if (!Object.values(mapped).every(value => Number.isSafeInteger(value) && value >= 0)) return;
          stats[name] = mapped;
          directCache[name] = {time: Date.now(), value: mapped};
        } catch { /* Keep the available provider and label partial results. */ }
      }));
      stats.status = stats.github && stats.huggingFace ? 'ok' : 'partial';
      return stats;
    }
    async function refresh() {
      if (busy) return;
      busy = true;
      try {
        const settings = await config;
        if (settings?.provider !== 'cloudflare') throw Error('No live endpoint');
        let stats;
        try {
          const result = await fetch(new URL('/release', settings.endpoint), {
            cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer', signal: AbortSignal.timeout(12000)
          });
          if (!result.ok) throw Error('Release counters unavailable');
          stats = await result.json();
          if (!['ok', 'partial'].includes(stats?.status)) throw Error('Invalid counters');
        } catch {
          stats = {provider: 'cloudflare', generatedAt: new Date().toISOString()};
        }
        stats = await fillMissing(stats);
        if (!stats.github && !stats.huggingFace) throw Error('All public sources unavailable');
        if (stats.status === 'partial' && !panel.dataset.releaseStats) {
          const fallback = await fetch(new URL('release-stats.json', base), {cache: 'no-store'});
          if (fallback.ok) update({...await fallback.json(), provider: 'snapshot'});
        }
        update(stats);
      } catch {
        // Keep the last successful live values, but do not label them live.
        if (['live', 'partial'].includes(panel.dataset.releaseStats)) {
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
