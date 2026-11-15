"""Optional daily finance-data downloader for personal research; review data rights."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd


def download_daily(ticker:str, start:str, end_exclusive:str, out:Path):
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("Install optional dependency: pip install -e '.[data]'") from exc
    result=yf.download(ticker,start=start,end=end_exclusive,interval='1d',
                       auto_adjust=False,progress=False,threads=False)
    if result.empty: raise ValueError(f'No {ticker} price rows returned; verify symbol and provider availability')
    if isinstance(result.columns,pd.MultiIndex):
        if ticker not in result.columns.get_level_values(-1):
            raise ValueError('Provider returned a mismatched ticker')
        result=result.xs(ticker,axis=1,level=-1)
    if not {'Open','Close'}.issubset(result.columns):
        raise ValueError('Provider missing Open/Close')
    prices=result[['Open','Close']].reset_index()
    prices=prices.rename(columns={'Date':'date','Open':'open','Close':'close'})
    prices['date']=pd.to_datetime(prices['date']).dt.strftime('%Y-%m-%d')
    out.parent.mkdir(parents=True,exist_ok=True)
    prices.to_csv(out,index=False)
    return len(prices)


def main(argv=None):
    p=argparse.ArgumentParser(description='Daily 1d market-price CSV, source yfinance, research-only')
    p.add_argument('--ticker',default='AAPL')
    p.add_argument('--start',required=True)
    p.add_argument('--end-exclusive',required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args(argv)
    n=download_daily(a.ticker.upper(),a.start,a.end_exclusive,Path(a.out))
    print(f'Wrote {n} daily rows to {a.out}; unadjusted Open/Close; independently audit corporate actions')

if __name__=='__main__': main()
