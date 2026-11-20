"""Inert package-gate counterexamples; no imported SDK, installs or children."""
import contextlib,io,json,pathlib,runpy,sys,tarfile,tempfile,zipfile

def fixture(root,mode):
    files={'market_data/__init__.py':b'# inert source\n','market_data/schema.sql':b'CREATE TABLE inert(value TEXT);\n'}
    math={name:b'# inert numerical source shape only\n' for name in ('market_math.py','market_compute_api.py','history_statistics.py')}
    for name,raw in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    for name,raw in math.items():
        path=root/'.source/math/python'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    wheels=dict(files);numbers=dict(math);archive=dict(files)
    if mode=='sql_changed':wheels['market_data/schema.sql']+=b'-- changed\n'
    if mode=='sql_missing':del wheels['market_data/schema.sql']
    if mode=='sql_extra':wheels['market_data/extra.sql']=b'-- extra\n'
    if mode=='python_crlf':wheels['market_data/__init__.py']=files['market_data/__init__.py'].replace(b'\n',b'\r\n')
    if mode=='math_changed':numbers['market_math.py']+=b'# changed\n'
    if mode=='math_missing':del numbers['history_statistics.py']
    if mode=='math_retired':numbers['market_profile_math.py']=b'# retired\n'
    if mode=='math_crlf':numbers['market_math.py']=numbers['market_math.py'].replace(b'\n',b'\r\n')
    if mode=='sdist_sql_changed':archive['market_data/schema.sql']+=b'-- changed\n'
    dist=root/'.candidate-dist';dist.mkdir()
    with zipfile.ZipFile(dist/'market_data-0.1.0-py3-none-any.whl','w') as z:
        for name,raw in wheels.items():z.writestr(name,raw)
        z.writestr('market_data-0.1.0.dist-info/entry_points.txt','market-data = market_data.cli:main\n')
        if mode=='duplicate_zip':
            with __import__('warnings').catch_warnings():
                __import__('warnings').simplefilter('ignore');z.writestr('market_data/__init__.py',files['market_data/__init__.py'])
    sdk=root/'math.whl'
    with zipfile.ZipFile(sdk,'w') as z:
        for name,raw in numbers.items():z.writestr(name,raw)
    with tarfile.open(dist/'market_data-0.1.0.tar.gz','w:gz') as t:
        for name,raw in archive.items():
            member=tarfile.TarInfo('market_data-0.1.0/'+name);member.size=len(raw);t.addfile(member,io.BytesIO(raw))
    return sdk

def main():
    checker=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else pathlib.Path(__file__).with_name('check_market_package.py')
    modes=('positive','sql_changed','sql_missing','sql_extra','python_crlf','math_changed','math_missing','math_retired','math_crlf','sdist_sql_changed','duplicate_zip')
    results={}
    for mode in modes:
        with tempfile.TemporaryDirectory(prefix='package-gate-control-') as directory:
            root=pathlib.Path(directory);sdk=fixture(root,mode);previous=sys.argv;sys.argv=[str(checker),str(root),str(sdk)]
            try:
                with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(checker),run_name='__main__')
            except (AssertionError,KeyError,ValueError):accepted=False
            else:accepted=True
            finally:sys.argv=previous
            results[mode]=accepted
    print(json.dumps({'accepted':results,'scope':'INERT_PACKAGE_BYTES_NO_SDK_EXECUTION'}))
    assert results['positive'] and not any(v for k,v in results.items() if k!='positive'),'package gate accepted a malformed/raw-drifted fixture'

if __name__=='__main__':main()
