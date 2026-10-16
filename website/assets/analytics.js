/* Count only the public project site; no token, query strings or model inputs. */
(() => {
  const base = new URL('.', document.currentScript.src);
  fetch(new URL('analytics-config.json', base)).then(response => response.ok ? response.json() : null).then(config => {
    if (!config) return;
    if (location.hostname !== config.productionHostname || !location.pathname.startsWith(config.productionPath)) return;
    if (navigator.globalPrivacyControl || navigator.doNotTrack === '1') return;
    if (config.provider === 'cloudflare') {
      const endpoint = new URL(config.endpoint);
      if (endpoint.protocol !== 'https:' || !endpoint.hostname.endsWith('.workers.dev')) return;
      fetch(new URL('/visit', endpoint), {
        method: 'POST', headers: {'Content-Type': 'text/plain;charset=UTF-8'},
        body: JSON.stringify({path: location.pathname}), credentials: 'omit',
        referrerPolicy: 'origin', keepalive: true
      }).then(response => {
        if (response.status === 201) window.dispatchEvent(new Event('quasileak:visitor-recorded'));
      }).catch(() => {});
      return;
    }
    if (!/^[a-z0-9][a-z0-9-]*$/.test(config.site || '')) return;
    window.goatcounter = {path: () => location.pathname, referrer: () => {
      try { const url = new URL(document.referrer); return url.origin + url.pathname; } catch { return ''; }
    }};
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://gc.zgo.at/count.js';
    script.dataset.goatcounter = 'https://' + config.site + '.goatcounter.com/count';
    document.head.append(script);
  }).catch(() => {});
})();
