#!/usr/bin/env python3
"""Read-only Codex thread policy. JSON stdin -> recommendation; never calls host tools."""
import json
from pathlib import Path
import sys


def text_ref(value):
    return isinstance(value, str) and bool(value.strip())


def reject(code):
    return dict(status='blocked', code=code, verified=False)


def scope(request):
    manifest_path = Path(request['workspace_manifest']).resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    context = request['context']
    requirement = context.get('project_requirement', 'registered')
    if not isinstance(requirement, str) or requirement not in {'registered', 'workspace'}:
        return reject('INVALID_PROJECT_REQUIREMENT')
    if 'project_id' in context and context['project_id'] is None and requirement == 'registered':
        return reject('HOST_PROJECT_REQUIRED')
    if not text_ref(context.get('cwd')):
        return reject('INVALID_INPUT')
    if not text_ref(context.get('current_thread_id')):
        return reject('PROJECT_UNVERIFIED')
    if 'project_id' in context and context['project_id'] is not None and not text_ref(context['project_id']):
        return reject('PROJECT_UNVERIFIED')
    root = (manifest_path.parent / manifest['project_root']).resolve(strict=True)
    if manifest.get('protocol') != 'qiming.workspace/1' or manifest.get('state') != 'ready':
        return reject('WORKSPACE_NOT_READY')
    if context.get('workspace_id') != manifest.get('workspace_id'):
        return reject('WORKSPACE_MISMATCH')
    # Exact current cwd matters: a fork must preserve it, including a task subdirectory.
    cwd = Path(context['cwd']).resolve()
    if not cwd.is_relative_to(root):
        return reject('CWD_MISMATCH')
    return None


def thread_scope(thread, context, manifest_path):
    if not text_ref(thread.get('id')):
        return 'THREAD_ID_REQUIRED'
    if 'project_id' in thread and thread['project_id'] is not None and not text_ref(thread['project_id']):
        return 'PROJECT_UNVERIFIED'
    if thread.get('workspace_id') != context['workspace_id']:
        return 'WORKSPACE_MISMATCH'
    if not thread.get('cwd') or Path(thread['cwd']).resolve() != Path(context['cwd']).resolve():
        return 'CWD_MISMATCH'
    if 'project_id' not in context or 'project_id' not in thread:
        return 'PROJECT_UNVERIFIED'
    if context.get('project_requirement', 'registered') == 'registered' and thread['project_id'] is None:
        return 'HOST_PROJECT_REQUIRED'
    if context['project_id'] is None and thread['project_id'] is None:
        # Explicit host null is an unregistered directory project, not an unknown ID.
        manifest_path = Path(manifest_path).resolve(strict=True)
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        root = (manifest_path.parent / manifest['project_root']).resolve(strict=True)
        if not thread.get('id'):
            return 'THREAD_ID_REQUIRED'
        if not context.get('current_thread_id'):
            return 'PROJECT_UNVERIFIED'
        for record in (context, thread):
            if (not isinstance(record.get('host_readback_ref'), str)
                    or not record['host_readback_ref'].strip()
                    or not isinstance(record.get('project_root'), str)
                    or Path(record['project_root']).resolve() != root):
                return 'PROJECT_UNVERIFIED'
        return None
    if not context['project_id'] or thread['project_id'] != context['project_id']:
        return 'PROJECT_UNVERIFIED'
    return None


def placement(thread, context):
    expected = context.get('expected_section_id')
    if expected is None:
        return None
    if not isinstance(expected, str) or not expected.strip():
        return 'SIDEBAR_UNVERIFIED'
    if 'section_id' not in thread:
        return 'SIDEBAR_UNVERIFIED'
    if thread['section_id'] != expected:
        return 'SIDEBAR_MISMATCH'
    if not isinstance(thread.get('sidebar_readback_ref'), str) or not thread['sidebar_readback_ref'].strip():
        return 'SIDEBAR_UNVERIFIED'
    return None


