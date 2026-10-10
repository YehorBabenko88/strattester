import pytest
import sqlite3
from strattester.telegram.controller import TelegramController


@pytest.mark.parametrize('command',['/start','/stop','/restart','/drain'])
def test_lifecycle_failure_returns_error_and_controller_remains_available(command):
    class Failed:
        def start(self): raise RuntimeError('SCM command rejected')
        def stop(self): raise RuntimeError('SCM command rejected')
        def restart(self): raise TimeoutError('worker stop timed out')
        def drain(self): raise RuntimeError('SCM command rejected')
    controller=TelegramController(['1'],Failed(),lambda:'HEALTHY',None)
    response=controller.handle('1',command)
    assert response.startswith(f'FAILED {command}:')
    assert controller.handle('1','/status')=='HEALTHY'


def test_locked_service_state_is_reported_without_crashing_controller():
    class Failed:
        def stop(self): raise sqlite3.OperationalError('database is locked')
    controller=TelegramController(['1'],Failed(),lambda:'HEALTHY',None)
    assert controller.handle('1','/stop').startswith('FAILED /stop:')
    assert controller.handle('1','/status')=='HEALTHY'
