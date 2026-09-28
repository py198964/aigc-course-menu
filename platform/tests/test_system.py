import sys, json
from pathlib import Path
from datetime import date,timedelta
import pytest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import database, manage, app as server
from security import password_hash
from domain import publish_check

@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(database,'DATA',tmp_path);monkeypatch.setattr(database,'DB',tmp_path/'test.sqlite3')
    monkeypatch.setattr(manage,'DATA',tmp_path);monkeypatch.setattr(manage,'DB',tmp_path/'test.sqlite3')
    monkeypatch.setattr(server,'DATA',tmp_path);(tmp_path/'files').mkdir()
    monkeypatch.setenv('BOOTSTRAP_PASSWORD','Owner-Test-Only-24680')
    manage.bootstrap()
    owner=TestClient(server.app);owner.headers['X-Requested-With']='course-platform'
    r=owner.post('/api/auth/login',json={'email':'owner@local.test','password':'Owner-Test-Only-24680'});assert r.status_code==200,r.text
    owner.headers['X-CSRF-Token']=r.json()['csrf'];me=owner.get('/api/auth/me').json();org=me['memberships'][0]['id']
    def customer(email='customer@example.test'):
        c=TestClient(server.app);c.headers['X-Requested-With']='course-platform'
        r=c.post('/api/auth/register',json={'email':email,'name':email.split('@')[0],'password':'Customer-Test-Only-24680'});assert r.status_code==200,r.text
        c.headers['X-CSRF-Token']=r.json()['csrf'];return c
    return owner,org,customer

def create_module(client,org,code_title='Test module',price=0):
    data={'title':code_title,'category':'P','intro':'A complete intro','description':'A course with real practice','audience':'New learners','minutes':60,'price_fen':price,'objectives':['Learn workflow'],'exercise':'Produce a short clip','output':'One video','criteria':['Complete flow'],'syllabus':[{'name':'Practice','minutes':60,'points':['Prepare','Build','Review'],'activity':'Make a clip'}]}
    r=client.post('/api/orgs/'+org+'/modules',json={'data':data});assert r.status_code==200,r.text
    return r.json()['id']

def publish(client,mid):
    v=client.get('/api/manage/modules/'+mid).json()['versions'][0]
    r=client.post('/api/manage/modules/'+mid+'/review',json={'action':'submit','revision':v['revision']});assert r.status_code==200,r.text
    r=client.post('/api/manage/modules/'+mid+'/review',json={'action':'approve','revision':v['revision']+1});assert r.status_code==200,r.text

def test_seed_public_private_and_all_prerequisites(env):
    o,org,_=env
    catalog=o.get('/api/catalog',params={'org':org}).json();assert len(catalog)==47
    assert sum(c['minutes'] for c in catalog)==4500
    assert all(c['price_fen']==0 and 'marketing_prompt' not in c for c in catalog)
    assert next(c for c in catalog if c['code']=='F13')['method_cards']
    with database.connect() as d:
        user=dict(d.execute('SELECT * FROM users LIMIT 1').fetchone())
        for c in catalog:publish_check(d,{'id':c['id'],'org_id':org},c,user)
    public=TestClient(server.app)
    assert public.get('/api/orgs/'+org+'/members').status_code==401
    assert public.get('/api/manage/modules/'+catalog[0]['id']).status_code==401

def test_csrf_origin_and_role_enforcement(env):
    o,org,new=env;c=new()
    assert c.post('/api/orgs/'+org+'/modules',json={'data':{'title':'No access'}}).status_code==403
    assert c.get('/api/orgs/'+org+'/audit').status_code==403
    assert c.post('/api/orgs',json={'name':'Other org','owner_email':'customer@example.test'}).status_code==403
    assert o.put('/api/orgs/'+org,json={'name':'New name'},headers={'X-CSRF-Token':'bad'}).status_code==403
    assert o.put('/api/orgs/'+org,json={'name':'New name'},headers={'Origin':'https://evil.example'}).status_code==403
    with database.connect() as d:uid=d.execute('SELECT id FROM users WHERE platform_admin=1').fetchone()[0]
    assert o.put(f'/api/orgs/{org}/members/{uid}',json={'role':'teacher','state':'active'}).status_code==409

