from test_system import env
import database


def department(client, org, name, parent=None):
    r = client.post(f'/api/orgs/{org}/departments', json={'name': name, 'parent_id': parent})
    assert r.status_code == 200, r.text
    return r.json()['id']


def test_learner_affiliation_never_grants_staff_or_cross_org_access(env):
    owner, org, new = env
    learner = new('learner@example.test'); other = new('other@example.test')
    dep = department(owner, org, '创作中心')
    assert owner.post(f'/api/orgs/{org}/members', json={'email':'learner@example.test','department_id':dep,'job_title':'学员'}).status_code == 200
    assert learner.get('/api/my/organizations').json()[0]['department_name'] == '创作中心'
    assert learner.get('/api/my/organizations').json()[0]['role'] == 'learner'
    for path in (f'/api/orgs/{org}/modules', f'/api/orgs/{org}/members', f'/api/orgs/{org}/departments', f'/api/orgs/{org}/overview', '/api/platform/users', '/api/platform/orgs'):
        assert learner.get(path).status_code == 403, path
    assert learner.post(f'/api/orgs/{org}/modules', json={'data':{'title':'Unauthorized'}}).status_code == 403
    assert learner.get('/api/catalog', params={'org':org}).status_code == 200
    assert learner.post('/api/agent/plan',json={'org_id':org,'days':1}).status_code == 200
    org2 = owner.post('/api/orgs',json={'name':'另一个机构','owner_email':'other@example.test'}).json()['id']
    dep2 = department(other, org2, '外部部门')
    uid = learner.get('/api/auth/me').json()['user']['id']
    assert owner.put(f'/api/orgs/{org}/members/{uid}',json={'role':'learner','department_id':dep2}).status_code == 422
    assert other.get(f'/api/orgs/{org}/departments').status_code == 403
    assert owner.get(f'/api/orgs/{org2}/members').status_code == 403
    assert owner.put(f'/api/platform/users/{uid}/memberships',json={'org_id':org2,'role':'learner','department_id':dep2}).status_code == 200
    assert len(learner.get('/api/my/organizations').json()) == 2
    # Disabling one membership does not disable the account or its other institution.
    assert owner.put(f'/api/orgs/{org}/members/{uid}',json={'role':'learner','state':'disabled'}).status_code == 200
    assert learner.get('/api/auth/me').json()['memberships'][0]['id'] == org2
    rows=owner.get(f'/api/orgs/{org}/members').json()
    assert next(x for x in rows if x['id']==uid)['department_id']==dep


def test_department_cycle_depth_delete_and_invite_assignment(env):
    owner, org, new = env
    root=department(owner,org,'学院'); child=department(owner,org,'视频部',root)
    assert owner.put(f'/api/orgs/{org}/departments/{root}',json={'name':'学院','parent_id':child}).status_code==422
    assert owner.post(f'/api/orgs/{org}/departments',json={'name':'视频部','parent_id':root}).status_code==409
    assert owner.delete(f'/api/orgs/{org}/departments/{root}').status_code==409
    deep=child
    for n in range(4): deep=department(owner,org,f'分组{n}',deep)
    assert owner.post(f'/api/orgs/{org}/departments',json={'name':'过深','parent_id':deep}).status_code==422
    invite=owner.post(f'/api/orgs/{org}/invites',json={'email':'student@example.test','department_id':child,'job_title':'研修学员'}).json()
    assert owner.delete(f'/api/orgs/{org}/departments/{child}').status_code==409
    student=new('student@example.test')
    assert student.post('/api/invites/accept',json={'token':invite['url'].split('invite=')[1]}).status_code==200
    assert student.get('/api/my/organizations').json()[0]['job_title']=='研修学员'
    assert student.get('/api/my/organizations').json()[0]['role']=='learner'
    standalone=department(owner,org,'临时部门')
    invite=owner.post(f'/api/orgs/{org}/invites',json={'email':'revoked@example.test','department_id':standalone}).json()
    row=next(x for x in owner.get(f'/api/orgs/{org}/invites').json() if x['email']=='revoked@example.test')
    assert 'token' not in row
    assert owner.delete(f'/api/orgs/{org}/invites/{row["id"]}').status_code==200
    assert owner.delete(f'/api/orgs/{org}/departments/{standalone}').status_code==200
    revoked=new('revoked@example.test')
    assert revoked.post('/api/invites/accept',json={'token':invite['url'].split('invite=')[1]}).status_code==404


