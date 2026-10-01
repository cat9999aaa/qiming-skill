import json
from pathlib import Path
from qiming_core.initialize import initialize
from qiming_core.index import reindex
from qiming_core.search import search
from qiming_core.quick_log import log_event

def setup(tmp_path):
    assert initialize(tmp_path,goal='第一章',hosts='codex')['status']=='ok'
    return tmp_path/'.qiming/workspace.json'

def test_nested_records_and_exclusions(tmp_path):
    manifest=setup(tmp_path)
    work=tmp_path/'.qiming/work'
    (work/'archive').mkdir()
    (work/'w-0001.json').rename(work/'archive/w-0001.json')
    event={'id':'evt-1','kind':'action','summary':'done','observed_at':'2026-10-01T00:00:00Z'}
    output=log_event(manifest,{'kind':'file','root':'project','path':'.qiming/work/archive/w-0001.json'},event,'test')
    assert output['status']=='ok',output
    profile_path=manifest.parent/'profile.json'
    profile=json.loads(profile_path.read_text())
    profile['collections']['work']['exclude']=['archive/**']
    profile_path.write_text(json.dumps(profile))
    assert search(manifest,{'query':'第一章'})['result']['items']==[]

def test_log_does_not_stage_secret(tmp_path):
    manifest=setup(tmp_path)
    event={'id':'evt-1','kind':'action','summary':'key sk-'+('a1B2'*12),'observed_at':'2026-10-01T00:00:00Z'}
    output=log_event(manifest,{'kind':'file','root':'project','path':'.qiming/work/w-0001.json'},event,'test')
    assert output['status']=='conflict',output
    assert output['diagnostics'][0]['code']=='SECRET_VALUE_FORBIDDEN'
    assert not any(event['summary'].encode() in p.read_bytes() for p in manifest.parent.rglob('*') if p.is_file())

def test_safe_tracking_url_and_secret_values():
    from qiming_core.secrets import validate_account_ref
    assert validate_account_ref({'url':'https://example.org/?utm_source=x'})==[]
    for record in [{'note':'ghp_'+('abCD12'*7)}, {'url':'https://example.org/?token=abc'}, {'note':'-----BEGIN PRIVATE KEY-----\nabc'}]:
        assert validate_account_ref(record)

def test_default_scan_finds_managed_records(tmp_path):
    from qiming_core.scan import scan
    manifest=setup(tmp_path)
    result=scan(manifest,[],[],{})
    assert result['coverage']['visited']>=1
