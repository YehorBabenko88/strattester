"""Proposed pure regression seam; SOURCE ONLY until Root allocates execution.

Future execution reads actual workflow/qualifier source, extracts actual AST
definitions, and compiles those definitions against inert fakes. It never imports
qualify.py, executes workflow top-level code, uses a real Popen/backend, creates
filesystem fixtures, or changes production/tests. Source extraction is the seam,
not a copied implementation. No results are claimed before an allocated RED.
"""
import ast
import hashlib
import io
from pathlib import Path, PurePosixPath
import stat
from types import SimpleNamespace
import traceback
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).absolute().parent
WORKFLOW = HERE.parents[4] / '.github/workflows/projection-recovery-47.yml'
QUALIFIER = HERE / 'qualify.py'


def workflow_definitions():
    lines = WORKFLOW.read_text(encoding='utf-8').splitlines()
    start = lines.index('        run: |') + 1
    body = []
    for line in lines[start:]:
        if line and not line.startswith('          '):
            break
        body.append(line[10:])
    parsed = ast.parse('\n'.join(body), filename=str(WORKFLOW))
    definitions = [node for node in parsed.body if isinstance(node, ast.FunctionDef)]
    if len([n for n in definitions if n.name == 'ledger']) != 1:
        raise AssertionError('Actual inline ledger definition required')
    return definitions


class InertTree:
    """Path metadata/content model. Every filesystem operation is an observation."""
    ROOT = '/sandbox/root'
    LEAF = '/sandbox/root/folder/item.txt'

    def __init__(self, blocked=None, kind=None):
        self.blocked = blocked
        self.kind = kind
        self.events = []
        self.payload_sha256 = None
        scenario = self

        class ModelPath(PurePosixPath):
            def resolve(self, *args, **kwargs):
                scenario.record('resolve', self)
                return self

            def is_symlink(self):
                scenario.record('is_symlink', self)
                return scenario.kind_for(self) == 'symlink'

            def is_dir(self):
                scenario.record('is_dir', self)
                return scenario.kind_for(self) in ('directory', 'reparse')

            def is_file(self):
                scenario.record('is_file', self)
                return scenario.kind_for(self) == 'file'

            def exists(self):
                scenario.record('exists', self)
                return scenario.kind_for(self) != 'missing'

            def lstat(self):
                scenario.record('lstat', self)
                kind = scenario.kind_for(self)
                if kind == 'missing':
                    raise FileNotFoundError(str(self))
                mode = stat.S_IFREG if kind == 'file' else stat.S_IFDIR
                if kind == 'symlink':
                    mode = stat.S_IFLNK
                return SimpleNamespace(st_mode=mode | 0o755, st_file_attributes=1024 if kind == 'reparse' else 0, st_nlink=1)

            def read_bytes(self):
                scenario.record('read_bytes', self)
                if str(self) != scenario.LEAF:
                    raise AssertionError('Only inert selected leaf may be read')
                return b'fixture bytes\n'

            def rglob(self, pattern):
                scenario.record('rglob', self)
                return iter([ModelPath('/sandbox/root/folder'), ModelPath(scenario.LEAF)])

            def iterdir(self):
                scenario.record('iterdir', self)
                if scenario.kind_for(self) != 'directory':
                    # Not caught as an expected source refusal by the nine
                    # cases: an unsafe listing must FAIL, never fake guard PASS.
                    raise TypeError('INERT_UNSAFE_DIRECTORY_LISTING_TRIPWIRE')
                if str(self) == scenario.ROOT:
                    return iter([ModelPath('/sandbox/root/folder')])
                if str(self) == '/sandbox/root/folder':
                    return iter([ModelPath(scenario.LEAF)])
                raise TypeError('INERT_UNEXPECTED_DIRECTORY_LISTING')

        self.Path = ModelPath
        self.root = ModelPath(self.ROOT)

    def kind_for(self, path):
        if str(path) == self.blocked:
            return self.kind
        return 'file' if str(path) == self.LEAF else 'directory'

    def record(self, operation, path):
        self.events.append((operation, str(path)))

    def git(self, root, *args, data=None):
        self.record('git', root)
        payload = b'fixture bytes\n'
        oid = hashlib.sha1(b'blob ' + str(len(payload)).encode() + b'\0' + payload).hexdigest().encode()
        if args == ('rev-parse', 'HEAD'):
            return b'1' * 40 + b'\n'
        if args == ('for-each-ref', 'refs/replace', '--format=%(refname)'):
            return b''
        if args == ('rev-parse', 'HEAD^{tree}'):
            return b'2' * 40 + b'\n'
        if args == ('ls-tree', '-rz', '--full-tree', 'HEAD'):
            return b'100644 blob ' + oid + b'\tfolder/item.txt\0'
        if args == ('cat-file', '--batch'):
            return oid + b' blob ' + str(len(payload)).encode() + b'\n' + payload + b'\n'
        raise AssertionError('Unexpected Git request in inert backend')

    def sha256(self, raw):
        self.events.append(('sha256', '<payload>'))
        result = hashlib.sha256(raw)
        self.payload_sha256 = result.hexdigest()
        return result

    def ledger(self):
        env = {'pathlib': SimpleNamespace(PurePosixPath=PurePosixPath, Path=self.Path),
               'Path': self.Path, 'stat': stat, 'io': io,
               'os': SimpleNamespace(), 'hashlib': SimpleNamespace(sha1=hashlib.sha1, sha256=self.sha256)}
        # Actual definitions only; imports, checkout, subprocess and writes from
        # the workflow are excluded. The actual g name is replaced with inert g.
        module = ast.Module(body=workflow_definitions(), type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(WORKFLOW), 'exec'), env)
        env['g'] = self.git
        return env['ledger'](self.root, '1' * 40, 1)