def test_platform_account_lifecycle_and_last_owner_guards(env):
    owner,org,new=env
    r=owner.post('/api/platform/users',json={'name':'机构讲师','email':'created@example.test'})
    assert r.status_code==200,r.text
    created=r.json();assert len(created['initial_password'])>=18
    assert owner.post('/api/platform/users',json={'name':'重复','email':'created@example.test'}).status_code==409
    rows=owner.get('/api/platform/users',params={'q':'created','org':'unassigned'}).json()
    assert rows['total']==1 and 'password' not in rows['items'][0]
    from fastapi.testclient import TestClient
    import app
    client=TestClient(app.app);client.headers['X-Requested-With']='course-platform'
    login=client.post('/api/auth/login',json={'email':created['email'],'password':created['initial_password']});assert login.status_code==200
    assert owner.put('/api/platform/users/'+created['id'],json={'name':'机构讲师','active':False}).status_code==200
    assert client.get('/api/auth/me').json()['user'] is None
    assert owner.put('/api/platform/users/'+created['id'],json={'name':'机构讲师','active':True}).status_code==200
    org2=owner.post('/api/orgs',json={'name':'新机构','owner_email':created['email']}).json()['id']
    assert owner.put('/api/platform/users/'+created['id'],json={'name':'机构讲师','active':False}).status_code==409
    uid=owner.get('/api/auth/me').json()['user']['id']
    assert owner.put(f'/api/platform/users/{uid}/memberships',json={'org_id':org,'role':'learner'}).status_code==409
    assert owner.put(f'/api/platform/users/{uid}',json={'name':'负责人','active':False}).status_code==409
    # Platform admin manages identities, without obtaining another institution's course access.
    assert owner.get(f'/api/orgs/{org2}/modules').status_code==403
    assert owner.put(f'/api/platform/users/{uid}/memberships',json={'org_id':org2,'role':'owner'}).status_code==200
    assert owner.put('/api/platform/users/'+created['id'],json={'name':'机构讲师','active':False}).status_code==200


def test_org_disable_restore_and_migration_preserves_existing_data(env):
    owner,org,new=env
    before=owner.get('/api/catalog',params={'org':org}).json()
    dep=department(owner,org,'培训中心')
    database.initialize();database.initialize()
    assert len(owner.get('/api/catalog',params={'org':org}).json())==47
    assert owner.get(f'/api/orgs/{org}/departments').json()[0]['id']==dep
    assert owner.put(f'/api/platform/orgs/{org}',json={'name':'学院','active':False}).status_code==200
    assert owner.get('/api/orgs').json()==[]
    assert owner.get('/api/modules/'+before[0]['id']).status_code==404
    assert owner.get(f'/api/orgs/{org}/members').status_code==403
    assert owner.get('/api/platform/orgs').json()[0]['active']==0
    assert owner.put(f'/api/platform/orgs/{org}',json={'name':'学院','active':True}).status_code==200
    assert len(owner.get('/api/catalog',params={'org':org}).json())==47


def test_admin_cannot_assign_owner_or_manage_platform(env):
    owner,org,new=env;admin=new('admin@example.test');person=new('person@example.test')
    assert owner.post(f'/api/orgs/{org}/members',json={'email':'admin@example.test','role':'admin'}).status_code==200
    assert admin.post(f'/api/orgs/{org}/members',json={'email':'person@example.test','role':'owner'}).status_code==403
    assert admin.post(f'/api/orgs/{org}/members',json={'email':'person@example.test','role':'learner'}).status_code==200
    person_id=person.get('/api/auth/me').json()['user']['id']
    assert admin.put(f'/api/orgs/{org}/members/{person_id}',json={'role':'owner'}).status_code==403
    assert admin.put(f'/api/platform/users/{person_id}',json={'name':'X','active':False}).status_code==403
    assert admin.post('/api/platform/users',json={'name':'X','email':'x@example.test'}).status_code==403
