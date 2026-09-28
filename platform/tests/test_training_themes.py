import json
from test_system import env
import database


def test_example_rename_is_targeted_and_runs_once(env):
    owner, org, _ = env
    with database.connect(True) as d:
        d.execute('DELETE FROM schema_version WHERE version=3')
        d.execute('UPDATE orgs SET name=? WHERE id=?', ('AIGC视频创作学院', org))
        d.execute('INSERT INTO orgs VALUES(?,?,?,1,30,?)',
                  ('custom', 'AIGC视频创作学院', '用户自行创建的同名机构', database.now()))
        before = {t: d.execute('SELECT count(*) FROM '+t).fetchone()[0]
                  for t in ['users', 'members', 'modules', 'versions', 'plans']}
    database.initialize()
    with database.connect(True) as d:
        assert d.execute('SELECT name FROM orgs WHERE id=?', (org,)).fetchone()[0] == '微墨AIGC培训学院'
        assert d.execute("SELECT name FROM orgs WHERE id='custom'").fetchone()[0] == 'AIGC视频创作学院'
        assert before == {t: d.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in before}
        d.execute('UPDATE orgs SET name=? WHERE id=?', ('用户重新命名的机构', org))
    database.initialize()
    assert next(o for o in owner.get('/api/orgs').json() if o['id'] == org)['name'] == '用户重新命名的机构'


def test_training_theme_is_independent_of_institution(env):
    owner, org, _ = env
    themes = json.loads((database.ROOT/'web/training-themes.json').read_text(encoding='utf-8'))
    assert themes[0]['id'] == 'aigc-video'
    assert themes[0]['name'] == 'AIGC视频创作学院'
    assert owner.get('/api/orgs').json()[0]['name'] == '微墨AIGC培训学院'
    assert len(owner.get('/api/catalog', params={'org': org}).json()) == 47
