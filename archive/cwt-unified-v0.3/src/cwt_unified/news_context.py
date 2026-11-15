"""Optional current-news lookup, kept OUT of historical forecasting features."""
import argparse,json,os
from datetime import datetime,timezone
from pathlib import Path

def fetch_current_news(query:str,*,max_results:int=5):
    from datetime import datetime,timezone
    out={'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
         'query':query,'model_feature_eligible':False,'tavily':None,'exa':None,'errors':[]}
    key=os.getenv('TAVILY_API_KEY')
    if key:
        try:
            from tavily import TavilyClient
            out['tavily']=TavilyClient(api_key=key).search(query=query,topic='news',max_results=max_results)
        except Exception as e:out['errors'].append('Tavily: '+type(e).__name__+': '+str(e)[:150])
    ek=os.getenv('EXA_API_KEY')
    if ek:
        try:
            from exa_py import Exa
            res=Exa(api_key=ek).search_and_contents(query,num_results=max_results)
            out['exa']=[{'title':r.title,'url':r.url,'published_date':getattr(r,'published_date',None)} for r in res.results]
        except Exception as e:out['errors'].append('Exa: '+type(e).__name__+': '+str(e)[:150])
    if not key and not ek:
        raise RuntimeError('No Tavily or Exa token; do not invent news')
    return out
def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--query',required=True);p.add_argument('--out',required=True)
    a=p.parse_args(argv); r=fetch_current_news(a.query)
    pth=Path(a.out);pth.parent.mkdir(parents=True,exist_ok=True)
    pth.write_text(json.dumps(r,indent=2,default=str))
    print('Current news saved; historical ML features remain price and X sentiment only')
if __name__=='__main__': main()
