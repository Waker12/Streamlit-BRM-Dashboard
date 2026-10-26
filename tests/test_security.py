from pathlib import Path
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/'app.py'

def test_required_auth_without_secret_is_locked(monkeypatch,tmp_path):
    monkeypatch.setenv('BOSCH_BI_DB',str(tmp_path/'db.sqlite'))
    monkeypatch.setenv('BOSCH_BI_REQUIRE_AUTH','1')
    monkeypatch.setenv('BOSCH_BI_PASSWORD','')
    app=AppTest.from_file(str(APP),default_timeout=45).run()
    assert not app.exception
    assert app.error and not app.radio
    assert not (tmp_path/'db.sqlite').exists()

def test_password_gate_and_logout(monkeypatch,tmp_path):
    monkeypatch.setenv('BOSCH_BI_DB',str(tmp_path/'db.sqlite'))
    monkeypatch.setenv('BOSCH_BI_REQUIRE_AUTH','1')
    monkeypatch.setenv('BOSCH_BI_PASSWORD','synthetic-test-password-only')
    app=AppTest.from_file(str(APP),default_timeout=45).run()
    assert not app.exception and not app.radio
    app.text_input[0].set_value('wrong');app.button[0].click().run()
    assert app.error and not app.radio
    app.text_input[0].set_value('synthetic-test-password-only');app.button[0].click().run()
    assert not app.exception and app.radio
    app.button(key='owner_signout').click().run()
    assert not app.exception and not app.radio

def test_default_access_is_locked(monkeypatch,tmp_path):
    monkeypatch.delenv('BOSCH_BI_REQUIRE_AUTH',raising=False)
    monkeypatch.setenv('BOSCH_BI_PASSWORD','')
    monkeypatch.setenv('BOSCH_BI_DB',str(tmp_path/'db.sqlite'))
    app=AppTest.from_file(str(APP),default_timeout=45).run()
    assert not app.exception
    assert app.error and not app.radio
    assert not (tmp_path/'db.sqlite').exists()
