/* Public text is always inserted as text, never executed as markup. */
'use strict';
(() => {
  document.querySelectorAll('.site-nav details').forEach(menu=>menu.addEventListener('toggle',()=>{if(menu.open)document.querySelectorAll('.site-nav details').forEach(other=>{if(other!==menu)other.open=false;});}));
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){document.querySelectorAll('.site-nav details[open]').forEach(menu=>{menu.open=false;menu.querySelector('summary').focus();});}});
  document.addEventListener('focusin',event=>{document.querySelectorAll('.site-nav details[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;});});
  if(document.body.dataset.page==='about')return;
  const data = JSON.parse(document.getElementById('archive-data').textContent);
  const isDirectory = document.body.dataset.page === 'directory';
  const sections = [['statutes','Statutes'],['case_law','Case Law'],['procedural_rules','Procedural Rules'],['local_rules','Local Rules']];
  const from = document.getElementById('from'), to = document.getElementById('to');
  const report = document.getElementById('report'), status = document.getElementById('status');
  const periods = document.getElementById('periods');
  const node = (tag, text, cls) => {const e=document.createElement(tag); if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
  const period = i => `${i.window_start} – ${i.window_end}`;
  const publicationDate = i => new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'long',day:'numeric'}).format(new Date(i.published_at));
  // Newest revision for each period; direct issue URLs retain older revisions.
  const seen=new Set();
  const issues=data.issues.filter(i=>{const k=period(i);if(seen.has(k))return false;seen.add(k);return true;});
  function filterRows(start,end){return issues.filter(i=>i.window_start<=end && i.window_end>=start);}
  function summary(text, isCaseLaw){
    const p=node('p',undefined,'summary');
    if(!isCaseLaw){p.textContent=text;return p;}
    // Only emphasize known labels at the start of a line; never parse source HTML.
    text.split('\n').forEach((line,index)=>{
      if(index)p.append('\n');
      const match=line.match(/^(\s*)(Holding|Disposition|Author):/);
      if(match)p.append(match[1],node('strong',match[2]+':'),line.slice(match[0].length));
      else p.append(line);
    });
    return p;
  }
  function citations(parent,refs){
    const sources=[...new Map(refs.map(c=>[c.url,c])).values()];
    const line=node('p');line.append(sources.length===1?'Source: ':'Sources: ');
    sources.forEach((c,n)=>{if(n)line.append(' · ');const a=node('a',c.label.split(' · ')[0]);a.href=c.url;line.append(a);});parent.append(line);
  }
  function render(selected, description){
    report.replaceChildren();periods.replaceChildren();status.textContent=description;status.hidden=!description;
    if(!selected.length){report.append(node('p',issues.length?'No published updates match this period. This does not establish that no legal changes occurred.':'No reviewed updates have been published yet.'));return;}
    const list=node('ul');
    selected.forEach(i=>{const li=node('li'),a=node('a',period(i));const q=new URLSearchParams({issue:i.id}),court=new URLSearchParams(location.search).get('court');if(court)q.set('court',court);a.href='?'+q;a.addEventListener('click',e=>{if(e.button===0&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey){e.preventDefault();navigate(a.getAttribute('href'));report.focus();}});li.append(a);list.append(li);});
    if(selected.length>1)periods.append(list);
    if(isDirectory){renderDirectory(selected[0]);return;}
    for(const [key,title] of sections){
      const section=node('section');section.append(node('h2',title));
      if(selected.some(issue=>issue.sections[key].status==='incomplete'))section.append(node('p','Research is incomplete; missing findings do not establish no changes.','notice'));
      if(selected.every(issue=>issue.sections[key].status==='reviewed'&&!issue.sections[key].items.length))section.append(node('p','No items included in this reviewed section.','meta'));
      selected.forEach(issue=>{
        const part=issue.sections[key];
        part.items.forEach(item=>{const article=node('article');article.append(node('h3',item.title));
          const dates=[];if(item.publication_date)dates.push(`Published: ${item.publication_date}`);if(item.effective_date)dates.push(`Effective: ${item.effective_date}`);if(item.legal_status!=='unknown')dates.push(item.legal_status);
          if(item.inclusion_basis==='opening_baseline')dates.push('Opening evidence baseline');
          if(item.inclusion_basis==='effective')dates.push('Included for its stated effective date');
          if(dates.length)article.append(node('p',dates.join(' · '),'meta'));
          article.append(summary(item.summary,key==='case_law'));citations(article,item.citations);section.append(article);
        });
      });report.append(section);
    }
  }
  function renderDirectory(snapshot){
    const courtId=new URLSearchParams(location.search).get('court');
    const court=(data.courts||[]).find(c=>c.group_id===courtId);
    const directory=node('section',undefined,'directory');directory.id='directory';
    directory.append(node('h2',court?court.label+' — Personnel': 'All covered courts — Personnel'));
    directory.append(node('p',snapshot.coverage?.directory_observed_at
      ? `Directory observed at ${snapshot.coverage.directory_observed_at}. Observation time is distinct from the report period. A date range shows the newest matching snapshot.`
      : `Directory snapshot for ${period(snapshot)}. A date range shows the newest matching snapshot.`));
    if(courtId&&!court){directory.append(node('p','This court is not in the covered directory.'));report.append(directory);return;}
    const circuitCounties={circuit_fourth:['Duval','Clay','Nassau'],circuit_seventh:['Putnam','St. Johns'],circuit_eighth:['Baker','Union']};
    const matches=person=>{
      if(!court)return true;
      if((person.court_ids||[]).includes(courtId))return true;
      if(courtId.startsWith('clerk_'))return person.counties.includes(court.label.replace(/ County$/, ''));
      if(circuitCounties[courtId])return person.counties.some(c=>circuitCounties[courtId].includes(c));
      return false;
    };
    if(courtId&&circuitCounties[courtId])directory.append(node('p','Personnel serving the covered counties within this circuit, including county-court and clerk contacts.'));
    const entries=snapshot.directory.filter(matches).sort((a,b)=>(a.counties.join(', ')+' '+a.name).localeCompare(b.counties.join(', ')+' '+b.name));
    if(!entries.length)directory.append(node('p','No personnel records for this court are available in this saved snapshot.'));
    else {
      const table=node('table');table.className='personnel-table';
      const headers=['Personnel','Court / County','Chambers / Office','Judicial Assistant','Procedures & Rules','Sources'];
      const thead=node('thead'),head=node('tr');headers.forEach(label=>{const th=node('th',label);th.scope='col';head.append(th);});thead.append(head);table.append(thead);
      const tbody=node('tbody');
      entries.forEach(person=>{
        const row=node('tr'),cells=headers.map(label=>{const td=node('td');td.dataset.label=label;row.append(td);return td;});
        cells[0].append(node('strong',person.name),node('p',person.kind==='clerk'?'Clerk':'Judge'));
        const courtLabels=(person.court_ids||[]).map(id=>(data.courts||[]).find(c=>c.group_id===id)?.label).filter(Boolean);
        cells[1].append(node('p',[...courtLabels,...person.counties].join(' · ')||'Court assignment not recorded'));
        let assistants=0,contacts=0;
        Object.entries(person.details).forEach(([key,value])=>{
          const p=node('p');p.append(node('strong',key+': '),document.createTextNode(value));
          if(/assistant/i.test(key)){cells[3].append(p);assistants++;}else{cells[2].append(p);contacts++;}
        });
        if(!contacts)cells[2].append(node('p','Not recorded'));
        if(!assistants)cells[3].append(node('p',person.kind==='clerk'?'Not applicable':'Not recorded'));
        if(person.procedures)cells[4].append(node('p',person.procedures));
        person.governing_rules.forEach(rule=>cells[4].append(node('p',rule)));
        if(!person.procedures&&!person.governing_rules.length)cells[4].append(node('p','Not recorded'));
        citations(cells[5],person.citations);tbody.append(row);
      });table.append(tbody);directory.append(table);
    }
    report.append(directory);
  }
  function validDate(value){return /^\d{4}-\d{2}-\d{2}$/.test(value)&&!Number.isNaN(Date.parse(value+'T00:00:00Z'))&&new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value;}
  function route(){
    const error=document.getElementById('date-error');error.hidden=true;error.textContent='';
    from.removeAttribute('aria-invalid');to.removeAttribute('aria-invalid');
    document.getElementById('updates-link').href='./'+location.search;
    const allQuery=new URLSearchParams(location.search);allQuery.delete('court');
    document.getElementById('directory-link').href='directory.html'+(allQuery.size?'?'+allQuery:'');
    document.querySelectorAll('[data-court]').forEach(link=>{const q=new URLSearchParams(allQuery);q.set('court',link.dataset.court);link.href='directory.html?'+q;});
    const query=new URLSearchParams(location.search),start=query.get('from'),end=query.get('to'),id=query.get('issue');
    if(id){const issue=data.issues.find(i=>i.id===id);from.value=issue?.window_start||'';to.value=issue?.window_end||'';render(issue?[issue]:[],issue?`Update: ${period(issue)}`:'The requested update was not found.');return;}
    if(start!==null||end!==null){from.value=start||'';to.value=end||'';if(!validDate(start||'')||!validDate(end||'')||start>end){const message='Enter a valid date range with From on or before Through.';error.textContent=message;error.hidden=false;if(!validDate(start||'')||start>end)from.setAttribute('aria-invalid','true');if(!validDate(end||'')||start>end)to.setAttribute('aria-invalid','true');render([],message);return;}const selected=filterRows(start,end);render(selected,`${selected.length} update${selected.length===1?'':'s'} for ${start} – ${end}`);return;}
    const latest=issues[0];from.value=latest?.window_start||'';to.value=latest?.window_end||'';render(latest?[latest]:[],latest?`Latest update: ${publicationDate(latest)}`:'');
  }
  function navigate(search){const q=new URLSearchParams(search),court=new URLSearchParams(location.search).get('court');if(court)q.set('court',court);history.pushState(null,'',location.pathname+(q.size?'?'+q:''));route();}
  document.getElementById('period-form').addEventListener('submit',e=>{e.preventDefault();navigate('?'+new URLSearchParams({from:from.value,to:to.value}));document.querySelector('[aria-invalid="true"]')?.focus();});
  document.getElementById('latest').addEventListener('click',()=>navigate(''));
  document.querySelectorAll('[data-days]').forEach(button=>button.addEventListener('click',()=>{
    // Calendar days in the reporting timezone, including today. UTC arithmetic
    // on that date avoids shortening or extending a range across DST changes.
    const parts=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const part=type=>parts.find(p=>p.type===type).value;
    const end=`${part('year')}-${part('month')}-${part('day')}`;
    const start=new Date(end+'T00:00:00Z');start.setUTCDate(start.getUTCDate()-Number(button.dataset.days)+1);
    navigate('?'+new URLSearchParams({from:start.toISOString().slice(0,10),to:end}));
  }));
  addEventListener('popstate',route);route();
})();
