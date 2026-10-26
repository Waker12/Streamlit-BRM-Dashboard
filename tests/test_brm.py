from pathlib import Path
import os
import pytest
from bosch_bi.adapters import parse_source
from bosch_bi.storage import Store,validate
from streamlit.testing.v1 import AppTest

@pytest.mark.skipif(not os.environ.get('BOSCH_BRM_FILE'),reason='Private BRM file not bundled')
def test_brm_sources_precedence_and_ui(tmp_path,monkeypatch):
    path=tmp_path/'brm.sqlite';monkeypatch.setenv('BOSCH_BI_DB',str(path))
    store=Store(path)
    internal=parse_source(Path(os.environ['BOSCH_INTERNAL_FILE']).read_bytes())
    assert store.ingest_bundle(internal.datasets,'internal.xlsx')['status']=='imported'
    before=store.read('financial_actuals').to_json()
    source=parse_source(Path(os.environ['BOSCH_BRM_FILE']).read_bytes())
    for key,frame in source.datasets.items():assert not validate(key,frame)[1],key
    assert store.ingest_bundle(source.datasets,'BRM.xlsx')['status']=='imported'
    assert store.read('financial_actuals').to_json()==before
    assert len(store.read('financial_rates'))==9
    assert len(store.read('ads'))==18
    assert len(store.read('kpi_benchmarks'))==2
    assert not (store.read('marketplace').marketplace=='Shopee').any()
    assert set(store.read('marketplace').period.str[:4])=={'2025'}
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
    assert not app.exception
    for page in ['BRM workbook','Financial performance','Marketplace performance','Advertising performance']:
        app.radio[0].set_value(page).run()
        assert not app.exception,(page,[e.message for e in app.exception])
    app.radio[0].set_value('Executive overview').run()
    app.selectbox(key='period_mode').set_value('Selected month').run()
    assert not app.exception
    expected=store.read('financial_rates').query("period=='2026-09'").gm_pct.iloc[0]
    assert app.metric[1].value==f'{expected:.2f}%'
