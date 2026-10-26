"""Transactional canonical imports. Uploaded files are never written to source control."""
from contextlib import nullcontext
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from .schemas import SCHEMAS, BUS
from .policy import fixed_rate

COUNT_FIELDS={'orders','units','visitors','buyers','atc_units','ad_orders'}

def validate(category, frame, existing_master=None):
    spec=SCHEMAS[category]
    df=frame.copy().reset_index(drop=True)
    errors=[]
    for c in spec.required:
        if c not in df: errors.append(f'Missing required column: {c}')
    if errors:return df,errors
    df=df[list(dict.fromkeys(spec.required+tuple(c for c in spec.optional if c in df)))]
    for col in df.select_dtypes(include=['object','string']).columns:
        df[col]=df[col].map(lambda x:x.strip() if isinstance(x,str) else x)
    if df.empty:errors.append('The report has no rows.')
    for col in spec.required:
        if df[col].isna().any() or df[col].astype(str).eq('').any():errors.append(f'{col}: required values are missing.')
    for col in spec.numeric:
        if col not in df:continue
        original=df[col].replace('',None)
        parsed=pd.to_numeric(original,errors='coerce')
        if (original.notna() & parsed.isna()).any():errors.append(f'{col}: invalid number. Map clean numeric fields; currency symbols and locale separators require a reviewed adapter.')
        if parsed.isin([float('inf'),float('-inf')]).any():errors.append(f'{col}: values must be finite.')
        if (parsed<0).any():errors.append(f'{col}: negative values require an approved adjustment workflow.')
        if col in COUNT_FIELDS and category not in ['forecasts','kpi_benchmarks'] and (parsed.dropna()%1!=0).any():errors.append(f'{col}: counts must be integers.')
        if col in {'gm_pct','return_rate','cost_concession_pct'} and (parsed>100).any():errors.append(f'{col}: percentages must be between 0 and 100.')
        if col=='rate' and (parsed<=0).any():errors.append('FX rate must be positive.')
        df[col]=parsed
    for col in ('country','currency','from_currency','to_currency'):
        if col not in df:continue
        df[col]=df[col].astype(str).str.upper()
        allowed={'MY','SG'} if col=='country' else {'MYR','SGD','EUR'}
        if not df[col].isin(allowed).all():errors.append(f'{col}: supported values are {sorted(allowed)}.')
    if 'marketplace' in df:
        df['marketplace']=df.marketplace.astype(str).str.title()
        allowed=['Shopee','Lazada','Consolidated'] if category in ['financial_actuals','forecasts','financial_rates','kpi_benchmarks'] else ['Shopee','Lazada']
        if not df.marketplace.isin(allowed).all():errors.append('Invalid marketplace scope for this dataset.')
    if 'date' in df:
        dates=pd.to_datetime(df.date,errors='coerce')
        if dates.isna().any():errors.append('Invalid daily date.')
        else:df['date']=dates.dt.strftime('%Y-%m-%d')
    if 'period' in df:
        values=pd.to_datetime(df.period.astype(str),errors='coerce')
        if (values.isna() & df.period.notna()).any() or ('period' in spec.required and values.isna().any()):errors.append('Period must be a valid month (YYYY-MM).')
        else:df['period']=values.dt.strftime('%Y-%m')
    for col in ['period_start','period_end']:
        if col in df:
            values=pd.to_datetime(df[col],errors='coerce')
            if values.isna().any():errors.append(f'{col}: invalid date.')
            else:df[col]=values.dt.strftime('%Y-%m-%d')
    if 'period_start' in df and 'period_end' in df:
        if (df.period_start>df.period_end).any():errors.append('Period start must not follow period end.')
        # Only complete monthly, YTD and annual intervals are supported by this monthly release.
        for a,b in zip(df.period_start,df.period_end):
            try:
                start,end=pd.Timestamp(a),pd.Timestamp(b)
                if start.day!=1 or not end.is_month_end or start.year!=end.year:errors.append('Intervals must start on the first day, end on month-end, and stay in one year.')
            except (ValueError,TypeError):pass
    if 'scenario' in df:
        df['scenario']=df.scenario.astype(str).str.lower()
        if not df.scenario.isin(['official','stretch','target']).all():errors.append('Scenario must be official, stretch or target.')
    if 'buyers' in df and 'visitors' in df and (df.buyers>df.visitors).any():errors.append('Buyers exceed visitors; validate denominator scope.')
    if category=='fx':
        for _,r in df.iterrows():
            fixed=fixed_rate(r.from_currency,r.to_currency)
            if fixed is not None and pd.notna(r.rate) and abs(r.rate-fixed)>1e-10:errors.append('Bosch FX policy requires EUR 1 = MYR 4.64; conflicting rates are rejected.')
    if category=='sku_master':
        if not df.business_unit.isin(BUS).all():errors.append('Unrecognized Bosch business unit.')
        flags=df.is_bundle.astype(str).str.lower()
        if not flags.isin(['true','false','1','0']).all():errors.append('is_bundle must be true or false.')
        df['is_bundle']=flags.isin(['true','1'])
        # Canonical identity must have consistent classifications, even across marketplaces.
        for sku,g in df.groupby('canonical_sku'):
            if any(g[c].nunique()>1 for c in ['business_unit','product_group','is_bundle']):errors.append(f'{sku}: canonical SKU has conflicting classifications.')
    if category=='products':
        if existing_master is None or existing_master.empty:errors.append('Import an approved SKU master before product performance.')
        else:
            m=df.merge(existing_master[['country','marketplace','listing_sku']],on=['country','marketplace','listing_sku'],how='left',indicator=True)
            if (m._merge=='left_only').any():errors.append('Unmapped listing SKUs: '+', '.join(m.loc[m._merge=='left_only','listing_sku'].astype(str).unique()[:10]))
    if df.duplicated(list(spec.keys)).any():errors.append('Duplicate business keys within this report; aggregate source data at the declared grain first.')
    return df,list(dict.fromkeys(errors))

