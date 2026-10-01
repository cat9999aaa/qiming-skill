import json
import hashlib
import shutil
from pathlib import Path
import pytest
from qiming_core.initialize import initialize
from qiming_core.plan import plan_changes
from qiming_core.upgrade import upgrade_preview,upgrade

@pytest.mark.parametrize('codec,alias,body',[('yaml','project','password: dummy-review-value\n'),('json','alternate','{"password":"dummy-review-value"}')])
def test_secret_cannot_use_yaml_or_alias(tmp_path,codec,alias,body):
    assert initialize(tmp_path)['status']=='ok'
    manifest=tmp_path/'.qiming/workspace.json'
    data=json.loads(manifest.read_text());data['roots']['alternate']=data['roots']['project'];manifest.write_text(json.dumps(data))
    profile_path=manifest.parent/'profile.json';profile=json.loads(profile_path.read_text());profile['collections']['work']['codec']=codec;profile_path.write_text(json.dumps(profile))
    staged=manifest.parent/'test-stage';staged.write_text(body)
    change={'action':'create','target':{'kind':'file','root':alias,'path':'.qiming/work/new.json'},'expected_sha256':None,'content_ref':'test-stage','desired_sha256':hashlib.sha256(staged.read_bytes()).hexdigest()}
    result=plan_changes(manifest,[change],'test',hashlib.sha256(profile_path.read_bytes()).hexdigest())
    assert result['status']=='conflict',result
    assert result['diagnostics'][0]['code']=='SECRET_VALUE_FORBIDDEN'

def test_bootstrap_earliest_interruption_can_resume(tmp_path,monkeypatch):
    original=Path.open
    def fail(self,*args,**kwargs):
        if self.name=='workspace.json' and args and args[0]=='xb': raise OSError('simulated interruption')
        return original(self,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path,'open',fail)
        with pytest.raises(OSError): initialize(tmp_path,goal='persist goal')
    assert initialize(tmp_path)['status']=='ok'
    assert json.loads((tmp_path/'.qiming/work/w-0001.json').read_text())['name']=='persist goal'

def test_copy_binding_upgraded_and_removed_both_handled(tmp_path,monkeypatch):
    def fail(*a,**kw): raise OSError('no symlink')
    monkeypatch.setattr(Path,'symlink_to',fail)
    root=tmp_path/'project';root.mkdir()
    assert initialize(root)['status']=='ok'
    manifest=root/'.qiming/workspace.json'
    import qiming
    seed=tmp_path/'seed';shutil.copytree(Path(qiming.__file__).parents[1],seed,ignore=shutil.ignore_patterns('__pycache__'))
    file=seed/'references/recover.md';file.write_bytes(file.read_bytes()+b'\nUpdated\n')
    (seed/'references/domains.md').unlink();(root/'.qiming/qiming-user/references/domains.md').unlink()
    preview=upgrade_preview(manifest,seed)['result']
    result=upgrade(manifest,preview,preview['plan_id'])
    assert result['status'] in {'ok','ok_with_warnings'},result
    assert (root/'.agents/skills/qiming-user/references/recover.md').read_bytes()==file.read_bytes()

def test_upgrade_does_not_overwrite_new_path_owned_by_copy(tmp_path,monkeypatch):
    monkeypatch.setattr(Path,'symlink_to',lambda *a,**kw: (_ for _ in ()).throw(OSError('no symlink')))
    root=tmp_path/'project';root.mkdir();assert initialize(root)['status']=='ok'
    manifest=root/'.qiming/workspace.json'
    import qiming
    seed=tmp_path/'seed';shutil.copytree(Path(qiming.__file__).parents[1],seed,ignore=shutil.ignore_patterns('__pycache__'))
    copy=root/'.agents/skills/qiming-user/scripts/local_helper.py';copy.write_text('# user-owned')
    (seed/'scripts/local_helper.py').write_text('# vendor helper')
    preview=upgrade_preview(manifest,seed)['result'];result=upgrade(manifest,preview,preview['plan_id'])
    assert copy.read_text()=='# user-owned'
    assert 'codex' in result['result']['binding_conflicts']

def test_upgrade_detects_late_change_to_preserved_file(tmp_path,monkeypatch):
    root=tmp_path/'project';root.mkdir();assert initialize(root)['status']=='ok'
    manifest=root/'.qiming/workspace.json'
    import qiming
    import qiming_core.upgrade as module
    seed=tmp_path/'seed';shutil.copytree(Path(qiming.__file__).parents[1],seed,ignore=shutil.ignore_patterns('__pycache__'))
    local=root/'.qiming/qiming-user/references/manage.md';local.write_bytes(local.read_bytes()+b'\nCustom')
    preview=upgrade_preview(manifest,seed)['result']
    before=(root/'.qiming/qiming-user/instance.json').read_bytes()
    original=module.plan_changes
    def race(*args,**kwargs):
        result=original(*args,**kwargs);local.write_bytes(local.read_bytes()+b'\nConcurrent');return result
    monkeypatch.setattr(module,'plan_changes',race)
    result=upgrade(manifest,preview,preview['plan_id'])
    assert result['status']=='conflict',result
    assert (root/'.qiming/qiming-user/instance.json').read_bytes()==before
