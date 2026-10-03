import hashlib,json
from qiming_core.initialize import initialize
from qiming_core.host_binding import ensure_project_entrypoints,binding_status
from qiming_core.search import search
from qiming_core.index import reindex
from qiming_core.quick_log import log_event

def test_log_path_base_hint(tmp_path):
    initialize(tmp_path,goal='test')
    r=log_event(tmp_path/'.qiming/workspace.json',{'kind':'file','root':'project','path':'work/w-0001.json'}, {'id':'x','kind':'action','summary':'saved','observed_at':'2026-10-03T00:00:00Z'},None)
    assert r['status']=='conflict'
    assert '.qiming/work' in r['diagnostics'][0]['hint']
    assert 'registered root' in r['diagnostics'][0]['hint']

def test_plain_markdown_reports_reason_and_partial(tmp_path):
    initialize(tmp_path)
    p=tmp_path/'.qiming/profile.json';profile=json.loads(p.read_text())
    profile['collections']['notes']={'root':'project','directory':'notes','pattern':'**/*.md','codec':'markdown-frontmatter','mapping':'record'}
    p.write_text(json.dumps(profile));(tmp_path/'notes').mkdir();(tmp_path/'notes/plain.md').write_text('# needle')
    for r in (search(tmp_path/'.qiming/workspace.json',{'query':'needle','collections':['notes']}),reindex(tmp_path/'.qiming/workspace.json',['notes'])):
        assert r['status']=='partial'
        coverage=r['result']['coverage']
        assert coverage['skipped_count']==1
        assert coverage['skipped_files'][0]['reason']=='missing-frontmatter'
        assert coverage['skipped_files'][0]['path']=='notes/plain.md'
        assert r['diagnostics'][0]['code']=='INCOMPLETE_COVERAGE'

def test_category_filter_and_nested_members(tmp_path):
    initialize(tmp_path)
    folder=tmp_path/'.qiming/members/00-foundation';folder.mkdir()
    (folder/'a.json').write_text(json.dumps({'id':'a','type':'service','name':'engine','category':'infra','scope':'workspace'}))
    m=tmp_path/'.qiming/workspace.json'
    r=search(m,{'query':'engine','categories':['infra']})
    assert len(r['result']['items'])==1
    assert r['result']['items'][0]['category']=='infra'
    assert search(m,{'categories':['writing']})['result']['items']==[]

def test_entry_opt_out_persists_without_overwriting_rules(tmp_path):
    original=b'# user rules\n';(tmp_path/'AGENTS.md').write_bytes(original)
    r=initialize(tmp_path,goal='work',entry='none');assert r['status']=='ok',r
    assert (tmp_path/'AGENTS.md').read_bytes()==original
    assert not (tmp_path/'CLAUDE.md').exists() and not (tmp_path/'GEMINI.md').exists()
    assert binding_status(tmp_path/'.qiming/workspace.json','codex')['status']=='manual-entry'
    assert initialize(tmp_path)['changed']==[]
    assert ensure_project_entrypoints(tmp_path/'.qiming/workspace.json')['changed']==[]

def test_entry_agents_and_dry_run(tmp_path):
    dry=initialize(tmp_path,entry='agents',dry_run=True)
    assert dry['result']['root_entry_files']==['AGENTS.md']
    assert list(tmp_path.iterdir())==[]
    r=initialize(tmp_path,entry='agents');assert r['status']=='ok'
    assert (tmp_path/'AGENTS.md').exists() and not (tmp_path/'CLAUDE.md').exists()
    assert binding_status(tmp_path/'.qiming/workspace.json','codex')['status']=='bound'
    assert binding_status(tmp_path/'.qiming/workspace.json','claude')['status']=='manual-entry'

def test_refresh_changed_at_top_level_has_hashes(tmp_path):
    initialize(tmp_path);m=tmp_path/'.qiming/workspace.json';a=tmp_path/'AGENTS.md'
    before=hashlib.sha256(a.read_bytes()).hexdigest()
    (tmp_path/'.qiming/startup.md').write_text('Changed context')
    r=ensure_project_entrypoints(m)
    row=next(x for x in r['changed'] if x['path'].endswith('AGENTS.md'))
    assert row['before_sha256']==before
    assert row['after_sha256']==hashlib.sha256(a.read_bytes()).hexdigest()
    assert ensure_project_entrypoints(m)['changed']==[]

def test_entry_policy_survives_resume_and_upgrade(tmp_path,monkeypatch):
    import qiming_core.initialize as module
    from qiming_core.upgrade import upgrade_preview,upgrade
    from pathlib import Path
    original=module.write_payloads
    monkeypatch.setattr(module,'write_payloads',lambda *a,**kw:{'status':'conflict','changed':[]})
    assert module.initialize(tmp_path,entry='none',goal='original goal')['status']=='conflict'
    monkeypatch.setattr(module,'write_payloads',original)
    assert module.initialize(tmp_path)['status']=='ok'
    manifest=tmp_path/'.qiming/workspace.json';profile=tmp_path/'.qiming/profile.json'
    before=profile.read_bytes();identity=json.loads(manifest.read_text())['workspace_id']
    seed=Path(__file__).resolve().parents[2]/'skills/qiming'
    preview=upgrade_preview(manifest,seed)['result']
    assert upgrade(manifest,preview,preview['plan_id'])['status']=='ok'
    assert not (tmp_path/'AGENTS.md').exists()
    assert profile.read_bytes()==before
    assert json.loads(manifest.read_text())['workspace_id']==identity
    assert json.loads((tmp_path/'.qiming/work/w-0001.json').read_text())['name']=='original goal'

def test_cli_dry_run_lists_root_files(tmp_path):
    import subprocess,sys
    from pathlib import Path
    script=Path(__file__).resolve().parents[2]/'skills/qiming/scripts/qiming.py'
    p=subprocess.run([sys.executable,str(script),'init','--root',str(tmp_path),'--entry','none','--dry-run'],text=True,capture_output=True)
    assert p.returncode==0,p.stdout+p.stderr
    assert json.loads(p.stdout)['result']['root_entry_files']==[]
    assert list(tmp_path.iterdir())==[]

def test_journal_only_resume_preview_lists_saved_entries(tmp_path):
    from qiming_core.bootstrap import bootstrap
    from qiming_core.initialize import default_profile
    manifest={'protocol':'qiming.workspace/1','workspace_id':'ws_resume','state':'initializing','profile':'profile.json','roots':{'project':{'location':'..','access':'read-write'}},'extensions':{'entry_policy':'all'}}
    assert bootstrap(tmp_path,tmp_path/'.qiming',manifest,default_profile(),'init-test')['status']=='ok'
    (tmp_path/'.qiming/workspace.json').unlink()
    before={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    r=initialize(tmp_path,dry_run=True,entry='none')
    assert r['result']['root_entry_files']==['AGENTS.md','CLAUDE.md','GEMINI.md']
    assert before=={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert initialize(tmp_path)['status']=='ok'
    assert (tmp_path/'AGENTS.md').is_file()
