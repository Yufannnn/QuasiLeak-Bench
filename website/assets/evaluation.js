
(function(){
  window.QLBPartialFigures.mount();
  const policyButtons=[...document.querySelectorAll('[data-policy]')],policyBadge=document.getElementById('policy-badge'),policyTitle=document.getElementById('policy-title'),policyExplainer=document.getElementById('policy-explainer');
  const policyText={HIDE:['Reportable disclosure','Flag the joint evidence group','The clues jointly support an inference about nationality. Because nationality is HIDE, the detector should return the complete group.'],KEEP:['Permitted disclosure','Do not flag this evidence','The same inference may be possible, but the sender has explicitly permitted disclosure of nationality in this recipient context.'],NEUTRAL:['Not a violation target','Do not flag this evidence','The policy makes nationality NEUTRAL, so this group is not a prohibited disclosure and should not be reported.']};
  policyButtons.forEach(b=>b.setAttribute('aria-pressed',String(b.classList.contains('active'))));
  policyButtons.forEach(b=>b.addEventListener('click',()=>{let v=b.dataset.policy;policyButtons.forEach(z=>{z.classList.toggle('active',z===b);z.setAttribute('aria-pressed',String(z===b))});let t=policyText[v];policyBadge.textContent=t[0];policyBadge.classList.toggle('pass',v!=='HIDE');policyTitle.textContent=t[1];policyExplainer.textContent=t[2]}));
  const k=document.getElementById('k-range'),m=document.getElementById('m-range'),other=document.getElementById('other-range'),junk=document.getElementById('junk-range'),bind=document.getElementById('bind-select'),policy=document.getElementById('policy-select');
  function updateFactor(){const K=+k.value; m.max=String(K);if(+m.value>K)m.value=String(K);let M=+m.value,O=+other.value,J=+junk.value;const r=M+O+J,ncue=M+O,EC=(M/K)**2,EL=r?ncue/r:0,BG=ncue?M/ncue:0,BA=+bind.value,P=policy.value==='HIDE'?1:0,CP=EC*EL*BG*BA*P;[['k-val',K],['m-val',M],['other-val',O],['junk-val',J]].forEach(z=>document.getElementById(z[0]).textContent=z[1]);[['ec-out',EC],['el-out',EL],['bg-out',BG],['ba-out',BA]].forEach(z=>document.getElementById(z[0]).textContent=z[1].toFixed(2));document.getElementById('cp-out').textContent=CP.toFixed(3);window.QLBPartialFigures.render({K,M,O,J,EC,EL,BG,BA,CP,policy:policy.value})}[k,m,other,junk,bind,policy].forEach(i=>i.addEventListener('input',updateFactor)); updateFactor();
  const copyIcon='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"></rect><path d="M16 8V4H4v12h4"></path></svg>';
  const doneIcon='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m5 12 4 4L19 6"></path></svg>';
  document.querySelectorAll('[data-copy]').forEach(button=>{
    button.innerHTML=copyIcon;
    button.addEventListener('click',async()=>{
      const label=button.title;
      try{await navigator.clipboard.writeText(button.dataset.copy);button.innerHTML=doneIcon;button.setAttribute('aria-label','Copied');button.title='Copied';}
      catch(error){button.setAttribute('aria-label','Copy unavailable');button.title='Copy unavailable';}
      setTimeout(()=>{button.innerHTML=copyIcon;button.setAttribute('aria-label',label);button.title=label;},1700);
    });
  });
  const links=[...document.querySelectorAll('.side-link')],sections=links.map(a=>document.querySelector(a.getAttribute('href'))).filter(Boolean);
  const selector=document.getElementById('page-section');
  function markSection(id){
    links.forEach(a=>{const active=a.getAttribute('href')==='#'+id;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});
    if(selector&&[...selector.options].some(option=>option.value===id))selector.value=id;
  }
  function revealAnchor(){
    const id=decodeURIComponent(location.hash.slice(1));
    if(!id)return;
    const target=document.getElementById(id);
    if(!target)return;
    let parent=target;
    while(parent){if(parent.tagName==='DETAILS')parent.open=true;parent=parent.parentElement;}
    const section=target.closest('.doc-section');if(section)markSection(section.id);
    requestAnimationFrame(()=>target.scrollIntoView({block:'start'}));
  }
  selector?.addEventListener('change',event=>{const id=event.target.value;if(location.hash==='#'+id)document.getElementById(id).scrollIntoView({block:'start'});else location.hash=id;});
  window.addEventListener('hashchange',revealAnchor);revealAnchor();
  if('IntersectionObserver' in window){
    const visible=new Map();
    const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting)visible.set(entry.target.id,entry.target);else visible.delete(entry.target.id);}const first=[...visible.values()].sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top)[0];if(first)markSection(first.id);},{rootMargin:'-100px 0px -55% 0px',threshold:0});
    sections.forEach(section=>observer.observe(section));
  }
})();
