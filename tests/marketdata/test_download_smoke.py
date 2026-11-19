from strattester.marketdata.download_smoke import validate_candle_smoke

def test_candle_smoke_validation_requires_contiguous_unique_rows():
    rows=[
      ['120000','2','3','1','2.5','10','20'],
      ['60000','1','2','.5','1.5','9','15'],
    ]
    r=validate_candle_smoke(rows,60000,120000)
    assert r.ok and r.count==2 and r.duplicates==0 and r.gaps==0

def test_candle_smoke_validation_rejects_gap():
    rows=[['60000','1','2','.5','1.5','9','15'],['180000','2','3','1','2.5','10','20']]
    assert not validate_candle_smoke(rows,60000,180000).ok

def test_no_implicit_exchange_client_or_disk_mutation(tmp_path, monkeypatch):
    from strattester.marketdata.download_smoke import run_download_smoke
    import strattester.marketdata.bybit_client as bybit_client
    def forbidden(*args, **kwargs):
        raise AssertionError('legacy smoke must never create an exchange client')
    monkeypatch.setattr(bybit_client, 'BybitClient', forbidden)
    root = tmp_path / 'never-created'
    result = run_download_smoke(root)
    assert not result.ok and result.detail == 'GRID_SOURCE_REQUIRED'
    assert not root.exists()


def test_invalid_grid_source_denied_without_files(tmp_path):
    from strattester.marketdata.download_smoke import run_download_smoke
    root = tmp_path / 'no-files'
    result = run_download_smoke(root, client=object())
    assert result.detail == 'GRID_KLINES_INTERFACE_REQUIRED'
    assert not root.exists()


def test_legacy_cli_never_downloads(monkeypatch, capsys):
    from strattester.marketdata import download_smoke_cli
    def forbidden(*args, **kwargs):
        raise AssertionError('legacy CLI must not invoke download')
    monkeypatch.setattr(download_smoke_cli, 'run_download_smoke', forbidden, raising=False)
    monkeypatch.setattr('sys.argv', ['download-smoke', '--minutes', '10'])
    assert download_smoke_cli.main() == 2
    assert 'GRID_SOURCE_REQUIRED' in capsys.readouterr().out
