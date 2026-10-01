import json,subprocess,sys
from pathlib import Path
from qiming_core.initialize import initialize
from qiming_core.validate import validate
from qiming_core.host_binding import binding_status
SCRIPT=Path(__file__).resolve().parents[2]/'skills/qiming/scripts/qiming.py'

def test_local_edit_warns_but_missing_resource_is_error(tmp_path):
    assert initialize(tmp_path)['status']=='ok'
    manifest=tmp_path/'.qiming/workspace.json';file=tmp_path/'.qiming/qiming-user/references/manage.md'
    file.write_bytes(file.read_bytes()+b'\nLocal rule.\n')
    checked=validate(manifest,[],False)
    assert checked['status']=='ok_with_warnings',checked
    assert checked['diagnostics'][0]['code']=='LOCAL_MODIFICATION'
    assert binding_status(manifest,'codex')['status']=='bound'
    repeat=initialize(tmp_path)
    assert repeat['status']=='ok_with_warnings',repeat
    assert repeat['changed']==[]
    file.unlink()
    assert validate(manifest,[],False)['status']=='error'

def test_success_removes_only_own_staging(tmp_path):
    control=tmp_path/'.qiming'
    assert initialize(tmp_path,goal='Draft')['status']=='ok'
    for directory in ('.staging','.host-entry-staging'):
        assert not any(p.is_file() for p in (control/directory).rglob('*'))
    from qiming_core.initialize import write_payloads
    saved=control/'.staging/unrelated';saved.parent.mkdir(exist_ok=True);saved.write_bytes(b'pending other operation')
    result=write_payloads(control/'workspace.json',[(tmp_path/'note.md',b'note',None)],'test')
    assert result['status']=='ok' and saved.read_bytes()==b'pending other operation'

def test_short_init_summary_and_default_log_intent(tmp_path):
    init=subprocess.run([sys.executable,str(SCRIPT),'init','--root',str(tmp_path),'--goal','Chapter one'],capture_output=True,text=True)
    assert init.returncode==0
    assert '项目目录' in init.stderr and '下一步' in init.stderr
    json.loads(init.stdout)
    command=[sys.executable,str(SCRIPT),'log','.qiming/work/w-0001.json','Draft saved','--workspace-manifest','.qiming/workspace.json','--event-id','once']
    result=subprocess.run(command,cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr+result.stdout
    journal=Path(json.loads(result.stdout)['result']['journal_ref'])
    assert json.loads(journal.read_text())['plan']['intent_ref']=='w-0001'

def test_seed_metadata_has_byte_fingerprint(tmp_path):
    from qiming_core.upgrade import seed_metadata
    seed=tmp_path/'seed';(seed/'assets/contracts').mkdir(parents=True)
    (seed/'SKILL.md').write_text('Skill')
    (seed/'assets/contracts/version.json').write_text(json.dumps({'version':'test','commit':'a'*40,'commit_kind':'release-source'}))
    first=seed_metadata(seed)
    assert len(first['package_sha256'])==64
    (seed/'SKILL.md').write_text('Changed')
    assert seed_metadata(seed)['package_sha256']!=first['package_sha256']
    assert first['commit']=='a'*40


def test_interrupted_write_keeps_its_staged_bytes(tmp_path,monkeypatch):
    import qiming_core.initialize as module
    assert initialize(tmp_path)['status']=='ok'
    monkeypatch.setattr(module,'apply_plan',lambda *a,**kw:{'status':'partial','result':{'journal_ref':'interrupted'},'changed':[]})
    result=module.write_payloads(tmp_path/'.qiming/workspace.json',[(tmp_path/'note.md',b'needed for resume',None)],'test')
    assert result['status']=='partial'
    assert any(p.read_bytes()==b'needed for resume' for p in (tmp_path/'.qiming/.staging').rglob('*') if p.is_file())


def test_default_log_intent_requires_record_id(tmp_path):
    assert initialize(tmp_path,goal='Draft')['status']=='ok'
    path=tmp_path/'.qiming/work/w-0001.json';record=json.loads(path.read_text());del record['id'];path.write_text(json.dumps(record))
    before=path.read_bytes()
    result=subprocess.run([sys.executable,str(SCRIPT),'log','.qiming/work/w-0001.json','Saved','--workspace-manifest','.qiming/workspace.json'],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==2
    assert 'no id' in result.stdout and path.read_bytes()==before
