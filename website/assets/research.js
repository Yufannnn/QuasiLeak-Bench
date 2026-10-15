/* Shared, static research views. All charts use recorded results. */
(() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const metrics = [['pgf1','P-GF1','Policy group F1'],['pgp','P-GP','Policy group precision'],['pgr','P-GR','Policy group recall'],['egf1','E-GF1','Evidence group F1'],['dsr','DSR','Distractor selection rate'],['bg','B_G','Group purity'],['ba','B_A','Attribute binding'],['el','E_L','Localization purity'],['ec','E_C','Composition completeness'],['npred','N_pred','Number of predicted groups'],['far','FAR','False-alarm rate']];
  const format = (value, key) => value == null ? '\u2014' : key === 'npred' ? Math.round(value).toLocaleString('en-US') : Number(value).toFixed(1);
  const condition = row => row.method === 'trained' ? `${row.regime} \u00b7 lr ${row.lr} \u00b7 ${row.seeds.length} ${row.seeds.length===1?'seed':'seeds'}` : `${row.regime} \u00b7 Think ${row.think == null?'unreported':row.think?'on':'off'}`;
  const size = row => row.size_b == null ? '\u2014' : row.size_b + 'B';
  // Model availability is distinct from the inference route stored in row.access.
  // DeepSeek publishes weights: https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro
  const proprietaryModels = new Set(['gpt-5.6-sol','claude-opus-5','gemini-3.8-flash','grok-4.5']);
  const deployment = row => row.access === 'weights' || row.model_id === 'deepseek-v4-pro' ? 'Open-weight' : proprietaryModels.has(row.model_id) ? 'Proprietary' : 'Not reported';
  const runUrl = (row, view) => `run.html?set=${view}&id=${encodeURIComponent(row.id)}`;
  const repo = 'https://github.com/Yufannnn/QuasiLeak-Bench';
  const VIEWS = {test:'QLB-Test · 1,000 documents / 100 profiles',full:'QLB-Full · 5,000 documents / 500 profiles',nonrevealing:'QLB-SNR · 1,618 documents / Subset Non-Revealing',policyshift:'QLB-PS · 500 policy-study pairs, reassigned policy'};
  const allRows = view => (recordedScores[view] || []).flatMap(row=>[row,...(row.alternatives||[])]);
  function download(name, value) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value,null,2)+'\n'],{type:'application/json'}));
    const a = document.createElement('a'); a.href=url;a.download=name;a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function details(row, view) {
    const param = row.scorer_parameters;
    const corpusHash = row.evaluation.corpus_sha256 || (researchData.diagnostics[row.id] ? researchData.historical_corpus_sha256 : null);
    return `<div class="run-heading"><div><h1>${esc(row.name)}</h1><p>${esc(condition(row))}</p></div><span class="source-badge">${esc(row.result_origin)}</span></div>
      <div class="run-summary">${metrics.slice(0,5).map(([key,label,title])=>`<div><span title="${title}">${label}</span><strong>${format(row[key],key)}</strong></div>`).join('')}</div>
      <div class="run-grid"><section class="research-card"><h2>Configuration</h2><dl class="definition-list">
      ${[['Evaluation',VIEWS[view]],['Base model',row.model_id],['Size',size(row)],['Model type',deployment(row)],['Method',row.method==='trained'?'Task-specific supervision':'Prompted'],['Condition',condition(row)],['Reasoning configuration',row.think==null?'Not reported':`Think ${row.think?'enabled':'disabled'}; further effort settings not recorded in this summary`],['Training exposure',row.method==='trained'?'QuasiLeak-Bench training partition; held-out Test profiles':'Prompted reference; no task-specific fine-tuning in this condition'],['Seeds',row.seeds?.join(', ') ?? 'Not reported'],['P-GF1 seed SD',row.sd==null?'Not reported':format(row.sd)],['Result status',row.verification]].map(([label,value])=>`<div><dt>${label}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl></section>
      <section class="research-card"><h2>Provenance</h2><p>${esc(row.note)}</p>${param?`<p>Scorer parameters: \u03b8 = ${param.iou}, \u03b3 = ${param.gamma}, secondary credit = ${param.rho_sec}, KEEP penalty = ${param.lambda_k}.</p>`:'<p>Scorer parameters are not stored in this summary.</p>'}<p>Scorer commit: ${esc(row.run_provenance?.scorer_commit ?? 'not recorded')}.</p>${corpusHash?`<details><summary>Evaluation snapshot</summary><p>Historical corpus SHA-256</p><code class="hash-code">${esc(corpusHash)}</code>${row.evaluation.split_sha256?`<p>Profile split SHA-256</p><code class="hash-code">${esc(row.evaluation.split_sha256)}</code>`:''}</details>`:''}<details class="result-source"><summary>Recorded source files</summary>${row.source_records.map(p=>`<p><code>${esc(p.path)}</code><code class="hash-code">SHA-256 ${p.sha256}</code></p>`).join('')}${row.sources.filter(p=>!row.source_records.some(r=>r.path===p)).map(p=>`<p><code>${esc(p)}</code></p>`).join('')}</details><div class="run-actions"><button class="button secondary" data-download-run="${esc(row.id)}" data-view="${view}">Download result</button><a class="text-link" href="${repo}" target="_blank" rel="noopener">Code &nearr;</a></div></section></div>
      <details class="research-card"><summary>More metrics</summary><dl class="definition-list">${metrics.slice(5).map(([key,label,title])=>`<div><dt title="${title}">${label}</dt><dd>${format(row[key],key)}</dd></div>`).join('')}</dl></details>
      ${row.alternatives?.length?`<details class="research-card"><summary>Other learning rates</summary><div class="table-scroll"><table class="compare-table"><thead><tr><th>Learning rate</th><th>Seeds</th><th>P-GF1</th><th>P-GP</th><th>P-GR</th><th>E-GF1</th></tr></thead><tbody>${row.alternatives.map(r=>`<tr><td>${esc(r.lr)}</td><td>${r.seeds.length}</td><td>${format(r.pgf1)}</td><td>${format(r.pgp)}</td><td>${format(r.pgr)}</td><td>${format(r.egf1)}</td></tr>`).join('')}</tbody></table></div></details>`:''}`;
  }
  function interval(a,b) {
    const direct = researchData.paired_intervals[`${a.id}|${b.id}`];
    const reverse = researchData.paired_intervals[`${b.id}|${a.id}`];
    return direct || (reverse ? [-reverse[1],-reverse[0]] : null);
  }
  function comparison(rows, view) {
    const first=rows[0];
    const chartKeys=[['egf1','Evidence recovery','E-GF1'],['ba','Attribute binding','B_A'],['pgf1','Policy recovery','P-GF1']];
    const charts=chartKeys.map(([key,title,label])=>`<section class="research-card comparison-chart"><h2>${title}</h2><span class="chart-metric">${label} \u00b7 0\u2013100</span>${rows.map((row,index)=>`<div class="chart-row"><span>${esc(row.name)}<small>${esc(condition(row))}</small></span><div class="bar-track"><i class="series-${index}" style="width:${Math.max(0,Math.min(100,row[key]??0))}%"></i></div><b>${format(row[key])}</b></div>`).join('')}</section>`).join('');
    const diffs=rows.slice(1).map(row=>{const ci=interval(row,first);return `<tr><th>${esc(row.name)}<small>${esc(condition(row))}</small></th><td>${format(row.pgf1-first.pgf1)}</td><td>${ci?`${ci[0].toFixed(1)} to ${ci[1].toFixed(1)}`:'Not available'}</td></tr>`;}).join('');
    const fields=[['Condition',condition],['Size',size],['Model type',deployment],...metrics.map(([key,label])=>[label,r=>format(r[key],key)]),['Seed SD',r=>format(r.sd)],['Source',r=>r.result_origin]];
    return `<p class="comparison-context">${VIEWS[view]} \u00b7 ${rows.length} recorded conditions</p><div class="comparison-systems">${rows.map((row,i)=>`<a class="research-card" href="${runUrl(row,view)}"><span class="series-dot series-${i}"></span><h2>${esc(row.name)}</h2><p>${esc(condition(row))}</p><span>${deployment(row)} \u00b7 ${size(row)}</span></a>`).join('')}</div>${charts}
      <section class="research-card"><h2>Score difference</h2><p>Relative to ${esc(first.name)} (${esc(condition(first))}).</p><div class="table-scroll"><table class="compare-table"><thead><tr><th>Condition</th><th>P-GF1 difference</th><th>Paired 95% interval</th></tr></thead><tbody>${diffs}</tbody></table></div><p class="small-copy">Intervals use 2,000 paired bootstrap samples of profiles, preserving all documents within each profile. They describe matched recorded conditions; seed SD is a separate measure. A small score difference alone does not establish superiority.</p></section>
      <section class="research-card"><h2>Breakdowns</h2><label class="filter-field">Graded recall by<select id="breakdown-dimension"><option value="arity">Group size</option><option value="attribute">Attribute</option><option value="distance">Cue distance</option></select></label><div id="comparison-breakdowns"></div><p class="small-copy">P-GR by gold group category. Missing cells mean that this condition has no matching saved per-document diagnostics.</p></section>
      <details class="research-card"><summary>All metrics</summary><div class="table-scroll"><table class="compare-table"><thead><tr><th>Metric</th>${rows.map(row=>`<th>${esc(row.name)}</th>`).join('')}</tr></thead><tbody>${fields.map(([label,get])=>`<tr><th>${label}</th>${rows.map(row=>`<td>${esc(get(row))}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`;
  }
  function breakdowns(rows,dimension) {
    const keys=[...new Set(rows.flatMap(row=>Object.keys(researchData.diagnostics[row.id]?.[dimension]||{})))].sort();
    if (!keys.length) return '<p>No saved breakdown for these conditions.</p>';
    const labels={sex:'Gender',arity:'Group size'};
    return `<div class="table-scroll"><table class="compare-table heatmap"><thead><tr><th>${dimension==='arity'?'Cues':dimension==='attribute'?'Attribute':'Distance'}</th>${rows.map(row=>`<th>${esc(row.name)}</th>`).join('')}</tr></thead><tbody>${keys.map(key=>`<tr><th>${esc(labels[key]||key[0].toUpperCase()+key.slice(1))}</th>${rows.map(row=>{const cell=researchData.diagnostics[row.id]?.[dimension]?.[key];return `<td>${cell?`<span class="heat-cell" style="--strength:${cell.recall/100}">${format(cell.recall)}</span><small>${cell.groups} groups</small>`:'\u2014'}</td>`;}).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  window.QLB = {esc,metrics,format,condition,size,deployment,runUrl,details,download,allRows};
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-download-run]');if(!button)return;
    const row=allRows(button.dataset.view).find(r=>r.id===button.dataset.downloadRun);
    if(row)download(row.id+'.json',row);
  });
  const params=new URLSearchParams(location.search);
  const view=Object.hasOwn(recordedScores,params.get('set')||'')?params.get('set'):'test';
  const run=document.querySelector('#run-content');
  if(run){const row=allRows(view).find(r=>r.id===params.get('id'));run.innerHTML=row?details(row,view)+(view==='full'&&row.regime==='few-shot'&&row.run_provenance?.predictions?`<p><a class="text-link" href="explore.html?model=${encodeURIComponent(row.id)}">Explore a recorded prediction &rarr;</a></p>`:'')+'<a class="text-link" href="index.html#'+view+'">Back to '+(view==='test'?'QLB-Test':'QLB-Full')+' &rarr;</a>':'<h1>Result unavailable</h1><p>Select a recorded condition from the leaderboard.</p>';if(row)document.title=row.name+' \u00b7 QuasiLeak-Bench';}
  const compare=document.querySelector('#comparison-content');
  if(compare){const ids=[...new Set((params.get('runs')||'').split(','))];const rows=ids.map(id=>allRows(view).find(r=>r.id===id)).filter(Boolean).slice(0,4);compare.innerHTML=rows.length>=2?comparison(rows,view):'<p>Select two to four conditions from one evaluation set.</p>';if(rows.length>=2){const render=()=>document.querySelector('#comparison-breakdowns').innerHTML=breakdowns(rows,document.querySelector('#breakdown-dimension').value);document.querySelector('#breakdown-dimension').addEventListener('change',render);render();}}
  document.querySelectorAll('[data-figure-open]').forEach(link=>link.addEventListener('click',event=>{event.preventDefault();const modal=document.querySelector('#figure-dialog');modal.classList.remove('native-size');document.querySelector('#figure-zoom').textContent='Actual size';document.querySelector('#figure-zoom').setAttribute('aria-pressed','false');modal.showModal();document.querySelector('.figure-viewer').scrollTo(0,0);}));
  document.querySelector('#figure-zoom')?.addEventListener('click',event=>{const native=document.querySelector('#figure-dialog').classList.toggle('native-size');event.target.textContent=native?'Fit to window':'Actual size';event.target.setAttribute('aria-pressed',String(native));});
  document.querySelectorAll('.close-dialog').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));
  document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('click',event=>{if(event.target!==dialog)return;const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}));
})();
