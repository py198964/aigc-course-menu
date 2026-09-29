import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from test_system import env
import database as db
import app as server
import ai_studio

COPY={'title':'产品短视频实训','subtitle':'从策划到作品交付','introduction':'通过案例练习学习产品短视频的策划、制作与交付方法。',
      'objectives':['能够说明视频制作流程','能够完成产品短片练习'],
      'highlights':['真实案例贯穿训练','以作品检验学习成果'],'promotion':'面向新媒体运营人员，结合课程模块完成视频创作实训。'}

def body(owner,org,kind='copy'):
    courses=owner.get('/api/catalog',params={'org':org}).json()
    return {'plan':{'org_id':org,'ids':[courses[0]['id']],'audience':'企业员工'},'kind':kind,'request_key':db.uid()}

def test_missing_key_auth_and_no_secret_disclosure(env,monkeypatch):
    owner,org,_=env;monkeypatch.delenv('SILICONFLOW_API_KEY',raising=False)
    b=body(owner,org)
    assert owner.post('/api/creative/jobs',json=b).status_code==409
    public=TestClient(server.app)
    assert public.post('/api/creative/jobs',json=b,headers={'X-Requested-With':'course-platform'}).status_code==401
    monkeypatch.setenv('SILICONFLOW_API_KEY','mock-private-key')
    config=owner.get('/api/creative/config');assert config.json()['available']
    assert 'mock-private-key' not in config.text

def test_copy_validation_persistence_idempotency_and_access(env,monkeypatch):
    owner,org,new=env;other=new();monkeypatch.setenv('SILICONFLOW_API_KEY','mock-private-key')
    calls=[]
    def fake(path,payload):
        calls.append((path,payload));return {'choices':[{'message':{'content':json.dumps(COPY)}}]}
    monkeypatch.setattr(ai_studio,'provider_post',fake)
    b=body(owner,org);j=owner.post('/api/creative/jobs',json=b).json()
    out=owner.get('/api/creative/jobs/'+j['id']).json();assert out['state']=='complete'
    assert out['result']['copy']==COPY
    assert owner.post('/api/creative/jobs',json=b).json()['id']==j['id'];assert len(calls)==1
    b['plan']['audience']='变更对象';assert owner.post('/api/creative/jobs',json=b).status_code==409
    assert other.get('/api/creative/jobs/'+j['id']).status_code==404
    assert other.get('/api/creative/jobs',params={'org':org}).json()==[]
    source=json.loads(calls[0][1]['messages'][1]['content'])
    assert 'marketing_prompt' not in json.dumps(source) and 'password' not in json.dumps(source)
    plan={**b['plan'],**COPY}
    saved=owner.post('/api/plans',json=plan);assert saved.status_code==200
    pid=saved.json()['id'];md=owner.get('/api/plans/'+pid+'/export').text
    assert COPY['objectives'][0] in md and COPY['highlights'][0] in md
    assert next(x for x in owner.get('/api/plans').json() if x['id']==pid)['data']['subtitle']==COPY['subtitle']

def test_provider_failures_and_invalid_json_are_explicit(env,monkeypatch):
    owner,org,_=env;monkeypatch.setenv('SILICONFLOW_API_KEY','mock-private-key')
    monkeypatch.setattr(ai_studio,'provider_post',lambda *args:{'choices':[{'message':{'content':'{"title":"Incomplete"}'}}]})
    j=owner.post('/api/creative/jobs',json=body(owner,org)).json()
    out=owner.get('/api/creative/jobs/'+j['id']).json();assert out['state']=='failed' and not out['result']
    assert '完整有效' in out['error']
    with db.connect(True) as d:d.execute("UPDATE creative_jobs SET state='running',updated=0 WHERE id=?",(j['id'],))
    out=owner.get('/api/creative/jobs/'+j['id']).json();assert out['state']=='failed' and '中断' in out['error']

def test_image_storage_visibility_limits_and_url_validation(env,monkeypatch):
    owner,org,new=env;other=new();monkeypatch.setenv('SILICONFLOW_API_KEY','mock-private-key')
    monkeypatch.setattr(ai_studio,'provider_post',lambda *args:{'images':[{'url':'https://files.siliconflow.cn/example.png'}]})
    monkeypatch.setattr(ai_studio,'fetch_image',lambda url:(b'\x89PNG\r\n\x1a\nfixture','png'))
    for _ in range(3):j=owner.post('/api/creative/jobs',json=body(owner,org,'image')).json()
    out=owner.get('/api/creative/jobs/'+j['id']).json();assert out['state']=='complete'
    assert 'file' not in out['result'] and 'url' not in out['result']
    assert owner.get(out['result']['image_url']).headers['content-type']=='image/png'
    assert other.get(out['result']['image_url']).status_code==404
    assert owner.post('/api/creative/jobs',json=body(owner,org,'image')).status_code==429
    with db.connect(True) as d:
        mid=body(owner,org)['plan']['ids'][0]
        d.execute('UPDATE modules SET active=0 WHERE id=?',(mid,))
    assert owner.get(out['result']['image_url']).status_code==404
    assert owner.get('/api/creative/jobs',params={'org':org}).json()==[]

@pytest.mark.parametrize('url',['http://files.siliconflow.cn/a','https://127.0.0.1/a','https://siliconflow.cn.evil.test/a','https://example.test/a','https://u:p@files.siliconflow.cn/a'])
def test_download_rejects_unapproved_urls(url):
    with pytest.raises(ai_studio.ProviderError):ai_studio.fetch_image(url)
