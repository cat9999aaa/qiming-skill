"""Three-way instance upgrade. Local policies and record layouts are never migrated."""
from __future__ import annotations
import hashlib
import json
import uuid
from pathlib import Path
from .codec import load_record
from .materialize import _default_resources, _entry, _json, _sha, _root_alias
from .validate import _control_path, validate
from .plan import plan_changes
from .transactions import apply_plan
from .host_binding import ensure_project_entrypoints


def seed_metadata(seed):
    version=seed/'assets/contracts/version.json'
    metadata = load_record(version,'json')[0] if version.is_file() else {'version':'legacy','commit':None}
    digest = hashlib.sha256()
    paths = {seed/'SKILL.md'} | {seed/row['source'] for row in _default_resources(seed)}
    for path in sorted(paths):
        if path.is_file():
            digest.update(path.relative_to(seed).as_posix().encode()+b'\0'+hashlib.sha256(path.read_bytes()).digest())
    return {**metadata, 'package_sha256': digest.hexdigest()}


def _new_resources(seed, name, workspace_id):
    values={'SKILL.md':(_entry(name,workspace_id),'generated-for-workspace'), 'agents/openai.yaml':(b'policy:\n  allow_implicit_invocation: true\n','generated-for-workspace')}
    for resource in _default_resources(seed):
        source=_control_path(seed,resource['source'])
        values[resource['path']]=(source.read_bytes(),{'source':resource['source'],'license':resource['license']})
    return values


def _resource_map(resources):
    """Older Windows instances serialized native separators in resource keys."""
    result = {}
    for row in resources:
        name = row['path'].replace('\\', '/')
        if name in result:
            raise ValueError('Duplicate instance resource after path normalization')
        result[name] = {**row, 'path': name}
    return result


def upgrade_preview(manifest_path: Path, seed_dir: Path):
    manifest_path=manifest_path.resolve(); seed_dir=seed_dir.resolve()
    manifest,_=load_record(manifest_path,'json')
    if manifest.get('state')!='ready': raise ValueError('Upgrade requires a ready workspace')
    instance_path=_control_path(manifest_path.parent,manifest['instance']['manifest'])
    instance,raw=load_record(instance_path,'json')
    if not (seed_dir/'scripts/qiming.py').is_file() or not (seed_dir/'SKILL.md').is_file():
        raise ValueError('seed_dir must point to a complete Qiming package')
    current=_resource_map(instance['resources'])
    target=instance_path.parent
    new=_new_resources(seed_dir,target.name,manifest['workspace_id'])
    rows=[]
    for name in sorted(set(current)|set(new)):
        path=_control_path(target,name)
        actual=_sha(path.read_bytes()) if path.is_file() else None
        base=current.get(name,{}).get('seed_sha256',current.get(name,{}).get('sha256'))
        incoming=_sha(new[name][0]) if name in new else None
        if actual is None and incoming is None: state='removed'
        elif actual==incoming: state='unchanged'
        elif name not in current: state='added' if actual is None else 'conflict'
        elif actual!=base: state='local_modified' if incoming==base else 'conflict'
        else: state='removed' if incoming is None else 'upgrade'
        rows.append({'path':name,'state':state,'base_sha256':base,'current_sha256':actual,'incoming_sha256':incoming})
    from .discovery import project_root
    from .host_binding import _HOST_DIRS
    bindings=[]
    for host,directory in _HOST_DIRS.items():
        copy=project_root(manifest_path)/directory/'skills'/target.name
        if copy.is_symlink() or not copy.exists(): continue
        hashes={}
        for name in set(current)|set(new)|{'instance.json'}:
            file=copy/name
            hashes[name]=_sha(file.read_bytes()) if file.is_file() and not file.is_symlink() else None
        bindings.append({'host':host,'path':str(copy),'hashes':hashes})
    result={'bindings':bindings,'protocol':'qiming.upgrade/1' ,'workspace_id':manifest['workspace_id'],'instance_id':instance['instance_id'],'instance_sha256':_sha(raw),'seed_dir':str(seed_dir),'seed':seed_metadata(seed_dir),'resources':rows}
    result['plan_id']='upgrade_'+_sha(_json(result))
    return {'status':'ok','result':result,'changed':[],'diagnostics':[]}