class RootFirstControls(unittest.TestCase):
    def assert_unsafe_parent_refuses_before_descendants(self, kind):
        tree = InertTree('/sandbox', kind)
        result = None
        caught = None
        try:
            result = tree.ledger()
        except (AssertionError, RuntimeError, OSError) as error:
            caught = error
        descendant_events = [(op, path) for op, path in tree.events
                             if path.startswith('/sandbox/') or op in ('git', 'sha256')]
        self.assertEqual(descendant_events, [], 'Unsafe parent must stop before root/descendant/Git/hash access')
        self.assertIsNotNone(caught, 'Unsafe ancestry must be refused')
        self.assertIsNone(result, 'Unsafe ancestry cannot yield a ledger')
        self.assertIsNone(tree.payload_sha256, 'Failure observation hash must remain null')

    def test_reparse_parent_stops_before_descendant_or_git(self):
        self.assert_unsafe_parent_refuses_before_descendants('reparse')

    def test_file_parent_stops_before_descendant_or_git(self):
        self.assert_unsafe_parent_refuses_before_descendants('file')

    def test_missing_parent_stops_before_descendant_or_git(self):
        self.assert_unsafe_parent_refuses_before_descendants('missing')

    def test_file_root_stops_before_leaf_git_or_hash(self):
        tree = InertTree(InertTree.ROOT, 'file')
        result = None
        caught = None
        try:
            result = tree.ledger()
        except (AssertionError, RuntimeError, OSError) as error:
            caught = error
        self.assertFalse(any(op in ('git', 'sha256') or path.startswith(tree.ROOT + '/') for op, path in tree.events))
        self.assertIsNotNone(caught)
        self.assertIsNone(result)
        self.assertIsNone(tree.payload_sha256)

    def test_selected_reparse_parent_stops_before_leaf_inspection(self):
        tree = InertTree('/sandbox/root/folder', 'reparse')
        result = None
        caught = None
        try:
            result = tree.ledger()
        except (AssertionError, RuntimeError, OSError) as error:
            caught = error
        self.assertFalse(any(path == tree.LEAF for _, path in tree.events), 'Selected leaf cannot be inspected through unsafe parent')
        self.assertIsNotNone(caught)
        self.assertIsNone(result)
        self.assertIsNone(tree.payload_sha256)

    def test_ordinary_tree_retains_exact_blob_and_ledger(self):
        tree = InertTree()
        actual_tree, ledger = tree.ledger()
        self.assertEqual(actual_tree, '2' * 40)
        self.assertEqual(ledger, {'folder/item.txt': {'bytes': 14, 'sha256': hashlib.sha256(b'fixture bytes\n').hexdigest()}})


