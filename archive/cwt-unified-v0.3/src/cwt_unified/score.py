"""Optional offline sentiment scoring. Scores are EXPERIMENTAL and need manual validation."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from .sentiment import lexical_sentiment


def score_texts(texts: list[str], method: str = 'lexical') -> list[float]:
    if method == 'lexical':
        return [float(lexical_sentiment(s)) for s in texts]
    if method == 'vader':
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        except ImportError as exc:
            raise RuntimeError("Install optional dependency: pip install -e '.[data]'") from exc
        analyzer=SentimentIntensityAnalyzer()
        return [float(analyzer.polarity_scores(s)['compound']) for s in texts]
    raise ValueError('Method must be lexical or vader')


def main(argv=None):
    ap=argparse.ArgumentParser(description='Score historical text without LLM/API tokens')
    ap.add_argument('--posts',required=True)
    ap.add_argument('--method',choices=['lexical','vader'],default='vader')
    ap.add_argument('--out',required=True)
    args=ap.parse_args(argv)
    df=pd.read_csv(args.posts)
    if 'text' not in df.columns: raise ValueError('posts CSV missing text')
    df['sentiment']=score_texts(df.text.fillna('').astype(str).tolist(),args.method)
    p=Path(args.out);p.parent.mkdir(exist_ok=True,parents=True)
    df.to_csv(p,index=False)
    print(f'Wrote {len(df)} text scores to {p}; method={args.method}, research-only')

if __name__=='__main__': main()
