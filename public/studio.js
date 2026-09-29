'use strict';
const Studio={job:null,poster:null,image:null,qr:null};
const studioStyles={academy:'院校研修',business:'企业内训',creative:'社会招生'};
function studioSameSource(job){return job.org_id===S.org&&JSON.stringify(job.source.ids)===JSON.stringify(S.cart)&&job.source.audience===S.plan.audience&&S.courses.filter(c=>S.cart.includes(c.id)).every(c=>job.source.versions[c.id]===c.version_id)}
async function studioPlan(){if(!S.cart.length)throw Error('请先选择课程');if($('#plan-form')){if(!$('#plan-form').reportValidity())throw Error('请检查组课信息');readPlan($('#plan-form'))}return await previewPlan()}
async function studioGenerate(kind,style='academy'){
 if(!requireLogin())return;
 const plan=await studioPlan(),cfg=await api('/creative/config');
 if(!cfg.available){modal('AI服务尚未连接','<p>平台管理员配置硅基流动 API Key 后，即可生成课程文案与海报背景。</p><p>现在仍可使用已有课程信息制作模板海报。</p>'+action('制作模板海报','studio-poster','','primary'));return}
 const request={plan:{...planPayload(),expected_versions:plan.versions},kind,style,request_key:crypto.randomUUID()};
 modal(kind==='copy'?'生成课程信息':'生成海报背景','<p>正在提交生成任务…</p><p class="hint">课程内容与培训需求将发送给硅基流动。任务记录可在“宣传素材”中查看。</p>');
 const job=await api('/creative/jobs','POST',request);await studioWatch(job.id);
}
async function studioWatch(id){
 Studio.job=id;
 modal('内容生成中',`<div class="loading">正在生成，通常需要一段时间…</div><p>可以关闭窗口，稍后到“宣传素材”查看结果。</p>`);
 $('#dialog').dataset.studioJob=id;
 for(let i=0;i<90;i++){
  const j=await api('/creative/jobs/'+id);
  if(Studio.job!==id)return;
  if(j.state==='complete'||j.state==='failed'){if($('#dialog').open&&$('#dialog').dataset.studioJob===id)studioResult(j);else toast(j.state==='complete'?'生成完成，可在宣传素材中查看':j.error);return}
  await new Promise(r=>setTimeout(r,2000));
 }
 if($('#dialog').open&&$('#dialog').dataset.studioJob===id)modal('任务仍在处理中','<p>请稍后到“宣传素材”查看任务状态。</p>');
}
function studioResult(j){
 Studio.result=j;
 if(j.state==='failed'){modal('生成未完成',`<p>${esc(j.error)}</p><p class="hint">本次未采用生成结果，未自动切换其他模型。</p>`);return}
 if(j.kind==='copy'){
  const c=j.result.copy;
  modal('课程信息草稿',`<p class="hint">检查后选择需要应用的字段。原有内容仅在点击“应用选中内容”后替换。</p><div class="studio-copy">${[['title','课程名称'],['subtitle','副标题'],['introduction','课程简介'],['objectives','培训目标'],['highlights','课程亮点'],['promotion','宣传摘要']].map(([k,t])=>`<section><label class="check"><input type="checkbox" name="studio-field" value="${k}" checked><b>${t}</b></label>${Array.isArray(c[k])?list(c[k]):`<p>${esc(c[k])}</p>`}</section>`).join('')}</div><div class="actions">${action('应用选中内容','studio-apply','','primary')}</div>`);
 }else modal('海报背景已生成',`<img class="studio-background" src="${esc(j.result.image_url)}" alt="AI生成的海报背景"><p class="hint">背景已保存；标题、课程亮点与机构信息由海报模板排版。</p>${action('用于当前海报','studio-use-image','','primary')}`);
}
async function studioHistory(){
 if(!requireLogin())return;
 const jobs=await api('/creative/jobs?org='+encodeURIComponent(S.org));
 $('#content').innerHTML=head('宣传素材','查看课程文案与海报背景生成记录。完成组课后，可在方案页面制作宣传海报。',link('返回课程组合','plan'))+`<div class="studio-jobs">${jobs.map(j=>`<article class="panel"><span class="badge type-${j.kind==='copy'?'F':'P'}">${j.kind==='copy'?'课程文案':'海报背景'}</span><h3>${esc(j.title)}</h3><p class="hint">${new Date(j.created*1000).toLocaleString()} · ${{queued:'排队中',running:'生成中',complete:'已完成',failed:'未完成'}[j.state]}</p>${j.error?`<p>${esc(j.error)}</p>`:''}${action('查看结果','studio-job',j.id)}</article>`).join('')||'<div class="empty">暂无生成记录。选择课程后，在培训方案中生成课程信息或海报背景。</div>'}</div>`;
}
async function studioPoster(){
 Studio.poster=await studioPlan();Studio.qr=null;
 modal('制作宣传海报',`<div class="studio-editor"><div><div class="form-grid">${select('宣传模板','poster-style',Object.entries(studioStyles),'academy')}${field('海报标题','poster-title',Studio.poster.title,'text','maxlength="100"')}${field('副标题','poster-subtitle',Studio.poster.subtitle||'专业课程 · 实践导向','text','maxlength="100"')}${field('机构名称','poster-org',S.orgs.find(x=>x.id===S.org)?.name||'','text','maxlength="80"')}${area('课程亮点（每行一条，最多3条）','poster-highlights',(Studio.poster.highlights?.length?Studio.poster.highlights:Studio.poster.courses.slice(0,3).map(c=>c.title)).join('\n'),'maxlength="500"')}${field('时间 / 报名说明（可选）','poster-note','','text','maxlength="100"')}${field('报名二维码（可选，本机排版）','poster-qr','','file','accept="image/png,image/jpeg"')}</div><div class="actions form-actions">${action('生成AI背景','studio-image')}${action('使用模板背景','studio-clear-image')}${action('下载 PNG','studio-download','','primary')}</div><p class="hint">修改文字与模板不调用模型。AI背景通过硅基流动生成，可在“宣传素材”再次取用。下载前请检查文字与二维码。</p></div><canvas id="poster-canvas" width="1080" height="1440" aria-label="宣传海报预览"></canvas></div>`);
 if(Studio.posterDraft)for(const [k,v] of Object.entries(Studio.posterDraft)){const f=$(`[name="${k}"]`);if(f)f.value=v}
 await studioDraw();
}
function posterLines(ctx,text,x,y,width,lineHeight,maxLines){
 let line='',linesOut=[];
 for(const ch of String(text)){if(ctx.measureText(line+ch).width>width&&line){linesOut.push(line);line=ch}else line+=ch}
 if(line)linesOut.push(line);
 if(linesOut.length>maxLines){linesOut=linesOut.slice(0,maxLines);let last=linesOut[maxLines-1];while(ctx.measureText(last+'…').width>width)last=last.slice(0,-1);linesOut[maxLines-1]=last+'…'}
 linesOut.forEach((s,i)=>ctx.fillText(s,x,y+i*lineHeight));return linesOut.length*lineHeight;
}
async function studioDraw(){
 const canvas=$('#poster-canvas');if(!canvas)return;const ctx=canvas.getContext('2d'),value=n=>$(`[name=poster-${n}]`)?.value||'';
 const palettes={academy:['#112744','#204a70','#efddae'],business:['#123d35','#286957','#f3ddb0'],creative:['#302446','#654185','#ffb59e']},[base,accent,gold]=palettes[value('style')];
 ctx.fillStyle=base;ctx.fillRect(0,0,1080,1440);
 if(Studio.image){ctx.drawImage(Studio.image,0,0,1080,1440);ctx.fillStyle=base+'bb';ctx.fillRect(0,0,1080,1440)}else{const g=ctx.createLinearGradient(0,0,1080,1440);g.addColorStop(0,base);g.addColorStop(1,accent);ctx.fillStyle=g;ctx.fillRect(0,0,1080,1440);ctx.strokeStyle=gold+'35';ctx.lineWidth=2;for(let i=0;i<5;i++){ctx.beginPath();ctx.arc(940,490,170+i*65,0,Math.PI*2);ctx.stroke()}}
 ctx.textBaseline='top';ctx.fillStyle=gold;ctx.font='600 25px "Microsoft YaHei",sans-serif';ctx.fillText('AI微课工坊  /  '+studioStyles[value('style')],72,76);
 ctx.fillStyle='#ffffff';ctx.font='700 68px "Microsoft YaHei",sans-serif';const titleHeight=posterLines(ctx,value('title'),72,175,936,92,4);
 ctx.fillStyle='#e1e9e5';ctx.font='30px "Microsoft YaHei",sans-serif';posterLines(ctx,value('subtitle'),72,200+titleHeight,936,45,2);
 ctx.fillStyle=gold;ctx.fillRect(72,705,64,5);ctx.font='600 26px "Microsoft YaHei",sans-serif';ctx.fillText('课程亮点',72,748);
 ctx.fillStyle='#ffffff';ctx.font='30px "Microsoft YaHei",sans-serif';lines(value('highlights')).slice(0,3).forEach((s,i)=>posterLines(ctx,`${String(i+1).padStart(2,'0')}  ${s}`,72,806+i*87,936,39,2));
 ctx.fillStyle=gold;ctx.font='600 27px "Microsoft YaHei",sans-serif';ctx.fillText(`${Studio.poster.total_minutes/60} 小时实训  ·  ${Studio.poster.courses.length} 个课程模块`,72,1110);
 ctx.fillStyle='#ffffff';ctx.font='500 28px "Microsoft YaHei",sans-serif';posterLines(ctx,value('org'),72,1190,Studio.qr?720:936,40,2);
 ctx.fillStyle='#dae5e1';ctx.font='22px "Microsoft YaHei",sans-serif';posterLines(ctx,value('note'),72,1282,Studio.qr?710:936,31,2);
 if(Studio.qr){ctx.fillStyle='#fff';ctx.fillRect(840,1180,170,170);ctx.drawImage(Studio.qr,850,1190,150,150)}
 ctx.font='16px "Microsoft YaHei",sans-serif';ctx.fillStyle='#d6e4dc';ctx.fillText(Studio.image?'背景由 AI 生成 · 课程安排以正式方案为准':'课程安排以正式方案为准',72,1380);
}
async function studioLoadImage(url){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(Error('图片读取失败'));img.src=url})}
document.addEventListener('click',async e=>{
 const b=e.target.closest('[data-action]');if(!b||!b.dataset.action.startsWith('studio-'))return;
 b.disabled=true;
 try{const a=b.dataset.action;
  if(a==='studio-copy')await studioGenerate('copy');
  if(a==='studio-poster'){Studio.image=null;Studio.posterDraft=null;await studioPoster()}
  if(a==='studio-image'){Studio.posterDraft=Object.fromEntries($$('[name^=poster-]').filter(f=>f.type!=='file').map(f=>[f.name,f.value]));await studioGenerate('image',$('[name=poster-style]').value)}
  if(a==='studio-job'){const j=await api('/creative/jobs/'+b.dataset.id);if(['queued','running'].includes(j.state))await studioWatch(j.id);else studioResult(j)}
  if(a==='studio-apply'){const j=Studio.result;if(!studioSameSource(j))throw Error('当前课程组合或培训对象已变化，请返回原组合或重新生成。');for(const x of $$('[name=studio-field]:checked'))S.plan[x.value]=j.result.copy[x.value];S.preview=null;$('#dialog').close();location.hash='plan';await route();toast('已应用到当前方案，请保存方案留存。')}
  if(a==='studio-use-image'){if(!studioSameSource(Studio.result))throw Error('请先载入生成时的课程组合，再使用此背景。');Studio.image=await studioLoadImage(Studio.result.result.image_url);if(!Studio.posterDraft)Studio.posterDraft={'poster-style':Studio.result.result.style};await studioPoster()}
  if(a==='studio-clear-image'){Studio.image=null;await studioDraw()}
  if(a==='studio-download'){await studioDraw();const c=$('#poster-canvas');c.toBlob(blob=>{if(!blob){toast('海报导出失败');return}const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='培训宣传海报.png';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)},'image/png')}
 }catch(err){error(err)}finally{b.disabled=false}
});
document.addEventListener('input',e=>{if(e.target.name?.startsWith('poster-')&&e.target.name!=='poster-qr')studioDraw().catch(error)});
document.addEventListener('change',async e=>{if(e.target.name!=='poster-qr')return;try{const f=e.target.files[0];if(!f){Studio.qr=null;await studioDraw();return}if(f.size>2*1024*1024||!['image/png','image/jpeg'].includes(f.type))throw Error('请选择不超过2MB的 PNG / JPG 二维码');const url=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(f)});Studio.qr=await studioLoadImage(url);await studioDraw()}catch(err){error(err)}});