def actual_class_seam():
    parsed = ast.parse(QUALIFIER.read_text(encoding='utf-8'), filename=str(QUALIFIER))
    run = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    cls = [n for n in ast.walk(run) if isinstance(n, ast.ClassDef) and n.name == 'OwnedPopen']
    need = [n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == 'need']
    path_helpers = [n for n in parsed.body if isinstance(n, ast.FunctionDef)
                    and n.name in ('ordinary', 'absent', 'admit_child_paths')]
    for required in ('ordinary', 'absent'):
        if len([n for n in path_helpers if n.name == required]) != 1:
            raise AssertionError('Actual path helper required: ' + required)
    if len([n for n in path_helpers if n.name == 'admit_child_paths']) > 1:
        raise AssertionError('Ambiguous actual child path-admission helper')
    outer_try = next(n for n in run.body if isinstance(n, ast.Try))
    held_loops = [n for n in outer_try.finalbody if isinstance(n, ast.For)
                  and isinstance(n.target, ast.Name) and n.target.id == 'child'
                  and isinstance(n.iter, ast.Name) and n.iter.id == 'held']
    cleanup = [loop for loop in held_loops
               if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))
                          for n in ast.walk(loop))
               and {'kill', 'wait'}.issubset({
                   n.func.attr for n in ast.walk(loop)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and isinstance(n.func.value, ast.Name) and n.func.value.id == 'child'
               })]
    if len(cls) != 1 or len(need) != 1 or len(cleanup) != 1:
        raise AssertionError('One actual OwnedPopen/need/held-handle cleanup loop required')
    # Synthetic binding wrapper only; actual class and cleanup loop AST unchanged.
    wrapper = ast.parse('def seam():\n pending=None\n stopped=False\n def cleanup():\n  nonlocal stopped\n  stopped=True\n return None\n').body[0]
    cleanup_wrapper = wrapper.body[-2]
    cleanup_wrapper.body.extend(cleanup)
    wrapper.body.insert(2, cls[0])
    wrapper.body[-1] = ast.Return(value=ast.Tuple(elts=[ast.Name(id='OwnedPopen', ctx=ast.Load()), ast.Name(id='cleanup', ctx=ast.Load())], ctx=ast.Load()))
    return ast.Module(body=[need[0], *path_helpers, wrapper], type_ignores=[])


class ReturnedHandleControls(unittest.TestCase):
    def make_seam(self, path_tree=None):
        state = {'creation_intents': [], 'held_children': [], 'errors': [], 'cleanup_uncertain': False}
        held, effects = [], []

        class ModelPath(PurePosixPath):
            def resolve(self, *args, **kwargs):
                return self

            @classmethod
            def cwd(cls):
                return cls('/source')

            def lstat(self):
                if path_tree is not None:
                    return path_tree.lstat_path(str(self))
                directories = {'/', '/source', '/owned', '/owned/temp', '/owned/temp/case'}
                files = {'/python', '/source/helper.py', '/owned/temp/case/own.sqlite'}
                if str(self) == '/owned/temp/case/phase.marker':
                    raise FileNotFoundError(str(self))
                if str(self) not in directories | files:
                    raise TypeError('INERT_UNEXPECTED_LIFECYCLE_PATH')
                return SimpleNamespace(st_mode=(stat.S_IFREG if str(self) in files else stat.S_IFDIR) | 0o755,
                                       st_file_attributes=0, st_nlink=1, st_size=1)

        class InertSuccessfulPopen:
            def __init__(self, command, **kwargs):
                effects.append('constructor_returned')
                self.pid = 7001
                self.returncode = None
                # Deliberately leave the allowance pending. Actual class must
                # refuse this invariant, but still retain the returned handle.

            def poll(self):
                return self.returncode

            def kill(self):
                effects.append('kill_held_handle')

            def wait(self, timeout):
                effects.append(('wait_held_handle', timeout))
                if 'kill_held_handle' not in effects:
                    raise AssertionError('wait must follow kill')
                self.returncode = -1
                return self.returncode

        main = object()
        env = {'original_popen': InertSuccessfulPopen, 'state': state, 'held': held,
               'Path': ModelPath, 'target': ModelPath('/source'), 'real': ModelPath('/python'),
               'helper': ModelPath('/source/helper.py'), 'temp': ModelPath('/owned/temp'),
               'CHILD_PHASES': ('BEFORE_COMMIT', 'AFTER_COMMIT', 'AFTER_COMMIT'),
               'started': 0, 'time': SimpleNamespace(monotonic=lambda: 1), 'traceback': traceback, 'stat': stat,
               'threading': SimpleNamespace(current_thread=lambda: main, main_thread=lambda: main, get_ident=lambda: 1),
               'subprocess': SimpleNamespace(PIPE=-1, CREATE_NO_WINDOW=0x08000000, list2cmdline=lambda args: ' '.join(args))}
        exec(compile(ast.fix_missing_locations(actual_class_seam()), str(QUALIFIER), 'exec'), env)
        creator, cleanup = env['seam']()
        command = ['/python', '-I', '-S', '-B', '/source/helper.py', 'BEFORE_COMMIT', '/owned/temp/case/own.sqlite', '/owned/temp/case/phase.marker']
        kwargs = {'stdout': -1, 'stderr': -1, 'creationflags': 0x08000000}
        return creator, cleanup, command, kwargs, held, effects, state

    def test_returned_handle_registered_before_invariant_refusal(self):
        creator, _, command, kwargs, held, effects, state = self.make_seam()
        with self.assertRaisesRegex(RuntimeError, 'Audit allowance not consumed'):
            creator(command, **kwargs)
        self.assertEqual(effects, ['constructor_returned'])
        self.assertEqual(len(held), 1, 'Returned backend handle must already be in cleanup registry')
        self.assertTrue(state['cleanup_uncertain'], 'Invariant refusal must not become success')

    def test_invariant_refusal_cleanup_kills_and_waits_known_handle(self):
        creator, cleanup, command, kwargs, held, effects, state = self.make_seam()
        with self.assertRaisesRegex(RuntimeError, 'Audit allowance not consumed'):
            creator(command, **kwargs)
        cleanup()  # Actual finally-loop AST, inert handles only.
        self.assertEqual(effects, ['constructor_returned', 'kill_held_handle', ('wait_held_handle', 2)])
        self.assertEqual(len(held), 1)
        self.assertIsNotNone(held[0].poll())
        self.assertTrue(state['cleanup_required'])

    def test_preconstructor_refusal_creates_no_handle(self):
        creator, _, command, kwargs, held, effects, _ = self.make_seam()
        kwargs['shell'] = True
        with self.assertRaisesRegex(RuntimeError, 'No cwd/env/shell override'):
            creator(command, **kwargs)
        self.assertEqual(held, [])
        self.assertEqual(effects, [])


