/* GitHub Pages: public catalogue and local planning. No account or server emulation. */
window.COURSE_PUBLIC_MODE=true;
let publicCatalogPromise;
async function publicCatalog(){
  if(!publicCatalogPromise)publicCatalogPromise=fetch('public/catalog.json').then(r=>{if(!r.ok)throw Error('课程数据读取失败');return r.json()});
  return publicCatalogPromise;
}
function publicServiceInfo(){
  modal('平台服务',`<p>您正在访问 AI微课工坊的公开课程站，可浏览课程、组合培训方案、生成组课建议及导出教案。</p><div class="notice">机构账号、课程发布审核、客户询价和项目报价需要完整系统服务。当前公开站尚未连接这些服务。</div><p>课程组合保存在当前浏览器中，建议导出文件留存。完整系统源码和服务器部署包已在 GitHub 提供。</p><div class="actions"><a class="btn primary" href="https://github.com/py198964/aigc-course-menu/releases/latest" target="_blank" rel="noopener">下载完整系统</a><a class="btn" href="https://github.com/py198964/aigc-course-menu/tree/main/platform" target="_blank" rel="noopener">查看部署说明</a></div>`);
}
function publicPlan(body,cs){
  if(body.org_id!=='aigc-public')throw Error('此方案属于独立机构系统，请使用原系统打开，或导入旧版课程编号组合。');
  const ids=[...new Set(body.ids||[])];if(ids.length>100)throw Error('课程数量超限');
  const daily=Number(body.daily_minutes??360),days=Number(body.days??0),people=Number(body.people??20),batches=Number(body.batches??1);
  if(!Number.isInteger(daily)||daily<60||daily>480||!Number.isInteger(days)||days<0||days>30||!Number.isInteger(people)||people<1||people>10000||!Number.isInteger(batches)||batches<1||batches>100)throw Error('排课参数无效');
  if(body.budget_fen!=null&&(!Number.isInteger(body.budget_fen)||body.budget_fen<0))throw Error('预算无效');
  const courses=[],warnings=[],seen=new Set();
  for(const id of ids){const c=cs.find(x=>x.id===id);if(!c)throw Error('课程已不可用：'+id);if(body.expected_versions?.[id]&&body.expected_versions[id]!==c.version_id)throw Error('课程版本已变化，请确认使用当前版本');const req=c.prereq_ids||[];if(req.length&&!body.equivalent&&!(c.prereq_mode==='any'?req.some(x=>seen.has(x)):req.every(x=>seen.has(x))))warnings.push(c.code+'缺少先修模块或顺序不正确');if(people>c.class_size)warnings.push(c.code+'超过建议班额，需要机构确认');if(c.minutes>daily)warnings.push(c.code+'单模块超过每天净教学时长');courses.push(c);seen.add(id)}
  const schedule=[];let current=[],minutes=0;
  for(const c of courses){if(current.length&&minutes+c.minutes>daily){schedule.push({minutes,courses:current});current=[];minutes=0}current.push(c.id);minutes+=c.minutes}if(current.length)schedule.push({minutes,courses:current});
  const total=courses.reduce((n,c)=>n+c.minutes,0),price=courses.reduce((n,c)=>n+c.price_fen,0)*batches;
  if(days&&schedule.length>days)warnings.push('完整模块排课超过目标天数');if(days&&total<days*daily)warnings.push(`距离目标净课时尚余${days*daily-total}分钟，可安排加练或补充模块`);if(body.budget_fen!=null&&price>body.budget_fen)warnings.push('模块参考小计超过预算');
  return {org_id:'aigc-public',ids,courses,versions:Object.fromEntries(courses.map(c=>[c.id,c.version_id])),title:body.title||`${body.audience||'社会学员'}·AIGC视频创作（${total/60}小时）`,audience:body.audience||'社会学员',notes:body.notes||'',introduction:body.introduction||'',promotion:body.promotion||'',total_minutes:total,subtotal_fen:price,schedule,warnings,daily_minutes:daily,days,people,batches,budget_fen:body.budget_fen??null,equivalent:!!body.equivalent,price_note:'模块参考小计；未明确的实施、差旅、场地及工具费用另行询价。'};
}
function publicRecommend(req,cs){
  const themes={'口播':['口播','数字人','配音'],'转绘':['转绘','Redraw','尾帧'],'短剧':['短剧','剧情','分镜','角色'],'教学':['教学','微课','讲解'],'广告':['广告','产品','电商','卖点'],'综合':['视频','基础','交付']};
  if(!themes[req.theme])throw Error('主题无效');
  const pool=new Map(cs.map(c=>[c.id,c]));let selected=[];const reasons={},limitations=[];
  function closure(id,stack=new Set()){if(!pool.has(id)||stack.has(id))throw Error('先修课程不可用');if(selected.includes(id))return [];const c=pool.get(id),next=new Set([...stack,id]);let deps=req.equivalent?[]:c.prereq_ids;if(c.prereq_mode==='any'&&deps.length){const valid=deps.filter(x=>pool.has(x)).sort((a,b)=>pool.get(a).price_fen-pool.get(b).price_fen||pool.get(a).minutes-pool.get(b).minutes);deps=[valid.find(x=>selected.includes(x))||valid[0]]}return [...new Set([...deps.flatMap(x=>closure(x,next)),id])]}
  function score(c){const text=c.title+' '+c.intro+' '+c.audience;return themes[req.theme].filter(t=>text.includes(t)).length*5+(c.category==='P'?3:0)+(req.level==='入门'&&['F01','F06','F12'].includes(c.code)?18:0)}
  const must=[...new Set(req.required_ids||[])];if(must.length>20)throw Error('优先保留模块最多20个');
  const candidates=[...cs].sort((a,b)=>score(b)-score(a)||a.code.localeCompare(b.code)).filter(c=>score(c)>0);
  for(const id of [...must,...candidates.map(c=>c.id)]){if(selected.includes(id))continue;let extra;try{extra=closure(id).filter(x=>!selected.includes(x))}catch{if(must.includes(id))limitations.push('必选课程或其先修课程不可用');continue}const test=publicPlan({...req,ids:[...selected,...extra]},cs);if(test.schedule.length<=req.days&&test.courses.every(c=>c.minutes<=req.daily_minutes)&&(req.budget_fen==null||test.subtotal_fen<=req.budget_fen)){selected=test.ids;for(const x of extra)reasons[x]=x===id?(must.includes(id)?'用户指定必选':'匹配'+req.theme+'主题'):'满足所选模块的工具前置'}else if(must.includes(id))limitations.push(pool.get(id).code+'及其前置超出排课容量或模块预算')}
  return {...publicPlan({...req,ids:selected,title:req.audience+'·'+req.theme+'视频创作课程'},cs),mode:'rules',reasons,limitations:[...limitations,'公开站在浏览器内完成规则组课；实际项目费用与授课安排由机构确认。']};
}
async function publicApi(path,method='GET',body){
  if(path==='/assets/config')return {max_upload_mb:512};
  if(path==='/auth/me')return {user:null,memberships:[]};
  if(path==='/orgs')return [{id:'aigc-public',name:'微墨AIGC培训学院',description:'公开课程目录与培训方案'}];
  if(path==='/agent/config')return {ai_available:false,default_mode:'rules'};
  const cs=await publicCatalog();
  if(path.startsWith('/catalog?'))return cs;
  if(path.startsWith('/modules/')){const c=cs.find(x=>x.id===path.split('/').pop());if(!c)throw Error('课程不存在');return {...c,assets:[]}}
  if(path==='/plans/validate'&&method==='POST')return publicPlan(body,cs);
  if(path==='/agent/plan'&&method==='POST'){const plan=publicRecommend(body,cs);return {id:'browser-plan',plan,markdown:exportMd(plan)}}
  throw Error('该功能需要完整系统服务，请通过右上角“平台服务”查看部署说明。');
}
