/* Course details share the same authorized asset API as project resources. */
function resourceType(asset) {
  const ext=asset.name.split('.').pop().toLowerCase();
  return ['ppt','pptx','pdf'].includes(ext)?'slides':['mp4','webm'].includes(ext)?'video':'file';
}
function resourceEntry(a) {
  const ext=a.name.split('.').pop().toLowerCase();
  const preview=['pdf','mp4','webm'].includes(ext);
  const size=a.size>=1024*1024?(a.size/1024/1024).toFixed(1)+' MB':(a.size/1024).toFixed(1)+' KB';
  return `<div class="resource-entry"><div><strong>${esc(a.name)}</strong><span class="hint">${esc(ext.toUpperCase())} · ${size}</span></div><div class="actions">${preview?action(ext==='pdf'?'在线预览':'播放视频','preview-resource',a.id,'small'):''}<a class="btn small" href="/api/assets/${encodeURIComponent(a.id)}">下载</a></div></div>`;
}
function courseResources(c) {
  const assets=c.assets||[];
  const groups=[['slides','PPT与课件','课件资料','支持PPT下载、PDF在线预览。'],['video','课程录播','录播视频','支持MP4 / WebM在线播放与下载。'],['file','配套资料','练习与素材','课程练习、项目素材与参考文档。']];
  return `<div class="resource-intro"><h3>课程资料</h3><p class="muted">课件、录播与练习资料随课程发布，按授课安排及账号权限开放。</p></div><div class="resource-sections">${groups.map(([kind,title,label,note])=>{const found=assets.filter(a=>resourceType(a)===kind);return `<section class="resource-group"><div class="resource-group-heading"><span class="resource-symbol ${kind}">${kind==='slides'?'PPT':kind==='video'?'▶':'DOC'}</span><div><h4>${title}</h4><p>${note}</p></div><span class="resource-count">${found.length?found.length+' 份':'待提供'}</span></div>${found.length?found.map(resourceEntry).join(''):`<div class="resource-empty">暂无可访问的${label}。资料发布或授权后，可在此查看。</div>`}</section>`}).join('')}</div><div id="resource-viewer" aria-live="polite"></div>`;
}
function detailPane(c,tab) {
  if(tab==='resources')return courseResources(c);
  if(tab==='syllabus')return `<div class="section-heading"><h3>教学大纲</h3><span>${c.syllabus.length} 个环节 · 共 ${c.minutes} 分钟</span></div><ol class="syllabus-timeline">${c.syllabus.map((u,i)=>`<li><span class="step-number">${String(i+1).padStart(2,'0')}</span><div class="step-content"><div class="step-title"><h4>${esc(u.name)}</h4><span>${u.minutes} 分钟</span></div>${list(u.points)}${u.activity?`<p class="step-activity"><strong>教学活动</strong>${esc(u.activity)}</p>`:''}</div></li>`).join('')}</ol>${c.method_cards?.length?`<section class="detail-section"><h3>镜头方法卡</h3>${c.method_cards.map(m=>`<details class="method-card"><summary>${esc(m.name||m.title||'方法卡')}</summary>${list(m.points||[])}</details>`).join('')}</section>`:''}${c.shot_template?`<section class="detail-section"><h3>镜头施工单</h3><p>${esc(c.shot_template)}</p></section>`:''}`;
  const prereqs=(c.prereq_ids||[]).map(id=>S.courses.find(x=>x.id===id)).filter(Boolean);
  return `<section class="detail-section"><h3>课程介绍</h3><p>${esc(c.description)}</p></section><section class="detail-section"><h3>学习目标</h3><ol class="objective-list">${c.objectives.map((x,i)=>`<li><span>${String(i+1).padStart(2,'0')}</span>${esc(x)}</li>`).join('')}</ol></section><div class="detail-columns"><section class="detail-section"><h3>实践任务</h3><p>${esc(c.exercise)}</p><div class="deliverable"><span>课程成果</span><p>${esc(c.output)}</p></div></section><section class="detail-section"><h3>评价标准</h3>${list(c.criteria)}</section></div><section class="detail-section"><h3>学习准备</h3>${list(c.materials)}<p><strong>先修要求：</strong>${prereqs.length?esc(prereqs.map(x=>x.code+' '+x.title).join(c.prereq_mode==='any'?' / ':'、'))+'（'+(c.prereq_mode==='any'?'任一满足':'全部满足')+'）':'无需必修先修课程。'}</p>${c.homework?`<p><strong>课后练习：</strong>${esc(c.homework)}</p>`:''}${c.note?`<p class="hint">${esc(c.note)}</p>`:''}</section>`;
}
function renderCourseDetail(c,tab='overview') {
  S.detailCourse=c;S.detailTab=tab;
  modal('课程详情',`<article class="course-detail"><header class="detail-heading"><div class="detail-badges"><span class="badge type-${c.category}">${c.code} · ${cats[c.category]}</span><span>${esc(c.level)} · ${c.minutes/60} 小时</span></div><h2>${esc(c.title)}</h2><p>${esc(c.intro)}</p></header><div class="detail-layout"><div class="detail-main"><div class="detail-tabs" role="tablist" aria-label="课程详情栏目">${[['overview','课程概览'],['syllabus','教学大纲'],['resources','课程资料']].map(([key,title])=>`<button type="button" id="detail-tab-${key}" role="tab" aria-selected="${key===tab}" aria-controls="detail-pane" tabindex="${key===tab?'0':'-1'}" data-action="detail-tab" data-id="${key}">${title}</button>`).join('')}</div><div id="detail-pane" role="tabpanel" tabindex="0" aria-labelledby="detail-tab-${tab}">${detailPane(c,tab)}</div></div><aside class="detail-facts"><div class="detail-price-label">模块参考价 / 班次</div><div class="detail-price">${money(c.price_fen)}</div><p class="hint">${esc(c.price_scope)}</p><dl><dt>适合对象</dt><dd>${esc(c.audience)}</dd><dt>使用工具</dt><dd>${esc(c.tools)}</dd><dt>授课形式</dt><dd>${esc(c.delivery)}</dd><dt>建议班额</dt><dd>${c.class_size} 人 / 班</dd></dl>${action(S.cart.includes(c.id)?'已加入组合 · 移除':'加入课程组合','detail-cart',c.id,'primary block')}<div class="detail-version">${esc(c.org_name)} · 课程版本 ${c.version}</div></aside></div></article>`);
  $('#dialog').classList.add('course-dialog');
}
function previewResource(id) {
  const a=S.detailCourse?.assets.find(x=>x.id===id);if(!a)return;
  const ext=a.name.split('.').pop().toLowerCase(),target=$('#resource-viewer');
  target.innerHTML=`<section class="resource-preview"><div class="section-heading"><h3>${esc(a.name)}</h3>${action('关闭预览','close-preview','','small')}</div>${ext==='pdf'?`<iframe title="${esc(a.name)} PDF预览" src="/api/assets/${encodeURIComponent(id)}/preview"></iframe>`:`<video controls playsinline preload="metadata" aria-label="${esc(a.name)}" src="/api/assets/${encodeURIComponent(id)}/preview">浏览器不支持在线播放，请下载视频。</video><p class="hint">若浏览器不支持此视频编码，可下载后使用本地播放器打开。</p>`}<p><a href="/api/assets/${encodeURIComponent(id)}">下载原文件</a></p></section>`;
  target.scrollIntoView({behavior:'smooth',block:'nearest'});
  const video=$('video',target);if(video)video.addEventListener('error',()=>{const p=document.createElement('p');p.className='error';p.textContent='暂时无法播放此视频，请确认文件格式及访问权限，或下载后播放。';target.append(p)},{once:true});
}
