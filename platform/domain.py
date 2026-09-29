import math
from pydantic import BaseModel, Field, ConfigDict, field_validator
from database import parse, dump
from security import fail, is_member

class Unit(BaseModel):
    name:str=Field(max_length=100)
    minutes:int=Field(ge=1,le=480,strict=True)
    points:list[str]=Field(default_factory=list,max_length=15)
    activity:str=Field(default='',max_length=1500)

class ModuleData(BaseModel):
    model_config=ConfigDict(extra='ignore')
    title:str=Field(min_length=2,max_length=150)
    category:str='F'
    intro:str=Field(default='',max_length=1500)
    description:str=Field(default='',max_length=6000)
    minutes:int=Field(default=60,ge=15,le=480,strict=True)
    price_fen:int=Field(default=0,ge=0,le=100000000,strict=True)
    price_scope:str=Field(default='模块内容参考价；师资实施、差旅、场地与AI工具用量以项目报价为准。',max_length=1500)
    class_size:int=Field(default=30,ge=1,le=1000,strict=True)
    delivery:str='线上或线下'
    visibility:str='public'
    track:str='通用'
    tools:str=Field(default='',max_length=500)
    level:str='入门'
    audience:str=Field(default='',max_length=500)
    objectives:list[str]=Field(default_factory=list,max_length=12)
    syllabus:list[Unit]=Field(default_factory=list,max_length=20)
    exercise:str=Field(default='',max_length=3000)
    output:str=Field(default='',max_length=1500)
    criteria:list[str]=Field(default_factory=list,max_length=15)
    materials:list[str]=Field(default_factory=list,max_length=30)
    homework:str=Field(default='',max_length=3000)
    note:str=Field(default='',max_length=3000)
    prereq_ids:list[str]=Field(default_factory=list,max_length=20)
    prereq_mode:str='all'
    marketing_prompt:str=Field(default='',max_length=12000)
    method_cards:list[dict]=Field(default_factory=list,max_length=30)
    shot_template:str=Field(default='',max_length=4000)
    @field_validator('category')
    @classmethod
    def cat(cls,v):
        if v not in ('F','T','P','B'):raise ValueError('类别必须为F、T、P或B')
        return v
    @field_validator('visibility')
    @classmethod
    def visible(cls,v):
        if v not in ('public','organization'):raise ValueError('无效可见范围')
        return v
    @field_validator('prereq_mode')
    @classmethod
    def reqmode(cls,v):
        if v not in ('all','any'):raise ValueError('前置关系必须为all或any')
        return v

def visible_version(d,module_id,user=None):
    r=d.execute('SELECT m.*,v.data,v.number,v.id AS version_id,o.name AS org_name,u.name AS author_name FROM modules m JOIN versions v ON v.id=m.published_id JOIN orgs o ON o.id=m.org_id JOIN users u ON u.id=m.author_id WHERE m.id=? AND m.active=1 AND o.active=1',(module_id,)).fetchone()
    if not r:fail(404,'课程未发布或已下架')
    c=parse(r['data'])
    if c['visibility']!='public' and not is_member(d,r['org_id'],user):fail(404,'课程不可见')
    return {**c,'id':r['id'],'code':r['code'],'org_id':r['org_id'],'org_name':r['org_name'],'author_name':r['author_name'],'version_id':r['version_id'],'version':r['number']}

def public_course(c):return {k:v for k,v in c.items() if k!='marketing_prompt'}

def publish_check(d,m,c,user):
    if not c['intro'].strip() or not c['description'].strip() or not c['audience'].strip() or not c['objectives'] or not c['exercise'].strip() or not c['output'].strip() or not c['criteria'] or not c['price_scope'].strip():fail(422,'请补齐简介、详细介绍、对象、目标、练习、成果、评价与费用范围')
    if not c['syllabus'] or sum(u['minutes'] for u in c['syllabus'])!=c['minutes']:fail(422,'课纲分钟数必须等于课程时长')
    seen=set()
    def visit(mid):
        if mid==m['id']:fail(422,'课程前置存在循环')
        if mid in seen:return
        seen.add(mid)
        p=visible_version(d,mid,user)
        if p['org_id']!=m['org_id']:fail(422,'前置课程必须属于当前机构')
        if c['visibility']=='public' and p['visibility']!='public':fail(422,'公开课程不能依赖内部课程')
        for dep in p['prereq_ids']:visit(dep)
    for dep in c['prereq_ids']:visit(dep)

