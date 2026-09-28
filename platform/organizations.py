"""Organization directory and account administration, separate from course permissions."""
import re
import secrets
from typing import Literal
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel, Field
from database import connect, uid, now, log
from security import identity, role, fail, password_hash

router = APIRouter()
MemberRole = Literal['owner', 'admin', 'teacher', 'operator', 'learner']

def platform_user(request):
    user = identity(request)
    if not user['platform_admin']: fail(403, '需要平台管理员权限')
    return user

def clean_name(value):
    value = value.strip()
    if not value: fail(422, '名称不能为空')
    return value

def clean_email(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value): fail(422, '请输入有效邮箱')
    return value

def department_check(d, org, department):
    if department and not d.execute('SELECT 1 FROM departments WHERE id=? AND org_id=?', (department, org)).fetchone():
        fail(422, '部门不存在或不属于当前机构')

def member_rows(d, org):
    return [dict(r) for r in d.execute('''SELECT u.id,u.name,u.email,u.active AS account_active,m.role,m.state,
        p.department_id,COALESCE(p.job_title,'') AS job_title,dep.name AS department_name
        FROM members m JOIN users u ON u.id=m.user_id
        LEFT JOIN member_profiles p ON p.org_id=m.org_id AND p.user_id=m.user_id
        LEFT JOIN departments dep ON dep.id=p.department_id
        WHERE m.org_id=? ORDER BY m.role='owner' DESC,u.name,u.email''', (org,))]

def department_rows(d, org):
    return [dict(r) for r in d.execute('''SELECT dep.*,
        (SELECT COUNT(*) FROM member_profiles p JOIN members m ON m.org_id=p.org_id AND m.user_id=p.user_id
         WHERE p.department_id=dep.id) AS member_count
        FROM departments dep WHERE dep.org_id=? ORDER BY sort_order,name,id''', (org,))]

class MembershipData(BaseModel):
    role: MemberRole = 'learner'
    state: Literal['active', 'disabled'] = 'active'
    department_id: str | None = Field(default=None, max_length=64)
    job_title: str = Field(default='', max_length=100)

def set_membership(d, org, person, data, actor, platform=False, create=False):
    organization = d.execute('SELECT active FROM orgs WHERE id=?', (org,)).fetchone()
    if not organization: fail(404, '机构不存在')
    if not organization['active']: fail(409, '请先启用机构，再调整成员')
    actor_role = 'owner' if platform else role(d, org, actor, {'owner', 'admin'})
    target = d.execute('SELECT active FROM users WHERE id=?', (person,)).fetchone()
    if not target: fail(404, '用户不存在')
    if not target['active'] and data.state == 'active': fail(409, '账号已被平台停用，请先恢复账号')
    old = d.execute('SELECT * FROM members WHERE org_id=? AND user_id=?', (org, person)).fetchone()
    if create and old: fail(409, '该用户已属于本机构，请在成员列表中编辑')
    if not create and not old: fail(404, '成员不存在')
    if (data.role == 'owner' or (old and old['role'] == 'owner')) and actor_role != 'owner':
        fail(403, '负责人权限只能由负责人或平台管理员调整')
    if old and old['role'] == 'owner' and old['state'] == 'active' and (data.role != 'owner' or data.state != 'active'):
        others = d.execute("""SELECT COUNT(*) FROM members m JOIN users u ON u.id=m.user_id
            WHERE m.org_id=? AND m.role='owner' AND m.state='active' AND u.active=1 AND m.user_id<>?""", (org, person)).fetchone()[0]
        if not others: fail(409, '请先指定另一位有效负责人，不能停用最后一位负责人')
    # Older clients changing only role/state must not clear a department assignment.
    profile = d.execute('SELECT * FROM member_profiles WHERE org_id=? AND user_id=?', (org, person)).fetchone()
    dept = data.department_id if 'department_id' in data.model_fields_set or not profile else profile['department_id']
    title = data.job_title.strip() if 'job_title' in data.model_fields_set or not profile else profile['job_title']
    department_check(d, org, dept)
    d.execute('INSERT INTO members VALUES(?,?,?,?) ON CONFLICT(org_id,user_id) DO UPDATE SET role=excluded.role,state=excluded.state', (org, person, data.role, data.state))
    d.execute('INSERT INTO member_profiles VALUES(?,?,?,?) ON CONFLICT(org_id,user_id) DO UPDATE SET department_id=excluded.department_id,job_title=excluded.job_title', (org, person, dept, title))
    log(d, org, actor['id'], 'member.add' if create else 'member.update', person, {'role': data.role, 'state': data.state, 'department_id': dept, 'job_title': title, 'platform': platform})