class PathAdmissionProbe:
    """New controls' inert metadata; no filesystem guard or runtime grant."""
    XML_PATH = '/unit/evidence/pytest.xml'
    DB = '/owned/temp/case/own.sqlite'
    MARKER = '/owned/temp/case/phase.marker'

    def __init__(self):
        self.entries = {p: 'directory' for p in ('/', '/source', '/unit', '/unit/evidence',
                                                '/owned', '/owned/temp', '/owned/temp/case')}
        self.entries.update({'/python': 'file', '/source/helper.py': 'file',
                             self.XML_PATH: 'file', self.DB: 'file', self.MARKER: 'missing'})
        self.events = []
        self.reported_xml_size = None
        self.ids = ['tests/fixed_module.py::test_fixed_%02d' % i for i in range(47)]
        self.xml_bytes = ('<testsuites><testsuite tests="47" failures="0" errors="0" skipped="0">'
                          + ''.join('<testcase classname="tests.fixed_module" name="test_fixed_%02d" />' % i for i in range(47))
                          + '</testsuite></testsuites>').encode('ascii')
        probe = self

        class ProbePath(PurePosixPath):
            def absolute(self):
                return self

            def resolve(self, *args, **kwargs):
                raise TypeError('INERT_RESOLVE_FOLLOWING_NOT_ALLOWED')

            def lstat(self):
                return probe.lstat_path(str(self))

            def read_bytes(self):
                probe.events.append(('file_read', str(self)))
                if str(self) != probe.XML_PATH:
                    raise TypeError('INERT_UNEXPECTED_FILE_READ')
                return probe.xml_bytes

            def open(self, mode='r', *args, **kwargs):
                probe.events.append(('file_open', str(self)))
                if str(self) != probe.XML_PATH or mode != 'rb':
                    raise TypeError('INERT_ONLY_XML_BINARY_READ_SUPPORTED')
                return io.BytesIO(probe.xml_bytes)

        self.Path = ProbePath

    def lstat_path(self, path):
        self.events.append(('lstat', path))
        kind = self.entries.get(path, 'missing')
        if kind == 'missing':
            raise FileNotFoundError(path)
        mode = stat.S_IFDIR if kind in ('directory', 'reparse-directory') else stat.S_IFREG
        size = len(self.xml_bytes) if path == self.XML_PATH else 1
        if path == self.XML_PATH and self.reported_xml_size is not None:
            size = self.reported_xml_size
        return SimpleNamespace(st_mode=mode | 0o755, st_nlink=1, st_size=size,
                               st_file_attributes=1024 if kind.startswith('reparse-') else 0)

    def sha256(self, raw):
        self.events.append(('payload_hash', '<bytes>'))
        return hashlib.sha256(raw)

    def parse(self, path):
        self.events.append(('xml_parse', str(path)))
        # Pure XML bytes only: never invoke a real file parser on the fake path.
        raw = path.read() if hasattr(path, 'read') else self.xml_bytes
        return ET.ElementTree(ET.fromstring(raw))

    def fromstring(self, raw):
        self.events.append(('xml_fromstring', '<bytes>'))
        if type(raw) is not bytes or raw != self.xml_bytes:
            raise TypeError('EXACT_INERT_XML_BYTES_REQUIRED')
        return ET.fromstring(raw)

    def junit(self):
        parsed = ast.parse(QUALIFIER.read_text(encoding='utf-8'), filename=str(QUALIFIER))
        names = ('need', 'ordinary', 'digest', 'junit_facts')
        functions = []
        for name in names:
            matches = [n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == name]
            if len(matches) != 1:
                raise AssertionError('Actual parser dependency required: ' + name)
            functions.extend(matches)
        env = {'stat': stat, 'Path': self.Path,
               'hashlib': SimpleNamespace(sha256=self.sha256),
               'ET': SimpleNamespace(parse=self.parse, fromstring=self.fromstring, ParseError=ET.ParseError)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), str(QUALIFIER), 'exec'), env)
        return env['junit_facts'](self.Path(self.XML_PATH), self.ids)


