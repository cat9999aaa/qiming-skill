import json
import shutil
from pathlib import Path
from qiming_core.initialize import initialize
from qiming_core.host_binding import bind
from qiming_core.startup import ensure_startup
from qiming_core.search import search

def test_binding_falls_back_to_copy(tmp_path,monkeypatch):
    assert initialize(tmp_path)['status']=='ok'
    def fail(*a,**kw): raise OSError('No symlink privilege')
    monkeypatch.setattr(Path,'symlink_to',fail)
    result=bind(tmp_path/'.qiming/workspace.json','claude')
    assert result['status']=='ok'
    assert result['result']['method']=='copy'
    assert result['result']['status']=='bound-copy'

def test_soft_budget_warning_and_hard_limit(tmp_path):
    assert initialize(tmp_path)['status']=='ok'
    manifest=tmp_path/'.qiming/workspace.json'
    source=manifest.parent/'startup.md'
    source.write_text('a'*3001)
    result=ensure_startup(manifest)
    assert result['status']=='ok_with_warnings',result
    assert result['diagnostics'][0]['code']=='STARTUP_BUDGET'
    source.write_text('a'*12001)
    assert ensure_startup(manifest)['status']=='conflict'

def test_overdue_knowledge_marked_for_review(tmp_path):
    assert initialize(tmp_path)['status']=='ok'
    manifest=tmp_path/'.qiming/workspace.json'
    (manifest.parent/'knowledge/k.json').write_text(json.dumps({'id':'k','name':'Old claim','type':'knowledge','review_after':'2000-01-01'}))
    result=search(manifest,{'query':'Old claim'})
    assert result['result']['items'][0]['review_status']=='due'
