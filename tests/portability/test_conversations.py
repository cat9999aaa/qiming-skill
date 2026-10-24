"""Synthetic subprocess tests; no host APIs or real workspace records."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

HELPER = Path(__file__).resolve().parents[2] / 'skills/qiming/scripts/session_policy.py'

@pytest.fixture
def request_data(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    control = root / '.qiming'
    control.mkdir()
    manifest = control / 'workspace.json'
    manifest.write_text(json.dumps(dict(protocol='qiming.workspace/1', state='ready', workspace_id='ws-test', project_root='..')), encoding='utf-8')
    context = dict(cwd=str(root), workspace_id='ws-test', project_id='project-test', current_thread_id='main', project_root=str(root), host_readback_ref='parent-readback.json')
    thread = dict(id='topic', cwd=str(root), workspace_id='ws-test', project_id='project-test', project_root=str(root), host_readback_ref='child-readback.json', task_ref='work-test', available=True, archived=False, status='completed', is_coordinator=False, executing=False, awaiting_approval=False, awaiting_user=False, outcome_refs=['outcome.json'], verification_refs=['verification.json'], handoff_ref='handoff.json')
    return dict(op='verify', workspace_manifest=str(manifest), context=context, thread=thread, task_ref='work-test', authorization=dict(split_current_work=True, archive_completed=True, source_ref='user-request'))

def call(data):
    result = subprocess.run([sys.executable, str(HELPER)], input=json.dumps(data), text=True, capture_output=True)
    assert result.returncode in (0, 2), result.stderr
    return json.loads(result.stdout)

def test_matching_identity_verified(request_data):
    assert call(request_data)['verified'] is True

@pytest.mark.parametrize('field,value,code', [('cwd','outside','CWD_MISMATCH'), ('workspace_id','other','WORKSPACE_MISMATCH'), ('project_id','other','PROJECT_UNVERIFIED')])
def test_wrong_child_scope(request_data, field, value, code):
    if field == 'cwd': value = str(Path(request_data['context']['cwd']).parent)
    request_data['thread'][field] = value
    assert call(request_data)['code'] == code

@pytest.mark.parametrize('record', ['context','thread'])
def test_missing_project_not_null(request_data, record):
    del request_data[record]['project_id']
    assert call(request_data)['code'] == 'PROJECT_UNVERIFIED'

def test_null_directory_project_is_not_registered(request_data):
    for key in ('context','thread'): request_data[key]['project_id'] = None
    request_data['context']['project_requirement'] = 'workspace'
    result = call(request_data)
    assert result['verified'] and result['host_project_membership'] == 'unregistered'
    del request_data['thread']['host_readback_ref']
    assert call(request_data)['code'] == 'PROJECT_UNVERIFIED'

def test_sidebar_separate_and_required_only_when_requested(request_data):
    request_data['context']['expected_section_id'] = 'section-test'
    assert call(request_data)['code'] == 'SIDEBAR_UNVERIFIED'
    request_data['thread']['section_id'] = 'wrong'
    assert call(request_data)['code'] == 'SIDEBAR_MISMATCH'
    request_data['thread']['section_id'] = 'section-test'
    request_data['thread']['sidebar_readback_ref'] = 'sidebar.json'
    assert call(request_data)['verified']

def test_reuse_precedes_creation_and_does_not_authorize_send(request_data):
    request_data.update(op='recommend', threads=[request_data['thread']], authorization={})
    assert call(request_data)['action'] == 'reuse'
    assert 'tool_request' not in call(request_data)

def test_misplaced_existing_thread_is_not_duplicated(request_data):
    request_data['context']['expected_section_id'] = 'section-test'
    request_data.update(op='recommend', threads=[request_data['thread']])
    result = call(request_data)
    assert result['action'] == 'reuse' and not result['verified']
    assert result['placement_code'] == 'SIDEBAR_UNVERIFIED'

def test_create_and_fork_need_authorization(request_data):
    request_data.update(op='recommend', authorization={})
    assert call(request_data)['code'] == 'CREATION_NOT_AUTHORIZED'

def test_registered_root_creates_in_project(request_data):
    request_data['op'] = 'recommend'
    result = call(request_data)
    assert result['tool_request']['args']['target']['projectId'] == 'project-test'
    assert not result['verified']

@pytest.mark.parametrize('unresolved', [True, False])
def test_unresolved_or_subdirectory_forks(request_data, unresolved):
    request_data['op'] = 'recommend'
    if unresolved:
        request_data['context']['project_id'] = None
        request_data['context']['project_requirement'] = 'workspace'
    else:
        child = Path(request_data['context']['cwd']) / 'component'
        child.mkdir()
        request_data['context']['cwd'] = str(child)
    result = call(request_data)
    assert result['action'] == 'fork'
    assert result['tool_request']['args']['environment']['type'] == 'same-directory'

@pytest.mark.parametrize('status', ['active', 'paused', 'awaiting_user', 'idle'])
def test_only_completed_can_archive(request_data,status):
    request_data['op'] = 'archive'; request_data['thread']['status'] = status
    assert call(request_data)['code'] == 'THREAD_NOT_COMPLETED'

@pytest.mark.parametrize('field', ['is_coordinator','executing','awaiting_approval','awaiting_user'])
def test_busy_flags_prevent_archive(request_data,field):
    request_data['op'] = 'archive'; request_data['thread'][field] = True
    assert call(request_data)['code'] == 'THREAD_BUSY_OR_COORDINATOR'

def test_archive_requires_authorization_evidence_preservation(request_data):
    request_data['op'] = 'archive'
    original = copy.deepcopy(request_data)
    request_data['authorization'] = {}
    assert call(request_data)['code'] == 'ARCHIVE_NOT_AUTHORIZED'
    request_data = copy.deepcopy(original); request_data['thread']['handoff_ref'] = ''
    assert call(request_data)['code'] == 'EVIDENCE_INCOMPLETE'
    request_data = copy.deepcopy(original); request_data['thread']['worktree'] = {}
    assert call(request_data)['code'] == 'WORKTREE_NOT_PRESERVED'
    request_data['thread']['worktree']['preservation_ref'] = 'snapshot.json'
    assert call(request_data)['action'] == 'archive'
    assert call(request_data)['project_requirement'] == 'registered'
    assert not call(request_data)['verified']

def test_current_thread_never_archived(request_data):
    request_data['op'] = 'archive'; request_data['thread']['id'] = 'main'
    assert call(request_data)['code'] == 'THREAD_BUSY_OR_COORDINATOR'

def test_invalid_input_is_structured():
    assert call({})['code'] == 'INVALID_INPUT'


def test_instance_packages_helper_and_upgrade_preserves_custom_entry(tmp_path):
    from qiming_core.initialize import initialize
    import qiming  # Registers the CLI protocol handlers.
    from qiming_core.protocol import dispatch
    root = tmp_path / 'project'
    root.mkdir()
    assert initialize(root, goal='synthetic session checks', hosts='codex')['status'] == 'ok'
    instance = root / '.qiming/qiming-user'
    assert (instance / 'scripts/session_policy.py').read_bytes() == HELPER.read_bytes()
    assert (instance / 'references/conversations.md').is_file()
    entry = instance / 'SKILL.md'
    assert 'references/conversations.md' in entry.read_text(encoding='utf-8')
    custom = entry.read_bytes() + b'\nUser-owned custom entry\n'
    entry.write_bytes(custom)
    result = dispatch(dict(protocol='qiming.tool/1', request_id='preview', op='upgrade_preview', workspace_manifest=str(root / '.qiming/workspace.json'), args=dict(seed_dir=str(HELPER.parents[1]))))
    assert result['status'] == 'ok', result
    rows = {r['path']: r['state'] for r in result['result']['resources']}
    assert rows['SKILL.md'] == 'local_modified'
    assert entry.read_bytes() == custom


def test_archive_unknown_current_thread_is_not_safe(request_data):
    request_data['op'] = 'archive'
    del request_data['context']['current_thread_id']
    assert call(request_data)['status'] == 'blocked'

@pytest.mark.parametrize('bad', [True, ['ref'], '   '])
def test_authorization_requires_reference_string(request_data, bad):
    request_data['op'] = 'archive'; request_data['authorization']['source_ref'] = bad
    assert call(request_data)['code'] == 'ARCHIVE_NOT_AUTHORIZED'

@pytest.mark.parametrize('bad', [True, ['ref'], '   '])
def test_worktree_preservation_requires_reference_string(request_data, bad):
    request_data['op'] = 'archive'
    request_data['thread']['worktree'] = dict(has_independent_changes=True, preservation_ref=bad)
    assert call(request_data)['code'] == 'WORKTREE_NOT_PRESERVED'

@pytest.mark.parametrize('field', ['project_id','id'])
def test_ids_are_scalar_strings(request_data, field):
    request_data['thread'][field] = ['wrong-shape']
    if field == 'project_id': request_data['context'][field] = ['wrong-shape']
    assert call(request_data)['status'] == 'blocked'


@pytest.mark.parametrize('op', ['verify', 'recommend', 'archive'])
def test_formal_project_requirement_cannot_be_satisfied_by_null_directory_mode(request_data, op):
    for key in ('context', 'thread'):
        request_data[key]['project_id'] = None
    request_data['context']['expected_section_id'] = 'section-test'
    request_data['thread']['section_id'] = 'section-test'
    request_data['thread']['sidebar_readback_ref'] = 'sidebar.json'
    request_data['op'] = op
    request_data['threads'] = [request_data['thread']]
    result = call(request_data)
    assert result['code'] == 'HOST_PROJECT_REQUIRED'
    assert not result['verified']
    assert 'tool_request' not in result

@pytest.mark.parametrize('bad', [None, True, [], 'directory', ''])
def test_unknown_project_requirement_does_not_silently_downgrade(request_data, bad):
    request_data['context']['project_requirement'] = bad
    assert call(request_data)['code'] == 'INVALID_PROJECT_REQUIREMENT'

def test_explicit_registered_requirement_still_verifies_real_project(request_data):
    request_data['context']['project_requirement'] = 'registered'
    assert call(request_data)['verified']

@pytest.mark.parametrize('marker',['.git','.qiming/workspace.json'])
def test_parent_policy_rejects_nested_independent_project(request_data,marker):
    root=Path(request_data['context']['cwd']);child=root/'independent';child.mkdir()
    target=child/marker
    if marker=='.git':target.mkdir()
    else:
        target.parent.mkdir();target.write_text(json.dumps({'protocol':'qiming.workspace/1','workspace_id':'ws_other'}))
    for name in ('context','thread'):request_data[name]['cwd']=str(child)
    assert call(request_data)['status']=='blocked'
    request_data['op']='recommend';assert call(request_data)['status']=='blocked'
