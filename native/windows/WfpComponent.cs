// Disposable VM component experiment, never a research execution authorizer.
// Native layouts/constants follow Microsoft's fwpmtypes.h/fwpmu.h x64 ABI.
using System;
using System.ComponentModel;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;

namespace StratTester.Native {
    internal static class WfpComponent {
        internal static string Phase = "INITIAL";
        internal static int Probe(string[] args) {
            int v4, v6;
            if (args.Length != 4 || args[1] != "COMPONENT_TESTS_ONLY" || !Int32.TryParse(args[2], out v4) ||
                !Int32.TryParse(args[3], out v6) || v4 < 1 || v4 > 65535 || v6 < 1 || v6 > 65535) return 102;
            int a = Connect(IPAddress.Loopback, v4), b = Connect(IPAddress.IPv6Loopback, v6);
            return a == 0 && b == 0 ? 100 : (a == 1 && b == 1 ? 101 : 102);
        }
        private static int Connect(IPAddress address, int port) {
            try { using (var client = new TcpClient(address.AddressFamily)) { client.Connect(address, port); return 0; } }
            catch (SocketException error) { return error.SocketErrorCode == SocketError.AccessDenied ? 1 : 2; }
            catch { return 2; }
        }
        internal static void Run() {
            // Refuse ABI mismatches before opening any policy session.
            if (IntPtr.Size != 8 || Marshal.SizeOf(typeof(Wfp.Filter)) != 200 ||
                Marshal.SizeOf(typeof(Wfp.Condition)) != 40 || Marshal.SizeOf(typeof(Wfp.Session)) != 72)
                throw new InvalidOperationException("WFP ABI mismatch");
            var ipv4 = new TcpListener(IPAddress.Loopback, 0);
            var ipv6 = new TcpListener(IPAddress.IPv6Loopback, 0);
            ipv6.Server.DualMode = false;
            string folder = Path.Combine(Path.GetTempPath(), "native-wfp-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(folder);
            string image = Path.Combine(folder, "StratTester.OwnedNetworkProbe.exe");
            try {
                Phase = "OWNED_LISTENERS";
                ipv4.Start(8); ipv6.Start(8);
                int port4 = ((IPEndPoint)ipv4.LocalEndpoint).Port, port6 = ((IPEndPoint)ipv6.LocalEndpoint).Port;
                File.Copy(typeof(Broker).Assembly.Location, image);
                using (var imageLock = File.Open(image, FileMode.Open, FileAccess.Read, FileShare.Read)) {
                    Phase = "BASELINE_CONNECT";
                    if (RunOwned(image, port4, port6) != 100) throw new InvalidOperationException("Live loopback baseline unavailable");
                    Phase = "INSTALL_QUERY_DYNAMIC_FILTERS";
                    using (var policy = new WfpPolicy(image)) {
                        Phase = "BLOCKED_CONNECT";
                        if (RunOwned(image, port4, port6) != 101) throw new InvalidOperationException("Expected explicit socket access denial on both families");
                    }
                    Phase = "RECOVERY_CONNECT";
                    if (RunOwned(image, port4, port6) != 100) throw new InvalidOperationException("Dynamic policy cleanup recovery failed");
                }
            } finally {
                ipv4.Stop(); ipv6.Stop();
                if (File.Exists(image)) File.Delete(image);
                if (Directory.Exists(folder)) Directory.Delete(folder);
            }
        }
        private static uint RunOwned(string image, int port4, int port6) {
            using (var token = PreparedComponents.CreatePrivilegeRemovedToken())
            using (var environment = new ProbeEnvironment())
            using (var job = PreparedComponents.CreateBoundedJob(134217728, 1000, 50000000)) {
                var startup = new Native.StartupInfo { Size = (uint)Marshal.SizeOf(typeof(Native.StartupInfo)) };
                Native.ProcessInformation child;
                string command = "\"" + image + "\" --owned-network-probe COMPONENT_TESTS_ONLY " + port4 + " " + port6;
                if (!Native.CreateProcessAsUser(token, image, new StringBuilder(command), IntPtr.Zero, IntPtr.Zero,
                    false, 0x4 | 0x08000000 | 0x400, environment.Block, Path.GetDirectoryName(image), ref startup, out child))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                try {
                    if (!Native.AssignProcessToJobObject(job, child.Process)) throw new Win32Exception(Marshal.GetLastWin32Error());
                    bool assigned;
                    if (!Native.IsProcessInJob(child.Process, job.DangerousGetHandle(), out assigned) || !assigned) throw new InvalidOperationException("Network probe job assignment failed");
                    if (Native.ResumeThread(child.Thread) == UInt32.MaxValue) throw new Win32Exception(Marshal.GetLastWin32Error());
                    if (Native.WaitForSingleObject(child.Process, 5000) != 0) throw new InvalidOperationException("Network probe timed out");
                    uint code;
                    if (!Native.GetExitCodeProcess(child.Process, out code)) throw new Win32Exception(Marshal.GetLastWin32Error());
                    return code;
                } finally {
                    Native.TerminateProcess(child.Process, 125); Native.WaitForSingleObject(child.Process, 5000);
                    Native.CloseHandle(child.Thread); Native.CloseHandle(child.Process);
                }
            }
        }
    }