def test_invite_teacher_disable_and_other_org(env):
    o,org,new=env;teacher=new('teacher@example.test');other=new('other@example.test')
    r=o.post('/api/orgs/'+org+'/invites',json={'email':'teacher@example.test','role':'teacher'});token=r.json()['url'].split('invite=')[1]
    assert other.post('/api/invites/accept',json={'token':token}).status_code==403
    assert teacher.post('/api/invites/accept',json={'token':token}).status_code==200
    mid=create_module(teacher,org)
    assert teacher.post('/api/manage/modules/'+mid+'/review',json={'action':'approve','revision':1}).status_code==403
    catalog=o.get('/api/catalog',params={'org':org}).json()
    assert teacher.get('/api/manage/modules/'+catalog[0]['id']).status_code==403
    tid=teacher.get('/api/auth/me').json()['user']['id']
    assert o.put(f'/api/orgs/{org}/members/{tid}',json={'role':'teacher','state':'disabled'}).status_code==200
    assert teacher.get('/api/manage/modules/'+mid).status_code==403
    org2=o.post('/api/orgs',json={'name':'Org two','owner_email':'other@example.test'}).json()['id']
    assert other.get('/api/orgs/'+org+'/modules').status_code==403
    assert o.get('/api/orgs/'+org2+'/members').status_code==403

def test_versions_assets_and_optimistic_edit(env):
    o,org,new=env;public=TestClient(server.app);mid=create_module(o,org,price=12500)
    assert public.get('/api/modules/'+mid).status_code==404
    upload=o.post('/api/manage/modules/'+mid+'/assets',files={'file':('lesson.txt',b'lesson data')},data={'visibility':'public'});assert upload.status_code==200,upload.text;aid=upload.json()['id']
    assert public.get('/api/assets/'+aid).status_code==404
    publish(o,mid);assert public.get('/api/assets/'+aid).content==b'lesson data'
    detail=o.get('/api/manage/modules/'+mid).json();v=detail['versions'][0];data=v['data'];data['price_fen']=50000
    assert o.put('/api/manage/modules/'+mid,json={'data':data,'revision':v['revision']}).status_code==200
    assert public.get('/api/modules/'+mid).json()['price_fen']==12500
    detail=o.get('/api/manage/modules/'+mid).json();assert len(detail['assets'])==2
    new_asset=next(a for a in detail['assets'] if a['version_id']==detail['draft_id'])
    assert public.get('/api/assets/'+new_asset['id']).status_code==404
    assert o.put('/api/manage/modules/'+mid,json={'data':data,'revision':999}).status_code==409
    publish(o,mid);assert public.get('/api/modules/'+mid).json()['price_fen']==50000
    assert public.get('/api/assets/'+aid).status_code==404
    assert public.get('/api/assets/'+new_asset['id']).status_code==200

def test_quotes_immutable_idempotent_and_project_assets(env):
    o,org,new=env;c=new();stranger=new('stranger@example.test');mid=create_module(o,org,price=15000)
    a=o.post('/api/manage/modules/'+mid+'/assets',files={'file':('internal.txt',b'private')},data={'visibility':'project'}).json()['id']
    publish(o,mid);course=c.get('/api/modules/'+mid).json()
    p={'org_id':org,'ids':[mid],'batches':2,'expected_versions':{mid:course['version_id']}}
    body={'plan':p,'contact':'Customer','phone':'123456','request_key':'unique-request-key'}
    r=c.post('/api/inquiries',json=body);assert r.status_code==200,r.text;iid=r.json()['id']
    assert c.post('/api/inquiries',json=body).json()['id']==iid
    assert stranger.get('/api/inquiries/'+iid).status_code==403
    assert c.get('/api/assets/'+a).status_code==404
    assert o.post('/api/assets/'+a+'/grant',json={'inquiry_id':iid}).status_code==200
    assert c.get('/api/assets/'+a).content==b'private'
    assert stranger.get('/api/assets/'+a).status_code==404
    v=o.get('/api/manage/modules/'+mid).json()['versions'][0];v['data']['price_fen']=99000
    o.put('/api/manage/modules/'+mid,json={'data':v['data'],'revision':v['revision']});publish(o,mid)
    assert c.post('/api/plans/validate',json=p).status_code==409
    qi={'extras':[{'label':'Implementation','amount_fen':10000}],'discount_fen':1000,'valid_until':(date.today()+timedelta(days=7)).isoformat(),'included':'Modules plus implementation'}
    r=o.post('/api/inquiries/'+iid+'/quotes',json=qi);assert r.status_code==200,r.text;qid=r.json()['id'];assert r.json()['data']['total_fen']==39000
    assert c.get('/api/inquiries/'+iid).json()['quotes']==[]
    assert c.post('/api/quotes/'+qid+'/action',json={'action':'send'}).status_code==403
    assert o.post('/api/quotes/'+qid+'/action',json={'action':'send'}).status_code==200
    assert stranger.post('/api/quotes/'+qid+'/action',json={'action':'accept'}).status_code==403
    assert c.post('/api/quotes/'+qid+'/action',json={'action':'accept'}).status_code==200
    assert c.post('/api/quotes/'+qid+'/action',json={'action':'accept'}).status_code==200
    q2=o.post('/api/inquiries/'+iid+'/quotes',json=qi).json()['id']
    assert o.post('/api/quotes/'+q2+'/action',json={'action':'send'}).status_code==409
    assert c.get('/api/inquiries/'+iid).json()['snapshot']['subtotal_fen']==30000

