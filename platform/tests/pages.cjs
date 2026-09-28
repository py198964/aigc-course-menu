const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process'),path=require('path'),fs=require('fs'),assert=require('assert');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'platform/test-results');fs.mkdirSync(out,{recursive:true});
const live=process.env.PAGES_URL;const url=live||'http://127.0.0.1:8767/';
const server=live?null:spawn(path.join(root,'.venv/Scripts/python.exe'),['-m','http.server','8767','--bind','127.0.0.1'],{cwd:root,windowsHide:true,stdio:'ignore'});
let browser;
(async()=>{if(!live)for(let i=0;i<50;i++){try{if((await fetch(url)).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],failed=[];page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)failed.push(r.url()+' '+r.status())});page.on('dialog',d=>d.accept());
await page.goto(url+'#catalog');await page.locator('.course').first().waitFor();assert.equal(await page.locator('.course').count(),47);assert((await page.title()).includes('AI微课工坊'));
await page.locator('[data-action=detail]').first().click();await page.getByRole('tab',{name:'课程资料',exact:true}).click();assert.equal(await page.locator('.resource-empty').count(),3);await page.locator('[data-action=close]').click();
await page.locator('[data-action=cart]').first().click();await page.getByRole('link',{name:'生成课程方案',exact:true}).click();await page.locator('#plan-output .doc').waitFor();assert((await page.locator('#plan-output').textContent()).includes('学习目标'));
const dlPromise=page.waitForEvent('download');await page.locator('[data-action=export-json]').first().click();assert((await dlPromise).suggestedFilename().endsWith('.json'));
await page.goto(url+'#agent');await page.locator('#agent-form').waitFor();await page.locator('#agent-form button[type=submit]').click();await page.locator('[data-action=apply-agent]').waitFor();const result=await page.evaluate(()=>({minutes:S.agent.plan.total_minutes,days:S.agent.plan.schedule.length,warnings:S.agent.plan.warnings,courses:S.agent.plan.courses.length}));assert(result.courses>0&&result.minutes<=720&&result.days<=2);assert(!result.warnings.some(x=>x.includes('缺少先修')));
await page.locator('[data-action=apply-agent]').click();await page.locator('#plan-output .doc').waitFor();const mdPromise=page.waitForEvent('download');await page.locator('[data-action=export-md]').click();assert((await mdPromise).suggestedFilename().endsWith('.md'));
await page.goto(url+'#paths');await page.locator('[data-action=preset]').first().click();await page.locator('#plan-output .doc').waitFor();
await page.getByRole('button',{name:'平台服务',exact:true}).click();assert((await page.locator('#dialog-content').textContent()).includes('尚未连接'));assert.equal(await page.locator('#auth-form').count(),0);await page.locator('[data-action=close]').click();
await page.goto(url+'#catalog');await page.locator('.course').first().waitFor();await page.screenshot({path:path.join(out,live?'pages-live-desktop.png':'pages-desktop.png')});await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(out,live?'pages-live-mobile.png':'pages-mobile.png')});
assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);console.log(JSON.stringify({ok:true,url,courses:47,checks:['detail tabs','resource placeholders','cart','plan export','rule agent','markdown export','presets','honest service boundary','mobile layout'],errors,failed}));
})().catch(e=>{console.error(e);process.exitCode=1}).finally(async()=>{if(browser)await browser.close();if(server)server.kill()});
