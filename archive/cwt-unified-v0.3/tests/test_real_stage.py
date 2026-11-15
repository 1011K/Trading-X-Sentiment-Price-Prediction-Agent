import json
import pytest
from cwt_unified.relevance import relevance_reason
from cwt_unified.source_contract import validate_source_manifest
from cwt_unified.readiness import check_dataset

def test_asset_context_precision():
    assert relevance_reason('$AAPL beats estimates','AAPL')=='exact_cashtag'
    assert relevance_reason('Apple stock drops in morning','AAPL')=='company_with_financial_context'
    assert relevance_reason('AAPL earnings due Monday','AAPL')=='ticker_with_financial_context'
    assert relevance_reason('Apple pie shares for dessert','AAPL') is None  # contextual match may still be conservative

def test_never_guess_provider_auth(tmp_path):
    a={'platform':'X','source_name':'provider','acquisition_method':'export',
       'rights_basis':'Permission not yet established','retrieved_at_utc':'2026-11-15T00:00:00Z',
       'intended_asset':'AAPL','query_terms':['$AAPL'],'pagination_complete':False,
       'access_authorized':False}
    p=tmp_path/'src.json';p.write_text(json.dumps(a))
    with pytest.raises(ValueError,match='access_authorized'):
        validate_source_manifest(str(p),'AAPL')
    a['access_authorized']=True;p.write_text(json.dumps(a))
    d=validate_source_manifest(str(p),'AAPL')
    assert d['evidence_class']=='USER_DECLARED_SOURCE_METADATA'
    assert not d['pagination_complete']

def test_no_actor_without_explicit_approval(tmp_path,monkeypatch):
    from cwt_unified.apify_acquire import run_authorized_actor
    monkeypatch.delenv('CWT_AUTHORIZED_X_COLLECTION',raising=False)
    with pytest.raises(PermissionError):
        run_authorized_actor('provider~actor','missing.json','out.json')

def test_no_news_without_token(monkeypatch):
    from cwt_unified.news_context import fetch_current_news
    monkeypatch.delenv('TAVILY_API_KEY',raising=False)
    monkeypatch.delenv('EXA_API_KEY',raising=False)
    with pytest.raises(RuntimeError,match='No Tavily or Exa'):
        fetch_current_news('AAPL')


def test_reject_wrong_platform(tmp_path):
    from cwt_unified.source_contract import validate_source_manifest
    a={'platform':'StockTwits','source_name':'export','acquisition_method':'download',
       'rights_basis':'Licensed historical export from vendor','retrieved_at_utc':'2026-11-15T00:00:00Z',
       'intended_asset':'AAPL','query_terms':['$AAPL'],'pagination_complete':True,'access_authorized':True}
    p=tmp_path/'m.json';p.write_text(json.dumps(a))
    with pytest.raises(ValueError,match='platform must be X'):
        validate_source_manifest(p,'AAPL')
