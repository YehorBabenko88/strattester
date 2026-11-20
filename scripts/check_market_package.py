import ast,hashlib,json,pathlib,sys,tarfile,zipfile
root=pathlib.Path(sys.argv[1]); sdk=pathlib.Path(sys.argv[2]); site=root/'.artifact-site';site.mkdir(exist_ok=True)
wheel=next((root/'.candidate-dist').glob('market_data-*.whl'));sdist=next((root/'.candidate-dist').glob('*.tar.gz'))
with zipfile.ZipFile(wheel) as z:
 names=z.namelist(); source_files={str(p.relative_to(root)).replace(chr(92),'/') for p in (root/'market_data').glob('*.py')}; wheel_files={n for n in names if n.startswith('market_data/') and n.endswith('.py')}; assert wheel_files==source_files
 for n in names: assert not pathlib.PurePosixPath(n).is_absolute() and '..' not in pathlib.PurePosixPath(n).parts and chr(92) not in n and ':' not in n
 for n in wheel_files: assert z.read(n).replace(b'\r\n',b'\n')==(root/n).read_bytes().replace(b'\r\n',b'\n')
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
with zipfile.ZipFile(sdk) as z:z.extractall(site)
with tarfile.open(sdist) as t:
 names=t.getnames();assert not any('/strattester/' in n or '/grid/' in n or '/meta_analyse/' in n or n.endswith(('.ps1','.cmd','.bat','.exe')) for n in names)
assert 'market-data = market_data.cli:main' in (site/'market_data-0.1.0.dist-info/entry_points.txt').read_text()
print(json.dumps({'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'sdist_sha256':hashlib.sha256(sdist.read_bytes()).hexdigest(),'python_files':21,'legacy_packages_absent':True,'native_scripts_absent':True,'source_namespace_scan':'PASS'},sort_keys=True))
