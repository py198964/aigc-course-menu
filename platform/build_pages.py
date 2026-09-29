"""Build the public Pages site, using only the reviewed seed catalogue and web files."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DEST=ROOT.parent
PUBLIC=DEST/'public'

def build():
    PUBLIC.mkdir(exist_ok=True)
    courses=[]
    for raw in json.loads((ROOT/'seed_courses.json').read_text(encoding='utf-8')):
        if raw['visibility']!='public':continue
        c={k:v for k,v in raw.items() if k!='marketing_prompt'}
        version=hashlib.sha256(json.dumps(c,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:12]
        c.update(id=c['code'],version=1,version_id=version,org_id='aigc-public',org_name='微墨AIGC培训学院',author_name='课程教研团队')
        courses.append(c)
    (PUBLIC/'catalog.json').write_text(json.dumps(courses,ensure_ascii=False,indent=2),encoding='utf-8')
    for name in ['studio.js','training-themes.json','style.css','logo.svg','course-detail.js','organizations.js','presets.json','public-mode.js']:
        (PUBLIC/name).write_bytes((ROOT/'web'/name).read_bytes())
    js=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
    js=js.replace("async function api(path,method='GET',body){", "async function api(path,method='GET',body){if(window.COURSE_PUBLIC_MODE)return publicApi(path,method,body);")
    js=js.replace('function requireLogin(){', 'function requireLogin(){if(window.COURSE_PUBLIC_MODE){publicServiceInfo();return false;}')
    js=js.replace('function auth(mode){', 'function auth(mode){if(window.COURSE_PUBLIC_MODE){publicServiceInfo();return;}')
    js=js.replace("action('登录 / 注册','login'", "action('平台服务','login'")
    js=js.replace("action('保存方案','save-plan')", "action('导出保存','export-json')")
    js=js.replace("action('提交询价','inquire')", "action('询价与机构服务','login')")
    js=js.replace("case 'agent-form':if(!requireLogin())break;", "case 'agent-form':")
    js=js.replace("fetch('/static/training-themes.json')", "fetch('public/training-themes.json')")
    js=js.replace("fetch('/static/presets.json')", "fetch('public/presets.json')")
    js=js.replace("当前提供规则组课，AI文案服务暂未启用。", "当前为公开站的浏览器规则组课，无需登录。")
    (PUBLIC/'app.js').write_text(js,encoding='utf-8')
    html=(ROOT/'web'/'index.html').read_text(encoding='utf-8').replace('/static/','public/')
    html=html.replace('<script src="public/app.js" defer>', '<script src="public/public-mode.js" defer></script><script src="public/app.js" defer>')
    html=html.replace('模块参考价按班次计算，实施费用以机构报价为准。','公开课程站 · 组课数据保存在当前浏览器 · 机构服务需独立部署。')
    (DEST/'index.html').write_text(html,encoding='utf-8')
    (DEST/'.nojekyll').touch()
    print(f'Built public Pages site: {len(courses)} courses; no accounts, private prompts or runtime data.')

if __name__=='__main__':build()