@pytest.mark.parametrize('theme',['转绘','短剧','口播','广告','教学','综合'])
def test_agent_constraints_and_dependencies(env,theme):
    o,org,new=env;c=new();req={'org_id':org,'theme':theme,'days':2,'daily_minutes':360,'budget_fen':0}
    r=c.post('/api/agent/plan',json=req);assert r.status_code==200,r.text;p=r.json()['plan']
    assert p['mode']=='rules' and p['courses']
    assert p['total_minutes']<=720 and len(p['schedule'])<=2 and p['subtotal_fen']==0
    assert not any('缺少先修' in x for x in p['warnings'])
    assert all(d['minutes']<=360 for d in p['schedule'])
    assert 'marketing_prompt' not in json.dumps(p)
    r=c.post('/api/plans',json={'org_id':org,'ids':p['ids'],'title':p['title']});assert r.status_code==200
    pid=r.json()['id'];assert c.get('/api/plans/'+pid+'/export').status_code==200
    assert o.get('/api/plans/'+pid+'/export').status_code==404

def test_invalid_syllabus_budget_cycle_and_ai_fallback(env,monkeypatch):
    o,org,new=env;mid=create_module(o,org,price=10000)
    v=o.get('/api/manage/modules/'+mid).json()['versions'][0];v['data']['syllabus'][0]['minutes']=30
    o.put('/api/manage/modules/'+mid,json={'data':v['data'],'revision':v['revision']})
    assert o.post('/api/manage/modules/'+mid+'/review',json={'action':'submit','revision':2}).status_code==422
    v['data']['syllabus'][0]['minutes']=60;v['data']['prereq_ids']=[mid]
    o.put('/api/manage/modules/'+mid,json={'data':v['data'],'revision':2})
    assert o.post('/api/manage/modules/'+mid+'/review',json={'action':'submit','revision':3}).status_code==422
    v['data']['prereq_ids']=[];o.put('/api/manage/modules/'+mid,json={'data':v['data'],'revision':3});publish(o,mid)
    c=new();r=c.post('/api/agent/plan',json={'org_id':org,'theme':'转绘','budget_fen':0,'required_ids':[mid]});assert mid not in r.json()['plan']['ids'];assert '预算' in str(r.json()['plan']['limitations'])
    monkeypatch.setenv('AI_BASE_URL','https://example.test/v1');monkeypatch.setenv('AI_API_KEY','test-only');monkeypatch.setenv('AI_MODEL','test-model')
    def broken(*args,**kwargs):raise RuntimeError('Provider unavailable')
    monkeypatch.setattr(server.httpx,'post',broken)
    r=c.post('/api/agent/plan',json={'org_id':org,'mode':'ai'});assert r.status_code==200;assert r.json()['plan']['mode']=='rules-fallback'

def test_bootstrap_and_backup(env):
    o,org,_=env;assert manage.bootstrap()['created'] is False
    r=manage.backup();assert Path(r['backup_file']).is_file()
    assert o.get('/runtime/首次登录.txt').status_code==404
    assert o.get('/static/../runtime/courses.sqlite3').status_code==404

