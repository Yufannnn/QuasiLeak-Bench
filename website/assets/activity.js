/* Aggregate daily counts, reused from the Atlas; no additional provider requests. */
(() => {
  const card = document.getElementById('activity-card');
  if (!card) return;
  const base = new URL('.', document.currentScript.src);
  const grid = document.getElementById('activity-grid');
  const months = card.querySelector('.activity-months');
  const summary = document.getElementById('activity-summary');
  const status = document.getElementById('activity-status');
  const tooltip = document.getElementById('activity-tooltip');
  const launch = Date.parse('2026-10-16T04:27:00Z');
  const dayMs = 86400000;
  const dayKey = date => date.toISOString().slice(0, 10);
  const label = date => date.toLocaleDateString('en-US', {month:'short', day:'numeric', timeZone:'UTC'});
  let snapshot = null;

  function receive(stats) {
    if (!Array.isArray(stats?.daily) || !stats.daily.length) return false;
    const incoming = Date.parse(stats.generated_at || stats.generatedAt || '');
    const current = Date.parse(snapshot?.generated_at || snapshot?.generatedAt || '');
    if (Number.isFinite(current) && (!Number.isFinite(incoming) || incoming < current)) return false;
    snapshot = stats;
    render();
    return true;
  }

  function render() {
    const focusedDay = grid.contains(document.activeElement) ? document.activeElement.dataset.day : null;
    const now = new Date();
    const today = new Date(dayKey(now) + 'T00:00:00Z');
    const mondayOffset = (today.getUTCDay() + 6) % 7;
    const start = new Date(today.getTime() - (77 + mondayOffset) * dayMs);
    const values = new Map();
    let available = false;
    if (Array.isArray(snapshot?.daily) && snapshot.daily.length) {
      available = snapshot.daily.every(row => {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(row?.day || '') || !Number.isSafeInteger(row.views) || row.views < 0) return false;
        const parsed = new Date(row.day + 'T00:00:00Z');
        return Number.isFinite(parsed.getTime()) && dayKey(parsed) === row.day;
      });
      if (available && new Set(snapshot.daily.map(row=>row.day)).size !== snapshot.daily.length) available = false;
      if (available) for (const row of snapshot.daily) values.set(row.day, row.views);
    }
    const measured = [...values].filter(([day]) => day >= dayKey(start) && day <= dayKey(today));
    const peak = available ? Math.max(0, ...measured.map(([, views]) => views)) : 0;
    grid.replaceChildren(); months.replaceChildren();
    tooltip.hidden = true;
    grid.setAttribute('aria-label', 'Daily page views, Monday to Sunday, ' + label(start) + '–' + label(today) + ', UTC; 12 weeks');
    let previousMonth = -1;
    for (let week = 0; week < 12; week++) {
      const date = new Date(start.getTime() + week * 7 * dayMs);
      if (date.getUTCMonth() !== previousMonth) {
        const month = document.createElement('span');
        month.textContent = date.toLocaleDateString('en-US', {month:'short', timeZone:'UTC'});
        month.style.gridColumn = String(week + 1); months.append(month);
        previousMonth = date.getUTCMonth();
      }
      for (let weekday = 0; weekday < 7; weekday++) {
        const day = new Date(date.getTime() + weekday * dayMs);
        const key = dayKey(day), upcoming = day > today;
        const views = available && !upcoming ? (values.get(key) || 0) : 0;
        const cell = document.createElement('button');
        cell.type = 'button'; cell.className = 'activity-cell';
        cell.dataset.day = key;
        cell.dataset.level = String(!views ? 0 : Math.min(4, Math.max(1, Math.ceil(views / Math.max(1, peak) * 4))));
        if (key === dayKey(today)) cell.dataset.today = 'true';
        const description = label(day) + ' · ' + (upcoming ? 'Upcoming' : available && values.has(key) ? views.toLocaleString('en-US') + (views === 1 ? ' view' : ' views') : 'No data yet');
        cell.setAttribute('aria-label', description);
        cell.setAttribute('aria-describedby', 'activity-tooltip');
        const show = () => { tooltip.textContent = description; tooltip.hidden = false; };
        const hide = () => { tooltip.hidden = true; };
        cell.addEventListener('mouseenter', show); cell.addEventListener('mouseleave', hide);
        cell.addEventListener('focus', show); cell.addEventListener('blur', hide);
        cell.addEventListener('keydown', event => {
          const offset = {ArrowUp:-1, ArrowDown:1, ArrowLeft:-7, ArrowRight:7}[event.key];
          if (offset === undefined) return;
          event.preventDefault();
          const cells = [...grid.children], index = cells.indexOf(cell) + offset;
          if (cells[index]) cells[index].focus();
        });
        grid.append(cell);
      }
    }
    if (!available) {
      summary.textContent = 'Collecting since Oct 16'; status.textContent = 'Collecting'; status.dataset.live = 'false';
    } else {
      const hours = Math.max(0, Math.floor((now.getTime() - launch) / 3600000));
      summary.textContent = 'Today ' + (values.has(dayKey(today)) ? values.get(dayKey(today)).toLocaleString('en-US') : '—') +
        ' · Peak ' + peak.toLocaleString('en-US') + ' · Live ' + Math.floor(hours / 24) + 'd ' + hours % 24 + 'h';
      status.textContent = 'Live'; status.dataset.live = 'true';
      status.title = 'Daily aggregate snapshot: ' + (snapshot.generated_at || snapshot.generatedAt || '');
    }
    if (focusedDay) grid.querySelector(`[data-day="${focusedDay}"]`)?.focus();
  }
  async function refresh() {
    try {
      const result = await fetch(new URL('visitor-stats.json', base), {cache:'no-store', credentials:'omit'});
      if (!result.ok) throw Error('Snapshot unavailable');
      const stats = await result.json();
      receive(stats);
    } catch { /* Keep the last valid Atlas or static snapshot during an outage. */ }
    render();
  }
  window.addEventListener('quasileak:activity-stats', event => receive(event.detail));
  receive(window.quasiLeakVisitorStats);
  render(); refresh();
  setInterval(() => { if (!document.hidden) render(); }, 60000);
  // Six-hour static backup; live daily counts arrive with the Atlas's 30s refresh.
  setInterval(() => { if (!document.hidden) refresh(); }, 300000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
})();
