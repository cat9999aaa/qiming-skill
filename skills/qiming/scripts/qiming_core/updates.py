"""Read-only local version reporting and explicit official release discovery."""
from __future__ import annotations

import json
import http.client
from pathlib import Path
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .codec import load_record
from .validate import _control_path

REPOSITORY = 'cat9999aaa/qiming-skill'
RELEASES_URL = f'https://api.github.com/repos/{REPOSITORY}/releases?per_page=100'
MAX_BYTES = 2_000_000


def version_key(value):
    if not isinstance(value,str):
        raise ValueError('Version must be a semantic version string')
    match=re.fullmatch(r'v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?',value)
    if not match:
        raise ValueError('Unsupported semantic version')
    parts=match.group(4)
    tokens=[]
    if parts:
        for part in parts.split('.'):
            if part.isdigit() and len(part)>1 and part.startswith('0'):
                raise ValueError('Numeric prerelease identifiers cannot have leading zeroes')
            tokens.append((0,int(part)) if part.isdigit() else (1,part))
    return tuple(int(match.group(i)) for i in (1,2,3)) + ((1,()) if parts is None else (0,tuple(tokens)),)


def version_info(manifest_path: Path | None = None):
    package_path=Path(__file__).resolve().parents[2]/'assets/contracts/version.json'
    package,_=load_record(package_path,'json')
    result={'package':package,'installed':None,'package_source_differs':None,'repository':f'https://github.com/{REPOSITORY}'}
    if manifest_path is not None:
        manifest_path=Path(manifest_path).resolve()
        manifest,_=load_record(manifest_path,'json')
        if manifest.get('protocol')!='qiming.workspace/1' or manifest.get('state')!='ready':
            raise ValueError('Version reporting requires a ready Qiming workspace')
        instance_path=_control_path(manifest_path.parent,manifest['instance']['manifest'])
        instance,_=load_record(instance_path,'json')
        if instance.get('protocol')!='qiming.instance/1' or instance.get('instance_id')!=manifest['instance']['id'] or (instance_path.parent/instance.get('workspace_manifest','../workspace.json')).resolve()!=manifest_path:
            raise ValueError('Instance identity differs from the selected workspace')
        result['installed']={'version':instance.get('seed_version'),'commit':instance.get('seed_commit'),
                             'package_sha256':instance.get('seed_package_sha256'),
                             'instance_id':instance['instance_id'],'workspace_id':manifest['workspace_id'],
                             'preserved_resources':instance.get('upgrade_preserved',[])}
        if instance.get('seed_version')==package.get('version') and instance.get('seed_commit') and package.get('commit'):
            result['package_source_differs']=instance['seed_commit']!=package['commit']
    return {'status':'ok','result':result,'diagnostics':[],'changed':[]}


def fetch_releases():
    request=urllib.request.Request(RELEASES_URL,headers={'Accept':'application/vnd.github+json','User-Agent':'qiming-update-check'})
    with urllib.request.urlopen(request,timeout=10) as stream:
        raw=stream.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError('Release response exceeds size limit')
    data=json.loads(raw)
    if not isinstance(data,list):
        raise ValueError('Official release response must be a list')
    return data


def check_updates(manifest_path: Path | None = None, channel: str | None = None):
    local=version_info(manifest_path)['result']
    channel=channel or local['package'].get('release_channel','stable')
    if channel not in {'stable','preview'}:
        raise ValueError('channel must be stable or preview')
    current=local['installed'] if local['installed'] is not None else local['package']
    result={**local,'current_version':current.get('version'),'channel':channel,'latest':None,
            'update_available':None,'comparison':'unknown','checked_at':datetime.now(timezone.utc).isoformat(),
            'source':RELEASES_URL,'coverage':'up to 100 most recent official releases',
            'next_steps':['Get the official package, review upgrade_preview, then apply the exact reviewed upgrade under user authorization.']}
    diagnostics=[]
    try:
        candidates=[]
        for row in fetch_releases():
            if not isinstance(row,dict) or row.get('draft') is not False or not isinstance(row.get('prerelease'),bool):
                continue
            if channel=='stable' and row['prerelease']:
                continue
            try:
                tag=row.get('tag_name');key=version_key(tag)
            except ValueError:
                continue
            # SemVer prereleases remain previews even if a release flag was mistaken.
            if channel=='stable' and key[-1][0]==0:
                continue
            url=f'https://github.com/{REPOSITORY}/releases/tag/{tag}'
            if row.get('html_url')!=url:
                continue
            candidates.append((key,row))
        if not candidates:
            diagnostics.append({'code':'NO_ELIGIBLE_RELEASE','message':'No eligible published release found in this channel.', 'hint':'Try --channel preview to include prereleases, or inspect the official releases page.'})
            return {'status':'ok_with_warnings','result':result,'diagnostics':diagnostics,'changed':[]}
        _,latest=max(candidates,key=lambda pair:pair[0])
        result['latest']={'version':latest['tag_name'].removeprefix('v'),'tag':latest['tag_name'],
                          'release_url':latest['html_url'],'prerelease':latest['prerelease'],
                          'published_at':latest.get('published_at')}
        try:
            current_key=version_key(current.get('version'))
        except ValueError:
            diagnostics.append({'code':'LOCAL_VERSION_UNKNOWN','message':'Installed version is unknown; compare release and source metadata manually.',
                                'hint':'Run version with the authoritative workspace manifest; do not reinitialize the project.'})
        else:
            latest_key=version_key(result['latest']['version'])
            result['update_available']=latest_key>current_key
            result['comparison']='update_available' if latest_key>current_key else 'current' if latest_key==current_key else 'ahead'
            if latest_key<=current_key:
                result['next_steps']=['No newer eligible release found in the checked listing; retain the installed instance and local rules.']
    except (OSError,ValueError,TimeoutError,http.client.HTTPException,urllib.error.HTTPError) as exc:
        # Never echo arbitrary remote error bodies or claim a failed check is current.
        diagnostics.append({'code':'UPDATE_CHECK_UNAVAILABLE','message':f'Unable to determine official updates ({type(exc).__name__}).',
                            'hint':'Check connectivity/rate limits and retry later, or inspect the official releases page.'})
    return {'status':'ok_with_warnings' if diagnostics else 'ok','result':result,'diagnostics':diagnostics,'changed':[]}
