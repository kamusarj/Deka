import json
import pytest
from app.core.config import settings
from app.services.ai import dev
from tests.test_ai_credits import accounts, assert_balance


def test_dev_plan_adjustments_and_recovery(accounts, monkeypatch, capsys):
    monkeypatch.setattr(dev, 'CreditService', lambda: accounts)
    monkeypatch.setattr(settings, 'ENV', 'development')
    for args in [ ['plan', '--user-id', '1', '--plan', 'PRO'],
                  ['reset', '--user-id', '1', '--amount', '1500'],
                  ['grant', '--user-id', '1', '--amount', '-10'] ]:
        dev.main(args)
    assert_balance(accounts, 1490)
    assert accounts.account(1)['plan'] == 'PRO'
    request_id = accounts.reserve(1, 'exam_generation')
    for _ in range(2):
        dev.main(['recover', '--user-id', '1', '--request-id', request_id])
    assert_balance(accounts, 1490)
    dev.main(['usage', '--user-id', '1'])
    assert 'AI_INTERRUPTED' in capsys.readouterr().out


def test_cli_refuses_production_before_database_access(monkeypatch):
    monkeypatch.setattr(settings, 'ENV', 'production')
    def forbidden():
        pytest.fail('Database must not be opened')
    monkeypatch.setattr(dev, 'CreditService', forbidden)
    with pytest.raises(SystemExit) as error:
        dev.main(['grant', '--user-id', '1', '--amount', '100'])
    assert error.value.code == 2
