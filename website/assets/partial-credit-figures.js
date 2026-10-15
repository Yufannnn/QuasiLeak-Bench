/* Display-size diagrams: native labels and state-driven inline SVG marks.
   Scoring stays in evaluation.js; this renderer only consumes its results. */
(() => {
  const $ = id => document.getElementById(id);
  const check = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m5 12 4 4 10-10"/></svg>';
  const miss = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17"/></svg>';
  const arrow = '<svg class="credit-binding-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M3 12h17m-6-6 6 6-6 6"/></svg>';
  function mount() {
    for (const key of ['ec','el','bg','ba']) $('figure-'+key).setAttribute('role','img');
  }
  function completeness({K,M}) {
    const cues=Array.from({length:K},(_,i)=>{
      const found=i<M;
      return `<div class="credit-cue ${found?'is-found':'is-missed'}" data-cue-state="${found?'target':'empty'}"><span>Cue ${i+1}</span><span>${found?check:miss}${found?'Found':'Missed'}</span></div>`;
    }).join('');
    return `<div class="credit-cue-set">${cues}</div><p class="credit-diagram-caption">${M} of ${K} gold cues recovered</p>`;
  }
  function proportion(first,second,firstLabel,secondLabel) {
    const total=first+second;
    return `<div class="credit-proportion" aria-hidden="true">${total?`<span class="credit-proportion-target" style="flex-grow:${first}"></span><span class="credit-proportion-other" style="flex-grow:${second}"></span>`:''}</div><div class="credit-proportion-labels"><span><i class="credit-key target" aria-hidden="true"></i><b>${first}</b> ${firstLabel}</span><span><i class="credit-key other" aria-hidden="true"></i><b>${second}</b> ${secondLabel}</span></div>`;
  }
  function localization({M,O,J}) {
    return proportion(M+O,J,'recognized cues','unrelated spans')+`<p class="credit-diagram-caption">${M+O+J?`${M+O} of ${M+O+J} predicted spans match annotated cues`:'No predicted spans'}</p>`;
  }
  function purity({M,O}) {
    return proportion(M,O,'target cues','other-group cues')+`<p class="credit-diagram-caption">${M+O?`${M} of ${M+O} recognized cues belong to the target group`:'No recognized cues'}</p>`;
  }
  function binding({M,O,J,BA}) {
    const label=BA===1?'Primary':BA===0.5?'Verified secondary':'Unsupported';
    return `<div class="credit-binding-flow"><div class="credit-binding-evidence"><span>Evidence group</span><b>${M+O+J} spans</b></div>${arrow}<div class="credit-binding-label ${BA===0?'is-unsupported':''}" data-binding-choice="${BA}" data-active="true"><span>Attribute</span><b>${label}</b></div></div><p class="credit-diagram-caption">${BA===1?'Primary label earns full binding credit':BA===0.5?'Annotated secondary label earns half credit':'Unannotated label earns no binding credit'}</p>`;
  }
  function render(state) {
    const {K,M,O,J,EC,EL,BG,BA,CP,policy}=state;
    const descriptions={ec:`${M} of ${K} target cues recovered. EC ${EC.toFixed(2)}.`,el:`${M+O} recognized cue spans and ${J} unrelated spans out of ${M+O+J} predictions. EL ${EL.toFixed(2)}.`,bg:`${M} target cues and ${O} cues from other groups. BG ${BG.toFixed(2)}.`,ba:`${BA===1?'Primary':BA===0.5?'Verified secondary':'Unsupported'} attribute interpretation. BA ${BA.toFixed(2)}.`};
    const bodies={ec:completeness(state),el:localization(state),bg:purity(state),ba:binding(state)};
    for (const key of Object.keys(bodies)) {
      $('figure-'+key).innerHTML=bodies[key];
      $('figure-'+key).setAttribute('aria-label',descriptions[key]);
    }
    for (const [key,value] of Object.entries({ec:EC,el:EL,bg:BG,ba:BA})) document.querySelector(`[data-credit-factor="${key}"]`).textContent=value.toFixed(2);
    const open=policy==='HIDE';
    $('policy-gate').textContent=open?'1':'0';
    $('policy-gate').dataset.gate=open?'open':'closed';
    $('policy-gate').title=`${policy} policy multiplier`;
    $('credit-policy-name').textContent=policy+' policy';
    $('policy-credit-strip').dataset.policy=policy;
    $('policy-credit-strip').setAttribute('aria-label',`Pair-level policy credit ${CP.toFixed(3)}, computed from unrounded factors. Displayed factors: EC ${EC.toFixed(2)}, EL ${EL.toFixed(2)}, BG ${BG.toFixed(2)}, BA ${BA.toFixed(2)}, ${policy} policy multiplier ${open?1:0}.`);
  }
  window.QLBPartialFigures={mount,render};
})();
