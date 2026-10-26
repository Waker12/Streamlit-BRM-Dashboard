"""Explicit synthetic fixtures. Never loaded into the uploaded-data database."""
import calendar
import random
import pandas as pd
from .schemas import SCHEMAS, BUS
from .policy import EUR_TO_MYR

NAMES=['GSB 120-LI Impact Drill Kit','EasyGrassCut 23','GSB 600 Professional','EasyPump Cordless Pump','Bosch GO Smart Screwdriver','GHG 18-60 Heat Gun','X-Line Classic Drill Set','GSR 120-LI Drill Driver','EasyAquatak 110','GSR 185-LI','GBH 220 Rotary Hammer','108-in-1 Tool Kit','IXO 7','GAS 400 A Vacuum','GLM 400 AP Laser Measure','GCM 254 D Mitre Saw','GEX 125 Random Orbit Sander','UniversalAquatak 125','GWS 750 Angle Grinder','GSH 5 CE Demolition Hammer','18V Starter Battery Kit','GST 750 Jigsaw','Ratchet Screwdriver Set','UniversalBrush','Cordless Drill Value Bundle','LED Camping Light','Dust Extractor GDE 12','Expert 8Ah Battery','Torque Adapter','Professional Knife Set','Impact Bit Set','Drill Driver Value Bundle']

def generate():
    rng=random.Random(36026)
    rows={k:[] for k in SCHEMAS}
    for year in (2025,2026):
        for m in range(1,13):
            period=f'{year}-{m:02d}'
            for a,b,rate in [('MYR','EUR',1/EUR_TO_MYR),('SGD','EUR',.687),('MYR','SGD',.296),('SGD','MYR',3.378),('EUR','MYR',EUR_TO_MYR),('EUR','SGD',1.456)]:
                rows['fx'].append(dict(period=period,from_currency=a,to_currency=b,rate=rate,methodology='Demo fixed rates · illustrative only'))
    for country,local in [('MY','MYR'),('SG','SGD')]:
        for platform in ['Shopee','Lazada']:
            scope=dict(country=country,marketplace=platform)
            basis='Placed Order' if platform=='Shopee' else 'Lazada Revenue'
            scale=(1 if country=='MY' else .34)*(1 if platform=='Shopee' else .42)
            for i,name in enumerate(NAMES):
                rows['sku_master'].append(dict(**scope,listing_sku=f'{platform[:2].upper()}-{i+1:03d}',canonical_sku=f'DEMO-{i+1:04d}',product_name=name,business_unit=BUS[i%len(BUS)],product_group=['Drill drivers','Garden tools','Accessories','Measuring tools'][i%4],is_bundle=('Bundle' in name or 'Kit' in name)))
            for year in [2025,2026]:
                v_acc=b_acc=0
                for m in range(1,(13 if year==2025 else 10)):
                    period=f'{year}-{m:02d}'
                    start=f'{period}-01';end=f'{period}-{calendar.monthrange(year,m)[1]}'
                    season=[.94,.86,1.15,1.24,1.09,.99,.83,.68,.92,1.12,1.37,1.58][m-1]
                    gmv=round(215000*scale*season*(1.20 if year==2026 else 1)*rng.uniform(.91,1.09),2)
                    orders=int(gmv/240);units=int(orders*1.13)
                    visitors=int(65000*scale*rng.uniform(.80,1.2));buyers=int(orders*.87)
                    rows['marketplace'].append(dict(**scope,sales_basis=basis,period=period,currency=local,gmv=gmv,orders=orders,units=units))
                    rows['traffic'].append(dict(**scope,sales_basis=basis,period_start=start,period_end=end,visitors=visitors,buyers=buyers))
                    v_acc+=visitors;b_acc+=buyers
                    if m>1:rows['traffic'].append(dict(**scope,sales_basis=basis,period_start=f'{year}-01-01',period_end=end,visitors=int(v_acc*.79),buyers=int(b_acc*.84)))
                    tns=round(gmv*.79,2)
                    rows['financial_actuals'].append(dict(**scope,period=period,currency=local,tns=tns,orders=orders,gm_pct=round(rng.uniform(69,77),2),gm_basis=tns,return_rate=round(rng.uniform(1,2.4),2),return_basis=orders,cost_concession_pct=round(rng.uniform(33,38),2),concession_basis=gmv))
                    model='Demo · 7-day click' if platform=='Shopee' else 'Demo · 14-day click'
                    spend=round(gmv*rng.uniform(.024,.055),2)
                    rows['ads'].append(dict(**scope,period=period,currency=local,spend=spend,ads_gmv=round(spend*rng.uniform(5,13),2),ad_orders=int(orders*.35),attribution_model=model))
                    weights=[(33-i)**1.15*rng.uniform(.8,1.25) for i in range(len(NAMES))]
                    denom=sum(weights)
                    for i,(name,w) in enumerate(zip(NAMES,weights)):
                        revenue=round(gmv*w/denom,2);sold=max(1,int(units*w/denom));pv=max(30,int(visitors*w/denom*rng.uniform(.6,1.8)));pb=min(pv,max(0,int(sold*.8)))
                        rows['products'].append(dict(**scope,sales_basis=basis,period=period,currency=local,listing_sku=f'{platform[:2].upper()}-{i+1:03d}',product_name=name,revenue=revenue,units=sold,visitors=pv,buyers=pb,atc_units=int(sold*rng.uniform(2.2,5)),gm_pct=round(rng.uniform(60,85),1),gm_basis=revenue))
            for m in range(1,13):
                period=f'2026-{m:02d}';end=f'{period}-{calendar.monthrange(2026,m)[1]}'
                for scenario,mult in [('official',1.30),('stretch',1.45)]:
                    tns=round(215000*scale*.79*[.94,.86,1.15,1.24,1.09,.99,.83,.68,.92,1.12,1.37,1.58][m-1]*mult,2)
                    rows['forecasts'].append(dict(**scope,period_start=f'{period}-01',period_end=end,currency=local,scenario=scenario,tns=tns))
            rows['forecasts'].append(dict(**scope,period_start='2026-01-01',period_end='2026-12-31',currency='EUR',scenario='target',tns=round(215000*scale*.79*15.8*(1/EUR_TO_MYR if country=='MY' else .687),2),gm_pct=78,gm_basis=1,visitors=int(850000*scale),buyers=int(15000*scale),orders=int(17000*scale),return_rate=1.2,return_basis=1,cost_concession_pct=37.5,concession_basis=1))
    frames={k:pd.DataFrame(v) for k,v in rows.items()}
    for k,df in frames.items():
        for col in SCHEMAS[k].required+SCHEMAS[k].optional:
            if col not in df:df[col]=float('nan')
    return frames
