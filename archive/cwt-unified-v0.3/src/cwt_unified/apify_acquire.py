"""Only authorized, user-provided Apify Actor. Optional and explicit-cost; no login/cookie scraping.

No actor input fields are invented. Inspect the exact actor's documented input schema first.
"""
import argparse,json,os
from pathlib import Path

def run_authorized_actor(actor_id: str, input_path: str, output: str, *, max_items:int=5000):
    if os.getenv('CWT_AUTHORIZED_X_COLLECTION')!='YES':
        raise PermissionError('Verify your provider rights and set CWT_AUTHORIZED_X_COLLECTION=YES explicitly')
    token=os.getenv('APIFY_TOKEN')
    if not token: raise RuntimeError('APIFY_TOKEN missing from local environment')
    actor_input=json.loads(Path(input_path).read_text())
    if not isinstance(actor_input,dict) or not actor_input:
        raise ValueError('Actor input must be a non-empty JSON object matching provider schema')
    if max_items<1 or max_items>100000:raise ValueError('Invalid explicit item cap')
    try:from apify_client import ApifyClient
    except ImportError as e:raise RuntimeError("Install optional dependency: pip install -e '.[apify]'") from e
    client=ApifyClient(token)
    # This run may incur costs. Invoked ONLY by explicit CLI command.
    job=client.actor(actor_id).call(run_input=actor_input)
    if not job or not job.get('defaultDatasetId'):
        raise RuntimeError('Actor returned no dataset; inspect provider status')
    dataset_id=job['defaultDatasetId']
    items=[]
    iterator=client.dataset(dataset_id).iterate_items()
    for n,item in enumerate(iterator):
        if n>=max_items:
            raise RuntimeError('Maximum items reached. Data not saved because collection may be truncated')
        items.append(item)
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(items,ensure_ascii=False),encoding='utf8')
    return {'actor_id':actor_id,'dataset_id':dataset_id,'run_id':job.get('id'),
            'run_status':job.get('status'),'items_saved':len(items),'output':str(out)}

def main(argv=None):
    p=argparse.ArgumentParser(description='Authorized provider data fetch; may incur third-party costs')
    p.add_argument('--actor-id',required=True)
    p.add_argument('--actor-input',required=True,help='Provider-specific JSON saved locally')
    p.add_argument('--out',required=True)
    p.add_argument('--max-items',type=int,default=5000)
    a=p.parse_args(argv)
    print(json.dumps(run_authorized_actor(a.actor_id,a.actor_input,a.out,max_items=a.max_items),indent=2))
if __name__=='__main__':main()
