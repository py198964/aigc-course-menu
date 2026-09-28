import os
from pathlib import Path

def read_env():
    path=Path(__file__).parent/'.env'
    if path.exists():
        for raw in path.read_text(encoding='utf-8-sig').splitlines():
            raw=raw.strip()
            if not raw or raw.startswith('#') or '=' not in raw:continue
            k,v=raw.split('=',1)
            if k.strip() in {'APP_ORIGIN','APP_HOST','APP_PORT','COURSE_DATA_DIR','AI_BASE_URL','AI_API_KEY','AI_MODEL','BOOTSTRAP_PASSWORD'}:
                os.environ.setdefault(k.strip(),v.strip().strip('"').strip("'"))

if __name__=='__main__':
    read_env()
    from manage import bootstrap
    bootstrap()
    if os.getenv('COURSE_PID_FILE'):
        Path(os.environ['COURSE_PID_FILE']).write_text(str(os.getpid()),encoding='ascii')
    import uvicorn
    uvicorn.run('app:app',host=os.getenv('APP_HOST','127.0.0.1'),port=int(os.getenv('APP_PORT','8765')),workers=1,proxy_headers=False,access_log=False)