@router.get('/api/orgs/{org}/departments')
def departments(org: str, request: Request):
    user = identity(request)
    with connect() as d:
        role(d, org, user, {'owner', 'admin'})
        return department_rows(d, org)

class DepartmentData(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    parent_id: str | None = Field(default=None, max_length=64)
    sort_order: int = Field(default=0, ge=0, le=9999, strict=True)

def save_department(d, org, dep_id, data, actor, new=False):
    department_check(d, org, data.parent_id)
    rows = department_rows(d, org)
    if not new and not any(r['id'] == dep_id for r in rows): fail(404, '部门不存在')
    parents = {r['id']: r['parent_id'] for r in rows}
    parents[dep_id] = data.parent_id
    # Check all resulting paths: moving a subtree must not exceed the depth limit.
    for start in parents:
        seen = set(); current = start
        while current:
            if current in seen: fail(422, '不能将部门移动到自身或下级部门')
            seen.add(current); current = parents.get(current)
        if len(seen) > 6: fail(422, '组织架构最多支持六级部门')
    name = clean_name(data.name)
    if d.execute('SELECT 1 FROM departments WHERE org_id=? AND parent_id IS ? AND name=? AND id<>?', (org, data.parent_id, name, dep_id)).fetchone():
        fail(409, '同一上级下已存在同名部门')
    if new:
        d.execute('INSERT INTO departments VALUES(?,?,?,?,?,?)', (dep_id, org, data.parent_id, name, data.sort_order, now()))
    else:
        d.execute('UPDATE departments SET parent_id=?,name=?,sort_order=? WHERE id=?', (data.parent_id, name, data.sort_order, dep_id))
    log(d, org, actor['id'], 'department.create' if new else 'department.update', dep_id, data.model_dump())
    return {'id': dep_id}

@router.post('/api/orgs/{org}/departments')
def department_create(org: str, data: DepartmentData, request: Request):
    user = identity(request)
    with connect(True) as d:
        role(d, org, user, {'owner', 'admin'})
        return save_department(d, org, uid(), data, user, True)

@router.put('/api/orgs/{org}/departments/{department}')
def department_edit(org: str, department: str, data: DepartmentData, request: Request):
    user = identity(request)
    with connect(True) as d:
        role(d, org, user, {'owner', 'admin'})
        return save_department(d, org, department, data, user)

@router.delete('/api/orgs/{org}/departments/{department}')
def department_delete(org: str, department: str, request: Request):
    user = identity(request)
    with connect(True) as d:
        role(d, org, user, {'owner', 'admin'}); department_check(d, org, department)
        if d.execute('SELECT 1 FROM departments WHERE parent_id=?', (department,)).fetchone(): fail(409, '请先移动或删除下级部门')
        if d.execute('SELECT 1 FROM member_profiles WHERE department_id=?', (department,)).fetchone(): fail(409, '请先调出部门成员，包括已停用成员')
        if d.execute('''SELECT 1 FROM invite_profiles p JOIN invites i ON i.id=p.invite_id
            WHERE p.department_id=? AND i.used=0 AND i.expires>?''', (department, now())).fetchone(): fail(409, '此部门有待接受邀请，请先撤销邀请')
        d.execute('UPDATE invite_profiles SET department_id=NULL WHERE department_id=?', (department,))
        d.execute('DELETE FROM departments WHERE id=?', (department,)); log(d, org, user['id'], 'department.delete', department)
    return {'ok': True}

class AddMember(MembershipData):
    email: str = Field(max_length=254)

@router.post('/api/orgs/{org}/members')
def add_member(org: str, data: AddMember, request: Request):
    user = identity(request)
    with connect(True) as d:
        role(d, org, user, {'owner', 'admin'})
        person = d.execute('SELECT id FROM users WHERE email=?', (clean_email(data.email),)).fetchone()
        if not person: fail(422, '此邮箱尚未注册，可以先发送机构邀请')
        set_membership(d, org, person['id'], data, user, create=True)
    return {'ok': True}

@router.get('/api/orgs/{org}/invites')
def invitations(org: str, request: Request):
    user = identity(request)
    with connect() as d:
        role(d, org, user, {'owner', 'admin'})
        return [dict(r) for r in d.execute('''SELECT i.id,i.email,i.role,i.expires,i.used,p.department_id,dep.name AS department_name
            FROM invites i LEFT JOIN invite_profiles p ON p.invite_id=i.id LEFT JOIN departments dep ON dep.id=p.department_id
            WHERE i.org_id=? ORDER BY i.expires DESC LIMIT 100''', (org,))]

@router.delete('/api/orgs/{org}/invites/{invite}')
def revoke_invitation(org: str, invite: str, request: Request):
    user = identity(request)
    with connect(True) as d:
        role(d, org, user, {'owner', 'admin'})
        r = d.execute('SELECT used FROM invites WHERE id=? AND org_id=?', (invite, org)).fetchone()
        if not r: fail(404, '邀请不存在')
        if r['used']: fail(409, '邀请已处理')
        d.execute('UPDATE invites SET used=2 WHERE id=?', (invite,)); log(d, org, user['id'], 'member.invite.revoke', invite)
    return {'ok': True}

@router.get('/api/my/organizations')
def my_organizations(request: Request):
    user = identity(request)
    with connect() as d:
        return [dict(r) for r in d.execute('''SELECT o.id,o.name,o.active,m.role,m.state,p.department_id,
            dep.name AS department_name,COALESCE(p.job_title,'') AS job_title
            FROM members m JOIN orgs o ON o.id=m.org_id LEFT JOIN member_profiles p ON p.org_id=m.org_id AND p.user_id=m.user_id
            LEFT JOIN departments dep ON dep.id=p.department_id WHERE m.user_id=? ORDER BY o.created''', (user['id'],))]

@router.get('/api/platform/orgs')
def platform_orgs(request: Request):
    platform_user(request)
    with connect() as d:
        result = [dict(r) for r in d.execute('''SELECT o.*,
            (SELECT COUNT(*) FROM members m WHERE m.org_id=o.id) AS member_count,
            (SELECT COUNT(*) FROM departments dep WHERE dep.org_id=o.id) AS department_count FROM orgs o ORDER BY created DESC''')]
        for org in result:
            org['owners'] = [dict(r) for r in d.execute("SELECT u.id,u.name,u.email FROM members m JOIN users u ON u.id=m.user_id WHERE m.org_id=? AND m.role='owner' AND m.state='active' AND u.active=1", (org['id'],))]
        return result

class PlatformOrgEdit(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default='', max_length=2000)
    active: bool = True

@router.put('/api/platform/orgs/{org}')
def platform_org_edit(org: str, data: PlatformOrgEdit, request: Request):
    user = platform_user(request)
    with connect(True) as d:
        if not d.execute('SELECT 1 FROM orgs WHERE id=?', (org,)).fetchone(): fail(404, '机构不存在')
        if data.active and not d.execute("SELECT 1 FROM members m JOIN users u ON u.id=m.user_id WHERE m.org_id=? AND m.role='owner' AND m.state='active' AND u.active=1", (org,)).fetchone():
            fail(409, '机构缺少有效负责人，无法启用')
        d.execute('UPDATE orgs SET name=?,description=?,active=? WHERE id=?', (clean_name(data.name), data.description, int(data.active), org))
        log(d, org, user['id'], 'platform.org.update', org, data.model_dump())
    return {'ok': True}

@router.get('/api/platform/orgs/{org}/departments')
def platform_departments(org: str, request: Request):
    platform_user(request)
    with connect() as d: return department_rows(d, org)

@router.get('/api/platform/users')
def user_list(request: Request, q: str = Query(default='', max_length=100), org: str = '', status: Literal['all','active','disabled'] = 'all', page: int = Query(default=1, ge=1), size: int = Query(default=20, ge=1, le=100)):
    platform_user(request)
    conditions = ['(instr(lower(u.name),?)>0 OR instr(lower(u.email),?)>0)']; args = [q.strip().lower()] * 2
    if status != 'all': conditions.append('u.active=?'); args.append(int(status == 'active'))
    if org == 'unassigned': conditions.append('NOT EXISTS(SELECT 1 FROM members m WHERE m.user_id=u.id)')
    elif org: conditions.append('EXISTS(SELECT 1 FROM members m WHERE m.user_id=u.id AND m.org_id=?)'); args.append(org)
    where = ' AND '.join(conditions)
    with connect() as d:
        total = d.execute('SELECT COUNT(*) FROM users u WHERE '+where, args).fetchone()[0]
        items = [dict(r) for r in d.execute('SELECT u.id,u.name,u.email,u.active,u.platform_admin,u.created FROM users u WHERE '+where+' ORDER BY created DESC,id LIMIT ? OFFSET ?', (*args, size, (page-1)*size))]
        for item in items:
            item['memberships'] = [dict(r) for r in d.execute('''SELECT m.org_id,o.name AS org_name,o.active AS org_active,m.role,m.state,p.department_id,dep.name AS department_name,COALESCE(p.job_title,'') AS job_title
                FROM members m JOIN orgs o ON o.id=m.org_id LEFT JOIN member_profiles p ON p.org_id=m.org_id AND p.user_id=m.user_id
                LEFT JOIN departments dep ON dep.id=p.department_id WHERE m.user_id=? ORDER BY o.name''', (item['id'],))]
        return {'items': items, 'total': total, 'page': page, 'size': size}

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254)

