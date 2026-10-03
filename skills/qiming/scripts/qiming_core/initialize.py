"""Project-local onboarding; existing manifests and custom profiles remain authoritative."""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path

from .bootstrap import bootstrap
from .codec import load_record
from .materialize import materialize, _root_alias
from .plan import plan_changes, resolve_target
from .transactions import apply_plan
from .host_binding import bind, ensure_project_entrypoints
from .validate import validate
from .profile import load_profile


def default_profile(preset='general'):
    if preset not in {'general', 'dev', 'writing'}:
        raise ValueError('preset must be general, dev or writing')
    names = ['work', 'knowledge', 'members'] + (['incidents'] if preset == 'dev' else [])
    fields = ['id','type','name','summary','status','next','scope','lifecycle','review_after']
    return {'protocol':'qiming.profile/1',
            'collections': {n: {'purpose':n,'root':'project','directory':f'.qiming/{n}','pattern':'**/*.json','codec':'json','mapping':'record'} for n in names},
            'mappings': {'record': {f:{'source':f'/{f}','writable':True} for f in fields}},
            'record_rules':{}, 'scope_rules':{'exclude':['.git','node_modules','.venv','AGENTS.md','CLAUDE.md','GEMINI.md','.qiming/qiming-user','.qiming/operations']},
            'retrieval':{'max_results':50}, 'extensions':{'preset':preset}}


def write_payloads(manifest_path, payloads, intent):
    """Route generated files through fingerprinted plans; never overwrite unseen bytes."""
    manifest, _ = load_record(manifest_path,'json')
    binding = _root_alias(manifest_path,manifest)
    if binding is None:
        raise ValueError('No writable root contains the control directory')
    alias, root = binding
    pending=[]
    for path, data, previous in payloads:
        if data == previous:
            continue
        ref={'kind':'file','root':alias,'path':path.relative_to(root).as_posix()}
        resolve_target(manifest_path,ref)
        pending.append((ref,data,previous))
    if not pending:
        return {'status':'ok','result':{},'changed':[],'diagnostics':[]}
    stage=manifest_path.parent/'.staging'/('generated-'+str(uuid.uuid4()))
    stage.mkdir(parents=True)
    changes=[]
    for i,(ref,data,previous) in enumerate(pending):
        path=stage/str(i)
        path.write_bytes(data)
        changes.append({'action':'create' if previous is None else 'replace','target':ref,'expected_sha256':None if previous is None else hashlib.sha256(previous).hexdigest(),'content_ref':str(path.relative_to(manifest_path.parent)),'desired_sha256':hashlib.sha256(data).hexdigest()})
    planned=plan_changes(manifest_path,changes,intent,hashlib.sha256((manifest_path.parent/manifest['profile']).read_bytes()).hexdigest())
    result = apply_plan(manifest_path,planned['result']) if planned['status']=='ok' else planned
    from .staging import finish_stage
    return finish_stage(stage, result)