def evaluate(request):
    try:
        error = scope(request)
        if error:
            return error
        context = request['context']
        identity = (dict(project_identity_mode='workspace_root', host_project_membership='unregistered')
                    if 'project_id' in context and context['project_id'] is None
                    else dict(project_identity_mode='host_project', host_project_membership='registered'))
        requirement = context.get('project_requirement', 'registered')
        identity['project_requirement'] = requirement
        op = request['op']
        if op == 'recommend':
            if requirement == 'registered' and not context.get('project_id'):
                return reject('PROJECT_UNVERIFIED')
            task = request.get('task_ref')
            if not isinstance(task, str) or not task.strip():
                return reject('TASK_REQUIRED')
            for thread in request.get('threads', []):
                if (thread.get('task_ref') == task and thread.get('available') is True
                        and thread.get('id') and not thread.get('archived', False)
                        and thread_scope(thread, context, request['workspace_manifest']) is None):
                    placement_error = placement(thread, context)
                    return dict(status='ok', action='reuse', thread_id=thread['id'],
                                verified=placement_error is None, placement_code=placement_error,
                                next='Verify requested sidebar placement; reuse does not authorize messaging.', **identity)
            auth = request.get('authorization', {})
            if auth.get('split_current_work') is not True or not text_ref(auth.get('source_ref')):
                return reject('CREATION_NOT_AUTHORIZED')
            root = (Path(request['workspace_manifest']).resolve().parent / json.loads(Path(request['workspace_manifest']).read_text(encoding='utf-8'))['project_root']).resolve()
            if context.get('project_id') and Path(context['cwd']).resolve() == root:
                tool = 'mcp__codex_app__create_thread'
                args = dict(target=dict(type='project', projectId=context['project_id'], environment=dict(type='local')),
                            prompt='Continue task ' + task + ' in cwd ' + context['cwd'] +
                            '. Read local AGENTS.md and Qiming startup before work; report cwd and project identity first.')
                action = 'create'
            elif context.get('current_thread_id'):
                tool = 'mcp__codex_app__fork_thread'
                args = dict(threadId=context['current_thread_id'], environment=dict(type='same-directory'))
                action = 'fork'
            else:
                return reject('PARENT_THREAD_REQUIRED')
            return dict(status='ok', action=action, verified=False, project_requirement=requirement,
                        tool_request=dict(tool=tool, args=args),
                        next='Read back child cwd/workspace/project identity before reporting success or starting task.')
        if op not in {'verify', 'archive'}:
            return reject('UNKNOWN_OPERATION')
        thread = request['thread']
        error = thread_scope(thread, context, request['workspace_manifest'])
        if error:
            return reject(error)
        if not thread.get('id'):
            return reject('THREAD_ID_REQUIRED')
        error = placement(thread, context)
        if error:
            return reject(error)
        if op == 'verify':
            return dict(status='ok', action='verified', thread_id=thread['id'], verified=True, **identity)
        if (thread['id'] == context.get('current_thread_id') or thread.get('is_coordinator') is not False
                or thread.get('executing') is not False or thread.get('awaiting_approval') is not False
                or thread.get('awaiting_user') is not False):
            return reject('THREAD_BUSY_OR_COORDINATOR')
        if thread.get('status') != 'completed':
            return reject('THREAD_NOT_COMPLETED')
        auth = request.get('authorization', {})
        if auth.get('archive_completed') is not True or not text_ref(auth.get('source_ref')):
            return reject('ARCHIVE_NOT_AUTHORIZED')
        if not (all(isinstance(thread.get(key), list) and thread[key] and
                    all(isinstance(ref, str) and ref.strip() for ref in thread[key])
                    for key in ('outcome_refs', 'verification_refs'))
                and isinstance(thread.get('handoff_ref'), str) and thread['handoff_ref'].strip()):
            return reject('EVIDENCE_INCOMPLETE')
        tree = thread.get('worktree')
        if tree is not None and (not isinstance(tree, dict) or
                (tree.get('has_independent_changes') is not False and not text_ref(tree.get('preservation_ref')))):
            return reject('WORKTREE_NOT_PRESERVED')
        return dict(status='ok', action='archive', verified=False, project_requirement=requirement,
                    tool_request=dict(tool='mcp__codex_app__set_thread_archived',
                                      args=dict(threadId=thread['id'], archived=True)),
                    next='Host checks cited records, executes reversible archive if authorized, then reads back state. Never deletes worktree.')
    except (KeyError, TypeError, ValueError, OSError, AttributeError):
        return reject('INVALID_INPUT')


def main():
    try:
        result = evaluate(json.load(sys.stdin))
    except (ValueError, TypeError):
        result = reject('INVALID_INPUT')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'ok' else 2


if __name__ == '__main__':
    sys.exit(main())
