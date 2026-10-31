"""CI metadata comes from bounded attributes, never trace bodies or raw secrets."""
from pathlib import Path
import subprocess
import sys
from xml.sax.saxutils import quoteattr

HELPER = Path(__file__).resolve().parents[2] / 'scripts/pytest_diagnostics.py'


def diagnose(path):
    return subprocess.run([sys.executable, str(HELPER), str(path)], capture_output=True, text=True, timeout=10)


def test_first_ten_failure_ids_and_attributes_preserve_report(tmp_path):
    report = tmp_path / 'report.xml'
    cases = ''.join('<testcase classname="tests.core" name="test_%d"><failure message="short-%d">TRACE_BODY_MUST_NOT_PRINT</failure></testcase>' % (i, i) for i in range(12))
    report.write_text('<testsuites><testsuite>' + cases + '<testcase name="passed"/><testcase name="skipped"><skipped/></testcase></testsuite></testsuites>')
    before = report.read_bytes()
    result = diagnose(report)
    assert result.returncode == 0
    annotations = [line for line in result.stdout.splitlines() if line.startswith('::error ')]
    assert len(annotations) == 10
    assert 'tests.core::test_0' in annotations[0] and 'short-0' in annotations[0]
    assert 'tests.core::test_9' in annotations[-1]
    assert 'test_10' not in result.stdout and 'test_11' not in result.stdout
    assert 'TRACE_BODY_MUST_NOT_PRINT' not in result.stdout
    assert report.read_bytes() == before


def test_credentials_urls_and_workflow_command_newlines_are_safe(tmp_path):
    report = tmp_path / 'report.xml'
    name = 'test_percent% [https://user:password123@example.invalid/path?token=secret123]'
    message = 'password=hunter22 api_key=private22 Authorization: Bearer ghp_privateToken12345\r\n::error title=Injected::untrusted%'
    report.write_text('<testsuite><testcase classname="tests.core" name=' + quoteattr(name) + '><error message=' + quoteattr(message) + '>PRIVATE_TRACE</error></testcase></testsuite>')
    result = diagnose(report)
    assert result.returncode == 0
    for secret in ('hunter22', 'private22', 'ghp_privateToken12345', 'password123', 'secret123', 'example.invalid', 'PRIVATE_TRACE'):
        assert secret not in result.stdout
    assert '%25' in result.stdout and '%0D%0A' in result.stdout
    assert len([line for line in result.stdout.splitlines() if line.startswith('::error ')]) == 1
    assert '[REDACTED]' in result.stdout


def test_dtd_and_entity_declarations_never_reach_parser_output(tmp_path):
    report = tmp_path / 'report.xml'
    xml = '<!DOCTYPE testsuite [<!ENTITY private "secret_do_not_print">]><testsuite><testcase name="test"><failure message="&private;"/></testcase></testsuite>'
    for encoding in ('utf-8', 'utf-16'):
        report.write_bytes(xml.encode(encoding))
        result = diagnose(report)
        assert result.returncode == 0
        assert 'secret_do_not_print' not in result.stdout
        assert not any(line.startswith('::error ') for line in result.stdout.splitlines())
        assert '::warning ' in result.stdout


def test_oversized_report_is_rejected_without_emitting_input(tmp_path):
    report = tmp_path / 'report.xml'
    report.write_bytes(b'x' * (16 * 1024 * 1024 + 1))
    result = diagnose(report)
    assert result.returncode == 0
    assert 'REPORT_TOO_LARGE' in result.stdout
    assert len(result.stdout) < 500


def test_missing_or_invalid_report_cannot_mask_original_pytest_outcome(tmp_path):
    report = tmp_path / 'report.xml'
    result = diagnose(report)
    assert result.returncode == 0 and 'REPORT_MISSING' in result.stdout
    report.write_text('<invalid secret="must_not_print"')
    result = diagnose(report)
    assert result.returncode == 0 and 'XML_INVALID' in result.stdout
    assert 'must_not_print' not in result.stdout


def test_quoted_credential_keys_cli_values_and_bare_auth_tokens_are_redacted(tmp_path):
    report = tmp_path / 'report.xml'
    message = "'password': 'quoted-private'; \"api_key\": \"json-private\"; --token cli-private; Bearer bearerPrivate99; sk-proj-privateKeyValue99"
    report.write_text('<testsuite><testcase name="test_auth"><failure message=' + quoteattr(message) + '/></testcase></testsuite>')
    result = diagnose(report)
    assert result.returncode == 0
    for secret in ('quoted-private', 'json-private', 'cli-private', 'bearerPrivate99', 'sk-proj-privateKeyValue99'):
        assert secret not in result.stdout
    assert 'test_auth' in result.stdout and '[REDACTED]' in result.stdout


def test_non_ascii_test_identifiers_do_not_break_ascii_ci_stdout(tmp_path, monkeypatch):
    report = tmp_path / 'report.xml'
    report.write_bytes('<testsuite><testcase classname="tests.unicode" name="test_\u2603"><failure message="expected\u2192actual"/></testcase></testsuite>'.encode('utf-8'))
    monkeypatch.setenv('PYTHONIOENCODING', 'ascii')
    result = diagnose(report)
    assert result.returncode == 0
    assert 'test_\\u2603' in result.stdout and 'expected\\u2192actual' in result.stdout
