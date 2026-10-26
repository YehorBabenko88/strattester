"""Malicious disposable-owned fixtures. Never run on LS5 or a physical target.

The broker stages this file and a pinned embedded CPython in a read-only LPAC
runtime. No probe accepts production paths or credentials from the CLI.
"""
import ctypes as c
from ctypes import wintypes as w
import json
import os
import sys
import time

k = c.WinDLL("kernel32", use_last_error=True)
a = c.WinDLL("advapi32", use_last_error=True)
k.GetCurrentProcess.restype = w.HANDLE
k.GetStdHandle.argtypes = [w.DWORD]
k.GetStdHandle.restype = w.HANDLE
k.CloseHandle.argtypes = [w.HANDLE]
a.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)]
a.GetTokenInformation.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)]


def guard():
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
            or os.environ.get("RUNNER_OS") != "Windows"
            or len(sys.argv) < 3 or sys.argv[1] != "COMPONENT_TESTS_ONLY"):
        raise RuntimeError("host guard")
    token = w.HANDLE()
    if not a.OpenProcessToken(k.GetCurrentProcess(), 8 | 2, c.byref(token)):
        raise c.WinError(c.get_last_error())
    try:
        for kind, expected in ((29, 1),):
            value, returned = w.DWORD(), w.DWORD()
            if not a.GetTokenInformation(token, kind, c.byref(value), 4, c.byref(returned)) or value.value != expected:
                raise RuntimeError("not LPAC")
        if package_access(token, "S-1-15-2-1") or not package_access(token, "S-1-15-2-2"):
            raise RuntimeError("LPAC authorization differential")
        for kind in (3, 30):
            returned = w.DWORD()
            a.GetTokenInformation(token, kind, None, 0, c.byref(returned))
            if not 4 <= returned.value <= 1048576:
                raise RuntimeError("token size")
            buffer = c.create_string_buffer(returned.value)
            if not a.GetTokenInformation(token, kind, buffer, len(buffer), c.byref(returned)) or w.DWORD.from_buffer(buffer).value:
                raise RuntimeError("token capabilities or privileges")
    finally:
        k.CloseHandle(token)
    allowed = {"GITHUB_ACTIONS", "RUNNER_ENVIRONMENT", "RUNNER_OS", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LOCALAPPDATA"}
    if set(key.upper() for key in os.environ) - allowed:
        raise RuntimeError("environment leaked")


class Mapping(c.Structure):
    _fields_ = [("read", w.DWORD), ("write", w.DWORD), ("execute", w.DWORD), ("all", w.DWORD)]


def package_access(primary, sid):
    a.DuplicateToken.argtypes = [w.HANDLE, c.c_int, c.POINTER(w.HANDLE)]
    a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [w.LPCWSTR, w.DWORD, c.POINTER(c.c_void_p), c.POINTER(w.DWORD)]
    a.AccessCheck.argtypes = [c.c_void_p, w.HANDLE, w.DWORD, c.POINTER(Mapping), c.c_void_p, c.POINTER(w.DWORD), c.POINTER(w.DWORD), c.POINTER(w.BOOL)]
    k.LocalFree.argtypes = [c.c_void_p]
    token, descriptor, size = w.HANDLE(), c.c_void_p(), w.DWORD()
    if not a.DuplicateToken(primary, 2, c.byref(token)):
        raise c.WinError(c.get_last_error())
    try:
        text = "O:SYG:SYD:(A;;0x1;;;WD)(A;;0x1;;;" + sid + ")"
        if not a.ConvertStringSecurityDescriptorToSecurityDescriptorW(text, 1, c.byref(descriptor), c.byref(size)):
            raise c.WinError(c.get_last_error())
        privileges, required, granted, status = c.create_string_buffer(1024), w.DWORD(1024), w.DWORD(), w.BOOL()
        mapping = Mapping(1, 2, 4, 7)
        if not a.AccessCheck(descriptor, token, 1, c.byref(mapping), privileges, c.byref(required), c.byref(granted), c.byref(status)):
            raise c.WinError(c.get_last_error())
        return bool(status.value and granted.value & 1)
    finally:
        if descriptor:
            k.LocalFree(descriptor)
        k.CloseHandle(token)


def denied_file(path, mode):
    try:
        with open(path, mode) as stream:
            if "w" in mode:
                stream.write(b"malicious owned mutation")
            else:
                stream.read(1)
    except PermissionError:
        return
    raise RuntimeError("filesystem access not denied")


def denied_acl_change(path):
    # Attempt to replace an owned fixture's DACL with a NULL DACL. Owner rights
    # must not let the lowbox grant itself unbounded filesystem output access.
    a.InitializeSecurityDescriptor.argtypes = [c.c_void_p, w.DWORD]
    a.SetSecurityDescriptorDacl.argtypes = [c.c_void_p, w.BOOL, c.c_void_p, w.BOOL]
    a.SetFileSecurityW.argtypes = [w.LPCWSTR, w.DWORD, c.c_void_p]
    descriptor = c.create_string_buffer(64)
    if not a.InitializeSecurityDescriptor(descriptor, 1) or not a.SetSecurityDescriptorDacl(descriptor, True, None, False):
        raise c.WinError(c.get_last_error())
    if a.SetFileSecurityW(path, 4, descriptor) or c.get_last_error() != 5:
        raise RuntimeError("ACL mutation not explicitly denied")


def denied_socket(family, kind, address, port):
    import socket
    try:
        with socket.socket(family, kind) as connection:
            connection.settimeout(1)
            if kind == socket.SOCK_STREAM:
                connection.connect((address, port))
            else:
                connection.sendto(b"owned malicious UDP", (address, port))
    except OSError as error:
        if getattr(error, "winerror", None) == 10013:
            return
        raise RuntimeError("socket denial was not WSAEACCES") from error
    raise RuntimeError("network access not denied")


class DnsRequest(c.Structure):
    _fields_ = [("version", w.ULONG), ("name", w.LPCWSTR), ("type", w.WORD),
                ("options", c.c_ulonglong), ("servers", c.c_void_p),
                ("interface", w.ULONG), ("completion", c.c_void_p), ("context", c.c_void_p)]


class DnsResult(c.Structure):
    _fields_ = [("version", w.ULONG), ("status", w.ULONG),
                ("options", c.c_ulonglong), ("records", c.c_void_p), ("reserved", c.c_void_p)]


def denied_dns(name):
    dns = c.WinDLL("dnsapi")
    dns.DnsQueryEx.argtypes = [c.POINTER(DnsRequest), c.POINTER(DnsResult), c.c_void_p]
    dns.DnsQueryEx.restype = w.ULONG
    dns.DnsRecordListFree.argtypes = [c.c_void_p, c.c_int]
    servers = c.create_string_buffer(96)
    w.ULONG.from_buffer(servers, 0).value = 1
    w.ULONG.from_buffer(servers, 4).value = 1
    w.WORD.from_buffer(servers, 32).value = 2
    w.ULONG.from_buffer(servers, 36).value = 0x0100007F
    query = DnsRequest(1, name, 1, 8, c.addressof(servers), 0, None, None)
    result = DnsResult(version=1)
    status = dns.DnsQueryEx(c.byref(query), c.byref(result), None)
    if result.records:
        dns.DnsRecordListFree(result.records, 1)
    if status != 5:
        raise RuntimeError("dns_status=" + str(status))


def adversarial(args):
    import socket
    import subprocess
    import winreg
    input_path, canary, profile, port4, port6, dns_name, parent, event, registry = args
    if sys.stdin.buffer.read(4) != b"abc":
        raise RuntimeError("input identity")
    k.WriteFile.argtypes = [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]
    count = w.DWORD()
    if k.WriteFile(k.GetStdHandle(0xFFFFFFF6), c.c_char_p(b"x"), 1, c.byref(count), None) or c.get_last_error() != 5:
        raise RuntimeError("inherited input writable")
    denied_file(input_path, "rb")
    denied_file(canary, "rb")
    denied_file("\\\\?\\" + canary, "rb")
    denied_file(canary, "wb")
    denied_file(canary + ":escape", "wb")
    denied_file(os.path.join(profile, "escape"), "wb")
    denied_file(os.path.join(os.path.dirname(profile), "escape"), "wb")
    denied_acl_change(profile)
    denied_acl_change(os.path.dirname(profile))
    denied_acl_change(os.path.dirname(sys.executable))
    print("CHECK:filesystem,input_handle,environment,acl_write", flush=True)
    for family, address, port in ((socket.AF_INET, "127.0.0.1", int(port4)), (socket.AF_INET6, "::1", int(port6))):
        denied_socket(family, socket.SOCK_STREAM, address, port)
        denied_socket(family, socket.SOCK_DGRAM, address, port)
    denied_socket(socket.AF_INET, socket.SOCK_DGRAM, "192.0.2.1", 53)
    denied_socket(socket.AF_INET6, socket.SOCK_DGRAM, "2001:db8::1", 53)
    print("CHECK:tcp_udp_ipv4_ipv6_loopback", flush=True)
    denied_dns(dns_name)
    print("CHECK:dns_service_proxy", flush=True)
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    process = k.OpenProcess(0x12, False, int(parent))
    if process:
        k.CloseHandle(process)
        raise RuntimeError("parent process readable")
    if c.get_last_error() != 5:
        raise RuntimeError("parent denial")
    k.OpenEventW.argtypes = [w.DWORD, w.BOOL, w.LPCWSTR]
    k.OpenEventW.restype = w.HANDLE
    handle = k.OpenEventW(2, False, event)
    if handle:
        k.CloseHandle(handle)
        raise RuntimeError("ordinary event namespace visible")
    if c.get_last_error() not in (2, 5):
        raise RuntimeError("event namespace denial")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry):
            pass
    except (PermissionError, FileNotFoundError):
        pass
    else:
        raise RuntimeError("registry namespace visible")
    try:
        child = subprocess.Popen([sys.executable, "-I", "-S", "-c", "raise SystemExit(212)"], close_fds=True)
    except OSError as error:
        if getattr(error, "winerror", None) not in (5, 1293):
            raise
    else:
        child.kill()
        child.wait(timeout=5)
        raise RuntimeError("child creation permitted")
    print("CHECK:parent_process,named_object,registry,child_creation", flush=True)
    return 200


def main():
    guard()
    mode = sys.argv[2]
    if mode == "adversarial":
        return adversarial(sys.argv[3:])
    if mode == "sleep":
        time.sleep(30)
        return 199
    if mode == "cpu":
        value = 0
        while True:
            value = (value * 1664525 + 1013904223) & 0xFFFFFFFF
    if mode == "output":
        block = bytes(65536)
        while True:
            sys.stdout.buffer.write(block)
            sys.stdout.buffer.flush()
    if mode == "memory":
        blocks = []
        try:
            while True:
                blocks.append(bytearray(4194304))
        except MemoryError:
            print("MEMORY_DENIED", end="", flush=True)
            return 205
    if mode == "synthetic":
        assert sys.stdin.buffer.read(4) == b"abc"
        values = [float(i) for i in range(1, 101)]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        print(json.dumps(dict(schema=1, synthetic_only=True, n=len(values), mean=mean, variance=variance), sort_keys=True, separators=(",", ":")))
        return 0
    raise RuntimeError("unknown mode")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("PROBE_FAIL:" + type(error).__name__ + ":" + str(error), flush=True)
        raise SystemExit(201)
