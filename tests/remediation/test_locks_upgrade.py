import json
import os
import socket
import subprocess
import sys
import shutil
from pathlib import Path
import qiming
from qiming_core.protocol import dispatch
from qiming_core.initialize import initialize

def op(manifest, name, **args):
    return dispatch({'protocol':'qiming.tool/1','request_id':'test','workspace_manifest':str(manifest),'op':name,'args':args})

def test_lock_alive_never_stale_by_age(tmp_path):
    path=tmp_path/'operations/.lock';path.parent.mkdir()
    path.write_text(json.dumps({'host':socket.gethostname(),'pid':os.getpid(),'run_id':'active','created_at':'2000-01-01T00:00:00Z'}))
    output=op(tmp_path/'workspace.json','lock_status')
    assert output['status']=='ok',output
    assert output['result']['state']=='alive'
    assert op(tmp_path/'workspace.json','lock_break',run_id='active',expected_sha256=output['result']['sha256'])['status']=='conflict'
    assert path.exists()

def test_dead_lock_break_requires_identity_and_fingerprint(tmp_path):
    child=subprocess.Popen([sys.executable,'-c','pass']); child.wait()
    path=tmp_path/'operations/.lock';path.parent.mkdir()
    path.write_text(json.dumps({'host':socket.gethostname(),'pid':child.pid,'run_id':'dead','created_at':'2000-01-01T00:00:00Z'}))
    output=op(tmp_path/'workspace.json','lock_status')
    assert output['status']=='ok',output
    assert output['result']['state']=='stale'
    assert op(tmp_path/'workspace.json','lock_break',run_id='other',expected_sha256=output['result']['sha256'])['status']=='conflict'
    assert op(tmp_path/'workspace.json','lock_break',run_id='dead',expected_sha256=output['result']['sha256'])['status']=='ok'
    assert not path.exists()

def test_upgrade_preserves_customization_and_rejects_changed_preview(tmp_path):
    root=tmp_path/'project';root.mkdir()
    assert initialize(root,goal='test')['status']=='ok'
    manifest=root/'.qiming/workspace.json'
    seed=tmp_path/'seed'
    shutil.copytree(Path(qiming.__file__).parents[1],seed,ignore=shutil.ignore_patterns('__pycache__'))
    instance=root/'.qiming/qiming-user'
    customized=instance/'references/manage.md'
    customized.write_bytes(customized.read_bytes()+b'\nUser custom rule\n')
    changed=seed/'references/recover.md';changed.write_bytes(changed.read_bytes()+b'\nNew recovery note\n')
    preview=op(manifest,'upgrade_preview',seed_dir=str(seed))
    assert preview['status']=='ok',preview
    rows={r['path']:r['state'] for r in preview['result']['resources']}
    assert rows['references/manage.md']=='local_modified'
    assert rows['references/recover.md']=='upgrade'
    output=op(manifest,'upgrade',preview=preview['result'],plan_id=preview['result']['plan_id'])
    assert output['status'] in {'ok','ok_with_warnings'},output
    assert customized.read_bytes().endswith(b'User custom rule\n')
    assert (instance/'references/recover.md').read_bytes()==changed.read_bytes()
    assert json.loads(manifest.read_text())['workspace_id']==preview['result']['workspace_id']
    assert op(manifest,'validate')['status'] in {'ok','ok_with_warnings'}

def test_crashed_breaker_marker_does_not_permanently_block_recovery(tmp_path):
    child=subprocess.Popen([sys.executable,'-c','pass']);child.wait()
    directory=tmp_path/'operations';directory.mkdir()
    (directory/'.lock').write_text(json.dumps({'host':socket.gethostname(),'pid':child.pid,'run_id':'dead'}))
    (directory/'.lock-break').write_text('')
    state=op(tmp_path/'workspace.json','lock_status')['result']
    result=op(tmp_path/'workspace.json','lock_break',run_id='dead',expected_sha256=state['sha256'])
    assert result['status']=='ok',result
