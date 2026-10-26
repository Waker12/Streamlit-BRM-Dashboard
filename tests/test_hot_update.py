from pathlib import Path
from streamlit.testing.v1 import AppTest
from bosch_bi import charts


def test_existing_session_refreshes_legacy_chart_helpers(monkeypatch,tmp_path):
    """An already-running server may keep the old imported combo signature."""
    original=charts.combo
    def legacy_combo(df,bars,lines,currency='',second_axis=False):
        return original(df,bars,lines,currency,second_axis)
    monkeypatch.setattr(charts,'combo',legacy_combo)
    monkeypatch.delattr(charts,'DISPLAY_API_VERSION',raising=False)
    monkeypatch.setenv('BOSCH_BI_DB',str(tmp_path/'hot-update.sqlite'))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
    assert not app.exception,[e.message for e in app.exception]
    app.radio[0].set_value('Financial performance').run()
    assert not app.exception,[e.message for e in app.exception]
    assert app.toggle(key='chart_labels_financial_main')
