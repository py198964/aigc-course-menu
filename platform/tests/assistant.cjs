/* External AI is simulated here; real-provider checks are run separately. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process'),fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..'),out=path.join(root,'test-results'),data=path.join(out,'assistant-'+Date.now());fs.mkdirSync(data,{recursive:true});
const url='http://127.0.0.1:8768',log=fs.openSync(path.join(data,'server.log'),'w');
const server=spawn(path.resolve(root,'../.venv/Scripts/python.exe'),[path.join(root,'tests/studio_server.py')],{cwd:root,windowsHide:true,env:{...process.env,COURSE_DATA_DIR:data,APP_ORIGIN:url,BOOTSTRAP_PASSWORD:'Assistant-Test-24680',SILICONFLOW_API_KEY:'fixture-not-real'},stdio:['ignore',log,log]});let browser,page;
(async()=>{
 for(let i=0;i<60;i++){try{if((await fetch(url+'/api/health')).ok)break}catch{}await new Promise(r=>setTimeout(r,200))}
 browser=await chromium.launch({channel:'msedge',headless:true});page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(url);await page.locator('.course').first().waitFor();await page.locator('[data-action=login]').click();await page.locator('#auth-form [name=email]').fill('owner@local.test');await page.locator('#auth-form [name=password]').fill('Assistant-Test-24680');await page.locator('#auth-form button[type=submit]').click();await page.locator('#dialog').waitFor({state:'hidden'});
 await page.goto(url+'/#agent');await page.locator('[data-advisor=example]').first().click();assert((await page.locator('#advisor-message').inputValue()).includes('老师'));
 await page.locator('#advisor-message').fill('企业新媒体团队两天视频培训');await page.locator('#advisor-form [type=submit]').click();await page.locator('[data-advisor=apply]').waitFor();assert((await page.locator('.advisor-result').textContent()).includes('2天'));assert(await page.locator('.advisor-course-list article').count()>0);
 await page.locator('#advisor-message').fill('改成一天');await page.locator('#advisor-form [type=submit]').click();await page.locator('.advisor-thread p').nth(1).waitFor();assert((await page.locator('.advisor-result .summary').textContent()).includes('1天'));
 await page.reload();await page.locator('.advisor-thread p').nth(1).waitFor();await page.screenshot({path:path.join(out,'assistant-desktop.png')});
 await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(out,'assistant-mobile.png'),fullPage:true});
 await page.locator('[data-advisor=apply]').click();await page.locator('#plan-form').waitFor();assert.equal(await page.locator('#plan-form [name=days]').inputValue(),'1');await page.locator('[data-action=save-plan]').click();await page.getByText('方案已保存',{exact:true}).waitFor();
 await page.goto(url+'/#saved');await page.locator('[data-action=load-plan]').first().click();await page.locator('#plan-form').waitFor();assert.equal(await page.locator('#plan-form [name=days]').inputValue(),'1');
 await page.goto(url+'/#agent');await page.locator('[data-advisor=reset]').click();await page.locator('.advisor-result').waitFor({state:'hidden'});
 await page.locator('.advisor-manual summary').click();await page.locator('#agent-form [type=submit]').click();await page.locator('[data-action=apply-agent]').waitFor();assert.deepEqual(errors,[]);
 console.log(JSON.stringify({ok:true,provider:'simulated',checks:['natural-language request','follow-up changes','session restore','mobile layout','adopt and save','saved plan reload','new conversation','manual rules preserved'],errors}));
})().catch(async e=>{if(page)await page.screenshot({path:path.join(out,'assistant-failure.png')});console.error(e);process.exitCode=1}).finally(async()=>{if(browser)await browser.close();server.kill();fs.closeSync(log)});
