// Actual malicious owned-fixture experiments; only execute on disposable hosted Windows.
using System;
using System.Collections;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using Microsoft.Win32;

namespace StratTester.Native {
    internal static class SandboxProbes {
        internal static string Phase = "INITIAL", LastDetail = "NONE";
        private static readonly SandboxLimits Normal = new SandboxLimits(536870912, 10000, 100000000, 15000, 32768);
        internal static int Probe(string[] args) {
            if (!Broker.HostedVm() || args.Length < 3 || args[1] != "COMPONENT_TESTS_ONLY" || !OwnLpac()) return 198;
            string mode = args[2];
            if (mode == "sleep") { Thread.Sleep(30000); return 199; }
            if (mode == "output") { byte[] bytes = new byte[65536]; while (true) Console.OpenStandardOutput().Write(bytes, 0, bytes.Length); }
            if (mode == "cpu") { ulong i = 0; while (true) { i = unchecked(i * 1664525 + 1013904223); if (i == UInt64.MaxValue) Console.Write(i); } }
            if (mode == "memory") {
                var blocks = new List<byte[]>();
                try { while (true) { byte[] block = new byte[4194304]; for (int i = 0; i < block.Length; i += 4096) block[i] = 1; blocks.Add(block); } }
                catch (OutOfMemoryException) { Console.Write("MEMORY_DENIED"); return 205; }
            }
            if (mode != "adversarial" || args.Length != 12) return 197;
            try {
                CheckEnvironment();
                using (Stream input = Console.OpenStandardInput()) {
                    byte[] bytes = new byte[4]; int read = input.Read(bytes, 0, bytes.Length);
                    if (read != 3 || bytes[0] != 97 || bytes[1] != 98 || bytes[2] != 99) throw new InvalidOperationException("Input");
                }
                DenyFileRead(args[3]); DenyFileRead(args[4]);
                DenyFileWrite(args[4]); DenyFileWrite(Path.Combine(args[5], "escape"));
                // The inherited input is read-only even though the parent owns it.
                uint written;
                using (var stdin = new KernelHandle(SandboxProbeNative.GetStdHandle(-10), false)) {
                    if (Native.WriteFile(stdin, new byte[] { 120 }, 1, out written, IntPtr.Zero) || Marshal.GetLastWin32Error() != 5) throw new InvalidOperationException("Input write");
                }
                Console.WriteLine("CHECK:filesystem,input_handle,environment");
                int port4 = Int32.Parse(args[6]), port6 = Int32.Parse(args[7]);
                DenySocket(AddressFamily.InterNetwork, SocketType.Stream, IPAddress.Loopback, port4);
                DenySocket(AddressFamily.InterNetworkV6, SocketType.Stream, IPAddress.IPv6Loopback, port6);
                DenySocket(AddressFamily.InterNetwork, SocketType.Dgram, IPAddress.Loopback, port4);
                DenySocket(AddressFamily.InterNetworkV6, SocketType.Dgram, IPAddress.IPv6Loopback, port6);
                DenySocket(AddressFamily.InterNetwork, SocketType.Dgram, IPAddress.Parse("192.0.2.1"), 53);
                DenySocket(AddressFamily.InterNetworkV6, SocketType.Dgram, IPAddress.Parse("2001:db8::1"), 53);
                Console.WriteLine("CHECK:tcp_udp_ipv4_ipv6_loopback");
                uint dns = QueryOwnedDns(args[8]);
                if (dns != 5) { Console.WriteLine("DNS_RESULT:" + dns); return 211; }
                Console.WriteLine("CHECK:dns_service_proxy");
                IntPtr parent = SandboxProbeNative.OpenProcess(0x10 | 0x2, false, UInt32.Parse(args[9]));
                if (parent != IntPtr.Zero) { Native.CloseHandle(parent); throw new InvalidOperationException("Parent process access"); }
                if (Marshal.GetLastWin32Error() != 5) throw new InvalidOperationException("Parent process error");
                IntPtr named = SandboxProbeNative.OpenEvent(2, false, args[10]);
                if (named != IntPtr.Zero) { Native.CloseHandle(named); throw new InvalidOperationException("Event namespace escape"); }
                // The ordinary user namespace must not be visible from the lowbox.
                int eventError = Marshal.GetLastWin32Error(); if (eventError != 2 && eventError != 5) throw new InvalidOperationException("Event namespace error");
                bool registryDenied = false;
                try { using (var key = Registry.CurrentUser.OpenSubKey(args[11])) { registryDenied = key == null; } }
                catch (UnauthorizedAccessException) { registryDenied = true; }
                catch (System.Security.SecurityException) { registryDenied = true; }
                if (!registryDenied) throw new InvalidOperationException("Registry escape");
                bool childDenied = false;
                try {
                    var start = new ProcessStartInfo(typeof(Broker).Assembly.Location, "--owned-sandbox-probe COMPONENT_TESTS_ONLY sleep") { UseShellExecute = false, CreateNoWindow = true };
                    using (var child = Process.Start(start)) { if (child != null) { child.Kill(); child.WaitForExit(5000); } }
                } catch (Win32Exception error) { childDenied = error.NativeErrorCode == 5 || error.NativeErrorCode == 1293; }
                if (!childDenied) throw new InvalidOperationException("Child creation");
                Console.WriteLine("CHECK:parent_process,named_object,registry,child_creation");
                return 200;
            } catch (Exception error) { Console.WriteLine("PROBE_FAIL:" + error.GetType().Name + ":" + error.Message); return 201; }
        }
        private static bool OwnLpac() {
            KernelHandle token;
            if (!Native.OpenProcessToken(Native.GetCurrentProcess(), 8 | 2, out token)) return false;
            using (token) return AppContainerProfile.ReadScalar(token, 29) == 1 && AppContainerProfile.IsLpac(token) && AppContainerProfile.ReadScalar(token, 30) == 0;
        }
        private static void CheckEnvironment() {
            string[] names = { "GITHUB_ACTIONS", "RUNNER_ENVIRONMENT", "RUNNER_OS", "SystemRoot", "WINDIR", "TEMP", "TMP", "LOCALAPPDATA" };
            foreach (DictionaryEntry item in Environment.GetEnvironmentVariables()) {
                bool found = false; foreach (string name in names) if (String.Equals(name, (string)item.Key, StringComparison.OrdinalIgnoreCase)) found = true;
                if (!found) throw new InvalidOperationException("Environment leaked");
            }
        }
        private static void DenyFileRead(string path) {
            bool denied = false;
            try { using (File.OpenRead(path)) { } } catch (UnauthorizedAccessException) { denied = true; }
            if (!denied) throw new InvalidOperationException("File read escape");
        }
        private static void DenyFileWrite(string path) {
            bool denied = false;
            try { File.WriteAllText(path, "owned malicious mutation"); } catch (UnauthorizedAccessException) { denied = true; }
            if (!denied) throw new InvalidOperationException("File write escape");
        }
        private static void DenySocket(AddressFamily family, SocketType type, IPAddress address, int port) {
            bool denied = false;
            try {
                using (var socket = new Socket(family, type, type == SocketType.Stream ? ProtocolType.Tcp : ProtocolType.Udp)) {
                    socket.SendTimeout = 500; socket.ReceiveTimeout = 500;
                    if (type == SocketType.Stream) socket.Connect(new IPEndPoint(address, port));
                    else socket.SendTo(new byte[] { 1, 2, 3 }, new IPEndPoint(address, port));
                }
            } catch (SocketException error) { denied = error.SocketErrorCode == SocketError.AccessDenied; }
            if (!denied) throw new InvalidOperationException("Socket access not explicitly denied");
        }
        private static uint QueryOwnedDns(string name) {
            // Documented DNS_QUERY_REQUEST server array; no reserved DnsQuery_W
            // arguments, host DNS reconfiguration, or external DNS observer.
            IntPtr servers = Marshal.AllocHGlobal(96);
            try {
                Marshal.Copy(new byte[96], 0, servers, 96);
                // MaxCount follows Microsoft's DNSAsyncQuery native sample (one
                // DNS_ADDR), matching AddrCount; backing allocation is 96 bytes.
                Marshal.WriteInt32(servers, 0, 1); Marshal.WriteInt32(servers, 4, 1);
                Marshal.WriteInt16(servers, 32, 2); Marshal.WriteInt32(servers, 36, 0x0100007f);
                var request = new SandboxProbeNative.DnsRequest { Version = 1, Name = name, Type = 1, Options = 8, Servers = servers };
                var result = new SandboxProbeNative.DnsResult { Version = 1 };
                uint status = SandboxProbeNative.DnsQueryEx(ref request, ref result, IntPtr.Zero);
                if (result.Records != IntPtr.Zero) SandboxProbeNative.DnsRecordListFree(result.Records, 1);
                return status;
            } finally { Marshal.FreeHGlobal(servers); }
        }
        internal static void Run() {
            if (!Broker.HostedVm()) throw new InvalidOperationException("Disposable VM required");
            string root = Path.Combine(Path.GetTempPath(), "native-lpac-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            string runtime = Path.Combine(root, "runtime"), outside = Path.Combine(root, "outside"), inputPath = Path.Combine(root, "input");
            Directory.CreateDirectory(runtime); Directory.CreateDirectory(outside);
            string image = null, canary = Path.Combine(outside, "canary"), registryPath = "Software\\StratTesterProbe-" + Guid.NewGuid().ToString("N");
            File.WriteAllText(canary, "disposable canary"); File.WriteAllBytes(inputPath, new byte[] { 97, 98, 99 });
            string eventName = "Local\\StratTesterProbe-" + Guid.NewGuid().ToString("N");
            string profileFolder = null;
            try {
                using (var key = Registry.CurrentUser.CreateSubKey(registryPath)) key.SetValue("canary", "owned fixture");
                using (var named = new EventWaitHandle(false, EventResetMode.ManualReset, eventName))
                using (var dns = new OwnedDnsObserver()) {
                    Phase = "DNS_OBSERVER_POSITIVE_CONTROL";
                    string baselineName = "baseline-" + Guid.NewGuid().ToString("N") + ".strattester.invalid";
                    uint baseline = QueryOwnedDns(baselineName);
                    LastDetail = "baseline_dns=" + baseline + ",packets=" + dns.Count;
                    if (baseline != 9003 || !dns.WaitForCount(1, 3000)) throw new InvalidOperationException("DNS positive control unavailable");
                    dns.Reset();
                    var tcp4 = new TcpListener(IPAddress.Loopback, 0); var tcp6 = new TcpListener(IPAddress.IPv6Loopback, 0); tcp6.Server.DualMode = false;
                    tcp4.Start(); tcp6.Start();
                    try {
                        using (var profile = new AppContainerProfile())
                        using (var input = LockedInput.Open(inputPath, 3)) {
                            profileFolder = profile.Folder; image = PreparePython(profile, runtime); profile.GrantReadTree(runtime);
                            Phase = "ADVERSARIAL_LPAC";
                            var result = ResearchSandbox.RunOwned(profile, image, PythonCommand(image, "adversarial", new string[] { inputPath, canary, profile.Folder,
                                ((IPEndPoint)tcp4.LocalEndpoint).Port.ToString(), ((IPEndPoint)tcp6.LocalEndpoint).Port.ToString(), "sandbox-" + Guid.NewGuid().ToString("N") + ".strattester.invalid", Process.GetCurrentProcess().Id.ToString(), eventName, registryPath }), input, Normal, CancellationToken.None, delegate { AssertRuntimeSealed(image); });
                            LastDetail = "exit=" + result.ExitCode + ",reason=" + result.StopReason + ",bytes=" + result.OutputBytes + ",output=" + SafeDetail(result.Output);
                            if (result.ExitCode != 200 || !result.TokenVerified || !result.JobVerified || result.StopReason != "EXIT") throw new InvalidOperationException("Adversarial probe failed");
                            if (dns.Count != 0 || tcp4.Pending() || tcp6.Pending()) throw new InvalidOperationException("Observed sandbox network escape");
                            if (File.ReadAllText(canary) != "disposable canary" || File.ReadAllBytes(inputPath)[0] != 97) throw new InvalidOperationException("Fixture changed");
                            Emit("ADVERSARIAL", result);
                            TestLimits(profile, image, input);
                            Phase = "PYTHON_SYNTHETIC";
                            RunPython(profile, image, input);
                        }
                    } finally { tcp4.Stop(); tcp6.Stop(); }
                }
                Phase = "PROFILE_CLEANUP";
                if (profileFolder == null || Directory.Exists(profileFolder)) throw new InvalidOperationException("Profile cleanup incomplete");
            } finally {
                Registry.CurrentUser.DeleteSubKeyTree(registryPath, false);
                // These paths are literal descendants of this method's fresh GUID
                // fixture. No caller-supplied path reaches recursive cleanup.
                if (Directory.Exists(root)) Directory.Delete(root, true);
            }
        }
        private static void TestLimits(AppContainerProfile profile, string image, LockedInput input) {
            Phase = "OUTPUT_LIMIT";
            var result = RunMode(profile, image, input, "output", new SandboxLimits(536870912, 10000, 100000000, 10000, 4096), CancellationToken.None);
            if (result.StopReason != "OUTPUT_LIMIT" || result.OutputBytes != 4096) throw new InvalidOperationException("Output limit failed"); Emit("OUTPUT", result);
            Phase = "WALL_LIMIT";
            result = RunMode(profile, image, input, "sleep", new SandboxLimits(536870912, 10000, 100000000, 1500, 4096), CancellationToken.None);
            if (result.StopReason != "WALL_LIMIT" || result.WallMilliseconds > 8000 || !result.Output.Contains("CHECK:sleep_started")) throw new InvalidOperationException("Wall limit failed"); Emit("WALL", result);
            Phase = "CANCELLATION";
            using (var cancel = new CancellationTokenSource()) {
                result = ResearchSandbox.RunOwned(profile, image, PythonCommand(image, "sleep", new string[0]), input, Normal, cancel.Token, delegate { cancel.CancelAfter(1500); });
                if (result.StopReason != "CANCELLED" || result.WallMilliseconds > 8000 || !result.Output.Contains("CHECK:sleep_started")) throw new InvalidOperationException("Cancellation failed"); Emit("CANCEL", result);
            }
            Phase = "CPU_LIMIT";
            result = RunMode(profile, image, input, "cpu", new SandboxLimits(536870912, 1000, 10000000, 15000, 4096), CancellationToken.None);
            double normalizedCpu = (result.UserTime100ns + result.KernelTime100ns) / (10000.0 * Math.Max(1, result.WallMilliseconds) * Environment.ProcessorCount);
            if (result.StopReason != "EXIT" || result.ExitCode == 0 || result.UserTime100ns < 8000000 || result.UserTime100ns > 30000000 || normalizedCpu > 0.15) throw new InvalidOperationException("CPU time/hard-cap limit failed"); Emit("CPU", result);
            Phase = "MEMORY_LIMIT";
            result = RunMode(profile, image, input, "memory", new SandboxLimits(268435456, 10000, 100000000, 15000, 4096), CancellationToken.None);
            if (result.StopReason != "EXIT" || result.ExitCode != 205 || result.Output != "MEMORY_DENIED" || result.PeakJobMemory > 268435456 || result.PeakJobMemory < 67108864) throw new InvalidOperationException("Memory limit failed"); Emit("MEMORY", result);
        }
        private static SandboxResult RunMode(AppContainerProfile profile, string image, LockedInput input, string mode, SandboxLimits limits, CancellationToken cancel) {
            var result = ResearchSandbox.RunOwned(profile, image, PythonCommand(image, mode, new string[0]), input, limits, cancel, null);
            LastDetail = "mode=" + mode + ",exit=" + result.ExitCode + ",reason=" + result.StopReason + ",wall=" + result.WallMilliseconds + ",user_cpu=" + result.UserTime100ns + ",peak_memory=" + result.PeakJobMemory + ",output=" + SafeDetail(result.Output);
            return result;
        }
        private static string[] PythonCommand(string image, string mode, string[] extra) {
            var command = new List<string> { "-I", "-S", "-B", Path.Combine(Path.GetDirectoryName(image), "owned_adversary.py"), "COMPONENT_TESTS_ONLY", mode };
            command.AddRange(extra); return command.ToArray();
        }
        private static void AssertRuntimeSealed(string image) {
            int count = 0;
            foreach (string path in Directory.GetFiles(Path.GetDirectoryName(image))) {
                bool denied = false;
                try { using (File.Open(path, FileMode.Open, FileAccess.Write, FileShare.ReadWrite | FileShare.Delete)) { } }
                catch (IOException) { denied = true; }
                if (!denied) throw new InvalidOperationException("Staged runtime mutable during suspended admission"); count++;
            }
            if (count < 4) throw new InvalidOperationException("Incomplete runtime seal fixture");
        }
        private static string PreparePython(AppContainerProfile profile, string runtime) {
            // The workflow prepares an isolated embedded Python runtime, copied into
            // the owned read-only tree. Never grant RX to an installed host runtime.
            string source = Environment.GetEnvironmentVariable("STRATTESTER_OWNED_PYTHON");
            if (String.IsNullOrEmpty(source) || !Path.IsPathRooted(source) || !File.Exists(Path.Combine(source, "python.exe"))) throw new InvalidOperationException("Owned embedded Python fixture required");
            string probe = Environment.GetEnvironmentVariable("STRATTESTER_OWNED_PROBE_SCRIPT");
            if (String.IsNullOrEmpty(probe) || !Path.IsPathRooted(probe)) throw new InvalidOperationException("Owned probe source required");
            string target = Path.Combine(runtime, "python"); CopyTree(source, target);
            File.Copy(probe, Path.Combine(target, "owned_adversary.py"));
            profile.GrantReadTree(target);
            return Path.Combine(target, "python.exe");
        }
        private static void RunPython(AppContainerProfile profile, string image, LockedInput input) {
            var result = RunMode(profile, image, input, "synthetic", Normal, CancellationToken.None);
            LastDetail = "python_exit=" + result.ExitCode + ",reason=" + result.StopReason + ",output=" + SafeDetail(result.Output);
            if (result.ExitCode != 0 || result.Output.Trim() != "{\"mean\":50.5,\"n\":100,\"schema\":1,\"synthetic_only\":true,\"variance\":833.25}") throw new InvalidOperationException("Synthetic Python worker failed");
            Emit("PYTHON_SYNTHETIC", result);
        }
        private static void CopyTree(string source, string target) {
            if ((File.GetAttributes(source) & FileAttributes.ReparsePoint) != 0) throw new IOException("Runtime reparse refused");
            Directory.CreateDirectory(target);
            foreach (string path in Directory.GetFileSystemEntries(source)) {
                if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) throw new IOException("Runtime reparse refused");
                string destination = Path.Combine(target, Path.GetFileName(path)); if (Directory.Exists(path)) CopyTree(path, destination); else File.Copy(path, destination);
            }
        }
        private static void Emit(string name, SandboxResult result) {
            Console.WriteLine("{\"component\":\"" + name + "\",\"exit_code\":" + result.ExitCode + ",\"stop_reason\":\"" + result.StopReason + "\",\"output_bytes\":" + result.OutputBytes + ",\"wall_ms\":" + result.WallMilliseconds + ",\"user_cpu_100ns\":" + result.UserTime100ns + ",\"kernel_cpu_100ns\":" + result.KernelTime100ns + ",\"peak_job_memory\":" + result.PeakJobMemory + ",\"lpac_verified_before_resume\":" + (result.TokenVerified ? "true" : "false") + ",\"job_verified_before_resume\":" + (result.JobVerified ? "true" : "false") + ",\"native_enforcement\":false}");
        }
        private static string SafeDetail(string value) {
            // Redacted numeric/check-name diagnostics only. Never print runtime paths.
            var result = new StringBuilder(); foreach (char c in value) { if (result.Length >= 300) break; if (Char.IsLetterOrDigit(c) || ":,=_-".IndexOf(c) >= 0) result.Append(c); }
            return result.ToString();
        }
        private sealed class OwnedDnsObserver : IDisposable {
            private readonly UdpClient server;
            private readonly Thread thread;
            private volatile bool stopping;
            private int count;
            internal int Count { get { return Interlocked.CompareExchange(ref count, 0, 0); } }
            internal OwnedDnsObserver() {
                server = new UdpClient(new IPEndPoint(IPAddress.Loopback, 53)); server.Client.ReceiveTimeout = 200;
                thread = new Thread(Serve) { IsBackground = true }; thread.Start();
            }
            private void Serve() {
                while (!stopping) {
                    try {
                        IPEndPoint remote = null; byte[] packet = server.Receive(ref remote);
                        if (packet.Length < 12) continue;
                        Interlocked.Increment(ref count); packet[2] = 0x81; packet[3] = 0x83;
                        for (int i = 6; i < 12; i++) packet[i] = 0;
                        server.Send(packet, packet.Length, remote);
                    } catch (SocketException) { if (stopping) break; }
                    catch (ObjectDisposedException) { break; }
                }
            }
            internal bool WaitForCount(int minimum, int milliseconds) { var timer = Stopwatch.StartNew(); while (timer.ElapsedMilliseconds < milliseconds) { if (Count >= minimum) return true; Thread.Sleep(10); } return false; }
            internal void Reset() { Interlocked.Exchange(ref count, 0); }
            public void Dispose() { stopping = true; server.Close(); if (!thread.Join(5000)) throw new InvalidOperationException("DNS observer cleanup failed"); }
        }
    }
    internal static class SandboxProbeNative {
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] internal struct DnsRequest {
            internal uint Version; [MarshalAs(UnmanagedType.LPWStr)] internal string Name; internal ushort Type;
            internal ulong Options; internal IntPtr Servers; internal uint InterfaceIndex; internal IntPtr Completion, Context;
        }
        [StructLayout(LayoutKind.Sequential)] internal struct DnsResult { internal uint Version, Status; internal ulong Options; internal IntPtr Records, Reserved; }
        [DllImport("kernel32.dll")] internal static extern IntPtr GetStdHandle(int kind);
        [DllImport("kernel32.dll", SetLastError = true)] internal static extern IntPtr OpenProcess(uint access, [MarshalAs(UnmanagedType.Bool)] bool inherit, uint pid);
        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)] internal static extern IntPtr OpenEvent(uint access, [MarshalAs(UnmanagedType.Bool)] bool inherit, string name);
        [DllImport("dnsapi.dll")] internal static extern uint DnsQueryEx(ref DnsRequest request, ref DnsResult result, IntPtr cancel);
        [DllImport("dnsapi.dll")] internal static extern void DnsRecordListFree(IntPtr records, int freeType);
    }
}
