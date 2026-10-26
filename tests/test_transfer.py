from io import BytesIO
import json
from zipfile import ZipFile
import pandas as pd
import pytest
from bosch_bi.storage import Store
from bosch_bi.demo import generate
from bosch_bi.transfer import export_workspace, read_workspace, import_workspace, FORMAT


def package(datasets):
    buf=BytesIO()
    with ZipFile(buf,'w') as archive:
        archive.writestr('workspace.json',json.dumps(dict(format=FORMAT,datasets=datasets)))
    return buf.getvalue()


def test_round_trip_with_master_and_audit(tmp_path):
    source=Store(tmp_path/'source.sqlite')
    frames=generate()
    for key in ['sku_master','financial_actuals','marketplace','products']:
        assert source.ingest(key,frames[key],key+'.csv')['status']=='imported'
    raw=export_workspace(source)
    target=Store(tmp_path/'target.sqlite')
    assert import_workspace(target,raw,'transfer.zip')['status']=='imported'
    for key in ['sku_master','financial_actuals','marketplace','products']:
        a=source.read(key).sort_values(list(source.read(key).columns)).reset_index(drop=True)
        b=target.read(key).sort_values(list(target.read(key).columns)).reset_index(drop=True)
        pd.testing.assert_frame_equal(a[b.columns],b,check_dtype=False)
    assert 'original_import_history' in target.history().query("category=='source_notes'").detail.iloc[0]
    assert import_workspace(target,raw,'again.zip')['status']=='duplicate'


def test_conflict_and_bad_dataset_roll_back_entire_package(tmp_path):
    store=Store(tmp_path/'target.sqlite')
    frame=generate()['financial_actuals'].head(1)
    assert store.ingest('financial_actuals',frame,'existing.csv')['status']=='imported'
    changed=frame.copy();changed['tns']=frame.tns+1
    data={'marketplace':generate()['marketplace'].head(1).to_dict('records'),
          'financial_actuals':changed.to_dict('records')}
    assert import_workspace(store,package(data),'conflict.zip')['status']=='rejected'
    assert store.read('marketplace').empty
    assert import_workspace(store,package(data),'replace.zip',True)['status']=='imported'
    bad=changed.copy();bad['tns']=-1
    data['financial_actuals']=bad.to_dict('records')
    assert import_workspace(store,package(data),'invalid.zip',True)['status']=='rejected'
    assert store.read('financial_actuals').tns.iloc[0]==changed.tns.iloc[0]


def test_reject_unknown_or_executable_packages():
    for raw in [b'not a ZIP',package({'unknown':[{}]}),package({'financial_actuals':'bad'})]:
        with pytest.raises(ValueError):read_workspace(raw)
    out=BytesIO()
    with ZipFile(out,'w') as archive:archive.writestr('../workspace.json','{}')
    with pytest.raises(ValueError):read_workspace(out.getvalue())
