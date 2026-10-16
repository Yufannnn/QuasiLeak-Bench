/* Render the aggregate release snapshot prepared by the Pages workflow. */
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
    status.textContent = Number.isFinite(generated.getTime())
      ? 'Updated ' + generated.toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'UTC'})
      : 'Live';
    status.title = Number.isFinite(generated.getTime()) ? generated.toISOString() : '';
    panel.dataset.releaseStats = 'live';
  };

  if (panel) {
    fetch(new URL('release-stats.json', base), {cache: 'no-store'})
      .then(response => response.ok ? response.json() : null)
      .then(update)
      .catch(() => {});
  }
})();
