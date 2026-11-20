import ast,hashlib,json,pathlib,sys,tarfile,zipfile,tempfile
bindings={}
root=pathlib.Path(sys.argv[1]); sdk=pathlib.Path(sys.argv[2]); site=pathlib.Path(tempfile.mkdtemp(prefix='.artifact-site-',dir=root))
wheel=next((root/'.candidate-dist').glob('market_data-*.whl'));sdist=next((root/'.candidate-dist').glob('*.tar.gz'))
with zipfile.ZipFile(wheel) as z:
 names=z.namelist(); assert len(names)==len(set(names)); source_files={p.relative_to(root).as_posix() for p in (root/'market_data').iterdir() if p.suffix in ('.py','.sql')}; wheel_files={n for n in names if n.startswith('market_data/') and not n.endswith('/')}; assert wheel_files==source_files
 for n in names: assert not pathlib.PurePosixPath(n).is_absolute() and '..' not in pathlib.PurePosixPath(n).parts and chr(92) not in n and ':' not in n
 for n in wheel_files:
  assert z.read(n)==(root/n).read_bytes()
  bindings[n]=hashlib.sha256(z.read(n)).hexdigest()
 assert not any(n.startswith(('grid/','strattester/','meta_analyse/')) or n.endswith(('.ps1','.cmd','.bat','.exe')) for n in names)
 for name in names:
  if not name.endswith('.py'):continue
  tree=ast.parse(z.read(name))
  for node in ast.walk(tree):
   if isinstance(node,ast.Import): imports=[item.name for item in node.names]
   elif isinstance(node,ast.ImportFrom):imports=[node.module or '']
   else:continue
   assert not any(i.split('.')[0] in ('grid','strattester','meta_analyse','subprocess') for i in imports),(name,imports)
 z.extractall(site)
with zipfile.ZipFile(sdk) as z:
 math_files={n for n in z.namelist() if not n.endswith('/') and '.dist-info/' not in n}
 assert math_files=={'market_math.py','market_compute_api.py','history_statistics.py'}
 for n in math_files:
  assert z.read(n)==(root/'.source/math/python'/n).read_bytes()
  bindings[n]=hashlib.sha256(z.read(n)).hexdigest()
 z.extractall(site)
with tarfile.open(sdist) as t:
 names=t.getnames();assert len(names)==len(set(names));assert not any('/strattester/' in n or '/grid/' in n or '/meta_analyse/' in n or n.endswith(('.ps1','.cmd','.bat','.exe')) for n in names)
 for source in source_files:
  members=[n for n in names if n.endswith('/'+source)]
  assert len(members)==1 and t.extractfile(members[0]).read()==(root/source).read_bytes()
assert 'market-data = market_data.cli:main' in (site/'market_data-0.1.0.dist-info/entry_points.txt').read_text()
print(json.dumps({'bindings':bindings,'artifact_site':str(site),'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'sdist_sha256':hashlib.sha256(sdist.read_bytes()).hexdigest(),'runtime_files':len(wheel_files),'python_files':sum(n.endswith('.py') for n in wheel_files),'sql_files':sum(n.endswith('.sql') for n in wheel_files),'math_files':len(math_files),'byte_comparison':'RAW_IDENTICAL','legacy_packages_absent':True,'native_scripts_absent':True,'source_namespace_scan':'PASS'},sort_keys=True))