def upgrade(manifest_path: Path, preview: dict, plan_id: str):
    fresh=upgrade_preview(manifest_path,Path(preview['seed_dir']))['result']
    if fresh!=preview or plan_id!=fresh['plan_id']:
        return {'status':'conflict','result':None,'diagnostics':[{'code':'STALE_PREVIEW','message':'Instance or seed changed after preview','hint':'Run upgrade_preview again and review the differences.'}],'changed':[]}
    manifest,_=load_record(manifest_path,'json')
    instance_path=_control_path(manifest_path.parent,manifest['instance']['manifest'])
    instance,raw=load_record(instance_path,'json')
    target=instance_path.parent
    new=_new_resources(Path(fresh['seed_dir']),target.name,manifest['workspace_id'])
    old=_resource_map(instance['resources'])
    alias,root=_root_alias(manifest_path,manifest)
    resources=[];payloads=[];preserved=[]
    for row in fresh['resources']:
        name=row['path'];state=row['state'];path=_control_path(target,name)
        if state in {'local_modified','conflict'}:
            preserved.append({'path':name,'state':state})
            if name in old:
                record={**old[name],'seed_sha256':row['base_sha256'],'sha256':row['current_sha256'],'local_modified':True}
                resources.append(record)
            # Missing local files remain a validation issue; never silently recreate.
            continue
        if state=='removed':
            if row['current_sha256'] is not None: payloads.append((path,None,row['current_sha256']))
            continue
        data,origin=new[name]
        resources.append({'path':name,'purpose':old.get(name,{}).get('purpose','runtime'),'required':old.get(name,{}).get('required',True),'origin':origin,'sha256':row['incoming_sha256'],'seed_sha256':row['incoming_sha256']})
        if state in {'added','upgrade'}: payloads.append((path,data,row['current_sha256']))
    updated={**instance,'resources':resources,'seed_version':fresh['seed'].get('version'),'seed_commit':fresh['seed'].get('commit'),'seed_commit_kind':fresh['seed'].get('commit_kind'),'seed_package_sha256':fresh['seed']['package_sha256'],'upgrade_preserved':preserved}
    if _json(updated)!=raw: payloads.append((instance_path,_json(updated),_sha(raw)))
    binding_conflicts=[]
    for binding in fresh['bindings']:
        copy=Path(binding['path']);hashes=binding['hashes']
        if hashes.get('instance.json')!=_sha(raw) or any(hashes.get(name)!=record.get('sha256') for name,record in old.items()) or any(name not in old and hashes.get(name) not in {None,_sha(value[0])} for name,value in new.items()):
            binding_conflicts.append(binding['host']);continue
        for record in resources:
            name=record['path']
            data=(new[name][0] if name in new and _sha(new[name][0])==record['sha256'] else (target/name).read_bytes())
            if _sha(data)!=hashes.get(name): payloads.append((copy/name,data,hashes.get(name)))
        for name in set(old)-{r['path'] for r in resources}:
            if hashes.get(name) is not None: payloads.append((copy/name,None,hashes[name]))
        if _sha(_json(updated))!=hashes['instance.json']:
            payloads.append((copy/'instance.json',_json(updated),hashes['instance.json']))
    if not payloads: return {'status':'ok','result':{'preserved':preserved},'changed':[]}
    stage=manifest_path.parent/'.staging'/('upgrade-'+str(uuid.uuid4()));stage.mkdir(parents=True)
    changes=[]
    for i,(path,data,expected) in enumerate(payloads):
        content=stage/str(i)
        if data is not None: content.write_bytes(data)
        changes.append({'action':'remove' if data is None else 'create' if expected is None else 'replace','target':{'kind':'file','root':alias,'path':path.relative_to(root).as_posix()},'expected_sha256':expected,'content_ref':str(content.relative_to(manifest_path.parent)) if data is not None else None,'desired_sha256':_sha(data) if data is not None else None})
    planned=plan_changes(manifest_path,changes,plan_id,_sha((manifest_path.parent/manifest['profile']).read_bytes()))
    if planned['status']!='ok': return planned
    # Read-only preconditions prevent committing metadata for concurrently edited resources.
    changed_paths={str(path) for path,_,_ in payloads}
    guards=[]
    for row in fresh['resources']:
        path=target/row['path']
        if str(path) not in changed_paths:
            guards.append({'target':{'kind':'file','root':alias,'path':path.relative_to(root).as_posix()},'expected_sha256':row['current_sha256']})
    for binding in fresh['bindings']:
        for name,sha in binding['hashes'].items():
            path=Path(binding['path'])/name
            if str(path) not in changed_paths:
                guards.append({'target':{'kind':'file','root':alias,'path':path.relative_to(root).as_posix()},'expected_sha256':sha})
    planned['result']['guards']=guards
    applied=apply_plan(manifest_path,planned['result'])
    if applied['status']!='ok': return applied
    from .staging import finish_stage
    applied=finish_stage(stage,applied)
    context=ensure_project_entrypoints(manifest_path)
    check=validate(manifest_path,[],False)
    status='ok_with_warnings' if preserved or binding_conflicts else 'ok'
    if context['status'] not in {'ok','ok_with_warnings'} or check['status'] not in {'ok','ok_with_warnings'}: status='partial'
    return {**applied,'status':status,'result':{**applied.get('result',{}),'preserved':preserved,'binding_conflicts':binding_conflicts,'validation':check,'context':context,'seed_version':updated['seed_version']},'changed':applied['changed']+context.get('changed',[])}