def test_ai_copy_stays_with_validated_plan_and_revision_never_reuses(env,monkeypatch):
    o,org,new=env;c=new()
    monkeypatch.setenv('AI_BASE_URL','https://example.test/v1');monkeypatch.setenv('AI_API_KEY','test-only');monkeypatch.setenv('AI_MODEL','test-model')
    class Reply:
        def raise_for_status(self):pass
        def json(self):return {'choices':[{'message':{'content':json.dumps({'title':'Valid course plan','introduction':'Verified introduction','promotion':'Verified promotion'})}}]}
    def ok(*args,**kwargs):
        payload=kwargs['json'];assert 'marketing_prompt' not in json.dumps(payload);return Reply()
    monkeypatch.setattr(server.httpx,'post',ok)
    p=c.post('/api/agent/plan',json={'org_id':org,'mode':'ai'}).json()['plan'];assert p['mode']=='ai-assisted'
    r=c.post('/api/plans',json={**p,'expected_versions':p['versions']});assert r.status_code==200,r.text
    assert r.json()['plan']['introduction']=='Verified introduction'
    seeded=o.get('/api/catalog',params={'org':org}).json()[0];mid=seeded['id'];v=o.get('/api/manage/modules/'+mid).json()['versions'][0]
    assert o.put('/api/manage/modules/'+mid,json={'data':v['data'],'revision':v['revision']}).status_code==200
    assert o.put('/api/manage/modules/'+mid,json={'data':v['data'],'revision':v['revision']}).status_code==409

def test_resource_preview_permissions_ranges_types_and_upload_limits(env,monkeypatch):
    o,org,new=env;public=TestClient(server.app);customer=new();mid=create_module(o,org)
    samples=[('slides.pdf',b'%PDF-1.4\nTest PDF content\n%%EOF','public'),('recording.webm',b'\x1aE\xdf\xa3'+b'webm-test'*200,'public'),('private.mp4',b'\x00\x00\x00\x18ftypisom'+b'x'*500,'organization'),('slides.pptx',b'PK-test-pptx','public')]
    assets={}
    for filename,content,visibility in samples:
        r=o.post('/api/manage/modules/'+mid+'/assets',files={'file':(filename,content)},data={'visibility':visibility});assert r.status_code==200,r.text;assets[filename]=r.json()['id']
    assert public.get('/api/assets/'+assets['recording.webm']+'/preview').status_code==404
    publish(o,mid)
    pdf=public.get('/api/assets/'+assets['slides.pdf']+'/preview');assert pdf.status_code==200
    assert pdf.headers['content-type'].startswith('application/pdf') and pdf.headers['content-disposition'].startswith('inline')
    assert pdf.headers['x-frame-options']=='SAMEORIGIN'
    assert "frame-ancestors 'self'" in pdf.headers['content-security-policy']
    video=public.get('/api/assets/'+assets['recording.webm']+'/preview',headers={'Range':'bytes=0-15'})
    assert video.status_code==206 and len(video.content)==16 and video.headers['content-type']=='video/webm'
    assert customer.get('/api/assets/'+assets['private.mp4']+'/preview').status_code==404
    assert o.get('/api/assets/'+assets['private.mp4']+'/preview').status_code==200
    assert public.get('/api/assets/'+assets['slides.pptx']+'/preview').status_code==415
    assert public.get('/api/assets/'+assets['slides.pptx']).headers['content-disposition'].startswith('attachment')
    # A failed large upload leaves no database row or partial file.
    v=o.get('/api/manage/modules/'+mid).json()['versions'][0];o.put('/api/manage/modules/'+mid,json={'data':v['data'],'revision':v['revision']})
    monkeypatch.setattr(server,'MAX_UPLOAD_MB',1);before=set(server.DATA.joinpath('files').iterdir())
    r=o.post('/api/manage/modules/'+mid+'/assets',files={'file':('large.mp4',b'x'*(2*1024*1024))});assert r.status_code==413
    assert set(server.DATA.joinpath('files').iterdir())==before
    r=o.post('/api/manage/modules/'+mid+'/assets',files={'file':('empty.pdf',b'')});assert r.status_code==422
    assert o.get('/api/assets/config').json()['max_upload_mb']==1
