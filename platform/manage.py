"""Local administration. Credentials and backups stay outside the web root."""
import argparse, os, secrets, sqlite3, zipfile, getpass, json, uuid
from contextlib import closing
from pathlib import Path
from datetime import datetime
from run import read_env
read_env()
from database import ROOT, DATA, DB, initialize, connect, uid, now, dump, log
from security import password_hash
from domain import ModuleData

def bootstrap(admin_email='owner@local.test',org_name='AIGC视频创作学院'):
    initialize()
    with connect(True) as d:
        if d.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            return {'created':False,'message':'数据库已初始化，未覆盖账号或课程。'}
        password=os.getenv('BOOTSTRAP_PASSWORD') or secrets.token_urlsafe(18)
        user=uid();org=uid()
        d.execute('INSERT INTO users VALUES(?,?,?,?,1,1,?)',(user,admin_email.lower(),'机构负责人',password_hash(password),now()))
        d.execute('INSERT INTO orgs VALUES(?,?,?,1,30,?)',(org,org_name,'以画布、转绘和导演台为核心，提供基础方法、工具入门、案例实战与商业交付课程。',now()))
        d.execute("INSERT INTO members VALUES(?,?,'owner','active')",(org,user))
        seeds=json.loads((ROOT/'seed_courses.json').read_text(encoding='utf-8'))
        ids={c['code']:uuid.uuid5(uuid.NAMESPACE_URL,org+'/'+c['code']).hex for c in seeds}
        for c in seeds:
            data=ModuleData(**{**c,'prereq_ids':[ids[x] for x in c['prereq_ids']]}).model_dump()
            mid=ids[c['code']];vid=uid()
            d.execute('INSERT INTO modules VALUES(?,?,?,?,?,NULL,1,?)',(mid,org,c['code'],user,vid,now()))
            d.execute("INSERT INTO versions VALUES(?,?,1,?,'published','初始化课程库',1,?,?)",(vid,mid,dump(data),user,now()))
        log(d,org,user,'system.bootstrap',org,{'courses':len(seeds)})
    credential=DATA/'首次登录.txt'
    credential.write_text('微课工坊 · 首次登录\n\n地址：'+os.getenv('APP_ORIGIN','http://127.0.0.1:8765')+'\n邮箱：'+admin_email+'\n密码：'+password+'\n\n首次登录后请在“设置”修改密码，并妥善保管或删除本文件。\n此文件不通过网站提供，不包含于部署包。\n',encoding='utf-8')
    try:os.chmod(credential,0o600)
    except OSError:pass
    return {'created':True,'courses':len(seeds),'credential_file':str(credential)}

def backup():
    initialize();stamp=datetime.now().strftime('%Y%m%d-%H%M%S');dest=DATA/'backups';dest.mkdir(exist_ok=True)
    snapshot=dest/('snapshot-'+stamp+'.sqlite3');archive=dest/('course-backup-'+stamp+'.zip')
    # SQLite backup API captures committed state including the WAL. Files are immutable.
    with closing(sqlite3.connect(DB)) as src,closing(sqlite3.connect(snapshot)) as dst:src.backup(dst)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(snapshot,'courses.sqlite3')
        for f in (DATA/'files').iterdir():
            if f.is_file():z.write(f,'files/'+f.name)
    snapshot.unlink()
    return {'backup_file':str(archive),'note':'备份包含个人资料和授权资源，请限制访问。'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['init','backup','reset-password']);parser.add_argument('--email',default='owner@local.test');parser.add_argument('--org',default='AIGC视频创作学院');args=parser.parse_args()
    if args.command=='init':result=bootstrap(args.email,args.org)
    elif args.command=='backup':result=backup()
    else:
        initialize();password=getpass.getpass('New password (10+ characters): ')
        with connect(True) as d:
            u=d.execute('SELECT id FROM users WHERE email=?',(args.email.lower(),)).fetchone()
            if not u:raise SystemExit('Account not found')
            d.execute('UPDATE users SET password=? WHERE id=?',(password_hash(password),u['id']));d.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],));log(d,None,u['id'],'account.local-reset',u['id'])
        result={'reset':True}
    print(json.dumps(result,ensure_ascii=True))
