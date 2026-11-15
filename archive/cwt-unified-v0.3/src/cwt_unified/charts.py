"""Research plotting; creates PNG with explicit source/evidence labels."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def sentiment_price_figure(df: pd.DataFrame, path: str | Path, ticker: str, synthetic: bool):
    fig,ax=plt.subplots(figsize=(11,5))
    x=pd.to_datetime(df.date)
    ax.plot(x,df.close.to_numpy(float),linewidth=1.7,label='Observed close')
    ax.set_ylabel('Observed price (input units)')
    ax2=ax.twinx()
    ax2.bar(x,df.sentiment_mean.to_numpy(float),alpha=.22,width=1.0,label='X text sentiment')
    ax2.set_ylim(-1.05,1.05)
    ax2.set_ylabel('Sentiment [-1,+1]')
    ax.set_title(f'{ticker} | Session-aligned sentiment versus close | '+('SYNTHETIC' if synthetic else 'USER-SUPPLIED; SOURCE UNVERIFIED'))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path,dpi=140)
    plt.close(fig)