    internal sealed class WfpPolicy : IDisposable {
        private IntPtr engine;
        internal WfpPolicy(string ownedImage) {
            var session = new Wfp.Session { Key = Guid.NewGuid(), Display = new Wfp.Display { Name = "StratTester disposable owned probe" }, Flags = 1 };
            Wfp.Check(Wfp.FwpmEngineOpen0(null, 10, IntPtr.Zero, ref session, out engine));
            IntPtr app = IntPtr.Zero;
            try {
                Guid sublayerKey = Guid.NewGuid();
                var sublayer = new Wfp.Sublayer { Key = sublayerKey, Display = new Wfp.Display { Name = "StratTester disposable owned probe only" }, Weight = UInt16.MaxValue };
                Wfp.Check(Wfp.FwpmSubLayerAdd0(engine, ref sublayer, IntPtr.Zero));
                Wfp.Check(Wfp.FwpmGetAppIdFromFileName0(ownedImage, out app));
                foreach (var layer in Wfp.Layers) AddAndQuery(layer, sublayerKey, app);
            } catch { Dispose(); throw; }
            finally { if (app != IntPtr.Zero) Wfp.FwpmFreeMemory0(ref app); }
        }
        private void AddAndQuery(Guid layer, Guid sublayer, IntPtr app) {
            var condition = new Wfp.Condition { Field = Wfp.AppId, Match = 0, Value = new Wfp.Value { Type = 12, Pointer = app } };
            IntPtr p = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Wfp.Condition)));
            IntPtr queried = IntPtr.Zero;
            try {
                Marshal.StructureToPtr(condition, p, false);
                var filter = new Wfp.Filter { Key = Guid.NewGuid(), Display = new Wfp.Display { Name = "StratTester owned probe deny sockets" },
                    Layer = layer, Sublayer = sublayer, ConditionCount = 1, Conditions = p, Action = new Wfp.Action { Type = 0x1001 } };
                ulong id;
                Wfp.Check(Wfp.FwpmFilterAdd0(engine, ref filter, IntPtr.Zero, out id));
                Wfp.Check(Wfp.FwpmFilterGetByKey0(engine, ref filter.Key, out queried));
                var actual = (Wfp.Filter)Marshal.PtrToStructure(queried, typeof(Wfp.Filter));
                if (actual.Key != filter.Key || actual.Layer != layer || actual.Sublayer != sublayer || actual.Action.Type != 0x1001 || actual.ConditionCount != 1 || actual.Id != id || actual.Flags != 0)
                    throw new InvalidOperationException("WFP filter query mismatch");
                var actualCondition = (Wfp.Condition)Marshal.PtrToStructure(actual.Conditions, typeof(Wfp.Condition));
                if (actualCondition.Field != Wfp.AppId || actualCondition.Match != 0 || actualCondition.Value.Type != 12 || !Wfp.SameBlob(app, actualCondition.Value.Pointer))
                    throw new InvalidOperationException("WFP app identity query mismatch");
            } finally {
                if (queried != IntPtr.Zero) Wfp.FwpmFreeMemory0(ref queried);
                Marshal.FreeHGlobal(p);
            }
        }
        public void Dispose() {
            if (engine != IntPtr.Zero) { IntPtr old = engine; engine = IntPtr.Zero; Wfp.Check(Wfp.FwpmEngineClose0(old)); }
        }
    }

    internal static class Wfp {
        internal static readonly Guid AppId = new Guid("d78e1e87-8644-4ea5-9437-d809ecefc971");
        internal static readonly Guid[] Layers = new Guid[] {
            new Guid("c38d57d1-05a7-4c33-904f-7fbceee60e82"), new Guid("4a72393b-319f-44bc-84c3-ba54dcb3b6b4"),
            new Guid("e1cd9fe7-f4b5-4273-96c0-592e487b8650"), new Guid("a3b42c97-9f04-4672-b87e-cee9c483257f") };
        internal static void Check(uint status) { if (status != 0) throw new Win32Exception(unchecked((int)status)); }
        internal static bool SameBlob(IntPtr one, IntPtr two) {
            if (one == IntPtr.Zero || two == IntPtr.Zero) return false;
            var a = (Blob)Marshal.PtrToStructure(one, typeof(Blob)); var b = (Blob)Marshal.PtrToStructure(two, typeof(Blob));
            if (a.Size == 0 || a.Size > 65536 || a.Size != b.Size || a.Data == IntPtr.Zero || b.Data == IntPtr.Zero) return false;
            byte[] x = new byte[a.Size], y = new byte[b.Size]; Marshal.Copy(a.Data, x, 0, x.Length); Marshal.Copy(b.Data, y, 0, y.Length);
            for (int i = 0; i < x.Length; i++) if (x[i] != y[i]) return false;
            return true;
        }
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] internal struct Display { [MarshalAs(UnmanagedType.LPWStr)] internal string Name, Description; }
        [StructLayout(LayoutKind.Sequential)] internal struct Blob { internal uint Size; internal IntPtr Data; }
        [StructLayout(LayoutKind.Sequential)] internal struct Value { internal uint Type; internal IntPtr Pointer; }
        [StructLayout(LayoutKind.Sequential)] internal struct Condition { internal Guid Field; internal uint Match; internal Value Value; }
        [StructLayout(LayoutKind.Sequential)] internal struct Action { internal uint Type; internal Guid Key; }
        [StructLayout(LayoutKind.Explicit, Size = 16)] internal struct Context { [FieldOffset(0)] internal ulong Raw; [FieldOffset(0)] internal Guid Provider; }
        [StructLayout(LayoutKind.Sequential)] internal struct Session { internal Guid Key; internal Display Display; internal uint Flags, Timeout, ProcessId; internal IntPtr Sid, UserName; internal int Kernel; }
        [StructLayout(LayoutKind.Sequential)] internal struct Sublayer { internal Guid Key; internal Display Display; internal uint Flags; internal IntPtr Provider; internal Blob ProviderData; internal ushort Weight; }
        [StructLayout(LayoutKind.Sequential)] internal struct Filter {
            internal Guid Key; internal Display Display; internal uint Flags; internal IntPtr Provider; internal Blob ProviderData;
            internal Guid Layer, Sublayer; internal Value Weight; internal uint ConditionCount; internal IntPtr Conditions;
            internal Action Action; internal Context Context; internal IntPtr Reserved; internal ulong Id; internal Value EffectiveWeight;
        }
        [DllImport("fwpuclnt.dll", CharSet = CharSet.Unicode)] internal static extern uint FwpmEngineOpen0(string server, uint auth, IntPtr identity, ref Session session, out IntPtr engine);
        [DllImport("fwpuclnt.dll")] internal static extern uint FwpmEngineClose0(IntPtr engine);
        [DllImport("fwpuclnt.dll")] internal static extern uint FwpmSubLayerAdd0(IntPtr engine, ref Sublayer sublayer, IntPtr security);
        [DllImport("fwpuclnt.dll", CharSet = CharSet.Unicode)] internal static extern uint FwpmGetAppIdFromFileName0(string file, out IntPtr blob);
        [DllImport("fwpuclnt.dll")] internal static extern uint FwpmFilterAdd0(IntPtr engine, ref Filter filter, IntPtr security, out ulong id);
        [DllImport("fwpuclnt.dll")] internal static extern uint FwpmFilterGetByKey0(IntPtr engine, ref Guid key, out IntPtr filter);
        [DllImport("fwpuclnt.dll")] internal static extern void FwpmFreeMemory0(ref IntPtr memory);
    }
}
