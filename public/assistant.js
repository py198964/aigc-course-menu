'use strict';
const Advisor={scope:'',result:null,busy:false,error:'',draft:''};
const advisorKey=()=>`course-advisor-${S.user?.id||'guest'}-${S.org}`;
const advisorExamples=['给20位零基础老师安排2天培训，每天6小时，重点学习教学视频和数字人口播。','为企业新媒体团队安排1天6小时实训，学习产品广告视频，不要短剧，模块预算2000元。','我们已经会画布工具，想用半天重点学习短剧转绘，并做出一个练习作品。'];
async function agentView(){
 await ruleAgentView();
 const manual=$('#agent-form').outerHTML,result=$('#agent-result').outerHTML;
 const scope=advisorKey();
 if(Advisor.scope!==scope){Advisor.scope=scope;Advisor.result=null;Advisor.error='';Advisor.draft='';Advisor.busy=false}
 if(!Advisor.result&&S.user&&!window.COURSE_PUBLIC_MODE){const id=sessionStorage.getItem(scope);if(id)try{Advisor.result=await api('/agent/assistant/'+id)}catch{sessionStorage.removeItem(scope)}}
 $('#content').innerHTML=head('AI选课助手','描述培训对象、希望解决的问题和可用时间，获取课程组合建议。')+`<section class="advisor-panel"><div class="advisor-intro"><span class="badge type-P">培训需求咨询</span><h2>这次培训，您希望学员学会什么？</h2><p>可以直接说出您的想法，也可以从下面的示例开始。</p></div><div class="advisor-examples">${advisorExamples.map((t,i)=>`<button class="advisor-example" data-advisor="example" data-id="${i}">${esc(t)}<span aria-hidden="true">↗</span></button>`).join('')}</div><div id="advisor-output"></div><form id="advisor-form"><label for="advisor-message">${Advisor.result?'继续补充或调整需求':'培训需求'}</label><textarea id="advisor-message" name="message" maxlength="2000" required minlength="2" rows="4" placeholder="例如：给30位零基础老师做2天培训，希望学会用AI制作教学视频，每天6小时，预算5000元。">${esc(Advisor.draft)}</textarea><div class="advisor-controls"><p class="hint">AI将使用您的需求描述和当前课程目录。推荐结果可检查并继续调整。</p><div class="actions">${Advisor.result?'<button type="button" class="btn" data-advisor="reset">新建对话</button>':''}<button type="submit" class="btn primary" ${Advisor.busy?'disabled':''}>${Advisor.busy?'正在分析需求…':Advisor.result?'调整推荐':'推荐课程组合'}</button></div></div><div id="advisor-error" class="error" role="alert">${esc(Advisor.error)}</div></form></section><details class="advisor-manual" ${window.COURSE_PUBLIC_MODE?'open':''}><summary>按条件组课 <span>手动设置方向、课时和预算</span></summary>${manual}${result}</details>`;
 advisorRender();
}
function advisorRender(){
 const box=$('#advisor-output');if(!box)return;
 if(Advisor.busy){box.innerHTML='<div class="loading" role="status">正在理解需求并核对课程、前置条件和排课容量…</div>';return}
 const r=Advisor.result;if(!r){box.innerHTML='';return}
 const p=r.plan,q=r.requirements;
 box.innerHTML=`<div class="advisor-result"><div class="advisor-thread">${r.messages.map((m,i)=>`<p><span>${i?'补充要求':'培训需求'}</span>${esc(m)}</p>`).join('')}</div><div class="eyebrow">需求理解与推荐</div><h3>${esc(r.summary)}</h3><div class="summary"><span>${esc(q.audience)}</span><span>${q.level}</span><span>${q.days}天 · 每天${q.daily_minutes/60}小时</span><span>${q.people}人</span><span>${q.budget_fen===null?'未限定模块预算':'模块预算 '+money(q.budget_fen)}</span>${q.total_minutes?`<span>总课时上限 ${q.total_minutes/60}小时</span>`:''}</div>${r.assumptions.length?`<div class="advisor-assumptions"><b>尚未说明的条件</b>${list(r.assumptions)}<p>可在下方补充实际安排，重新推荐。</p></div>`:''}<div class="advisor-course-list">${p.courses.map(c=>`<article><span class="badge type-${c.category}">${esc(c.code)} · ${cats[c.category]}</span><div><h4>${esc(c.title)}</h4><p>${esc(p.reasons[c.id])}</p></div><strong>${c.minutes/60}小时</strong><button class="textbtn" type="button" data-action="detail" data-id="${c.id}">课程详情</button></article>`).join('')}</div>${p.courses.length?`<div class="advisor-total"><b>${p.courses.length}门课程 · ${p.total_minutes/60}小时</b><span>模块参考小计 ${money(p.subtotal_fen)}</span></div><div class="advisor-schedule">${p.schedule.map((day,i)=>`<p><b>第${i+1}天 · ${day.minutes/60}小时</b><span>${day.courses.map(id=>esc(p.courses.find(c=>c.id===id).code)).join(' → ')}</span></p>`).join('')}</div>`:''}${notice(p.limitations)}${notice(p.warnings)}${r.questions.length?`<div class="advisor-questions"><b>可进一步确认</b>${list(r.questions)}</div>`:''}<p class="hint">模块参考价不包含全部实施费用，师资、差旅、场地和工具费用由机构确认。</p>${p.courses.length?'<button class="btn primary" type="button" data-advisor="apply">采用组合并继续编辑</button>':''}</div>`;
}
document.addEventListener('input',e=>{if(e.target.id==='advisor-message')Advisor.draft=e.target.value});
document.addEventListener('click',async e=>{
 const b=e.target.closest('[data-advisor]');if(!b)return;
 try{
  if(b.dataset.advisor==='example'){const f=$('#advisor-message');f.value=advisorExamples[+b.dataset.id];Advisor.draft=f.value;f.focus()}
  if(b.dataset.advisor==='reset'){if(Advisor.busy)return;sessionStorage.removeItem(advisorKey());Advisor.result=null;Advisor.error='';Advisor.draft='';await agentView()}
  if(b.dataset.advisor==='apply'){if(!Advisor.result)return;const p=Advisor.result.plan;await api('/plans/validate','POST',{...planDefaults(),...p,expected_versions:p.versions});await setFromPlan(p);toast('已载入推荐组合，可调整后保存或生成宣传素材。')}
 }catch(err){error(err)}
});
document.addEventListener('submit',async e=>{
 if(e.target.id!=='advisor-form')return;e.preventDefault();if(Advisor.busy)return;if(!requireLogin())return;
 const message=$('#advisor-message').value.trim();if(message.length<2)return;
 const scope=advisorKey(),org=S.org;Advisor.busy=true;Advisor.error='';Advisor.draft=message;$('#advisor-error').textContent='';const b=e.target.querySelector('[type=submit]');b.disabled=true;b.textContent='正在分析需求…';advisorRender();
 try{const r=await api('/agent/assistant','POST',{org_id:org,message,previous_id:Advisor.result?.id||null});
  if(scope!==advisorKey())return;
  Advisor.result=r;Advisor.draft='';sessionStorage.setItem(scope,r.id);
 }catch(err){if(scope===advisorKey())Advisor.error=err.message}
 finally{if(scope===advisorKey()){Advisor.busy=false;if(location.hash.split('?')[0]==='#agent')await agentView()}}
});
