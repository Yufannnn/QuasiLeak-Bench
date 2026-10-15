/* Paginated rankings from recorded scoring outputs. */
(() => {
  const $=selector=>document.querySelector(selector), $$=selector=>[...document.querySelectorAll(selector)];
  const {esc,metrics,format,condition,size,deployment,runUrl,details,allRows}=window.QLB;
  let subset='test',sortKey='pgf1',descending=true,query='',page=1,pageSize=Number($('#page-size').value),resultsView='systems',compareMode=false;
  const filters={access:'all',method:'all',size:'all'}, selected=new Set(),expanded=new Set();
  const defaultColumns=()=>['size','deployment',...(innerWidth<=600?[]:['pgp','pgr'])];
  const columns=new Set(defaultColumns());
  const optionalColumns=[['size','Model size'],['deployment','Model type'],...metrics.filter(([key])=>key!=='pgf1').map(([key,label])=>[key,key==='far'?'False-alarm rate ↓':label])];
  const filterLabels={access:'Model type',method:'Method',size:'Model size'};
  const filterValues={access:{api:'Proprietary',weights:'Open-weight'},method:{prompted:'Prompted',trained:'Fine-tuned'},size:{'4':'\u22644B','14':'\u226414B',large:'>14B',unknown:'Not reported'}};
  const header=$('.results-table thead').innerHTML;
  const tableScroll=$('.table-scroll');
  let pan=null,suppressPanClick=false;
  const updatePanning=()=>tableScroll.classList.toggle('can-pan',tableScroll.scrollWidth>tableScroll.clientWidth+1);
  const panObserver=new ResizeObserver(updatePanning);
  panObserver.observe(tableScroll);panObserver.observe($('.results-table'));
  function finishPan(event){
    if(!pan||event.pointerId!==pan.pointerId)return;
    suppressPanClick=pan.dragging&&event.type==='pointerup';
    if(tableScroll.hasPointerCapture(pan.pointerId))tableScroll.releasePointerCapture(pan.pointerId);
    pan=null;tableScroll.classList.remove('is-dragging');
    setTimeout(()=>{suppressPanClick=false;},0);
  }
  tableScroll.addEventListener('pointerdown',event=>{
    suppressPanClick=false;
    if(event.pointerType!=='mouse'||event.button!==0||!tableScroll.classList.contains('can-pan')||event.target.closest('input,select,textarea'))return;
    const rect=tableScroll.getBoundingClientRect();
    if(event.clientY>=rect.top+tableScroll.clientTop+tableScroll.clientHeight)return;
    pan={pointerId:event.pointerId,x:event.clientX,y:event.clientY,scrollLeft:tableScroll.scrollLeft,dragging:false};
  });
  window.addEventListener('pointermove',event=>{
    if(!pan||event.pointerId!==pan.pointerId)return;
    const dx=event.clientX-pan.x,dy=event.clientY-pan.y;
    if(!pan.dragging){
      if(Math.abs(dx)<5&&Math.abs(dy)<5)return;
      if(Math.abs(dy)>Math.abs(dx)){pan=null;return;}
      pan.dragging=true;tableScroll.setPointerCapture(event.pointerId);
      tableScroll.classList.add('is-dragging');window.getSelection()?.removeAllRanges();hideLocalTooltip();
    }
    event.preventDefault();tableScroll.scrollLeft=pan.scrollLeft-dx;
  },{passive:false});
  window.addEventListener('pointerup',finishPan);
  window.addEventListener('pointercancel',finishPan);
  tableScroll.addEventListener('lostpointercapture',event=>{
    if(pan?.pointerId===event.pointerId){pan=null;tableScroll.classList.remove('is-dragging');}
  });
  tableScroll.addEventListener('dragstart',event=>{if(pan)event.preventDefault();});
  tableScroll.addEventListener('click',event=>{
    if(suppressPanClick){event.preventDefault();event.stopImmediatePropagation();suppressPanClick=false;}
  },true);
  const viewContexts={nonrevealing:'The 1,618 documents in which no smaller subset of any HIDE group reveals its attribute.',policyshift:'The paper’s 500-pair policy study, scored under the reassigned policy.'};
  const defaultSort=()=>['pgf1',true];
  const viewLabel=()=>({test:'QLB-Test',full:'QLB-Full',nonrevealing:'QLB-SNR',policyshift:'QLB-PS'})[subset];
  const localTooltip=$('#local-marker-definition');
  let localTooltipOwner=null;
  function hideLocalTooltip(){localTooltip.hidden=true;localTooltipOwner=null;}
  function showLocalTooltip(tag){
    localTooltipOwner=tag;localTooltip.hidden=false;
    const rect=tag.getBoundingClientRect(),width=localTooltip.offsetWidth,height=localTooltip.offsetHeight;
    localTooltip.style.left=Math.max(12,Math.min(rect.left,innerWidth-width-12))+'px';
    localTooltip.style.top=(rect.bottom+height+8<innerHeight?rect.bottom+7:Math.max(12,rect.top-height-7))+'px';
  }
  document.addEventListener('pointerover',event=>{const tag=event.target.closest('.local-tag');if(tag&&tag!==localTooltipOwner)showLocalTooltip(tag);});
  document.addEventListener('pointerout',event=>{const tag=event.target.closest('.local-tag');if(tag&&!tag.contains(event.relatedTarget)&&document.activeElement!==tag)hideLocalTooltip();});
  document.addEventListener('focusin',event=>{if(event.target.matches('.local-tag'))showLocalTooltip(event.target);});
  document.addEventListener('focusout',event=>{if(event.target.matches('.local-tag'))hideLocalTooltip();});
  document.addEventListener('click',event=>{const tag=event.target.closest('.local-tag');if(tag)showLocalTooltip(tag);else hideLocalTooltip();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape')hideLocalTooltip();});
  window.addEventListener('scroll',hideLocalTooltip,{passive:true});
  const systemKey=row=>row.model_id+'::'+row.method;
  const bestFirst=(a,b)=>{const [key,desc]=defaultSort(subset),x=a[key]??(desc?-1:Infinity),y=b[key]??(desc?-1:Infinity);return (desc?y-x:x-y)||a.id.localeCompare(b.id);};
  function systems(){
    const groups=new Map();
    for(const row of allRows(subset)){const key=systemKey(row);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}
    return [...groups].map(([key,runs])=>({key,runs:runs.sort(bestFirst),row:runs[0]}));
  }
  function visibleRows(){
    const entries=resultsView==='systems'?systems():allRows(subset).map(row=>({key:row.id,runs:[row],row}));
    return entries.filter(entry=>{
      const row=entry.row;
      const matchSize=filters.size==='all'||(filters.size==='unknown'?row.size_b==null:row.size_b!=null&&(filters.size==='large'?row.size_b>14:row.size_b<=Number(filters.size)));
      const searchText=resultsView==='systems'?row.name:`${row.name} ${condition(row)}`;
      return (filters.access==='all'||deployment(row)===filterValues.access[filters.access])&&(filters.method==='all'||row.method===filters.method)&&matchSize&&searchText.toLowerCase().includes(query.toLowerCase());
    }).sort((a,b)=>{
      a=a.row;b=b.row;
      if(a[sortKey]==null&&b[sortKey]==null)return bestFirst(a,b);
      if(a[sortKey]==null)return 1;if(b[sortKey]==null)return -1;
      return (descending?-1:1)*(a[sortKey]-b[sortKey])||bestFirst(a,b);
    });
  }
  function tray(){
    $('#compare-tray').hidden=!compareMode;$('#compare-count').textContent=selected.size;$('#compare').disabled=selected.size<2;
    $$('[data-compare]').forEach(box=>{box.checked=selected.has(box.dataset.compare);box.disabled=selected.size===4&&!box.checked;});
  }
  function selection(row){return `<input type="checkbox" data-compare="${row.id}" aria-label="Compare ${esc(row.name+' '+condition(row))}" ${selected.has(row.id)?'checked':''}>`;}
  function configurations(entry){
    const id='config-'+entry.row.id;
    return `<tr class="configurations-row" id="${id}" ${expanded.has(entry.key)?'':'hidden'}><td colspan="${4+columns.size+(compareMode?1:0)}"><div class="configurations-panel"><div class="configuration-heading"><h3>${resultsView==='systems'?'Configurations':'Run configuration'}</h3><span>${entry.runs.length} reported ${entry.runs.length===1?'configuration':'configurations'}</span></div><div class="configuration-list">${entry.runs.map(row=>`<div class="configuration-item">${compareMode?`<span class="configuration-select">${selection(row)}</span>`:''}<span class="configuration-label">${esc(condition(row))}</span><strong class="configuration-score" title="Policy group F1">${format(row.pgf1)}</strong><button type="button" class="text-button configuration-details" data-details="${row.id}">Details</button></div>`).join('')}</div></div></td></tr>`;
  }
  function headline(entry,ranks){
    const row=entry.row,open=expanded.has(entry.key),id='config-'+row.id;
    return `<tr class="system-headline"><td class="compare-column" ${compareMode?'':'hidden'}>${selection(row)}</td><td class="rank-mark">${ranks.findIndex(r=>r.id===row.id)+1}</td>
    <td class="system-cell"><div class="model-identity"><button type="button" class="text-button system-name" data-expand="${esc(entry.key)}" aria-expanded="${open}" aria-controls="${id}" title="${esc(row.name)}"><span class="model-icon"><img src="assets/model_icons/${row.icon}.svg" width="20" height="20" alt=""></span><span class="model-label">${esc(row.name)}</span></button>${row.local_marker_eligible?'<span class="local-tag" tabindex="0" aria-describedby="local-marker-definition">Local \u226414B</span>':''}</div>${resultsView==='runs'?`<span class="system-meta">${esc(condition(row))}</span>`:''}</td>
    <td class="size-column" data-column="size">${size(row)}</td><td class="deployment-column" data-column="deployment">${deployment(row)}</td>
    ${metrics.map(([key],index)=>`<td data-column="${key}" class="${key==='pgf1'?'score-cell':''} ${index>4?'extra-metric':''}" ${key!=='pgf1'&&!columns.has(key)?'hidden':''}>${format(row[key],key)}${key==='pgf1'?`<div class="score-bar" aria-hidden="true"><i style="width:${row.pgf1??0}%"></i></div>`:''}</td>`).join('')}
    <td class="expand-column"><button type="button" class="expand-system" data-expand="${esc(entry.key)}" aria-expanded="${open}" aria-controls="${id}" aria-label="${open?'Collapse':'Expand'} ${esc(row.name)} configurations"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="m5 7 5 5 5-5"></path></svg></button></td></tr>${configurations(entry)}`;
  }
  function renderFilterChips(){
    const active=Object.entries(filters).filter(([,value])=>value!=='all');
    $('#active-filters').hidden=!active.length;
    $('#active-filters').innerHTML=active.map(([key,value])=>`<button type="button" class="filter-chip" data-remove-filter="${key}" aria-label="Remove ${filterLabels[key]}: ${esc(filterValues[key][value])}">${esc(filterValues[key][value])}<span aria-hidden="true">\u00d7</span></button>`).join('');
    $('#filter-count').hidden=!active.length;$('#filter-count').textContent=active.length;
  }
  function closePopover(selector){const panel=$(selector);if(panel.matches(':popover-open'))panel.hidePopover();}
  function updateDraftReset(){$('#reset-filters').hidden=['access','method','size'].every(key=>$('#filter-'+key).value==='all');}
  function positionPopover(panel,button){
    const rect=button.getBoundingClientRect(),margin=12,width=panel.offsetWidth,height=panel.offsetHeight;
    const top=rect.bottom+8+height<=innerHeight-margin?rect.bottom+8:Math.max(margin,rect.top-height-8);
    panel.style.left=Math.max(margin,Math.min(rect.right-width,innerWidth-width-margin))+'px';panel.style.top=top+'px';
  }
  for(const [panelId,buttonId] of [['filters-popover','filters-toggle'],['columns-popover','columns-toggle']]){
    const panel=$('#'+panelId),button=$('#'+buttonId);
    panel.addEventListener('beforetoggle',event=>{if(event.newState!=='open')return;if(panelId==='filters-popover'){for(const key of ['access','method','size'])$('#filter-'+key).value=filters[key];updateDraftReset();}requestAnimationFrame(()=>positionPopover(panel,button));});
  }
  window.addEventListener('resize',()=>{if(!$('#leaderboard').classList.contains('columns-customized')){columns.clear();defaultColumns().forEach(key=>columns.add(key));$$('[data-column-choice]').forEach(box=>box.checked=columns.has(box.dataset.columnChoice));render();}for(const [panel,button] of [['filters-popover','filters-toggle'],['columns-popover','columns-toggle']])if($('#'+panel).matches(':popover-open'))positionPopover($('#'+panel),$('#'+button));});
  window.addEventListener('scroll',()=>{closePopover('#filters-popover');closePopover('#columns-popover');},{passive:true});
  $('#column-options').innerHTML=optionalColumns.map(([key,label])=>`<label class="column-option"><input type="checkbox" data-column-choice="${key}" ${columns.has(key)?'checked':''}> ${label}</label>`).join('');
  function render(){
    hideLocalTooltip();
    $('#view-context').textContent=viewContexts[subset]||((resultsView==='systems'?'Best reported configuration per system':'All reported configurations')+(subset==='test'?' on 1,000 held-out documents.':' on the full 5,000-document set.'));
    $('.results-table thead').innerHTML=header;
    const rows=visibleRows(),pages=Math.max(1,Math.ceil(rows.length/pageSize));page=Math.min(page,pages);
    const advanced=metrics.slice(5).some(([key])=>columns.has(key));$('#leaderboard').classList.toggle('expanded-metrics',advanced);
    const minimumWidth=innerWidth<=760&&columns.size?Math.max(740,390+columns.size*80):columns.size>4?390+columns.size*80:0;
    $('.results-table').style.minWidth=minimumWidth+'px';
    const ranks=(resultsView==='systems'?systems().map(entry=>entry.row):allRows(subset)).sort(bestFirst);
    $('#results-body').innerHTML=rows.slice((page-1)*pageSize,page*pageSize).map(entry=>headline(entry,ranks)).join('')||`<tr><td colspan="${4+columns.size+(compareMode?1:0)}" class="empty-row">No matches</td></tr>`;
    $('#leaderboard').classList.toggle('compare-mode',compareMode);$('#leaderboard').classList.toggle('all-runs-view',resultsView==='runs');
    $('.results-table thead .compare-column').hidden=!compareMode;
    $('#compare-mode').setAttribute('aria-pressed',String(compareMode));$('#compare-mode').textContent=compareMode?'Done':'Compare';
    $$('.results-table [data-column]').forEach(cell=>cell.hidden=cell.dataset.column!=='pgf1'&&!columns.has(cell.dataset.column));
    $$('[data-sort]').forEach(button=>{const key=button.dataset.sort;const label=metrics.find(m=>m[0]===key)[1];button.innerHTML=label.includes('_')?label.split('_')[0]+'<sub>'+label.split('_')[1]+'</sub>':label;if(key===sortKey){button.closest('th').setAttribute('aria-sort',descending?'descending':'ascending');button.innerHTML+=` <span aria-hidden="true">${descending?'\u2193':'\u2191'}</span>`;}});
    const sortLabel=metrics.find(([key])=>key===sortKey)[1];
    $('#result-count').textContent=`${rows.length} ${resultsView==='systems'?(rows.length===1?'system':'systems'):(rows.length===1?'run':'runs')}${sortKey===defaultSort(subset)[0]&&descending===defaultSort(subset)[1]?'':` \u00b7 ${sortLabel} ${descending?'\u2193':'\u2191'}`}`;
    $('#page-status').textContent=`${rows.length?(page-1)*pageSize+1:0}\u2013${Math.min(page*pageSize,rows.length)} of ${rows.length}`;
    $('#page-prev').disabled=page<=1;$('#page-next').disabled=page>=pages;$('#export').disabled=!rows.length;renderFilterChips();tray();
  }
  function chooseView(view){
    if(!Object.hasOwn(recordedScores,view))return;
    subset=view;[sortKey,descending]=defaultSort(view);selected.clear();
    if(!$('#leaderboard').classList.contains('columns-customized')){columns.clear();defaultColumns().forEach(key=>columns.add(key));$$('[data-column-choice]').forEach(box=>box.checked=columns.has(box.dataset.columnChoice));}expanded.clear();page=1;
    closePopover('#filters-popover');closePopover('#columns-popover');
    $$('[data-subset]').forEach(button=>{const active=button.dataset.subset===view;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});render();
  }
  $$('[data-subset]').forEach(button=>button.addEventListener('click',()=>{chooseView(button.dataset.subset);history.replaceState(null,'','#'+subset);}));
  for(const field of ['access','method','size'])$('#filter-'+field).addEventListener('change',updateDraftReset);
  $('#search').addEventListener('input',event=>{query=event.target.value;page=1;render();});
  $('#results-view').addEventListener('change',event=>{resultsView=event.target.value;expanded.clear();page=1;render();});
  $('#compare-mode').addEventListener('click',()=>{compareMode=!compareMode;if(!compareMode)selected.clear();render();});
  $('#apply-filters').addEventListener('click',()=>{for(const field of ['access','method','size'])filters[field]=$('#filter-'+field).value;page=1;render();closePopover('#filters-popover');$('#filters-toggle').focus();});
  $('#reset-filters').addEventListener('click',()=>{for(const field of ['access','method','size']){filters[field]='all';$('#filter-'+field).value='all';}page=1;updateDraftReset();render();});
  $('#active-filters').addEventListener('click',event=>{const button=event.target.closest('[data-remove-filter]');if(!button)return;filters[button.dataset.removeFilter]='all';page=1;render();$('#filters-toggle').focus();});
  $('#column-options').addEventListener('change',event=>{const key=event.target.dataset.columnChoice;if(!key)return;if(event.target.checked)columns.add(key);else columns.delete(key);$('#leaderboard').classList.add('columns-customized');render();});
  $('#reset-columns').addEventListener('click',()=>{columns.clear();defaultColumns().forEach(key=>columns.add(key));$$('[data-column-choice]').forEach(box=>box.checked=columns.has(box.dataset.columnChoice));$('#leaderboard').classList.remove('columns-customized');render();});
  $('.results-table thead').addEventListener('click',event=>{const button=event.target.closest('[data-sort]');if(!button)return;descending=sortKey===button.dataset.sort?!descending:!['dsr','far'].includes(button.dataset.sort);sortKey=button.dataset.sort;page=1;render();});
  $('#page-size').addEventListener('change',event=>{pageSize=Number(event.target.value);page=1;render();});
  $('#page-prev').addEventListener('click',()=>{page--;render();});$('#page-next').addEventListener('click',()=>{page++;render();});
  $('#results-body').addEventListener('click',event=>{const expand=event.target.closest('[data-expand]');if(expand){const key=expand.dataset.expand;if(expanded.has(key))expanded.delete(key);else expanded.add(key);render();$(`[data-expand="${CSS.escape(key)}"]`).focus();return;}const button=event.target.closest('[data-details]');if(!button)return;const row=allRows(subset).find(r=>r.id===button.dataset.details);$('#details-content').innerHTML=details(row,subset)+`<a class="text-link" href="${runUrl(row,subset)}">Open result page &rarr;</a>`;$('#details-dialog').showModal();});
  $('#results-body').addEventListener('change',event=>{const id=event.target.dataset.compare;if(!id)return;if(event.target.checked&&selected.size<4)selected.add(id);else selected.delete(id);tray();});
  $('#clear-compare').addEventListener('click',()=>{selected.clear();tray();});
  $('#compare').addEventListener('click',()=>{location.href=`compare.html?set=${subset}&runs=${encodeURIComponent([...selected].join(','))}`;});
  $('#export').addEventListener('click',()=>{
    const cell=value=>'"'+String(value??'').replaceAll('"','""')+'"';
    const data=[['Model','Condition','Set','View','Run ID','Size (B)','Model type',...metrics.map(m=>m[1]),'Result source','Verification','Source files'],...visibleRows().map(({row})=>[row.name,condition(row),viewLabel(),resultsView==='systems'?'Best reported configuration per system':'All runs',row.id,row.size_b,deployment(row),...metrics.map(([key])=>row[key]),row.result_origin,row.verification,row.sources.join('; ')])];
    const url=URL.createObjectURL(new Blob([data.map(row=>row.map(cell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`quasileak-${subset}-${resultsView}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  const hash=location.hash.slice(1);
  if(hash==='submit')location.replace('submit.html');
  else chooseView(Object.hasOwn(recordedScores,hash)?hash:'test');
  if(Object.hasOwn(recordedScores,hash))requestAnimationFrame(()=>$('#leaderboard').scrollIntoView({block:'start'}));
  window.addEventListener('hashchange',()=>{const view=location.hash.slice(1);if(Object.hasOwn(recordedScores,view)){chooseView(view);$('#leaderboard').scrollIntoView({block:'start'});}});
})();
