/* Only aggregate snapshots are public; provider API credentials stay in Actions. */
(() => {
  const base = new URL('.', document.currentScript.src);
  const atlas = document.getElementById('visitor-atlas');
  let map;
  let hadLiveData = false;
  const aliases = {'United States of America':'US','United Kingdom':'GB','Russia':'RU','S. Korea':'KR','N. Korea':'KP','Czechia':'CZ','Dem. Rep. Congo':'CD','Congo':'CG','Central African Rep.':'CF','Eq. Guinea':'GQ','S. Sudan':'SS','Dominican Rep.':'DO','Bosnia and Herz.':'BA','Solomon Is.':'SB','Falkland Is.':'FK','eSwatini':'SZ','W. Sahara':'EH','Taiwan':'TW','Palestine':'PS','Kosovo':'XK'};
  async function paintCountries(countries) {
    if (!atlas || !Array.isArray(countries) || !countries.length) return;
    if (!map) map = fetch(new URL('visitor-atlas.svg',base)).then(r=>r.ok?r.text():Promise.reject()).then(source=>{
      const svg = new DOMParser().parseFromString(source,'image/svg+xml').documentElement;
      if (svg.localName !== 'svg') throw Error('Invalid atlas map');
      svg.setAttribute('aria-label','Country-level page views. Dots mark approximate country locations, not visitor addresses.');
      svg.style.width = '100%';
      svg.style.height = 'auto';
      svg.removeAttribute('aria-labelledby');
      const description = svg.querySelector('desc');
      if (description) description.textContent = 'Shading and dots show aggregate country-level page views. Dot positions are approximate.';
      atlas.querySelector('.atlas-map').replaceChildren(document.importNode(svg,true));
      return atlas.querySelector('.atlas-map svg');
    });
    const svg = await map;
    svg.querySelector('.atlas-markers')?.remove();
    const markers = document.createElementNS('http://www.w3.org/2000/svg','g');
    markers.setAttribute('class','atlas-markers');
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
        title.textContent = name + ': ' + visits.toLocaleString('en-US') + ' page views';
      } else {
        delete path.dataset.visits; path.style.fill = ''; path.style.fillOpacity = ''; title.textContent = name;
      }
    }
    // This low-resolution outline omits Singapore and other small states.
    // Singapore is anchored on the map's equirectangular projection; other
    // countries use the centre of their largest polygon, not a visitor location.
    const paths = [...svg.querySelectorAll('path')];
    for (const country of countries) {
      if (!Number.isFinite(country.visits) || country.visits <= 0) continue;
      let point = country.code === 'SG' ? [709.6,209.1] : null;
      const displayName = names && /^[A-Z]{2}$/.test(country.code) ? names.of(country.code) : country.name;
      if (!point) {
        const path = paths.find(path => {
          const name = path.dataset.countryName || '';
          return normalize(name) === normalize(displayName) || normalize(name) === normalize(country.name) || aliases[name] === country.code;
        });
        let largest = 0;
        for (const polygon of (path?.getAttribute('d') || '').split('M')) {
          const numbers = polygon.match(/-?\d+(?:\.\d+)?/g)?.map(Number) || [];
          if (numbers.length < 6) continue;
          const xs = numbers.filter((_,i)=>i%2===0), ys = numbers.filter((_,i)=>i%2===1);
          const x0=Math.min(...xs), x1=Math.max(...xs), y0=Math.min(...ys), y1=Math.max(...ys);
          const area=(x1-x0)*(y1-y0);
          if(area>largest){largest=area;point=[(x0+x1)/2,(y0+y1)/2];}
        }
      }
      if (!point) continue;
      const marker=document.createElementNS('http://www.w3.org/2000/svg','g');
      const title=document.createElementNS('http://www.w3.org/2000/svg','title');
      title.textContent=displayName+': '+country.visits.toLocaleString('en-US')+' page views (approximate country location)';
      marker.append(title);
      for(const [radius,style] of [[9,'atlas-marker-halo'],[4.5,'atlas-marker']]){
        const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');
        circle.setAttribute('cx',String(point[0]));circle.setAttribute('cy',String(point[1]));
        circle.setAttribute('r',String(radius));circle.setAttribute('class',style);marker.append(circle);
      }
      markers.append(marker);
    }
    svg.append(markers);
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
      atlas.querySelectorAll('[data-visitor-label]').forEach(element => {
        const country = element.dataset.visitorLabel === 'countries';
        const value = stats[country ? 'countries' : 'pageViews'];
        element.textContent = country ? (value === 1 ? 'country' : 'countries') : (value === 1 ? 'view' : 'views');
      });
      const status = document.getElementById('visitor-atlas-status');
      const generated = new Date(stats.generatedAt);
      status.textContent = stats.provider === 'cloudflare' ? 'Live' : (Number.isFinite(generated.getTime()) ? 'Updated ' + generated.toLocaleDateString('en-US',{month:'short',day:'numeric',timeZone:'UTC'}) : 'Live');
      status.dataset.live = String(stats.provider === 'cloudflare');
      status.title = stats.collectedSince ? 'Page views recorded since ' + stats.collectedSince : (Number.isFinite(generated.getTime()) ? generated.toISOString() : '');
      atlas.dataset.analytics = 'live';
      if (stats.provider === 'cloudflare') hadLiveData = true;
      if (Array.isArray(stats.daily) && stats.daily.length) {
        window.quasiLeakVisitorStats = stats;
        window.dispatchEvent(new CustomEvent('quasileak:activity-stats', {detail:stats}));
      }
      paintCountries(stats.countryVisits).catch(()=>{});
    }
  };
  window.updateQuasiLeakVisitorAtlas = update;
  window.addEventListener('quasileak:visitor-stats', event => update(event.detail));
  const config = fetch(new URL('analytics-config.json',base),{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null);
  async function refresh() {
    const settings = await config;
    const endpoint = settings?.provider === 'cloudflare' ? new URL('/stats',settings.endpoint) : new URL('visitor-stats.json',base);
    try {
      const response = await fetch(endpoint,{cache:'no-store',credentials:'omit',referrerPolicy:'origin',signal:AbortSignal.timeout(10000)});
      if (!response.ok) throw Error('Atlas unavailable');
      const stats = await response.json();
      if (stats?.status !== 'ok') throw Error('Invalid Atlas data');
      update({...stats,provider:settings?.provider === 'cloudflare'?'cloudflare':'snapshot'});
    } catch {
      if (hadLiveData) {
        document.getElementById('visitor-atlas-status').textContent = 'Refresh delayed';
        document.getElementById('visitor-atlas-status').dataset.live = 'false';
        return;
      }
      const response = await fetch(new URL('visitor-stats.json',base),{cache:'no-store'});
      if (response.ok) { const stats=await response.json(); if(stats?.status==='ok') update({...stats,provider:'snapshot'}); }
    }
  }
  window.addEventListener('quasileak:visitor-recorded',()=>refresh().catch(()=>{}));
  if (atlas) {
    refresh().catch(()=>{});
    setInterval(()=>{if(!document.hidden) refresh().catch(()=>{});},30000);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden) refresh().catch(()=>{});});
  }
})();
