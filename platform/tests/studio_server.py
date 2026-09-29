"""Browser fixture server: external model responses are explicitly simulated."""
import sys, json, base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from manage import bootstrap
bootstrap()
import ai_studio
COPY={'title':'产品短视频创作实训','subtitle':'从策划到作品交付','introduction':'通过课程模块与案例练习，学习产品短视频制作和成果检查。',
      'objectives':['能够说明视频制作流程','能够完成产品短片练习'],
      'highlights':['案例贯穿教学','以作品检验学习成果'],'promotion':'面向企业运营人员，以实际作品为线索开展产品短视频实训。'}
def provider(path,payload):
    if path=='/chat/completions':return {'choices':[{'message':{'content':json.dumps(COPY)}}]}
    return {'images':[{'url':'https://files.siliconflow.cn/fixture.png'}]}
ai_studio.provider_post=provider
ai_studio.fetch_image=lambda url:(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5gAAAABJRU5ErkJggg=='),'png')
import uvicorn
uvicorn.run('app:app',host='127.0.0.1',port=8768,access_log=False)
