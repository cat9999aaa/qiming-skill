import hashlib,json,subprocess,sys
from pathlib import Path
import pytest
from qiming_core.initialize import initialize
from qiming_core.updates import version_info,check_updates,version_key
import qiming_core.updates as updates

SCRIPT=Path(__file__).resolve().parents[2]/'skills/qiming/scripts/qiming.py'

def release(version,preview=False):
    return {'tag_name':'v'+version,'draft':False,'prerelease':preview,'html_url':'https://github.com/cat9999aaa/qiming-skill/releases/tag/v'+version,'published_at':'2026-10-24T00:00:00Z','target_commitish':'main'}

def instance(tmp_path,version='0.2.2'):
    assert initialize(tmp_path,goal='Retain my work')['status']=='ok'
    path=tmp_path/'.qiming/qiming-user/instance.json';row=json.loads(path.read_text());row['seed_version']=version;row['seed_commit']='a'*40;path.write_text(json.dumps(row))
    return tmp_path/'.qiming/workspace.json'

def test_offline_version_uses_project_and_does_not_write(tmp_path,monkeypatch):
    m=instance(tmp_path)
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob('*') if p.is_file()}
    monkeypatch.setattr(updates,'fetch_releases',lambda:pytest.fail('offline version contacted network'))
    r=version_info(m)
    assert r['status']=='ok'
    assert r['result']['installed']['version']=='0.2.2'
    assert r['result']['installed']['commit']=='a'*40
    assert r['result']['package']['version']!= '0.2.2'
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob('*') if p.is_file()}

@pytest.mark.parametrize('older,newer',[('0.9.0','0.10.0'),('1.0.0-rc.2','1.0.0-rc.10'),('1.0.0-rc.10','1.0.0'),('1.0.0-alpha','1.0.0-beta')])
def test_semantic_version_order(older,newer):
    assert version_key(older)<version_key(newer)
    assert version_key('v1.2.3+build.1')==version_key('1.2.3+build.2')

@pytest.mark.parametrize('bad',['legacy','1.2','01.2.3','1.2.3-01','v1.2.3<script>','1٢.0.0','1.2٢.0'])
def test_invalid_versions_not_compared(bad):
    with pytest.raises(ValueError):version_key(bad)

def test_channel_and_draft_filtering(tmp_path,monkeypatch):
    m=instance(tmp_path)
    draft={**release('9.0.0'),'draft':True}
    monkeypatch.setattr(updates,'fetch_releases',lambda:[draft,release('0.3.0',True),release('0.2.2')])
    stable=check_updates(m,'stable');preview=check_updates(m,'preview')
    assert stable['result']['update_available'] is False
    assert stable['result']['latest']['version']=='0.2.2'
    assert preview['result']['update_available'] is True
    assert preview['result']['latest']['version']=='0.3.0'
    assert preview['changed']==[]

def test_empty_or_unknown_release_does_not_claim_current(tmp_path,monkeypatch):
    m=instance(tmp_path)
    for payload in ([],[release('invalid')]):
        monkeypatch.setattr(updates,'fetch_releases',lambda:payload)
        r=check_updates(m,'stable')
        assert r['result']['update_available'] is None
        assert r['result']['comparison']=='unknown'

def test_network_failure_reports_unknown(tmp_path,monkeypatch):
    from urllib.error import HTTPError
    m=instance(tmp_path)
    def fail():raise HTTPError('https://api.github.com',403,'rate limit',{},None)
    monkeypatch.setattr(updates,'fetch_releases',fail)
    r=check_updates(m,'preview')
    assert r['status']=='ok_with_warnings'
    assert r['result']['update_available'] is None
    assert r['diagnostics'][0]['code']=='UPDATE_CHECK_UNAVAILABLE'

def test_unknown_local_version_preserves_uncertainty(tmp_path,monkeypatch):
    m=instance(tmp_path,'legacy')
    monkeypatch.setattr(updates,'fetch_releases',lambda:[release('0.3.0',True)])
    r=check_updates(m,'preview')
    assert r['result']['update_available'] is None
    assert r['result']['comparison']=='unknown'

def test_cli_and_json_offline_version(tmp_path):
    m=instance(tmp_path)
    cli=subprocess.run([sys.executable,str(SCRIPT),'version','--workspace-manifest',str(m)],text=True,capture_output=True)
    assert cli.returncode==0,cli.stderr
    assert json.loads(cli.stdout)['result']['installed']['version']=='0.2.2'
    req={'protocol':'qiming.tool/1','request_id':'version-test','op':'version','workspace_manifest':str(m),'args':{}}
    api=subprocess.run([sys.executable,str(SCRIPT),'--stdin'],input=json.dumps(req),text=True,capture_output=True)
    assert json.loads(api.stdout)['result']['installed']['version']=='0.2.2'

def test_fetch_is_bounded_official_and_contains_no_local_data(monkeypatch):
    class Stream:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,size):
            assert size<=2_000_001
            return json.dumps([release('0.3.0',True)]).encode()
    def fake(req,timeout):
        assert req.full_url=='https://api.github.com/repos/cat9999aaa/qiming-skill/releases?per_page=100'
        assert req.data is None and timeout<=15
        assert 'Authorization' not in req.headers
        return Stream()
    monkeypatch.setattr(updates.urllib.request,'urlopen',fake)
    assert updates.fetch_releases()[0]['tag_name']=='v0.3.0'

def test_untrusted_release_urls_rejected(tmp_path,monkeypatch):
    m=instance(tmp_path)
    monkeypatch.setattr(updates,'fetch_releases',lambda:[{**release('0.3.0',True),'html_url':'https://untrusted.example/run'}])
    r=check_updates(m,'preview')
    assert r['result']['update_available'] is None

def test_same_version_different_package_source_is_visible(tmp_path,monkeypatch):
    m=instance(tmp_path,'0.3.0')
    real=updates.load_record
    def source(path,codec):
        data,raw=real(path,codec)
        if path.name=='version.json':data={**data,'commit':'b'*40}
        return data,raw
    monkeypatch.setattr(updates,'load_record',source)
    r=version_info(m)
    assert r['result']['package_source_differs'] is True

def test_truncated_http_response_is_unknown(tmp_path,monkeypatch):
    import http.client
    m=instance(tmp_path)
    def fail():raise http.client.IncompleteRead(b'partial')
    monkeypatch.setattr(updates,'fetch_releases',fail)
    r=check_updates(m,'preview')
    assert r['result']['update_available'] is None
    assert r['diagnostics'][0]['code']=='UPDATE_CHECK_UNAVAILABLE'

@pytest.mark.parametrize('raw',[b'not json',b'{}',b'x'*2_000_001])
def test_bad_or_oversized_response_rejected(monkeypatch,raw):
    class Stream:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,size):return raw
    monkeypatch.setattr(updates.urllib.request,'urlopen',lambda *a,**k:Stream())
    with pytest.raises(ValueError):updates.fetch_releases()