class JunitAdmissionControls(unittest.TestCase):
    def assert_refused_before_parser_read_hash(self, probe):
        caught, result = None, None
        try:
            result = probe.junit()
        except (AssertionError, RuntimeError, OSError) as error:
            caught = error
        self.assertEqual([event for event in probe.events
                          if event[0] in ('xml_parse', 'xml_fromstring', 'file_open', 'file_read', 'payload_hash')], [])
        self.assertIsNotNone(caught)
        self.assertIsNone(result)

    def test_reparse_xml_parent_refuses_before_parser_read_hash(self):
        probe = PathAdmissionProbe()
        probe.entries['/unit/evidence'] = 'reparse-directory'
        self.assert_refused_before_parser_read_hash(probe)

    def test_file_xml_parent_refuses_before_parser_read_hash(self):
        probe = PathAdmissionProbe()
        probe.entries['/unit/evidence'] = 'file'
        self.assert_refused_before_parser_read_hash(probe)

    def test_oversized_xml_refuses_before_parser_read_hash(self):
        probe = PathAdmissionProbe()
        # Proposed 16MiB profile cap, to be reviewed before implementation.
        # Only metadata is large; no large allocation/file is created.
        probe.reported_xml_size = 16 * 1024 * 1024 + 1
        self.assert_refused_before_parser_read_hash(probe)

    def test_ordinary_bounded_xml_preserves_exact_47_facts_control(self):
        probe = PathAdmissionProbe()
        facts = probe.junit()
        self.assertEqual(facts, {'counts': {'tests': 47, 'failures': 0, 'errors': 0, 'skipped': 0},
                                 'unique': 47, 'sha256': hashlib.sha256(probe.xml_bytes).hexdigest()})


