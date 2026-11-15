"""Single production command: no synthetic fallback, no brokerage connector."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
from .source_contract import validate_source_manifest
from .readiness import check_dataset
from .data import load_prices, sha256
from .ingest import apify_dataset_items,from_export,normalize_posts,normalize_prices,write_dataset
from .score import score_texts
from .cli import run
from .config import Config

def main(argv=None):
    ap=argparse.ArgumentParser(description='Run real X+price forecasting, paper research ONLY')
    ap.add_argument('--ticker',default='AAPL')
    ap.add_argument('--prices-csv',required=True)
    source=ap.add_mutually_exclusive_group(required=True)
    source.add_argument('--x-export',help='Authorized JSON, JSONL or CSV export')
    source.add_argument('--apify-dataset-id',help='Existing permissioned Apify dataset identifier')
    ap.add_argument('--source-manifest',required=True,help='Acquisition provenance and permissions JSON')
    ap.add_argument('--cutoff-utc',required=True,help='UTC closing timestamp for observed last bar')
    ap.add_argument('--sentiment',choices=['lexical','vader'],default='lexical')
    ap.add_argument('--min-posts',type=int,default=50)
    ap.add_argument('--min-post-sessions',type=int,default=20)
    ap.add_argument('--max-items',type=int,default=100000)
    ap.add_argument('--out',default='real_run')
    args=ap.parse_args(argv)
    ticker=args.ticker.strip().upper()
    if args.min_posts<50 or args.min_post_sessions<20:
        raise ValueError('Do not silently lower established minimum data-quality thresholds')
    meta=validate_source_manifest(args.source_manifest,ticker)
    # Refuse to invent completeness. The manifest represents a user attestation only.
    raw=from_export(args.x_export) if args.x_export else apify_dataset_items(args.apify_dataset_id,args.max_items)
    posts,p_audit=normalize_posts(raw,ticker,args.cutoff_utc)
    prices=normalize_prices(args.prices_csv,args.cutoff_utc)
    if not len(prices):raise ValueError('No market price bars; no fallback')
    # Guard: cutoff should equal the last observed market close; no Sunday pseudo-close.
    from .data import load_prices as verified_prices
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        price_tmp=Path(td)/'price.csv'; prices.to_csv(price_tmp,index=False)
        verify=verified_prices(price_tmp)
    expected_close=pd.Timestamp(verify.market_close_utc.iloc[-1]); request_close=pd.Timestamp(args.cutoff_utc)
    if request_close.tz is None or abs((expected_close-request_close).total_seconds())>60:
        raise ValueError(f'cutoff-utc must match last actual exchange close {expected_close.isoformat()}')
    posts['sentiment']=score_texts(posts.text.astype(str).tolist(),args.sentiment)
    d=Path(args.out);d.mkdir(parents=True,exist_ok=True)
    inputdir=d/'input'
    audit=write_dataset(posts,prices,inputdir,ticker,args.cutoff_utc,
          source_name=str(meta['source_name']),audit=p_audit,
          actor_id=meta.get('actor_id'),dataset_id=args.apify_dataset_id or meta.get('dataset_id'))
    check=check_dataset(inputdir/'posts.csv',inputdir/'prices.csv',ticker,meta,
             min_posts=args.min_posts,min_post_sessions=args.min_post_sessions)
    (d/'readiness.json').write_text(json.dumps(check.to_json(),indent=2),encoding='utf8')
    (d/'source_manifest_checked.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
    if check.state.startswith('BLOCKED'):
        raise RuntimeError(f'Insufficient or incomplete real data: {check.state}. See {d/"readiness.json"}')
    result=run(str(inputdir/'prices.csv'),str(inputdir/'posts.csv'),str(d/'results'),Config(ticker=ticker),synthetic=False)
    # Append explicit source status; never rename to VERIFIED prediction alpha.
    output={'classification':'REAL_DATA_RESEARCH_PROVISIONAL',
            'research_status':check.state, 'last_observed_close':str(verify.market_close_utc.iloc[-1]),
            'ticker':ticker,'sentiment_method':args.sentiment,
            'point_in_time_caveat':not check.historical_text_point_in_time_verified,
            'input_source_manifest_sha256':meta['source_manifest_sha256'],
            'forecast_file':str(d/'results'/'latest_forecasts.csv'),
            'metrics_file':str(d/'results'/'forecast_metrics.csv'),
            'trading': 'PAPER RESEARCH ONLY - no orders',
            'model_manifest_classification':result['classification']}
    (d/'result_status.json').write_text(json.dumps(output,indent=2),encoding='utf8')
    print(json.dumps(output,indent=2))
if __name__=='__main__':main()
