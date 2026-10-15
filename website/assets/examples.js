/* One original release record. UI exploration never writes to the corpus. */
(() => {
  const $ = selector => document.querySelector(selector);
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels = {age:'Age',sex:'Gender',nationality:'Nationality',education:'Education',occupation:'Occupation',income:'Income',relationship:'Relationship',health:'Health'};
  const icon = key => `<svg class="input-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="assets/icons/interactive-example/glyphs/sprite.svg#${key==='sex'?'gender':key}"></use></svg>`;
  document.querySelectorAll('[data-example-icon]').forEach(element=>{element.innerHTML=icon(element.dataset.exampleIcon);});
  function renderProfile() {
    $('#profile-number').textContent = 'Profile #' + record.profile.profile_id.replace(/^synthpai_pers/, '');
    $('#corpus-profile').innerHTML = `<dl class="attribute-tiles">${['age','sex','nationality','relationship','education','occupation','income','health'].map(key=>`<div class="attribute-tile"><dt>${icon(key)}<span>${labels[key]}</span></dt><dd>${escape(record.profile[key])}</dd></div>`).join('')}</dl>`;
  }
  const selected = new Set();
  const selectedDecoys = new Set();
  let record, group, policies, originalPolicies, mode = 'gold', storedPredictions = [];
  const goldSpans = () => record.gold.spans.filter(span => group.cue_ids.includes(span.span_id));

  function renderDocument() {
    const chars = Array.from(record.document);
    const spans = [...goldSpans(), ...($('#show-decoys').checked ? record.gold.decoys.map(d=>({...d,span_id:d.decoy_id,decoy:true})) : [])].sort((a,b) => a.start - b.start);
    let cursor = 0, html = '';
    for (const span of spans) {
      html += escape(chars.slice(cursor,span.start).join(''));
      html += span.decoy ? `<button class="cue decoy-cue" data-decoy="${escape(span.span_id)}" aria-pressed="${selectedDecoys.has(span.span_id)}" title="Annotated distractor">${escape(chars.slice(span.start,span.end).join(''))}</button>` : `<button class="cue" data-cue="${escape(span.span_id)}" aria-pressed="${selected.has(span.span_id)}" title="${escape(labels[group.attribute])} evidence">${escape(chars.slice(span.start,span.end).join(''))}</button>`;
      cursor = span.end;
    }
    html += escape(chars.slice(cursor).join(''));
    $('#corpus-document-text').innerHTML = html;
    $('#document-meta').textContent = `${goldSpans().length} cues · ${group.distance.toLowerCase()} distance`;
  }

  function renderPolicy() {
    const changed = Object.keys(labels).some(attribute => policies[attribute] !== originalPolicies[attribute]);
    $('#policy-origin').textContent = changed ? 'Exploratory policy · original record unchanged' : 'Original corpus policy';
    $('#restore-policy').disabled = !changed;
    $('#corpus-policy').innerHTML = ['hide','keep','neutral'].map(kind => `<section class="policy-lane ${kind}"><h3>${icon(kind)}<span>${kind.toUpperCase()}</span></h3><div class="policy-lane-attributes">${Object.keys(labels).filter(a => policies[a] === kind).map(a => `<span class="attribute-chip">${escape(labels[a])}</span>`).join('') || '<span class="empty-policy-lane">No attributes assigned</span>'}</div></section>`).join('');
    $('#policy').value = policies[group.attribute];
  }

  function renderOutput() {
    const spans = goldSpans();
    const complete = spans.every(span => selected.has(span.span_id));
    const policy = policies[group.attribute];
    const report = complete && policy === 'hide';
    const value = record.profile[group.attribute];
    $('#demo-output').classList.toggle('complete',complete);
    let description;
    if (!complete) description = 'Select every highlighted cue to recover this annotated group.';
    else if (report) description = `The complete group supports ${labels[group.attribute].toLowerCase()}: ${value}. The current HIDE policy calls for reporting it.`;
    else description = `The complete group supports ${labels[group.attribute].toLowerCase()}: ${value}. Its ${policy.toUpperCase()} status means it is not a prohibited disclosure.`;
    $('#demo-output').innerHTML = `<div class="progress-cues" aria-hidden="true">${spans.map(span => `<i class="${selected.has(span.span_id)?'on':''}"></i>`).join('')}</div><strong>${complete?'Complete group · '+policy.toUpperCase():selected.size+' / '+spans.length+' cues selected'}</strong><p>${escape(description)}</p>${complete?`<code>${report?escape(group.attribute+' → report '+spans.length+' evidence spans'):'No reportable group for this attribute'}</code>`:''}`;
    const matched = selected.size, ec = (matched / spans.length) ** 2, junk = selectedDecoys.size;
    const el = matched + junk ? matched / (matched + junk) : 0;
    $('#example-score').innerHTML = `<dl class="definition-list">${[['Selected cues',matched+' / '+spans.length],['Distractors',junk],['E_C',ec.toFixed(3)],['E_L',el.toFixed(3)],['B_G',matched?'1.000':'0.000'],['B_A','1.000'],['Policy',policy.toUpperCase()],['Policy credit',policy==='hide'?(ec*el).toFixed(3):'0.000']].map(([label,value])=>`<div><dt>${label}</dt><dd>${value}</dd></div>`).join('')}</dl><p class="small-copy">Exact annotated spans and the correct attribute. Completeness is (selected / total cues)²; including distractors reduces localization purity. This illustrates one group, not a corpus P-GF1 score.</p>`;
  }

  function renderPrediction() {
    const result = storedPredictions.find(p => p.id === $('#example-model').value);
    if (!result) { $('#prediction-output').textContent = 'No stored prediction for this example.'; return; }
    const evidence = result.evidence;
    // Highlight the final returned text spans, coalescing overlaps for readable HTML.
    const ranges = [];
    for (const item of evidence) for (const span of item.spans) {
      const text = typeof span === 'string' ? span : span.text;
      if (!text) continue;
      let start = record.document.indexOf(text);
      while (start >= 0) { ranges.push([start,start+text.length]);start=record.document.indexOf(text,start+text.length); }
    }
    ranges.sort((a,b)=>a[0]-b[0]);
    const merged = [];
    for (const range of ranges) { const last=merged[merged.length-1];if(last&&range[0]<=last[1])last[1]=Math.max(last[1],range[1]);else merged.push([...range]); }
    let cursor=0,html='';
    for (const [start,end] of merged) { html+=escape(record.document.slice(cursor,start))+`<mark class="predicted-cue">${escape(record.document.slice(start,end))}</mark>`;cursor=end; }
    $('#corpus-document-text').innerHTML = html+escape(record.document.slice(cursor));
    $('#document-meta').textContent = `${evidence.length} predicted groups · original policy`;
    const matched=result.scored.matched||[];
    const failures = [];
    if(result.scored.n_keep_flag) failures.push('The scorer charges predicted KEEP information as permitted-disclosure flags.');
    if(matched.some(m=>m.E_C<1)) failures.push('Incomplete groups: some supporting cues were missed.');
    if(matched.some(m=>m.E_L<1)) failures.push('Imprecise localization: predicted spans include non-evidence text.');
    if(matched.some(m=>m.B_G<1)) failures.push('Mixed groups: spans from distinct gold groups were combined.');
    if(matched.some(m=>m.B_A<1)) failures.push('Attribute binding lost credit.');
    if(result.scored.n_gold===0) failures.push(evidence.length?'The original policy has no reportable HIDE groups.':'The original policy has no reportable HIDE groups; an empty output is correct.');
    $('#prediction-output').innerHTML = `<div class="prediction-score">${['P-GF1','P-GP','P-GR'].map(key=>`<div><span>${key}</span><strong>${(100*result.scored[key]).toFixed(1)}</strong></div>`).join('')}</div><p class="small-copy">${result.scored.n_gold} HIDE gold groups; ${result.scored.n_pred} scored predictions; ${result.scored.n_keep_flag||0} KEEP flags.</p>${failures.map(text=>`<p class="small-copy">${escape(text)}</p>`).join('')}${evidence.map(item=>`<div class="prediction-group"><strong>${escape(labels[item.attribute]||item.attribute)}</strong><span class="model-badge">${escape((originalPolicies[item.attribute]||'unreported').toUpperCase())}</span><ul>${item.spans.map(span=>`<li>${escape(typeof span==='string'?span:span.text||JSON.stringify(span))}</li>`).join('')}</ul></div>`).join('')||'<p>No groups returned.</p>'}${matched.map(match=>`<div class="match-credit"><strong>Recorded alignment</strong><p>E_C ${match.E_C.toFixed(3)} · E_L ${match.E_L.toFixed(3)} · B_G ${match.B_G.toFixed(3)} · B_A ${match.B_A.toFixed(3)} · policy credit ${Number(match.c_P??match.c).toFixed(3)}</p></div>`).join('')}<details><summary>Stored output</summary><pre>${escape(JSON.stringify(evidence,null,2))}</pre><code class="hash-code">${escape(result.source)}</code></details><p class="small-copy">Recorded Full few-shot output on this exact document. Predictions are fixed; no model is called by this page.</p>`;
  }

  function chooseMode(next) {
    mode=next;
    document.querySelectorAll('[data-explore-mode]').forEach(button=>{const active=button.dataset.exploreMode===mode;button.classList.toggle('primary',active);button.classList.toggle('secondary',!active);button.setAttribute('aria-pressed',String(active));});
    $('#prediction-panel').hidden=mode!=='predictions';$('#score-panel').hidden=mode!=='score';
    $('.corpus-interaction-card:has(#evidence-group)').hidden=mode==='predictions';
    $('#restore-policy').hidden=mode==='predictions';$('#reset-cues').hidden=mode==='predictions';
    $('#show-decoys').closest('label').hidden=mode==='predictions';
    if(mode==='predictions'){policies={...originalPolicies};renderPolicy();renderPrediction();}
    else {renderDocument();renderPolicy();renderOutput();}
  }

  async function load() {
    const response = await fetch('assets/corpus-example.json');
    if (!response.ok) throw Error('The source example could not be loaded.');
    const data = await response.json();record = data.record;
    const predictionResponse = await fetch('assets/example-predictions.json');
    if (!predictionResponse.ok) throw Error('Stored example predictions could not be loaded.');
    const predictionData = await predictionResponse.json();
    if(predictionData.document_sha256!==data.document_sha256) throw Error('Prediction snapshot does not match the displayed document.');
    storedPredictions=predictionData.predictions;
    $('#example-model').innerHTML=storedPredictions.map(p=>`<option value="${escape(p.id)}">${escape(p.name)} · few-shot</option>`).join('');
    $('#example-model').addEventListener('change',renderPrediction);
    document.querySelectorAll('[data-explore-mode]').forEach(button=>button.addEventListener('click',()=>chooseMode(button.dataset.exploreMode)));
    const chars = Array.from(record.document);
    for (const span of record.gold.spans) {
      if (chars.slice(span.start,span.end).join('') !== span.text) throw Error('The example spans do not match the source text.');
    }
    originalPolicies = {};
    for (const kind of ['hide','keep','neutral']) for (const attribute of record.policy[kind]) originalPolicies[attribute] = kind;
    if (Object.keys(labels).some(attribute => !originalPolicies[attribute])) throw Error('The source policy is incomplete.');
    policies = {...originalPolicies};
    group = record.gold.groups.find(g => g.attribute === 'nationality') || record.gold.groups[0];
    renderProfile();
    $('#corpus-recipient').textContent = record.context.recipient.replace(/^./, c => c.toUpperCase());
    $('#corpus-purpose').textContent = record.context.purpose.replace(/^./, c => c.toUpperCase());
    $('#corpus-id').textContent = `${record.sample_id}\nSource: ${data.source}\nDocument SHA-256: ${data.document_sha256}`;
    $('#evidence-group').innerHTML = record.gold.groups.map(g => `<option value="${escape(g.group_id)}">${labels[g.attribute]} · ${g.cue_ids.length} cues</option>`).join('');
    $('#evidence-group').value = group.group_id;
    renderDocument();renderPolicy();renderOutput();$('#corpus-example').hidden = false;
    $('#corpus-document-text').addEventListener('click',event => {
      const decoy=event.target.closest('[data-decoy]');
      if(decoy){const id=decoy.dataset.decoy;if(selectedDecoys.has(id))selectedDecoys.delete(id);else selectedDecoys.add(id);decoy.setAttribute('aria-pressed',String(selectedDecoys.has(id)));renderOutput();return;}
      const button = event.target.closest('[data-cue]');if (!button) return;
      const id = button.dataset.cue;
      if (selected.has(id)) selected.delete(id); else selected.add(id);
      button.setAttribute('aria-pressed',String(selected.has(id)));renderOutput();
    });
    $('#show-decoys').addEventListener('change',()=>{selectedDecoys.clear();renderDocument();renderOutput();});
    $('#reset-cues').addEventListener('click',() => {selected.clear();selectedDecoys.clear();renderDocument();renderOutput();});
    $('#evidence-group').addEventListener('change',event => {
      group = record.gold.groups.find(g => g.group_id === event.target.value);selected.clear();selectedDecoys.clear();renderDocument();renderPolicy();renderOutput();
    });
    $('#policy').addEventListener('change',event => {policies[group.attribute] = event.target.value;renderPolicy();renderOutput();});
    $('#restore-policy').addEventListener('click',() => {policies = {...originalPolicies};renderPolicy();renderOutput();});
    const requested=new URLSearchParams(location.search).get('model');
    if(storedPredictions.some(p=>p.id===requested)){$('#example-model').value=requested;chooseMode('predictions');}
  }
  load().catch(error => {$('#example-error').hidden = false;$('#example-error').textContent = error.message;});
})();
