"""Installed canonical Data test lane; exact roster and approved wheel bytes."""
import argparse,hashlib,importlib.metadata as metadata,importlib.util,json,os,pathlib,sys,tempfile

def verify(site,bindings):
    owners={'market_data':'market_data','market_math':'unified-math-kernels','market_compute_api':'unified-math-kernels','history_statistics':'unified-math-kernels'}
    for relative,digest in bindings.items():
        path=site/relative
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise AssertionError('approved wheel bytes changed: '+relative)
        distribution=metadata.distribution(owners[relative.split('/')[0].removesuffix('.py')])
        files=distribution.files
        if files is None or sum(item.as_posix()==relative for item in files)!=1:
            raise AssertionError('wheel file not owned by named distribution: '+relative)
    for name,module in tuple(sys.modules.items()):
        if name!='market_data' and not name.startswith('market_data.') and name not in owners:continue
        origin=pathlib.Path(module.__file__).resolve(strict=True)
        if not origin.is_relative_to(site):raise AssertionError('canonical module source fallback: '+name)
        relative=origin.relative_to(site).as_posix()
        if relative not in bindings or module.__spec__ is None or pathlib.Path(module.__spec__.origin).resolve(strict=True)!=origin:
            raise AssertionError('unapproved canonical module origin: '+name)
    for retired in ('grid','strattester','meta_analyse','market_profile_math'):
        if importlib.util.find_spec(retired) is not None:raise AssertionError('retired package fallback visible: '+retired)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('site','bindings','evidence'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args(argv);root=pathlib.Path(__file__).resolve().parents[1]
    site=pathlib.Path(args.site).resolve(strict=True);output=pathlib.Path(args.evidence).absolute()
    if output.exists() or output.resolve().is_relative_to(root):raise ValueError('fresh external evidence required')
    bindings=json.loads(pathlib.Path(args.bindings).read_text())['bindings']
    if len(bindings)!=45:raise ValueError('exact42Data+3Math wheel bindings required')
    sys.path[:0]=[str(site),str(root/'scripts'),str(root/'tests/market_data'),str(root/'tests/marketdata')]
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
    from canonical_test_gate import StrictTestRoster
    expected=json.loads((root/'scripts/canonical_test_roster.json').read_text())
    guard=StrictTestRoster(expected,expected_count=640)
    import market_data,market_math,pytest
    verify(site,bindings)
    with tempfile.TemporaryDirectory(prefix='canonical-data-tests-') as case:
        previous=pathlib.Path.cwd();os.chdir(case)
        try:
            result=pytest.main(['--rootdir',str(root),'--import-mode=importlib','-p','pytest_asyncio.plugin','--confcutdir',str(root/'tests'),str(root/'tests/market_data'),str(root/'tests/marketdata/test_rich_sync.py'),str(root/'tests/marketdata/test_coverage.py'),str(root/'tests/unmigrated_market_data/test_source_provenance.py::test_event_time_ohlc_duplicate_and_late_trades'),str(root/'tests/unmigrated_market_data/test_source_provenance.py::test_actual_builder_decimal_tick_rounding_retains_integrity'),'-p','no:cacheprovider','-q'],plugins=[guard])
            verify(site,bindings)
            accepted=int(result)==0 and guard.accepted
            output.write_text(json.dumps({'status':'PASS_SCOPED' if accepted else 'FAIL','cases':640,'source_head':os.environ.get('MARKET_DATA_TEST_SHA'),'scope':'SYNTHETIC_FIXTURES_ONLY','native':'NOT_RUN','release_status':'NO_GO','errors':guard.errors},indent=2)+'\n')
            return 0 if accepted else 1
        finally:os.chdir(previous)

if __name__=='__main__':raise SystemExit(main())