def initialize(root: Path, preset='general', name=None, goal=None, hosts='auto', dry_run=False, entry='all'):
    if entry not in {'all','agents','none'}:
        raise ValueError('entry must be all, agents or none')
    if sys.version_info < (3,11):
        raise ValueError('Python 3.11+ required; install Python then run again')
    from .secrets import validate_account_ref
    issues=validate_account_ref({'name':name,'goal':goal})
    if issues: return {'status':'conflict','result':None,'diagnostics':issues,'changed':[]}
    if goal is not None and (not isinstance(goal,str) or not goal.strip() or len(goal)>2000):
        raise ValueError('goal must be a short nonempty sentence (max 2000 characters)')
    root=root.resolve()
    if not root.is_dir():
        raise ValueError('Choose an existing project directory')
    control=root/'.qiming'
    if control.is_symlink():
        raise ValueError('Control directory must not be a symlink')
    path=control/'workspace.json'
    profile=default_profile(preset)
    from .host_binding import selected_hosts
    selected=selected_hosts(root,hosts)
    exists=path.exists()
    if exists:
        manifest,_=load_record(path,'json')
        from .discovery import project_root
        if project_root(path,manifest)!=root or manifest.get('state') not in {'ready','initializing'}:
            raise ValueError('Existing workspace needs repair; inspect before initialization')
        profile=load_profile(path)
    elif control.exists() and any(control.iterdir()):
        journal,_=load_record(control/'init.json','json')
        original=journal.get('initial_manifest')
        original_profile=journal.get('initial_profile')
        if journal.get('protocol')!='qiming.initialization/1' or not isinstance(original,dict) or not isinstance(original_profile,dict):
            raise ValueError('Incomplete unrecognized initialization; inspect before retrying')
        if dry_run:
            policy=original.get('extensions',{}).get('entry_policy','all')
            if policy not in {'all','agents','none'}:
                raise ValueError('Saved entry_policy must be all, agents or none')
            entries=['AGENTS.md','CLAUDE.md','GEMINI.md'] if policy=='all' else ['AGENTS.md'] if policy=='agents' else []
            return {'status':'ok','result':{'dry_run':True,'resume_initialization':journal['initialization_id'],'entry_policy':policy,'root_entry_files':entries,'root_file_actions':[{'path':p,'action':'inspect-and-preserve' if (root/p).exists() else 'create'} for p in entries],'collections':original_profile['collections']},'changed':[]}
        resumed=bootstrap(root,control,original,original_profile,journal['initialization_id'])
        if resumed['status']!='ok': return resumed
        exists=True
        manifest,_=load_record(path,'json')
        profile=load_profile(path)
    entry = manifest.get('extensions',{}).get('entry_policy','all') if exists else entry
    root_entries = ['AGENTS.md','CLAUDE.md','GEMINI.md'] if entry=='all' else ['AGENTS.md'] if entry=='agents' else []
    if dry_run:
        return {'status':'ok','result':{'entry_policy':entry,'root_entry_files':root_entries,'root_file_actions':[{'path':p,'action':'inspect-and-preserve' if (root/p).exists() else 'create'} for p in root_entries],'dry_run':True,'already_initialized':exists,'root':str(root),'collections':profile['collections'],'hosts':selected,'next_steps':['Run init without --dry-run to apply this setup']},'changed':[]}
    changed=[]
    setup=manifest.get('extensions',{}).get('onboarding',{}) if exists else {}
    ready=exists and manifest['state']=='ready' and (not setup or setup.get('complete') is True)
    if setup and not ready:
        goal=setup.get('goal')
        name=setup.get('name')
    if not exists:
        manifest={'protocol':'qiming.workspace/1','workspace_id':f'ws_{uuid.uuid4()}','state':'initializing','workspace_entry':'START.md','conventions':'conventions.md','profile':'profile.json','init_journal':'init.json','roots':{'project':{'location':'..','access':'read-write'}},'extensions':{'entry_policy':entry,'onboarding':{'goal':goal,'name':name,'complete':False}}}
        init_id=f'init_{uuid.uuid4()}'
        output=bootstrap(root,control,manifest,profile,init_id)
        if output['status']!='ok': return output
        changed+=output['changed']
    else:
        init_id=load_record(control/manifest.get('init_journal','init.json'),'json')[0]['initialization_id'] if not ready else ''
    output=materialize(path,[],{},init_id)
    if output['status']!='ok': return output
    changed+=output['changed']
    payloads=[]
    if not ready:
        for config in profile['collections'].values():
            from .scan import _root, _relative_path
            directory=_relative_path(_root(path,config['root']),config.get('directory','.'))
            # Do not invent user draft directories or initialize external roots.
            if directory.is_relative_to(control): directory.mkdir(parents=True,exist_ok=True)
        if goal:
            work=control/'work/w-0001.json'
            if not work.exists():
                record={'id':'w-0001','type':'work','name':goal,'summary':goal,'status':'open','scope':'workspace','lifecycle':'maintained','next':'继续当前目标，先核验已有材料。','acceptance':[],'events':[]}
                payloads.append((work,(json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode(),None))
                start=control/manifest.get('workspace_entry','START.md')
                raw=start.read_bytes()
                payloads.append((start,raw+f'\n## 当前任务\n\n[当前目标](work/w-0001.json)：{goal}\n\n仅保留 3–5 个进行中的任务；完成记录保留在集合中。\n\n解释器：`{sys.executable}`。\n'.encode(),raw))
    ignore=control/'.gitignore'
    if not ignore.exists():
        payloads.append((ignore,b'index.sqlite*\noperations/\n.staging/\n.materialize/\n.host-entry-staging/\n__pycache__/\n',None))
    output=write_payloads(path,payloads,'initialize-project')
    if output['status']!='ok': return output
    changed+=output['changed']
    output=ensure_project_entrypoints(path)
    if output['status'] not in {'ok','ok_with_warnings'}: return output
    changed+=output['changed']
    bound=[]
    for host in selected:
        output=bind(path,host)
        if output['status']!='ok': return {**output,'changed':changed+output.get('changed',[])}
        changed+=output['changed']
        bound.append(output['result'])
    current,raw=load_record(path,'json')
    setup=current.get('extensions',{}).get('onboarding')
    if setup is not None and not setup.get('complete'):
        setup['complete']=True
        output=write_payloads(path,[(path,(json.dumps(current,ensure_ascii=False,indent=2)+'\n').encode(),raw)],'complete-onboarding')
        if output['status']!='ok': return output
        changed+=output['changed']
    check=validate(path,[],False)
    if check['status'] not in {'ok','ok_with_warnings'}: return check
    manifest,_=load_record(path,'json')
    return {'status':check['status'],'result':{'workspace_id':manifest['workspace_id'],'instance_id':manifest['instance']['id'],'already_initialized':ready,'created':not exists,'entry_policy':entry,'root_entry_files':root_entries,'bound_hosts':bound,'warnings':(['Writing preset leaves your manuscripts untouched; map existing drafts explicitly as read-only.'] if preset=='writing' else []),'next_steps':['Read .qiming/START.md. Daily work uses qiming-user.','Keep project-local seed for future upgrades or remove it yourself after backing up; never remove the user instance.']},'changed':changed,'diagnostics':check['diagnostics']}