class ChildPathAdmissionControls(unittest.TestCase):
    def create(self, probe):
        lifecycle = ReturnedHandleControls('test_preconstructor_refusal_creates_no_handle')
        return lifecycle.make_seam(path_tree=probe)

    def assert_refused_before_backend(self, probe):
        creator, _, command, kwargs, held, effects, _ = self.create(probe)
        with self.assertRaises((AssertionError, RuntimeError, OSError)):
            creator(command, **kwargs)
        self.assertEqual(effects, [], 'Path refusal must precede inert backend construction')
        self.assertEqual(held, [])

    def assert_valid_paths_reach_backend(self, probe):
        creator, _, command, kwargs, held, effects, _ = self.create(probe)
        # Existing post-constructor allowance invariant is deliberately refused;
        # reaching the fake backend is the local-path positive control only.
        with self.assertRaisesRegex(RuntimeError, 'Audit allowance not consumed'):
            creator(command, **kwargs)
        self.assertEqual(effects, ['constructor_returned'])
        self.assertEqual(len(held), 1)

    def test_temp_junction_refuses_before_backend(self):
        probe = PathAdmissionProbe()
        probe.entries['/owned/temp'] = 'reparse-directory'
        self.assert_refused_before_backend(probe)

    def test_db_parent_junction_refuses_before_backend(self):
        probe = PathAdmissionProbe()
        probe.entries['/owned/temp/case'] = 'reparse-directory'
        self.assert_refused_before_backend(probe)

    def test_db_parent_file_refuses_before_backend(self):
        probe = PathAdmissionProbe()
        probe.entries['/owned/temp/case'] = 'file'
        self.assert_refused_before_backend(probe)

    def test_db_reparse_leaf_refuses_before_backend(self):
        probe = PathAdmissionProbe()
        probe.entries[probe.DB] = 'reparse-file'
        self.assert_refused_before_backend(probe)

    def test_marker_reparse_leaf_refuses_before_backend(self):
        probe = PathAdmissionProbe()
        probe.entries[probe.MARKER] = 'reparse-file'
        self.assert_refused_before_backend(probe)

    def test_ordinary_db_absent_marker_reaches_backend_control(self):
        self.assert_valid_paths_reach_backend(PathAdmissionProbe())

    def test_ordinary_db_existing_marker_reaches_backend_control(self):
        probe = PathAdmissionProbe()
        probe.entries[probe.MARKER] = 'file'
        self.assert_valid_paths_reach_backend(probe)


def actual_held_cleanup_seam(lane):
    """Select actual named-function cleanup and its actual denial predicate."""
    parsed = ast.parse(QUALIFIER.read_text(encoding='utf-8'), filename=str(QUALIFIER))
    functions = {n.name: n for n in parsed.body if isinstance(n, ast.FunctionDef)}
    name = 'controls' if lane == 'controls' else 'run'
    function = functions[name]
    tries = [n for n in function.body if isinstance(n, ast.Try)]
    if len(tries) != 1:
        raise AssertionError('One actual outer cleanup Try required')
    final = tries[0].finalbody
    if lane == 'controls':
        branches = [n for n in final if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
                    and isinstance(n.test.left, ast.Name) and n.test.left.id == 'child'
                    and len(n.test.ops) == len(n.test.comparators) == 1
                    and isinstance(n.test.ops[0], ast.IsNot)
                    and isinstance(n.test.comparators[0], ast.Constant) and n.test.comparators[0].value is None]
        predicates = [n for n in final if isinstance(n, ast.Assign) and len(n.targets) == 1
                      and isinstance(n.targets[0], ast.Subscript)
                      and isinstance(n.targets[0].value, ast.Name) and n.targets[0].value.id == 'record'
                      and isinstance(n.targets[0].slice, ast.Constant) and n.targets[0].slice.value == 'observed_pass']
        if len(branches) != len(predicates) or len(branches) != 1:
            raise AssertionError('Actual controls held cleanup and observed-pass predicate required')
        wrapper = ast.parse('def cleanup(child, record):\n pass\n').body[0]
        wrapper.body = [branches[0], predicates[0]]
        module = ast.Module(body=[functions['need'], wrapper], type_ignores=[])
        env = {'traceback': traceback}
        exec(compile(ast.fix_missing_locations(module), str(QUALIFIER), 'exec'), env)
        return env['cleanup'], None
    if lane != 'run':
        raise AssertionError('Only actual controls/run cleanup lanes allowed')
    loops = [n for n in final if isinstance(n, ast.For)
             and isinstance(n.target, ast.Name) and n.target.id == 'child'
             and isinstance(n.iter, ast.Name) and n.iter.id == 'held'
             and not any(isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)) for x in ast.walk(n))
             and {'kill', 'wait'}.issubset({x.func.attr for x in ast.walk(n)
                 if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                 and isinstance(x.func.value, ast.Name) and x.func.value.id == 'child'})]
    gates = [n for n in ast.walk(functions['verify']) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
             and isinstance(n.value.func, ast.Name) and n.value.func.id == 'need'
             and len(n.value.args) == 2 and isinstance(n.value.args[1], ast.Constant)
             and n.value.args[1].value == 'Retirement/cleanup not established']
    if len(loops) != len(gates) or len(loops) != 1:
        raise AssertionError('Actual main held cleanup and verify retirement-denial gate required')
    wrapper = ast.parse('def cleanup(held, state):\n pass\n').body[0]
    wrapper.body = [loops[0]]
    denial = ast.parse('def deny(candidate):\n pass\n').body[0]
    denial.body = [gates[0]]
    env = {'traceback': traceback}
    module = ast.Module(body=[functions['need'], wrapper, denial], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(QUALIFIER), 'exec'), env)
    return env['cleanup'], env['deny']


