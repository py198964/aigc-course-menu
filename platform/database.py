import os, sqlite3, json, time, uuid
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent
DATA = Path(os.getenv('COURSE_DATA_DIR', str(ROOT / 'runtime'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
(DATA / 'files').mkdir(exist_ok=True)
DB = DATA / 'courses.sqlite3'

def uid(): return uuid.uuid4().hex
def now(): return int(time.time())
def dump(v): return json.dumps(v, ensure_ascii=False, separators=(',', ':'))
def parse(v): return json.loads(v)

@contextmanager
def connect(write=False):
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=20000')
    try:
        if write: db.execute('BEGIN IMMEDIATE')
        yield db
        if write: db.commit()
    except Exception:
        if write: db.rollback()
        raise
    finally: db.close()

def initialize():
    with connect() as d:
        d.execute('PRAGMA journal_mode=WAL')
        d.executescript('''
        CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
        INSERT OR IGNORE INTO schema_version VALUES(1);
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,platform_admin INTEGER DEFAULT 0,active INTEGER DEFAULT 1,created INTEGER);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),csrf TEXT,expires INTEGER);
        CREATE TABLE IF NOT EXISTS attempts(key TEXT,time INTEGER);
        CREATE INDEX IF NOT EXISTS attempts_lookup ON attempts(key,time);
        CREATE TABLE IF NOT EXISTS orgs(id TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT DEFAULT '',active INTEGER DEFAULT 1,agent_daily_limit INTEGER DEFAULT 30,created INTEGER);
        CREATE TABLE IF NOT EXISTS members(org_id TEXT REFERENCES orgs(id),user_id TEXT REFERENCES users(id),role TEXT,state TEXT DEFAULT 'active',PRIMARY KEY(org_id,user_id));
        CREATE TABLE IF NOT EXISTS invites(id TEXT PRIMARY KEY,org_id TEXT REFERENCES orgs(id),email TEXT,role TEXT,token TEXT UNIQUE,expires INTEGER,used INTEGER DEFAULT 0,created_by TEXT REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS modules(id TEXT PRIMARY KEY,org_id TEXT REFERENCES orgs(id),code TEXT,author_id TEXT REFERENCES users(id),published_id TEXT,draft_id TEXT,active INTEGER DEFAULT 1,created INTEGER,UNIQUE(org_id,code));
        CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY,module_id TEXT REFERENCES modules(id),number INTEGER,data TEXT,state TEXT,reason TEXT DEFAULT '',revision INTEGER DEFAULT 1,created_by TEXT REFERENCES users(id),created INTEGER,UNIQUE(module_id,number));
        CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,module_id TEXT REFERENCES modules(id),version_id TEXT REFERENCES versions(id),org_id TEXT REFERENCES orgs(id),name TEXT,size INTEGER,visibility TEXT,path TEXT,created INTEGER);
        CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY,org_id TEXT REFERENCES orgs(id),user_id TEXT REFERENCES users(id),title TEXT,data TEXT,revision INTEGER DEFAULT 1,created INTEGER,updated INTEGER);
        CREATE TABLE IF NOT EXISTS plan_versions(id TEXT PRIMARY KEY,plan_id TEXT REFERENCES plans(id),revision INTEGER,data TEXT,created INTEGER);
        CREATE TABLE IF NOT EXISTS inquiries(id TEXT PRIMARY KEY,org_id TEXT REFERENCES orgs(id),user_id TEXT REFERENCES users(id),request_key TEXT,user_data TEXT,snapshot TEXT,state TEXT DEFAULT 'pending',created INTEGER,updated INTEGER,UNIQUE(user_id,request_key));
        CREATE TABLE IF NOT EXISTS quotes(id TEXT PRIMARY KEY,inquiry_id TEXT REFERENCES inquiries(id),number INTEGER,data TEXT,state TEXT DEFAULT 'draft',revision INTEGER DEFAULT 1,created_by TEXT REFERENCES users(id),created INTEGER,sent INTEGER,UNIQUE(inquiry_id,number));
        CREATE TABLE IF NOT EXISTS asset_grants(asset_id TEXT REFERENCES assets(id),inquiry_id TEXT REFERENCES inquiries(id),PRIMARY KEY(asset_id,inquiry_id));
        CREATE TABLE IF NOT EXISTS agent_runs(id TEXT PRIMARY KEY,org_id TEXT REFERENCES orgs(id),user_id TEXT REFERENCES users(id),request TEXT,result TEXT,mode TEXT,state TEXT,created INTEGER);
        CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY,org_id TEXT,user_id TEXT,action TEXT,target TEXT,detail TEXT,created INTEGER);
        ''')

def log(d, org, user, action, target, detail=''):
    d.execute('INSERT INTO audit VALUES(?,?,?,?,?,?,?)',(uid(),org,user,action,target,dump(detail),now()))