class Store:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.path.touch(mode=0o600,exist_ok=True)
        self.path.chmod(0o600)
        with self.connect() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('CREATE TABLE IF NOT EXISTS imports (id INTEGER PRIMARY KEY, created TEXT, filename TEXT, category TEXT, fingerprint TEXT, status TEXT, rows INTEGER, detail TEXT)')
            conn.execute('CREATE TABLE IF NOT EXISTS import_configs (name TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            for category in SCHEMAS:
                conn.execute(f'CREATE TABLE IF NOT EXISTS {category} (business_key TEXT PRIMARY KEY, payload TEXT NOT NULL, import_id INTEGER NOT NULL REFERENCES imports(id))')
    def connect(self):
        c=sqlite3.connect(self.path,timeout=20)
        c.execute('PRAGMA foreign_keys=ON')
        return c
    def read(self,category):
        if category not in SCHEMAS:raise ValueError('Unknown dataset')
        with self.connect() as conn:rows=conn.execute(f'SELECT payload FROM {category}').fetchall()
        df=pd.DataFrame([json.loads(x[0]) for x in rows])
        for col in SCHEMAS[category].required+SCHEMAS[category].optional:
            if col not in df:df[col]=None
        return df
    def history(self):
        with self.connect() as conn:return pd.read_sql_query('SELECT id,created,filename,category,status,rows,detail FROM imports ORDER BY id DESC',conn)
    def save_config(self,name,payload):
        with self.connect() as conn:conn.execute('INSERT OR REPLACE INTO import_configs VALUES (?,?)',(name,json.dumps(payload)))
    def configs(self):
        with self.connect() as conn:return {n:json.loads(p) for n,p in conn.execute('SELECT name,payload FROM import_configs')}
    def ingest(self,category,frame,filename,replace=False,_conn=None):
        df,errors=validate(category,frame,self.read('sku_master'))
        records=json.loads(df.to_json(orient='records'))
        serialized=json.dumps(records,sort_keys=True,separators=(',',':'))
        fingerprint=hashlib.sha256((category+serialized).encode()).hexdigest()
        keys=[json.dumps([r[k] for k in SCHEMAS[category].keys],separators=(',',':')) for r in records] if not errors else []
        with (nullcontext(_conn) if _conn is not None else self.connect()) as conn:
            if not conn.in_transaction:conn.execute('BEGIN IMMEDIATE')
            # Cross-file consistency is checked against existing approved master rows too.
            if category=='sku_master' and not errors:
                old=self.read('sku_master')
                if not old.empty:
                    old=old[~old.apply(lambda r:json.dumps([r[k] for k in SCHEMAS[category].keys],separators=(',',':')) in keys,axis=1)]
                    _,cross_errors=validate(category,pd.concat([old,df],ignore_index=True))
                    errors+=cross_errors
            if category=='traffic' and not errors:
                old=self.read('traffic')
                for r in records:
                    x=old[(old.country==r['country']) & (old.marketplace==r['marketplace']) & (old.period_start==r['period_start']) & (old.period_end==r['period_end']) & (old.sales_basis==r['sales_basis'])]
                    if len(x)>1:errors.append('Overlapping audience scope.')
            duplicate=conn.execute("SELECT id FROM imports WHERE fingerprint=? AND status='imported'",(fingerprint,)).fetchone()
            if duplicate and not errors:
                current=[conn.execute(f'SELECT payload FROM {category} WHERE business_key=?',(key,)).fetchone() for key in keys]
                if all(row and json.loads(row[0])==record for row,record in zip(current,records)):
                    return {'status':'duplicate','detail':'This normalized report is already present.','rows':0}
            collisions=sum(conn.execute(f'SELECT 1 FROM {category} WHERE business_key=?',(key,)).fetchone() is not None for key in keys)
            if collisions and not replace:errors.append(f'{collisions} existing records conflict. Review then enable replacement explicitly.')
            status='rejected' if errors else 'imported'
            detail='; '.join(errors) if errors else f'{len(records)} canonical rows committed; {collisions} replaced.'
            cursor=conn.execute('INSERT INTO imports(created,filename,category,fingerprint,status,rows,detail) VALUES (?,?,?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),Path(filename).name,category,fingerprint,status,len(records),detail))
            if not errors:
                for key,record in zip(keys,records):conn.execute(f'INSERT OR REPLACE INTO {category} VALUES (?,?,?)',(key,json.dumps(record),cursor.lastrowid))
            return {'status':status,'detail':detail,'rows':len(records) if not errors else 0}

    def ingest_bundle(self,datasets,filename,replace=False,notes=None):
        """One source workbook commits all extracted datasets or none."""
        results={}
        try:
            with self.connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                for category,frame in datasets.items():
                    result=self.ingest(category,frame,filename,replace,_conn=conn)
                    results[category]=result
                    if result['status']=='rejected':raise ValueError(category+': '+result['detail'])
                if notes:
                    conn.execute('INSERT INTO imports(created,filename,category,fingerprint,status,rows,detail) VALUES (?,?,?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),Path(filename).name,'source_notes','', 'reviewed',0,json.dumps(notes)))
            return {'status':'imported' if any(r['status']=='imported' for r in results.values()) else 'duplicate','detail':'; '.join(k+': '+v['status'] for k,v in results.items()),'datasets':results}
        except ValueError as exc:
            with self.connect() as conn:
                conn.execute('INSERT INTO imports(created,filename,category,fingerprint,status,rows,detail) VALUES (?,?,?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),Path(filename).name,'source_bundle','', 'rejected',0,str(exc)))
            return {'status':'rejected','detail':str(exc),'datasets':{}}