@router.post('/api/platform/users')
def user_create(data: UserCreate, request: Request):
    user = platform_user(request); password = secrets.token_urlsafe(18); person = uid()
    with connect(True) as d:
        address = clean_email(data.email)
        if d.execute('SELECT 1 FROM users WHERE email=?', (address,)).fetchone(): fail(409, '此邮箱已注册')
        d.execute('INSERT INTO users VALUES(?,?,?,?,0,1,?)', (person, address, clean_name(data.name), password_hash(password), now()))
        log(d, None, user['id'], 'platform.user.create', person)
    return {'id': person, 'email': address, 'initial_password': password, 'note': '初始密码只展示一次。请通过安全渠道交给本人，首次登录后修改。系统不会自动发送邮件。'}

class UserEdit(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    active: bool = True

@router.put('/api/platform/users/{person}')
def user_edit(person: str, data: UserEdit, request: Request):
    user = platform_user(request)
    with connect(True) as d:
        target = d.execute('SELECT * FROM users WHERE id=?', (person,)).fetchone()
        if not target: fail(404, '用户不存在')
        if not data.active:
            if person == user['id']: fail(409, '不能停用当前登录账号')
            if target['platform_admin'] and not d.execute('SELECT 1 FROM users WHERE platform_admin=1 AND active=1 AND id<>?', (person,)).fetchone():
                fail(409, '不能停用最后一位平台管理员')
            for membership in d.execute("SELECT org_id FROM members WHERE user_id=? AND role='owner' AND state='active'", (person,)).fetchall():
                if not d.execute("SELECT 1 FROM members m JOIN users u ON u.id=m.user_id WHERE m.org_id=? AND m.role='owner' AND m.state='active' AND u.active=1 AND m.user_id<>?", (membership['org_id'], person)).fetchone():
                    fail(409, '此账号是机构唯一有效负责人，请先调整负责人')
        d.execute('UPDATE users SET name=?,active=? WHERE id=?', (clean_name(data.name), int(data.active), person))
        if not data.active: d.execute('DELETE FROM sessions WHERE user_id=?', (person,))
        log(d, None, user['id'], 'platform.user.update', person, data.model_dump())
    return {'ok': True}

class UserMembership(MembershipData):
    org_id: str = Field(max_length=64)

@router.put('/api/platform/users/{person}/memberships')
def platform_membership(person: str, data: UserMembership, request: Request):
    user = platform_user(request)
    with connect(True) as d:
        exists = d.execute('SELECT 1 FROM members WHERE org_id=? AND user_id=?', (data.org_id, person)).fetchone()
        set_membership(d, data.org_id, person, data, user, platform=True, create=not exists)
    return {'ok': True}