class InertHeldCleanupHandle:
    def __init__(self, poll_error=False, kill_error=False, wait_error=False):
        self.poll_error = poll_error
        self.kill_error = kill_error
        self.wait_error = wait_error
        self.returncode = None
        self.events = []

    def poll(self):
        self.events.append('poll')
        if self.poll_error:
            raise OSError('INERT_POLL_FAILURE')
        return self.returncode

    def kill(self):
        self.events.append('kill')
        if self.kill_error:
            raise OSError('INERT_KILL_FAILURE')

    def wait(self, timeout):
        self.events.append(('wait', timeout))
        if self.wait_error:
            raise OSError('INERT_WAIT_FAILURE')
        self.returncode = -1
        return self.returncode


def assert_actual_cleanup(case, lane, poll_error=False, kill_error=False, wait_error=False):
    cleanup, denial = actual_held_cleanup_seam(lane)
    handle = InertHeldCleanupHandle(poll_error, kill_error, wait_error)
    facts = {'errors': [], 'cleanup_uncertain': False, 'child': {'pid': 7001, 'identity': 'INERT_HELD_HANDLE'},
             'creation_status': 'HELD', 'remaining_new_threads': []}
    if lane == 'controls':
        cleanup(handle, facts)
    else:
        cleanup([handle], facts)
    case.assertEqual(handle.events.count('kill'), 1, 'Known returned handle must get one best-effort kill attempt')
    case.assertEqual(handle.events.count(('wait', 2)), 1, 'Wait must be attempted even when poll/kill fails')
    if poll_error or kill_error or wait_error:
        case.assertTrue(facts['cleanup_uncertain'], 'UNKNOWN must remain sticky after cleanup errors')
        case.assertTrue(facts['errors'], 'Cleanup failure evidence must be retained')
    else:
        case.assertFalse(facts['cleanup_uncertain'])
        case.assertEqual(facts['errors'], [])
        case.assertIsNotNone(handle.returncode)
    if lane == 'controls':
        case.assertIs(facts['observed_pass'], False, 'Actual controller predicate must deny uncertain/unexpected cleanup')
    else:
        with case.assertRaisesRegex(RuntimeError, 'Retirement/cleanup not established'):
            denial(facts)  # Actual verify predicate, not a fake runtime permit.


class ControlsHeldCleanupControls(unittest.TestCase):
    def test_poll_error_attempts_kill_and_wait_and_denies(self):
        assert_actual_cleanup(self, 'controls', poll_error=True)

    def test_poll_and_kill_error_still_attempts_wait_and_denies(self):
        assert_actual_cleanup(self, 'controls', poll_error=True, kill_error=True)

    def test_poll_and_wait_error_keeps_unknown_and_denies(self):
        assert_actual_cleanup(self, 'controls', poll_error=True, wait_error=True)

    def test_normal_running_handle_cleanup_control(self):
        assert_actual_cleanup(self, 'controls')


class MainRunHeldCleanupControls(unittest.TestCase):
    def test_poll_error_attempts_kill_and_wait_and_denies(self):
        assert_actual_cleanup(self, 'run', poll_error=True)

    def test_poll_and_kill_error_still_attempts_wait_and_denies(self):
        assert_actual_cleanup(self, 'run', poll_error=True, kill_error=True)

    def test_poll_and_wait_error_keeps_unknown_and_denies(self):
        assert_actual_cleanup(self, 'run', poll_error=True, wait_error=True)

    def test_normal_running_handle_cleanup_control(self):
        assert_actual_cleanup(self, 'run')


if __name__ == '__main__':
    unittest.main(verbosity=2)