def validate_plan(d,org,ids,user,daily=360,days=0,people=20,budget_fen=None,equivalent=False,batches=1,expected=None):
    if not isinstance(ids,list) or len(ids)>100 or any(not isinstance(x,str) for x in ids):fail(422,'课程数量或编号无效')
    ids=list(dict.fromkeys(ids));courses=[];warnings=[];seen=set()
    for mid in ids:
        c=visible_version(d,mid,user)
        if c['org_id']!=org:fail(422,'一份方案限同一机构课程')
        if expected and expected.get(mid) and expected[mid]!=c['version_id']:fail(409,'课程已有新版本，请重新核对并确认组合')
        req=c['prereq_ids'];passed=not req or (any(x in seen for x in req) if c['prereq_mode']=='any' else all(x in seen for x in req))
        if not passed and not equivalent:warnings.append(c['code']+'缺少先修模块或顺序不正确')
        if people>c['class_size']:warnings.append(c['code']+'超过建议班额，需要机构确认')
        if c['minutes']>daily:warnings.append(c['code']+'单模块超过每天净教学时长')
        seen.add(mid);courses.append(c)
    schedule=[];current=[];mins=0
    for c in courses:
        if current and mins+c['minutes']>daily:schedule.append({'minutes':mins,'courses':current});current=[];mins=0
        current.append(c['id']);mins+=c['minutes']
    if current:schedule.append({'minutes':mins,'courses':current})
    total=sum(c['minutes'] for c in courses);price=sum(c['price_fen'] for c in courses)*batches
    if days and len(schedule)>days:warnings.append('完整模块排课超过目标天数')
    if days and total<days*daily:warnings.append(f'距离目标净课时尚余{days*daily-total}分钟，可安排加练或补充模块')
    if budget_fen is not None and price>budget_fen:warnings.append('模块参考小计超过预算')
    return {'courses':[public_course(c) for c in courses],'ids':ids,'versions':{c['id']:c['version_id'] for c in courses},'total_minutes':total,'subtotal_fen':price,'schedule':schedule,'warnings':warnings,'daily_minutes':daily,'days':days,'people':people,'budget_fen':budget_fen,'equivalent':equivalent,'batches':batches,'price_note':'模块参考小计；未明确的实施、差旅、场地及工具费用另行询价。'}

