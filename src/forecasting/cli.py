"""Reproducible local CLI; commands emit a single JSON document."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .store import ArtifactStore, canonical_json
from .service import ForecastService


def main(argv=None):
    parser=argparse.ArgumentParser(prog='forecasting')
    sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('ingest',help='Acquire authorized source files with actual receipt time for durable replay')
    command.add_argument('config');command.add_argument('--store',required=True)
    command=sub.add_parser('forecast',help='Forecast an authorized normalized local file')
    command.add_argument('config');command.add_argument('--store',required=True)
    command=sub.add_parser('show',help='Retrieve an immutable result with current source ACLs')
    command.add_argument('artifact_id');command.add_argument('--store',required=True)
    command.add_argument('--tenant',required=True);command.add_argument('--source',action='append',default=[])
    sub.add_parser('models',help='List actual model capabilities and eligibility')
    command=sub.add_parser('evaluate',help='Run the bounded synthetic D/C/F comparison')
    command.add_argument('--seed',type=int,default=0);command.add_argument('--output')
    command=sub.add_parser('demo',help='Run synthetic Northstar handoffs in a fresh directory')
    command.add_argument('--output-dir',required=True)
    command=sub.add_parser('joint-demo',help='Run synthetic evidence, joint paths, exact shared-pool pricing and retrieval')
    command.add_argument('--output-dir',required=True)
    command.add_argument('--process',choices=('state','aggregate'),default='state')
    args=parser.parse_args(argv)
    try:
        if args.command=='ingest':
            from .integration import ingest_from_config
            value=ingest_from_config(args.config,args.store)
        elif args.command=='forecast':
            from .integration import forecast_from_config
            value=forecast_from_config(args.config,args.store)
        elif args.command=='show':
            value=ForecastService(ArtifactStore(args.store)).retrieve(args.tenant,args.artifact_id,allowed_sources=set(args.source))
        elif args.command=='joint-demo':
            from .joint_service import run_joint_demo
            value=run_joint_demo(args.output_dir,process=args.process)
        elif args.command=='models':
            from .models import MODEL_REGISTRY
            value={'schema_version':'1.0','models':{k:asdict(v) for k,v in MODEL_REGISTRY.items()}}
        elif args.command=='evaluate':
            from .evaluation import synthetic_evaluation
            value=synthetic_evaluation(args.seed)
            if args.output:
                Path(args.output).parent.mkdir(parents=True,exist_ok=True)
                Path(args.output).write_text(json.dumps(value,indent=2)+'\n')
        else:
            from .integration import run_demo
            value=run_demo(args.output_dir)
        print(canonical_json(value))
        return 0
    except (ValueError,PermissionError,OSError) as exc:
        print(canonical_json({'error':str(exc),'status':'failed'}),file=sys.stderr)
        return 2
