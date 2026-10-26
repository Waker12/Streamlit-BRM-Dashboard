import pytest

@pytest.fixture(autouse=True)
def local_test_access(monkeypatch):
    # Ordinary UI tests bypass login; security tests explicitly exercise the gate.
    monkeypatch.setenv('BOSCH_BI_REQUIRE_AUTH','0')
