"""Acquisition provenance. User declarations never amount to independent verification."""
from pathlib import Path
import json, hashlib
import pandas as pd

REQUIRED = ('source_name','acquisition_method','rights_basis','retrieved_at_utc',
            'query_terms','pagination_complete','intended_asset','platform')

def validate_source_manifest(path: str, ticker: str, *, require_permission=True) -> dict:
    obj = json.loads(Path(path).read_text(encoding='utf8'))
    missing=[k for k in REQUIRED if k not in obj]
    if missing: raise ValueError('Source manifest missing: '+', '.join(missing))
    if str(obj.get('platform','')).strip().upper()!='X':
        raise ValueError('Source manifest platform must be X: do not relabel StockTwits or news posts as X data')
    if str(obj['intended_asset']).upper()!=ticker.upper():
        raise ValueError('Source manifest symbol does not match requested ticker')
    if not obj['rights_basis'] or len(str(obj['rights_basis']).strip())<12:
        raise ValueError('Describe the permitted acquisition basis; do not assume a scraper listing grants rights')
    if require_permission and obj.get('access_authorized') is not True:
        raise ValueError('Explicit access_authorized=true is required; verify collection permission first')
    if not obj['query_terms'] or not isinstance(obj['query_terms'],list):
        raise ValueError('Source must record actual search queries')
    if not isinstance(obj['pagination_complete'],bool):
        raise ValueError('pagination_complete must be a boolean, not a guess/string')
    when=pd.Timestamp(obj['retrieved_at_utc'])
    if when.tz is None:
        raise ValueError('retrieved_at_utc must specify timezone')
    # user-provided provenance, not externally corroborated
    return {**obj, 'evidence_class':'USER_DECLARED_SOURCE_METADATA',
            'source_manifest_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
