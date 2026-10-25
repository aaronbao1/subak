"""Local authenticated WSGI example. Not a production identity provider.

FORECASTING_DEMO_TOKEN must be set by the caller; it is never written to results.
The file path and source scope are fixed at startup, not supplied by HTTP callers.
"""
import argparse
import hmac
import os
from wsgiref.simple_server import make_server

from forecasting.integration import load_snapshot
from forecasting.service import ForecastApplication, ForecastService
from forecasting.store import AccessDenied

parser=argparse.ArgumentParser()
parser.add_argument('--config',required=True)
parser.add_argument('--store',required=True)
parser.add_argument('--port',type=int,default=8080)
args=parser.parse_args()
token=os.environ.get('FORECASTING_DEMO_TOKEN')
if not token:
    parser.error('set FORECASTING_DEMO_TOKEN before starting the local example')
request,snapshot,store,policy=load_snapshot(args.config,args.store)


def authenticate(environ):
    supplied=environ.get('HTTP_AUTHORIZATION','')
    if not hmac.compare_digest(supplied,'Bearer '+token):
        raise AccessDenied('authentication required')
    return request.target.tenant_id,set(request.target.sources)


app=ForecastApplication(ForecastService(store),authenticate=authenticate,
                        snapshot_resolver=lambda body,tenant,sources:snapshot,run_options=policy)
with make_server('127.0.0.1',args.port,app) as server:
    print('Local reference service listening on 127.0.0.1:'+str(args.port),flush=True)
    server.serve_forever()
