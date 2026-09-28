"""Build a source-only deployment archive from an explicit file allowlist."""
import argparse, hashlib, json, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FILES=['organizations.py','web/organizations.js','RAILWAY.md','tests/test_organizations.py','tests/organizations.cjs','app.py','database.py','domain.py','security.py','manage.py','run.py','build_package.py','requirements.txt','requirements.in','.env.example','README.md','ACCEPTANCE.md','start.ps1','stop.ps1','Dockerfile','compose.yaml','.dockerignore','seed_courses.json','web/index.html','web/logo.svg','web/course-detail.js','web/app.js','web/style.css','web/presets.json','tests/test_system.py','tests/browser.cjs']

def build(output):
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in FILES}
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for name in FILES:z.write(ROOT/name,'platform/'+name)
        z.writestr('manifest.json',json.dumps({'product':'Course Studio','version':'1.2.0','files_sha256':hashes},indent=2))
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert all('/runtime/' not in n and '/test-results/' not in n and not n.endswith('/.env') for n in z.namelist())
    sha=hashlib.sha256(output.read_bytes()).hexdigest();output.with_suffix('.sha256').write_text(sha+'  '+output.name+'\n',encoding='utf-8')
    return {'file':str(output),'file_count':len(FILES)+1,'bytes':output.stat().st_size,'sha256':sha}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();print(json.dumps(build(args.output),ensure_ascii=True))