def recommend(d,org,user,req):
    rows=d.execute('SELECT id FROM modules WHERE org_id=? AND active=1 AND published_id IS NOT NULL',(org,)).fetchall();pool={}
    for row in rows:
        try:c=visible_version(d,row['id'],user);pool[c['id']]=c
        except Exception:continue
    theme=req['theme'];tokens={'口播':['口播','数字人','配音'],'转绘':['转绘','Redraw','尾帧'],'短剧':['短剧','剧情','分镜','角色'],'教学':['教学','微课','讲解'],'广告':['广告','产品','电商','卖点'],'综合':['视频','基础','交付']}[theme]
    selected=[];reasons={};capacity=req['days']*req['daily_minutes'];budget=req['budget_fen'];skipped=[]
    def closure(mid,stack=None):
        stack=set() if stack is None else set(stack)
        if mid in stack or mid not in pool:raise ValueError('依赖不可用')
        if mid in selected:return []
        stack.add(mid);c=pool[mid];out=[]
        deps=[] if req['equivalent'] else c['prereq_ids']
        if c['prereq_mode']=='any' and deps:
            valid=[x for x in deps if x in pool]
            if not valid:raise ValueError('依赖不可用')
            deps=[next((x for x in valid if x in selected),min(valid,key=lambda x:(pool[x]['price_fen'],pool[x]['minutes'])))]
        for dep in deps:out+=closure(dep,stack)
        return list(dict.fromkeys(out+[mid]))
    def score(c):
        text=c['title']+' '+c['intro']+' '+c['audience']
        value=sum(5 for t in tokens if t in text)+(3 if c['category']=='P' else 0)
        if req['level']=='入门' and c['code'] in ('F01','F06','F12'):value+=18
        return value
    candidates=sorted(pool.values(),key=lambda c:(-score(c),c['code']))
    must=list(dict.fromkeys(req['required_ids']))
    for mid in must+[c['id'] for c in candidates if score(c)>0]:
        if mid in selected:continue
        try:extra=[x for x in closure(mid) if x not in selected]
        except ValueError:
            if mid in must:skipped.append('必选课程或其前置不可用')
            continue
        candidate=selected+extra
        # Exact whole-module scheduling, not only the sum of hours.
        result=validate_plan(d,org,candidate,user,req['daily_minutes'],req['days'],req['people'],budget,req['equivalent'])
        fits=(len(result['schedule'])<=req['days'] and all(pool[x]['minutes']<=req['daily_minutes'] for x in candidate) and (budget is None or result['subtotal_fen']<=budget))
        if fits:
            selected=candidate
            for x in extra:reasons[x]='满足所选模块的工具前置' if x!=mid else ('用户指定必选' if mid in must else '匹配'+theme+'主题'+('及零基础起点' if pool[x]['code'] in ('F01','F06','F12') else ''))
        elif mid in must:skipped.append(pool.get(mid,{}).get('code','必选课程')+'及其前置超出完整排课容量或模块预算')
    result=validate_plan(d,org,selected,user,req['daily_minutes'],req['days'],req['people'],budget,req['equivalent'])
    result.update(title=req['audience']+'·'+theme+'视频创作课程',audience=req['audience'],notes=req['notes'],reasons=reasons,mode='rules',limitations=skipped+['按课程主题、学习起点、前置、完整模块时长和模块参考价匹配；实际项目费用由机构确认。'])
    return result

def lesson_markdown(plan):
    cs={c['id']:c for c in plan['courses']};lines=['# '+plan.get('title','课程方案'),'','对象：'+plan.get('audience','社会学员'),f"净课时：{plan['total_minutes']}分钟；模块参考小计：¥{plan['subtotal_fen']/100:.2f}",plan['price_note'],'','## 课程简介',plan.get('introduction') or ('围绕'+plan.get('title','视频创作')+'，通过'+str(len(cs))+'个模块完成方法学习、案例练习和成果检查。'),'','## 组课条件']
    if plan.get('subtitle'):lines+=['',plan['subtitle']]
    if plan.get('objectives'):lines+=['','## 培训目标']+['- '+x for x in plan['objectives']]
    if plan.get('highlights'):lines+=['','## 课程亮点']+['- '+x for x in plan['highlights']]
    lines+=['- '+x for x in plan['warnings']]
    if plan.get('notes'):lines+=['','需求重点：'+plan['notes']]
    for i,day in enumerate(plan['schedule'],1):
        lines+=['',f"## 第{i}天 · {day['minutes']}分钟"]
        for mid in day['courses']:
            c=cs[mid];lines+=['',f"### {c['code']} {c['title']}（版本{c['version']}）",c['description'],'目标：'+'；'.join(c['objectives']),'成果：'+c['output']]
            for u in c['syllabus']:lines.append(f"- {u['name']} · {u['minutes']}分钟："+'；'.join(u['points']))
            lines+=['练习：'+c['exercise'],'评价：'+'；'.join(c['criteria']),'课前：'+'；'.join(c['materials']),'实施说明：'+c['note'],'费用范围：'+c['price_scope']]
    lines+=['','## 宣传摘要',plan.get('promotion') or ('面向'+plan.get('audience','学习者')+'，以实际作品为线索完成'+str(plan['total_minutes']//60)+'小时模块化训练。涵盖'+ '、'.join(c['title'].split('：')[0] for c in list(cs.values())[:5])+'。具体授课及成果范围以方案为准。'),'','课间、午休和安装另计；参考价不等于最终项目报价。']
    return '\n'.join(lines)
