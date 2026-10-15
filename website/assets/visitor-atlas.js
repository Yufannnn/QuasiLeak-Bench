/* Only aggregate snapshots are public; provider API credentials stay in Actions. */
(() => {
  const base = new URL('.', document.currentScript.src);
  const atlas = document.getElementById('visitor-atlas');
  let map;
  const aliases = {'United States of America':'US','United Kingdom':'GB','Russia':'RU','S. Korea':'KR','N. Korea':'KP','Czechia':'CZ','Dem. Rep. Congo':'CD','Congo':'CG','Central African Rep.':'CF','Eq. Guinea':'GQ','S. Sudan':'SS','Dominican Rep.':'DO','Bosnia and Herz.':'BA','Solomon Is.':'SB','Falkland Is.':'FK','eSwatini':'SZ','W. Sahara':'EH','Taiwan':'TW','Palestine':'PS','Kosovo':'XK'};
  async function paintCountries(countries) {
    if (!atlas || !Array.isArray(countries) || !countries.length) return;
    if (!map) map = fetch(new URL('visitor-atlas.svg',base)).then(r=>r.ok?r.text():Promise.reject()).then(source=>{
      const svg = new DOMParser().parseFromString(source,'image/svg+xml').documentElement;
      if (svg.localName !== 'svg') throw Error('Invalid atlas map');
      svg.setAttribute('aria-label','Visitor countries. Shading represents recorded visits.');
      svg.removeAttribute('aria-labelledby');
      atlas.querySelector('.atlas-map').replaceChildren(document.importNode(svg,true));
      return atlas.querySelector('.atlas-map svg');
    });
    const svg = await map;
    const counts = new Map();
    const normalize = value => String(value).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
    const names = typeof Intl.DisplayNames === 'function' ? new Intl.DisplayNames(['en'],{type:'region'}) : null;
    let maximum = 1;
    for (const country of countries) {
      if (!Number.isFinite(country.visits) || country.visits <= 0) continue;
      counts.set(normalize(country.code),country.visits);
      counts.set(normalize(country.name),country.visits);
      if (names && /^[A-Z]{2}$/.test(country.code)) counts.set(normalize(names.of(country.code)),country.visits);
      maximum = Math.max(maximum,country.visits);
    }
    for (const path of svg.querySelectorAll('path')) {
      const title = path.querySelector('title');
      if (!title) continue;
      const name = path.dataset.countryName || title.textContent;
      path.dataset.countryName = name;
      const visits = counts.get(normalize(name)) || counts.get(normalize(aliases[name] || '')) || 0;
      if (visits) {
        path.dataset.visits = String(visits);
        path.style.fill = 'var(--lb-teal)';
        path.style.fillOpacity = String(0.35 + 0.65 * Math.log1p(visits) / Math.log1p(maximum));
        title.textContent = name + ': ' + visits.toLocaleString('en-US') + ' visits';
      } else {
        delete path.dataset.visits; path.style.fill = ''; path.style.fillOpacity = ''; title.textContent = name;
      }
    }
  }
  const update = stats => {
    if (!atlas || !stats || typeof stats !== 'object') return;
    let received = false;
    atlas.querySelectorAll('[data-visitor-stat]').forEach(element => {
      const value = stats[element.dataset.visitorStat];
      if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return;
      element.textContent = Math.floor(value).toLocaleString('en-US'); received = true;
    });
    if (received) {
      const status = document.getElementById('visitor-atlas-status');
      const generated = new Date(stats.generatedAt);
      status.textContent = Number.isFinite(generated.getTime()) ? 'Updated ' + generated.toLocaleDateString('en-US',{month:'short',day:'numeric',timeZone:'UTC'}) : 'Live';
      status.title = Number.isFinite(generated.getTime()) ? generated.toISOString() : '';
      atlas.dataset.analytics = 'live';
      paintCountries(stats.countryVisits).catch(()=>{});
    }
  };
  window.updateQuasiLeakVisitorAtlas = update;
  window.addEventListener('quasileak:visitor-stats', event => update(event.detail));
  if (atlas) fetch(new URL('visitor-stats.json',base),{cache:'no-store'}).then(r=>r.ok?r.json():null).then(stats=>{
    if (stats?.status === 'ok') update(stats);
  }).catch(()=>{});
})();
