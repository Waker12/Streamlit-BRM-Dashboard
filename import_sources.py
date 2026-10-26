"""Batch-import inspected workbooks, with an audit report kept beside the private DB.

Usage: python import_sources.py --manifest /private/source-files.json --database /data/reporting.sqlite
Manifest: [{"path": "/private/workbook.xlsx"}, ...]. Raw files are never copied to the repository.
"""
import argparse
import json
from pathlib import Path
from bosch_bi.adapters import parse_source,period_from_filename
from bosch_bi.storage import Store

def run(manifest,database,replace=False):
    store=Store(database);report=[]
    for item in json.loads(Path(manifest).read_text()):
        path=Path(item['path'])
        source=parse_source(path.read_bytes(),period=item.get('period') or period_from_filename(path.name))
        result=store.ingest_bundle(source.datasets,path.name,replace,notes={'adapter':source.kind,'notes':source.notes,'checks':source.checks})
        report.append({'filename':path.name,'source':source.kind,'datasets':{k:len(v) for k,v in source.datasets.items()},'result':result,'checks':source.checks,'notes':source.notes})
        print(path.name+': '+result['status'])
        if result['status']=='rejected':raise ValueError(result['detail'])
    out=Path(database).parent/'source-import-audit.json'
    out.write_text(json.dumps(report,indent=2))
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--database',required=True)
    parser.add_argument('--replace',action='store_true')
    args=parser.parse_args();run(args.manifest,args.database,args.replace)
