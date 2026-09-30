import json
import pytest
from fastapi.testclient import TestClient
from test_system import env,create_module,publish
import database as db
import app as server
import ai_studio
import course_assistant as ca

def stub(monkeypatch,**kwargs):
    monkeypatch.setenv('SILICONFLOW_API_KEY','fixture-secret')
    calls=[]
    def provider(path,payload):
        calls.append(payload)
        return {'choices':[{'message':{'content':json.dumps({'summary':'企业视频实训','in_scope':True,'days':2,'daily_minutes':360,'ranked_codes':['P02','F12'],**kwargs})}}]}
    monkeypatch.setattr(ai_studio,'provider_post',provider)
    return calls

def test_assistant_followup_persistence_and_access(env,monkeypatch):
    owner,org,new=env;other=new();calls=stub(monkeypatch,ranked_codes=['P02','F12','F01'],teaching_codes=['F01','P02','T01','F12'])
    b={'org_id':org,'message':'给企业新媒体员工安排两天视频制作培训'}
    r=owner.post('/api/agent/assistant',json=b);assert r.status_code==200,r.text
    first=r.json();p=first['plan'];assert p['ids'] and p['total_minutes']<=720
    assert not any('缺少先修' in w for w in p['warnings'])
    codes=[c['code'] for c in p['courses']]
    assert codes[0]=='F01' and codes.index('T01')<codes.index('P02')
    assert 'marketing_prompt' not in r.text and 'fixture-secret' not in r.text
    assert owner.get('/api/agent/assistant/'+first['id']).json()==first
    assert other.get('/api/agent/assistant/'+first['id']).status_code==404
    assert other.post('/api/agent/assistant',json={**b,'previous_id':first['id']}).status_code==404
    r=owner.post('/api/agent/assistant',json={**b,'message':'改为1天','previous_id':first['id']});assert r.status_code==200
    assert r.json()['messages']==[b['message'],'改为1天']
    source=json.loads(calls[-1]['messages'][1]['content'])
    assert source['conversation']==r.json()['messages']
    assert all('marketing_prompt' not in c for c in source['catalog'])
    saved=owner.post('/api/plans',json={**p,'expected_versions':p['versions']});assert saved.status_code==200,saved.text
    with db.connect(True) as d:d.execute('UPDATE modules SET active=0 WHERE id=?',(p['ids'][0],))
    assert owner.get('/api/agent/assistant/'+first['id']).status_code==404
    assert owner.post('/api/plans/validate',json={**p,'expected_versions':p['versions']}).status_code==404

def test_selection_hard_limits_exclusions_and_unknown_codes(env,monkeypatch):
    owner,org,_=env;stub(monkeypatch,ranked_codes=['FAKE','P02','F01'],excluded_codes=['T01'],budget_yuan=0,days=1,daily_minutes=60)
    r=owner.post('/api/agent/assistant',json={'org_id':org,'message':'只要免费的一小时基础课，排除画布入门'});assert r.status_code==200,r.text
    p=r.json()['plan'];assert p['subtotal_fen']==0 and p['total_minutes']<=60
    assert all(c['code'] not in ['T01','P02','FAKE'] for c in p['courses'])
    assert any('排除' in x for x in p['limitations']) and any('不存在' in x for x in p['limitations'])
    mid=create_module(owner,org,'付费专项模块',price=10000);publish(owner,mid)
    code=next(c['code'] for c in owner.get('/api/catalog',params={'org':org}).json() if c['id']==mid)
    stub(monkeypatch,ranked_codes=[code],required_codes=[code],budget_yuan=99)
    p=owner.post('/api/agent/assistant',json={'org_id':org,'message':'预算99元，指定付费专项模块'}).json()['plan']
    assert not p['ids'] and any('预算' in x for x in p['limitations'])

def test_missing_key_failed_provider_out_of_scope_and_quota(env,monkeypatch):
    owner,org,_=env;b={'org_id':org,'message':'我想学Excel办公自动化'}
    monkeypatch.setattr(ai_studio,'api_key',lambda:'')
    assert owner.post('/api/agent/assistant',json=b).status_code==409
    monkeypatch.setattr(ai_studio,'api_key',lambda:'fixture-secret')
    stub(monkeypatch,in_scope=False)
    r=owner.post('/api/agent/assistant',json=b).json();assert not r['plan']['ids'] and not r['in_scope']
    monkeypatch.setattr(ai_studio,'provider_post',lambda *args:{'choices':[{'message':{'content':'{"broken":true}'}}]})
    assert owner.post('/api/agent/assistant',json=b).status_code==502
    with db.connect(True) as d:
        assert d.execute("SELECT COUNT(*) FROM agent_runs WHERE state='failed'").fetchone()[0]==1
        d.execute('UPDATE orgs SET agent_daily_limit=2 WHERE id=?',(org,))
    assert owner.post('/api/agent/assistant',json=b).status_code==429
    guest=TestClient(server.app)
    assert guest.post('/api/agent/assistant',json=b,headers={'X-Requested-With':'course-platform'}).status_code==401

def test_only_visible_courses_sent_to_model_and_total_capacity(env,monkeypatch):
    owner,org,new=env;customer=new();calls=stub(monkeypatch,days=None,total_minutes=180,daily_minutes=None,ranked_codes=['P02','F01','F12'])
    courses=owner.get('/api/catalog',params={'org':org}).json();hidden=next(c for c in courses if c['code']=='F12')
    with db.connect(True) as d:
        v=d.execute('SELECT data FROM versions WHERE id=?',(hidden['version_id'],)).fetchone()
        data=json.loads(v['data']);data['visibility']='organization'
        d.execute('UPDATE versions SET data=? WHERE id=?',(json.dumps(data),hidden['version_id']))
    r=customer.post('/api/agent/assistant',json={'org_id':org,'message':'半天视频入门实训'});assert r.status_code==200,r.text
    assert r.json()['plan']['total_minutes']<=180
    assert hidden['id'] not in r.json()['plan']['ids']
    assert 'F12' not in [c['code'] for c in json.loads(calls[0]['messages'][1]['content'])['catalog']]
    assert r.json()['assumptions']

def test_followup_retains_conditions_and_prioritizes_core_outcome(env,monkeypatch):
    owner,org,_=env
    stub(monkeypatch,audience='零基础教师',people=30,budget_yuan=2000,core_codes=['P05'],ranked_codes=['F01','F02','F03','F04','P05'])
    first=owner.post('/api/agent/assistant',json={'org_id':org,'message':'30位零基础教师，两天口播培训，预算2000元'}).json()
    stub(monkeypatch,audience='所有学员',people=20,budget_yuan=None,days=1,changed_fields=['days'],core_codes=['P05'],ranked_codes=['F01','F02','F03','F04','P05'])
    second=owner.post('/api/agent/assistant',json={'org_id':org,'message':'改成一天','previous_id':first['id']}).json()
    assert second['requirements']['days']==1 and second['requirements']['audience']=='零基础教师'
    assert second['requirements']['people']==30 and second['requirements']['budget_fen']==200000
    assert 'P05' in [c['code'] for c in second['plan']['courses']] and second['plan']['total_minutes']<=360
