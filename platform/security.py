import hashlib, secrets, base64, hmac, os
from fastapi import HTTPException, Request
from database import connect, now

COOKIE = 'course_session'
ROLES = {'owner','admin','teacher','operator'}
def fail(status, message): raise HTTPException(status, message)
def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def password_hash(p):
    if len(p)<10 or len(p)>128: fail(422,'密码须为10—128个字符')
    salt=secrets.token_bytes(16)
    value=hashlib.scrypt(p.encode(),salt=salt,n=16384,r=8,p=1)
    return base64.b64encode(salt+value).decode()
def password_ok(p,value):
    try:
        raw=base64.b64decode(value)
        return hmac.compare_digest(raw[16:],hashlib.scrypt(p.encode(),salt=raw[:16],n=16384,r=8,p=1))
    except (ValueError,TypeError): return False
def identity(request: Request, required=True):
    token=request.cookies.get(COOKIE,'')
    with connect() as d:
        r=d.execute('SELECT u.*,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1',(digest(token),now())).fetchone()
    if not r:
        if required: fail(401,'请先登录')
        return None
    if request.method not in ('GET','HEAD','OPTIONS') and not hmac.compare_digest(request.headers.get('x-csrf-token',''),r['csrf']): fail(403,'会话校验失败，请刷新后重试')
    return dict(r)
def role(d, org, user, allowed=None):
    if not user: fail(401,'请先登录')
    r=d.execute('SELECT m.role FROM members m JOIN orgs o ON o.id=m.org_id WHERE m.org_id=? AND m.user_id=? AND m.state=\'active\' AND o.active=1',(org,user['id'])).fetchone()
    if not r or (allowed and r['role'] not in allowed): fail(403,'没有此机构的操作权限')
    return r['role']
def is_member(d, org, user):
    if not user:return False
    return bool(d.execute("SELECT 1 FROM members m JOIN orgs o ON o.id=m.org_id WHERE m.org_id=? AND m.user_id=? AND m.state='active' AND o.active=1",(org,user['id'])).fetchone())
def throttle(d,key,limit=10,seconds=600):
    d.execute('DELETE FROM attempts WHERE time<?',(now()-86400,))
    count=d.execute('SELECT COUNT(*) FROM attempts WHERE key=? AND time>?',(key,now()-seconds)).fetchone()[0]
    if count>=limit: fail(429,'操作过于频繁，请稍后再试')
    d.execute('INSERT INTO attempts VALUES(?,?)',(key,now()))
def safe_user(u):return {k:u[k] for k in ('id','email','name','platform_admin')}
