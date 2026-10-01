import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / 'skills/qiming/scripts/qiming.py'

def request(root, op, args):
    proc = subprocess.run([sys.executable, str(SCRIPT), '--stdin'], input=json.dumps({'protocol':'qiming.tool/1','request_id':'test','op':op,'workspace_manifest':str(root/'.qiming/workspace.json'),'args':args}), text=True, capture_output=True)
    assert proc.stdout, proc.stderr
    return json.loads(proc.stdout)

def test_init_record_search_log_and_repeat(tmp_path):
    original = b'# user rules\nKeep this.\n'
    (tmp_path/'AGENTS.md').write_bytes(original)
    result = request(tmp_path, 'init', {'root':str(tmp_path),'goal':'完成第一章修订','hosts':'codex'})
    assert result['status'] == 'ok', result
    work = tmp_path/'.qiming/work/w-0001.json'
    assert work.exists()
    assert 'work/w-0001.json' in (tmp_path/'.qiming/START.md').read_text()
    assert (tmp_path/'AGENTS.md').read_bytes().startswith(original)
    assert request(tmp_path,'reindex',{})['status'] == 'ok'
    found = request(tmp_path,'search',{'query':'第一章'})
    assert found['result']['items'][0]['id'] == 'w-0001'
    event = {'id':'evt-1','kind':'action','summary':'初稿完成','observed_at':'2026-10-01T00:00:00Z'}
    args = {'work_ref':{'kind':'file','root':'project','path':'.qiming/work/w-0001.json'},'event':event,'intent_ref':'w-0001'}
    assert request(tmp_path,'log_event',args)['status']=='ok'
    assert request(tmp_path,'log_event',args)['result']['already_recorded'] is True
    again=request(tmp_path,'init',{'root':str(tmp_path),'hosts':'codex'})
    assert again['status']=='ok', again
    assert again['result']['already_initialized'] is True
    assert again['changed']==[]
    assert request(tmp_path,'binding_status',{'host':'codex'})['result']['status']=='bound'

def test_init_dry_run_has_no_side_effects(tmp_path):
    result=request(tmp_path,'init',{'root':str(tmp_path),'goal':'x','dry_run':True})
    assert result['status']=='ok', result
    assert list(tmp_path.iterdir())==[]

def test_bootstrap_rejects_bad_mapping_before_writing(tmp_path):
    from qiming_core.bootstrap import bootstrap
    import pytest
    manifest={'protocol':'qiming.workspace/1','workspace_id':'ws_test','state':'initializing','profile':'profile.json','roots':{'project':{'location':'..','access':'read-write'}}}
    profile={'protocol':'qiming.profile/1','collections':{'work':{'root':'missing','mapping':'missing','codec':'unknown'}},'mappings':{}}
    with pytest.raises(ValueError):
        bootstrap(tmp_path,tmp_path/'.qiming',manifest,profile,'init')
    assert not (tmp_path/'.qiming').exists()

def test_init_resume_after_materialize_before_first_task(tmp_path,monkeypatch):
    import qiming_core.initialize as module
    real=module.write_payloads
    monkeypatch.setattr(module,'write_payloads',lambda *a,**kw: {'status':'conflict','result':None,'changed':[]})
    assert module.initialize(tmp_path,goal='saved goal')['status']=='conflict'
    monkeypatch.setattr(module,'write_payloads',real)
    result=module.initialize(tmp_path)
    assert result['status']=='ok',result
    assert json.loads((tmp_path/'.qiming/work/w-0001.json').read_text())['name']=='saved goal'

def test_general_without_site_packages(tmp_path):
    run=subprocess.run([sys.executable,'-S',str(SCRIPT),'init','--root',str(tmp_path),'--goal','No yaml'],capture_output=True,text=True)
    assert run.returncode==0,run.stdout+run.stderr
