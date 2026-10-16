/* Requested headless QA. All analytics are intercepted fixtures, never sent. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');
const os = require('node:os');
const {chromium} = require(process.env.QLB_PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '../website');
const output = path.join(os.tmpdir(), 'qlb-activity-qa');
const types = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.svg':'image/svg+xml',
  '.json':'application/json', '.woff2':'font/woff2', '.png':'image/png', '.webp':'image/webp'};
const live = {status:'ok', provider:'cloudflare', generatedAt:'2026-10-18T08:27:00Z',
  pageViews:5, visitors:5, countries:1, countryVisits:[{code:'SG', name:'SG', visits:5}]};
const daily = Array.from({length:84}, (_,index) => ({
  day:new Date(Date.UTC(2026,9,18)-(83-index)*86400000).toISOString().slice(0,10),
  views:index===83 ? 12 : [0,1,13,25,48][index%5]
}));

(async () => {
  await fs.mkdir(output, {recursive:true});
  const server = http.createServer(async (request, response) => {
    try {
      const file = path.resolve(root, '.' + new URL(request.url,'http://localhost').pathname.replace(/\/$/,'/index.html'));
      if (!file.startsWith(root + path.sep)) throw Error('Outside website');
      response.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
      response.end(await fs.readFile(file));
    } catch { response.writeHead(404); response.end(); }
  });
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  const browser = await chromium.launch({headless:true});
  try {
    for (const width of [1440,1024,390]) for (const mode of ['light','dark']) for (const populated of [false,true]) {
      const context = await browser.newContext({viewport:{width,height:1100},colorScheme:mode});
      const page = await context.newPage(), errors = [];
      let todayViews=12, generatedAt=live.generatedAt;
      page.on('pageerror', error => errors.push(error.message));
      await page.clock.install({time:new Date('2026-10-18T08:27:00Z')});
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.pathname.endsWith('/visitor-stats.json')) return route.fulfill({json:{...live, daily:populated?daily:[], generated_at:live.generatedAt}});
        if (url.hostname.endsWith('.workers.dev')) return route.fulfill({json:url.pathname==='/stats'?{
          ...live,generatedAt,generated_at:generatedAt,daily:populated?daily.map(row=>row.day==='2026-10-18'?{...row,views:todayViews}:row):[]
        }:{
          status:'ok',provider:'cloudflare',generatedAt:live.generatedAt,github:{stars:2,forks:1},huggingFace:{downloads:3,likes:1}
        }});
        // Existing release-counter fallbacks may run when the virtual clock
        // advances through an API timeout; they remain intercepted, never sent.
        if (url.hostname==='api.github.com') return route.fulfill({json:{stargazers_count:2,forks_count:1}});
        if (url.hostname==='huggingface.co') return route.fulfill({json:{downloads:3,likes:1}});
        if (url.hostname!=='127.0.0.1') throw Error('Unexpected third-party request: '+url.origin);
        return route.continue();
      });
      await page.goto('http://127.0.0.1:'+server.address().port+'/index.html');
      await page.waitForFunction(() => document.querySelectorAll('.activity-cell').length===84 && document.querySelector('.atlas-marker'));
      await page.waitForFunction(populated => document.getElementById('activity-summary').textContent.startsWith(populated?'Today':'Collecting'),populated);
      const layout = await page.evaluate(() => {
        const row=document.querySelector('.public-pulse');
        const cards=[...row.children].map(element=>{const r=element.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};});
        const grid=document.querySelector('.activity-grid'), cell=grid.firstElementChild.getBoundingClientRect();
        const colours=[...new Set([...grid.children].map(element=>getComputedStyle(element).backgroundColor))];
        const dot=document.querySelector('.atlas-marker');
        return {cards,scroll:document.documentElement.scrollWidth,viewport:innerWidth,
          columns:getComputedStyle(grid).gridTemplateColumns.split(' ').length,
          rows:getComputedStyle(grid).gridTemplateRows.split(' ').length,cell:{width:cell.width,height:cell.height},
          colours,summary:document.getElementById('activity-summary').textContent,
          theme:document.documentElement.dataset.researchTheme,marker:[Number(dot.getAttribute('cx')),Number(dot.getAttribute('cy'))]};
      });
      assert.equal(layout.scroll,layout.viewport,'No horizontal page overflow');
      assert.equal(layout.columns,12); assert.equal(layout.rows,7);
      assert.ok(Math.abs(layout.cell.width-layout.cell.height)<1,'Square cells');
      assert.equal(layout.theme,mode); assert.deepEqual(layout.marker,[709.6,209.1]);
      if(width===1440) {
        assert.ok(Math.max(...layout.cards.map(c=>c.height))-Math.min(...layout.cards.map(c=>c.height))<1,'Equal desktop heights');
        assert.ok(layout.cards.every(c=>Math.abs(c.y-layout.cards[0].y)<1));
      } else if(width===1024) {
        assert.ok(layout.cards[1].y>layout.cards[0].y);
        assert.ok(Math.abs(layout.cards[1].y-layout.cards[2].y)<1,'Tablet lower pair');
      } else {
        assert.ok(layout.cards[0].y<layout.cards[1].y && layout.cards[1].y<layout.cards[2].y);
        assert.ok(layout.cards.every(c=>Math.abs(c.x-16)<1 && Math.abs(c.width-(width-32))<1),'16px phone gutters');
      }
      assert.equal(layout.summary,populated?'Today 12 · Peak 48 · Live 2d 4h':'Collecting since Oct 16');
      if(populated) assert.equal(layout.colours.length,5,'Five distinct theme colours');
      else assert.equal(layout.colours.length,1,'Unconfigured cells empty');
      const today=page.locator('.activity-cell[data-today=true]');
      await today.focus();
      assert.match(await page.locator('#activity-tooltip').innerText(), populated?/Oct 18 · 12 views/:/No data yet/);
      await page.clock.runFor(60000);
      assert.equal(await page.locator(':focus').getAttribute('data-day'),'2026-10-18','Timer preserves keyboard focus');
      await page.keyboard.press('ArrowLeft');
      assert.equal(await page.locator(':focus').getAttribute('data-day'),'2026-10-11');
      assert.deepEqual(errors,[],'No JavaScript errors');
      await page.locator('.public-pulse').screenshot({path:path.join(output,`${width}-${mode}-${populated?'populated':'empty'}.png`),
        style:'.site-header{visibility:hidden!important}.activity-tooltip{visibility:hidden!important}'});
      if(width===1440 && mode==='light' && populated) {
        todayViews=17; generatedAt='2026-10-18T08:28:30Z';
        await page.clock.runFor(30000);
        await page.waitForFunction(()=>document.getElementById('activity-summary').textContent.startsWith('Today 17'));
        await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
        await page.waitForTimeout(100);
        assert.match(await page.locator('#activity-summary').innerText(),/^Today 17/,'Old static snapshots must not overwrite live counts');
        const oldColour=await page.locator('.activity-cell[data-level="4"]').first().evaluate(element=>getComputedStyle(element).backgroundColor);
        await page.emulateMedia({colorScheme:'dark'});
        await page.waitForFunction(()=>document.documentElement.dataset.researchTheme==='dark');
        assert.notEqual(await page.locator('.activity-cell[data-level="4"]').first().evaluate(element=>getComputedStyle(element).backgroundColor),oldColour);
        await page.locator('[data-theme-toggle]').click();
        assert.equal(await page.locator('html').getAttribute('data-research-theme'),'light');
        await page.clock.runFor(59*60000);
        assert.match(await page.locator('#activity-summary').innerText(),/Live 2d 5h$/);
        await page.clock.setFixedTime(new Date('2026-10-16T08:27:00Z'));
        await page.clock.runFor(60000);
        assert.equal(await page.locator('.activity-cell[data-today=true]').getAttribute('data-day'),'2026-10-16');
        assert.match(await page.locator('.activity-cell[data-day="2026-10-17"]').getAttribute('aria-label'),/Upcoming/);
        assert.equal(await page.locator('.activity-cell[data-day="2026-10-17"]').getAttribute('data-level'),'0');
        assert.deepEqual(errors,[]);
      }
      console.log(JSON.stringify({width,mode,populated,...layout}));
      await context.close();
    }
    console.log('All 12 responsive/theme/data checks passed. Screenshots: '+output);
  } finally {
    await browser.close(); await new Promise(resolve=>server.close(resolve));
  }
})().catch(error=>{console.error(error);process.exit(1);});
