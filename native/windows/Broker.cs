// Windows native admission broker. Arbitrary research launch remains blocked.
// Prepared Win32 components are NOT enforcement evidence; see README.md.
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Collections.Generic;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace StratTester.Native {
    internal static class Broker {
        internal const string Missing = "owner_signature_verifier,filesystem_confinement,network_egress,output_bounds,disposable_vm_verification";
        public static int Main(string[] args) {
            if (args.Length > 0 && (args[0] == "--selftest-sandbox" || args[0] == "--owned-sandbox-probe")) {
                if (args.Length < 2 || args[1] != "COMPONENT_TESTS_ONLY" || !HostedVm()) {
                    Console.WriteLine("{\"status\":\"REFUSED\",\"reason\":\"DISPOSABLE_HOSTED_VM_REQUIRED\",\"research_process_created\":false}");
                    return 78;
                }
                if (args[0] == "--owned-sandbox-probe") return SandboxProbes.Probe(args);
                if (args.Length != 2) return 64;
                try {
                    SandboxProbes.Run();
                    Console.WriteLine("{\"status\":\"LPAC_OWNED_SANDBOX_COMPONENT_PASS\",\"native_enforcement\":false,\"research_process_created\":false,\"scope\":\"OWNED_FIXTURES_ONLY\",\"full_filesystem_qualification\":\"INCOMPLETE\",\"owner_authorized_research\":\"BLOCKED\"}");
                    return 0;
                } catch (Exception error) {
                    var nativeError = error as Win32Exception;
                    Console.WriteLine("{\"status\":\"LPAC_OWNED_SANDBOX_COMPONENT_FAIL\",\"phase\":\"" + SandboxProbes.Phase + "\",\"engine_phase\":\"" + ResearchSandbox.Phase + "\",\"detail\":\"" + SandboxProbes.LastDetail + "\",\"error_type\":\"" + error.GetType().Name + "\",\"win32_error\":" + (nativeError == null ? 0 : nativeError.NativeErrorCode) + ",\"native_enforcement\":false,\"research_process_created\":false}");
                    return 1;
                }
            }
            if (args.Length > 0 && args[0] == "--owned-handle-probe" && HostedVm()) return ProbeEnvironment.IsMinimal() ? HandleComponent.Probe(args) : 103;
            if (args.Length > 0 && args[0] == "--selftest-handles") {
                if (args.Length != 2 || args[1] != "COMPONENT_TESTS_ONLY" || !HostedVm()) {
                    Console.WriteLine("{\"status\":\"REFUSED\",\"reason\":\"DISPOSABLE_HOSTED_VM_REQUIRED\",\"research_process_created\":false}");
                    return 78;
                }
                try {
                    HandleComponent.Run();
                    Console.WriteLine("{\"status\":\"READONLY_HANDLE_COMPONENT_PASS\",\"native_enforcement\":false,\"research_process_created\":false}");
                    return 0;
                } catch (Exception error) {
                    var nativeError = error as Win32Exception;
                    Console.WriteLine("{\"status\":\"READONLY_HANDLE_COMPONENT_FAIL\",\"error_type\":\"" + error.GetType().Name + "\",\"win32_error\":" + (nativeError == null ? 0 : nativeError.NativeErrorCode) + ",\"native_enforcement\":false,\"research_process_created\":false}");
                    return 1;
                }
            }
            if (args.Length > 0 && args[0] == "--owned-network-probe" && HostedVm()) return ProbeEnvironment.IsMinimal() ? WfpComponent.Probe(args) : 103;
            if (args.Length > 0 && args[0] == "--selftest-wfp") {
                if (args.Length != 2 || args[1] != "COMPONENT_TESTS_ONLY" || !HostedVm()) {
                    Console.WriteLine("{\"status\":\"REFUSED\",\"reason\":\"DISPOSABLE_HOSTED_VM_REQUIRED\",\"research_process_created\":false}");
                    return 78;
                }
                try {
                    WfpComponent.Run();
                    Console.WriteLine("{\"status\":\"WFP_OWNED_SOCKET_COMPONENT_PASS\",\"native_enforcement\":false,\"research_process_created\":false,\"dns_service_proxy\":\"NOTIMPLEMENTED\",\"arbitrary_child_identity\":\"NOTIMPLEMENTED\"}");
                    return 0;
                } catch (Exception error) {
                    var nativeError = error as Win32Exception;
                    Console.WriteLine("{\"status\":\"WFP_OWNED_SOCKET_COMPONENT_FAIL\",\"phase\":\"" + WfpComponent.Phase + "\",\"detail\":\"" + WfpComponent.Detail + "\",\"error_type\":\"" + error.GetType().Name + "\",\"win32_error\":" + (nativeError == null ? 0 : nativeError.NativeErrorCode) + ",\"native_enforcement\":false,\"research_process_created\":false}");
                    return 1;
                }
            }
            if (args.Length == 2 && args[0] == "--owned-probe" && args[1] == "COMPONENT_TESTS_ONLY" && HostedVm()) {
                if (!ProbeEnvironment.IsMinimal()) return 103;
                System.Threading.Thread.Sleep(30000);
                return 42;
            }
            if (args.Length > 0 && args[0] == "--selftest-native") {
                // Operational accident guard only, never trust evidence.
                if (args.Length != 2 || args[1] != "COMPONENT_TESTS_ONLY" ||
                    !HostedVm()) {
                    Console.WriteLine("{\"status\":\"REFUSED\",\"reason\":\"DISPOSABLE_HOSTED_VM_REQUIRED\",\"research_process_created\":false}");
                    return 78;
                }
                try {
                    ComponentTests.Run();
                    Console.WriteLine("{\"status\":\"COMPONENT_API_TESTS_PASS\",\"token_privileges_remaining\":0,\"job_limits_queried\":true,\"locked_input_fixtures\":true,\"owned_probe_kill_on_close\":true,\"native_enforcement\":false,\"research_process_created\":false}");
                    return 0;
                } catch (Exception error) {
                    var nativeError = error as Win32Exception;
                    Console.WriteLine("{\"status\":\"COMPONENT_API_TESTS_FAIL\",\"phase\":\"" + ComponentTests.Phase + "\",\"error_type\":\"" + error.GetType().Name + "\",\"win32_error\":" + (nativeError == null ? 0 : nativeError.NativeErrorCode) + ",\"native_enforcement\":false,\"research_process_created\":false}");
                    return 1;
                }
            }
            if (args.Length == 1 && args[0] == "--diagnose") {
                try {
                    bool inJob;
                    if (!Native.IsProcessInJob(Native.GetCurrentProcess(), IntPtr.Zero, out inJob))
                        throw new Win32Exception(Marshal.GetLastWin32Error());
                    string hash;
                    using (var stream = File.OpenRead(typeof(Broker).Assembly.Location))
                    using (var sha = SHA256.Create())
                        hash = BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
                    Console.WriteLine("{\"schema\":1,\"status\":\"BLOCKED\",\"native_enforcement\":false,\"research_process_created\":false,\"binary_sha256\":\"" + hash + "\",\"current_process_in_job\":" + (inJob ? "true" : "false") + ",\"component_validation\":\"NOTRUN\",\"missing_controls\":\"" + Missing + "\"}");
                    return 0;
                } catch (Exception) {
                    Console.WriteLine("{\"schema\":1,\"status\":\"DIAGNOSTIC_FAILED\",\"native_enforcement\":false,\"research_process_created\":false}");
                    return 70;
                }
            }
            if (args.Length > 0 && args[0] == "--launch") {
                // This gate intentionally precedes parsing files, trust data or commands.
                Console.WriteLine("{\"schema\":1,\"status\":\"BLOCKED\",\"reason\":\"MANDATORY_CONTROLS_NOT_IMPLEMENTED\",\"native_enforcement\":false,\"research_process_created\":false}");
                return 78;
            }
            Console.WriteLine("{\"schema\":1,\"status\":\"USAGE\",\"research_process_created\":false}");
            return 64;
        }
        internal static bool HostedVm() {
            return Environment.GetEnvironmentVariable("GITHUB_ACTIONS") == "true" &&
                   Environment.GetEnvironmentVariable("RUNNER_ENVIRONMENT") == "github-hosted" &&
                   Environment.GetEnvironmentVariable("RUNNER_OS") == "Windows";
        }
    }

    // A locked input artifact, not a filesystem sandbox. Parent handles deny
    // write/delete sharing for the lifetime of the leaf. No untrusted path is
    // accepted by any CLI mode. This component is only exercised in VM fixtures.
    internal sealed class LockedInput : IDisposable {
        private readonly List<KernelHandle> handles = new List<KernelHandle>();
        internal KernelHandle Leaf { get { return handles[handles.Count - 1]; } }
        internal string Sha256;
        internal ulong Length;
        internal uint Volume, FileIndexHigh, FileIndexLow;
        public void Dispose() { for (int i = handles.Count - 1; i >= 0; i--) handles[i].Dispose(); handles.Clear(); }
        internal static LockedInput Open(string path, ulong maximumBytes) {
            if (String.IsNullOrEmpty(path) || path.Length > 240 || maximumBytes == 0 || path.Length < 4 ||
                !Char.IsLetter(path[0]) || path[1] != ':' || path[2] != '\\' || path.IndexOf('/') >= 0 ||
                path.IndexOf(':', 2) >= 0 || path.IndexOfAny(new char[] { '\0', '*', '?', '"', '<', '>', '|' }) >= 0)
                throw new IOException("Noncanonical local path");
            string[] parts = path.Substring(3).Split('\\');
            foreach (string part in parts) {
                if (part.Length == 0 || part == "." || part == ".." || part.EndsWith(".") || part.EndsWith(" ")) throw new IOException("Unsafe component");
                foreach (char c in part) if (c < 32) throw new IOException("Control character");
                string stem = part.Split('.')[0].ToUpperInvariant();
                if (stem == "CON" || stem == "PRN" || stem == "AUX" || stem == "NUL" ||
                    stem == "CONIN$" || stem == "CONOUT$" ||
                    (stem.Length == 4 && (stem.StartsWith("COM") || stem.StartsWith("LPT")) && "123456789¹²³".IndexOf(stem[3]) >= 0))
                    throw new IOException("Device alias");
            }
            if (!String.Equals(Path.GetFullPath(path), path, StringComparison.OrdinalIgnoreCase)) throw new IOException("Path normalization");
            var locked = new LockedInput();
            try {
                string current = path.Substring(0, 3);
                for (int i = -1; i < parts.Length; i++) {
                    if (i >= 0) current = Path.Combine(current, parts[i]);
                    bool leaf = i == parts.Length - 1;
                    var handle = Native.CreateFile(current, leaf ? 0x80000000u : 0x80u, 1, IntPtr.Zero, 3, 0x00200000 | 0x02000000, IntPtr.Zero);
                    if (handle.IsInvalid) { handle.Dispose(); throw new Win32Exception(Marshal.GetLastWin32Error()); }
                    locked.handles.Add(handle);
                    Native.FileInformation info;
                    if (!Native.GetFileInformationByHandle(handle, out info) || Native.GetFileType(handle) != 1) throw new IOException("Not a disk object");
                    if ((info.Attributes & 0x400) != 0 || ((info.Attributes & 0x10) != 0) == leaf) throw new IOException("Reparse/type rejected");
                    Native.AttributeTag tag;
                    if (!Native.GetFileInformationByHandleEx(handle, 9, out tag, (uint)Marshal.SizeOf(typeof(Native.AttributeTag))) || tag.Tag != 0 || (tag.Attributes & 0x400) != 0)
                        throw new IOException("Reparse tag rejected");
                    var name = new StringBuilder(1024);
                    uint chars = Native.GetFinalPathNameByHandle(handle, name, (uint)name.Capacity, 0);
                    if (chars == 0 || chars >= name.Capacity || !String.Equals(name.ToString().TrimEnd('\\'), ("\\\\?\\" + current).TrimEnd('\\'), StringComparison.OrdinalIgnoreCase))
                        throw new IOException("Final path mismatch");
                    if (leaf) {
                        ulong length = ((ulong)info.SizeHigh << 32) | info.SizeLow;
                        if (info.Links != 1 || length > maximumBytes) throw new IOException("Link/size rejected");
                        locked.Length = length; locked.Volume = info.Volume; locked.FileIndexHigh = info.IndexHigh; locked.FileIndexLow = info.IndexLow;
                        using (var sha = SHA256.Create()) {
                            byte[] buffer = new byte[65536]; ulong total = 0;
                            while (true) {
                                uint read;
                                if (!Native.ReadFile(handle, buffer, (uint)buffer.Length, out read, IntPtr.Zero)) throw new Win32Exception(Marshal.GetLastWin32Error());
                                if (read == 0) break;
                                total += read; if (total > maximumBytes || total > length) throw new IOException("Input grew");
                                sha.TransformBlock(buffer, 0, (int)read, buffer, 0);
                            }
                            sha.TransformFinalBlock(new byte[0], 0, 0);
                            if (total != length) throw new IOException("Input size changed");
                            locked.Sha256 = BitConverter.ToString(sha.Hash).Replace("-", "").ToLowerInvariant();
                        }
                        Native.FileInformation after;
                        if (!Native.GetFileInformationByHandle(handle, out after) || after.Volume != info.Volume || after.IndexHigh != info.IndexHigh || after.IndexLow != info.IndexLow || after.SizeHigh != info.SizeHigh || after.SizeLow != info.SizeLow || after.Links != 1)
                            throw new IOException("Input identity changed");
                    }
                }
                return locked;
            } catch { locked.Dispose(); throw; }
        }
    }

    internal sealed class KernelHandle : SafeHandleZeroOrMinusOneIsInvalid {
        public KernelHandle() : base(true) { }
        internal KernelHandle(IntPtr value, bool owns) : base(owns) { SetHandle(value); }
        protected override bool ReleaseHandle() { return Native.CloseHandle(handle); }
    }

    // Compiled components only. Never called by the production CLI. No process is
    // created, no token assigned to a process, and no job assignment occurs here.
    internal static class PreparedComponents {
        internal static KernelHandle CreatePrivilegeRemovedToken() {
            KernelHandle original;
            if (!Native.OpenProcessToken(Native.GetCurrentProcess(), 0x0002 | 0x0008 | 0x0001 | 0x0020, out original))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            using (original) {
                KernelHandle restricted;
                // DISABLE_MAX_PRIVILEGE removes every privilege except SeChangeNotify.
                // Not filesystem confinement: no restricting SID/ACL is installed.
                if (!Native.CreateRestrictedToken(original, 0x1, 0, IntPtr.Zero, 0, IntPtr.Zero, 0, IntPtr.Zero, out restricted))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                try {
                    // DISABLE_MAX_PRIVILEGE leaves SeChangeNotifyPrivilege. Remove
                    // every remaining privilege rather than reporting it removed.
                    IntPtr privileges = Native.ReadTokenPrivileges(restricted);
                    try {
                        int count = Marshal.ReadInt32(privileges);
                        for (int i = 0; i < count; i++) Marshal.WriteInt32(privileges, 4 + i * 12 + 8, 4);
                        if (!Native.AdjustTokenPrivileges(restricted, false, privileges, 0, IntPtr.Zero, IntPtr.Zero) || Marshal.GetLastWin32Error() != 0)
                            throw new Win32Exception(Marshal.GetLastWin32Error());
                    } finally { Marshal.FreeHGlobal(privileges); }
                    return restricted;
                } catch { restricted.Dispose(); throw; }
            }
        }

        internal static KernelHandle CreateBoundedJob(ulong memoryBytes, uint cpuRate, long cpuTime100ns) {
            if (memoryBytes < 16777216 || memoryBytes > 17179869184 || cpuRate < 1 || cpuRate > 10000 || cpuTime100ns < 1)
                throw new ArgumentOutOfRangeException();
            var job = Native.CreateJobObject(IntPtr.Zero, null);
            if (job.IsInvalid) { job.Dispose(); throw new Win32Exception(Marshal.GetLastWin32Error()); }
            try {
                var limits = new Native.ExtendedLimits();
                limits.Basic.LimitFlags = 0x2000 | 0x200 | 0x8 | 0x2; // kill-on-close, job memory, active process, process CPU time
                limits.Basic.ActiveProcessLimit = 1;
                limits.Basic.PerProcessUserTimeLimit = cpuTime100ns;
                limits.JobMemoryLimit = new UIntPtr(memoryBytes);
                Set(job, 9, limits);
                var cpu = new Native.CpuRate { ControlFlags = 0x1 | 0x4, CpuRateValue = cpuRate };
                Set(job, 15, cpu);
                return job;
            } catch { job.Dispose(); throw; }
        }

        private static void Set<T>(KernelHandle job, int kind, T value) where T : struct {
            int size = Marshal.SizeOf(typeof(T));
            IntPtr p = Marshal.AllocHGlobal(size);
            try {
                Marshal.StructureToPtr(value, p, false);
                if (!Native.SetInformationJobObject(job, kind, p, (uint)size))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
            } finally { Marshal.FreeHGlobal(p); }
        }
    }

    internal static class ComponentTests {
        internal static string Phase = "INITIAL";
        internal static void Run() {
            Phase = "LOCKED_INPUT";
            TestLockedInput();
            Phase = "TOKEN_PRIVILEGES";
            using (var token = PreparedComponents.CreatePrivilegeRemovedToken()) {
                IntPtr p = Native.ReadTokenPrivileges(token);
                try {
                    if (Marshal.ReadInt32(p) != 0) throw new InvalidOperationException("Privileges remain");
                } finally { Marshal.FreeHGlobal(p); }
            }
            Phase = "JOB_QUERY";
            using (var job = PreparedComponents.CreateBoundedJob(67108864, 1000, 10000000)) {
                int size = Marshal.SizeOf(typeof(Native.ExtendedLimits));
                IntPtr p = Marshal.AllocHGlobal(size);
                try {
                    uint returned;
                    if (!Native.QueryInformationJobObject(job, 9, p, (uint)size, out returned)) throw new Win32Exception(Marshal.GetLastWin32Error());
                    var limits = (Native.ExtendedLimits)Marshal.PtrToStructure(p, typeof(Native.ExtendedLimits));
                    if (limits.Basic.LimitFlags != (0x2000 | 0x200 | 0x8 | 0x2) || limits.Basic.ActiveProcessLimit != 1 ||
                        limits.Basic.PerProcessUserTimeLimit != 10000000 || limits.JobMemoryLimit.ToUInt64() != 67108864)
                        throw new InvalidOperationException("Job query mismatch");
                    if (!Native.QueryInformationJobObject(job, 15, p, (uint)Marshal.SizeOf(typeof(Native.CpuRate)), out returned)) throw new Win32Exception(Marshal.GetLastWin32Error());
                    var cpu = (Native.CpuRate)Marshal.PtrToStructure(p, typeof(Native.CpuRate));
                    if (cpu.ControlFlags != 5 || cpu.CpuRateValue != 1000) throw new InvalidOperationException("CPU query mismatch");
                } finally { Marshal.FreeHGlobal(p); }
            }
            Phase = "OWNED_PROBE";
            TestOwnedProbe();
        }

        private static void TestLockedInput() {
            string folder = Path.Combine(Path.GetTempPath(), "native-fixture-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(folder);
            string path = Path.Combine(folder, "input.txt");
            string link = Path.Combine(folder, "reparse-link");
            string hardlink = Path.Combine(folder, "hardlink.txt");
            try {
                File.WriteAllBytes(path, new byte[] { 97, 98, 99 });
                using (var input = LockedInput.Open(path, 3)) {
                    if (input.Sha256 != "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" || input.Length != 3) throw new InvalidOperationException("Input hash mismatch");
                    bool writeDenied = false;
                    try { using (File.Open(path, FileMode.Open, FileAccess.Write, FileShare.ReadWrite | FileShare.Delete)) { } } catch (IOException) { writeDenied = true; }
                    if (!writeDenied) throw new InvalidOperationException("Input writable while locked");
                    bool renameDenied = false;
                    try { Directory.Move(folder, folder + "-moved"); } catch (IOException) { renameDenied = true; }
                    if (!renameDenied) { Directory.Move(folder + "-moved", folder); throw new InvalidOperationException("Parent mutable while locked"); }
                }
                foreach (string bad in new string[] { path + ":stream", Path.Combine(folder, "COM¹.txt"), Path.Combine(folder, "..", "input.txt"), "\\\\.\\NUL" }) {
                    bool denied = false;
                    try { using (LockedInput.Open(bad, 3)) { } } catch (IOException) { denied = true; }
                    if (!denied) throw new InvalidOperationException("Unsafe input path accepted");
                }
                bool oversized = false;
                try { using (LockedInput.Open(path, 2)) { } } catch (IOException) { oversized = true; }
                if (!oversized) throw new InvalidOperationException("Oversized input accepted");
                if (!Native.CreateHardLink(hardlink, path, IntPtr.Zero)) throw new Win32Exception(Marshal.GetLastWin32Error());
                bool hardlinkDenied = false;
                try { using (LockedInput.Open(path, 3)) { } } catch (IOException) { hardlinkDenied = true; }
                if (!hardlinkDenied) throw new InvalidOperationException("Hardlinked input accepted");
                File.Delete(hardlink);
                if (!Native.CreateSymbolicLink(link, folder, 3) && !Native.CreateSymbolicLink(link, folder, 1)) throw new Win32Exception(Marshal.GetLastWin32Error());
                bool reparseDenied = false;
                try { using (LockedInput.Open(Path.Combine(link, "input.txt"), 3)) { } } catch (IOException) { reparseDenied = true; }
                if (!reparseDenied) throw new InvalidOperationException("Parent reparse accepted");
            } finally {
                if (Directory.Exists(link)) Directory.Delete(link);
                if (File.Exists(hardlink)) File.Delete(hardlink);
                if (File.Exists(path)) File.Delete(path);
                if (Directory.Exists(folder)) Directory.Delete(folder);
            }
        }

        private static void TestOwnedProbe() {
            // Only this assembly and literal argv can be launched. No caller path,
            // environment, script, working directory or command is accepted.
            string executable = typeof(Broker).Assembly.Location;
            using (var imageLock = File.Open(executable, FileMode.Open, FileAccess.Read, FileShare.Read))
            using (var token = PreparedComponents.CreatePrivilegeRemovedToken())
            using (var environment = new ProbeEnvironment()) {
                KernelHandle job = PreparedComponents.CreateBoundedJob(134217728, 1000, 10000000);
                var startup = new Native.StartupInfo();
                startup.Size = (uint)Marshal.SizeOf(typeof(Native.StartupInfo));
                Native.ProcessInformation child;
                bool created = Native.CreateProcessAsUser(token, executable,
                    new StringBuilder("\"" + executable + "\" --owned-probe COMPONENT_TESTS_ONLY"),
                    IntPtr.Zero, IntPtr.Zero, false, 0x4 | 0x08000000 | 0x400, environment.Block,
                    Path.GetDirectoryName(executable), ref startup, out child);
                if (!created) { job.Dispose(); throw new Win32Exception(Marshal.GetLastWin32Error()); }
                try {
                    // Child is suspended. Assignment failure kills it before resume.
                    if (!Native.AssignProcessToJobObject(job, child.Process)) throw new Win32Exception(Marshal.GetLastWin32Error());
                    bool assigned;
                    if (!Native.IsProcessInJob(child.Process, job.DangerousGetHandle(), out assigned) || !assigned) throw new InvalidOperationException("Probe not in job");
                    if (Native.ResumeThread(child.Thread) == UInt32.MaxValue) throw new Win32Exception(Marshal.GetLastWin32Error());
                    if (Native.WaitForSingleObject(child.Process, 1000) != 258) throw new InvalidOperationException("Probe did not remain alive");
                    // Kill-on-close is tested on the owned benign sleeping child.
                    job.Dispose();
                    if (Native.WaitForSingleObject(child.Process, 5000) != 0) throw new InvalidOperationException("Kill-on-close failed");
                    uint exitCode;
                    if (!Native.GetExitCodeProcess(child.Process, out exitCode) || exitCode == 42 || exitCode == 259) throw new InvalidOperationException("Probe was not terminated");
                } finally {
                    // Dedicated direct process handle: cleanup does not depend on
                    // successful job assignment, resume, or job disposal.
                    Native.TerminateProcess(child.Process, 125);
                    Native.WaitForSingleObject(child.Process, 5000);
                    Native.CloseHandle(child.Thread); Native.CloseHandle(child.Process);
                    job.Dispose();
                }
            }
        }
    }

    internal static class Native {
        [StructLayout(LayoutKind.Sequential)] internal struct AttributeTag { internal uint Attributes, Tag; }
        [StructLayout(LayoutKind.Sequential)] internal struct FileInformation {
            internal uint Attributes;
            internal System.Runtime.InteropServices.ComTypes.FILETIME CreationTime, AccessTime, WriteTime;
            internal uint Volume, SizeHigh, SizeLow, Links, IndexHigh, IndexLow;
        }
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] internal struct StartupInfo {
            internal uint Size; internal string Reserved, Desktop, Title;
            internal uint X, Y, XSize, YSize, XCountChars, YCountChars, FillAttribute, Flags;
            internal ushort ShowWindow, Reserved2Size; internal IntPtr Reserved2, StdInput, StdOutput, StdError;
        }
        [StructLayout(LayoutKind.Sequential)] internal struct ProcessInformation { internal IntPtr Process, Thread; internal uint ProcessId, ThreadId; }
        [StructLayout(LayoutKind.Sequential)] internal struct StartupInfoEx { internal StartupInfo Startup; internal IntPtr Attributes; }
        internal static IntPtr ReadTokenPrivileges(KernelHandle token) {
            uint size;
            GetTokenInformation(token, 3, IntPtr.Zero, 0, out size);
            if (size < 4 || size > 1048576 || Marshal.GetLastWin32Error() != 122) throw new Win32Exception(Marshal.GetLastWin32Error());
            IntPtr p = Marshal.AllocHGlobal((int)size);
            if (!GetTokenInformation(token, 3, p, size, out size)) { Marshal.FreeHGlobal(p); throw new Win32Exception(Marshal.GetLastWin32Error()); }
            int count = Marshal.ReadInt32(p);
            if (count < 0 || count > (size - 4) / 12) { Marshal.FreeHGlobal(p); throw new InvalidOperationException("Token buffer invalid"); }
            return p;
        }
        [StructLayout(LayoutKind.Sequential)] internal struct BasicLimits {
            internal long PerProcessUserTimeLimit, PerJobUserTimeLimit;
            internal uint LimitFlags;
            internal UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize;
            internal uint ActiveProcessLimit;
            internal UIntPtr Affinity;
            internal uint PriorityClass, SchedulingClass;
        }
        [StructLayout(LayoutKind.Sequential)] internal struct IoCounters { internal ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes; }
        [StructLayout(LayoutKind.Sequential)] internal struct ExtendedLimits {
            internal BasicLimits Basic;
            internal IoCounters Io;
            internal UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
        }
        [StructLayout(LayoutKind.Sequential)] internal struct CpuRate { internal uint ControlFlags, CpuRateValue; }
        [DllImport("kernel32.dll")] internal static extern IntPtr GetCurrentProcess();
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool CloseHandle(IntPtr handle);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool IsProcessInJob(IntPtr process, IntPtr job, [MarshalAs(UnmanagedType.Bool)] out bool result);
        [DllImport("advapi32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool OpenProcessToken(IntPtr process, uint access, out KernelHandle token);
        [DllImport("advapi32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool CreateRestrictedToken(KernelHandle token, uint flags, uint disabledSidCount, IntPtr disabledSids, uint privilegeCount, IntPtr privileges, uint restrictedSidCount, IntPtr restrictedSids, out KernelHandle restricted);
        [DllImport("advapi32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetTokenInformation(KernelHandle token, int kind, IntPtr data, uint length, out uint returned);
        [DllImport("advapi32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool AdjustTokenPrivileges(KernelHandle token, [MarshalAs(UnmanagedType.Bool)] bool disableAll, IntPtr newState, uint length, IntPtr previous, IntPtr returned);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] internal static extern KernelHandle CreateJobObject(IntPtr attributes, string name);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool SetInformationJobObject(KernelHandle job, int kind, IntPtr information, uint length);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool QueryInformationJobObject(KernelHandle job, int kind, IntPtr information, uint length, out uint returned);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] internal static extern KernelHandle CreateFile(string path, uint access, uint share, IntPtr security, uint disposition, uint flags, IntPtr template);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetFileInformationByHandle(KernelHandle file, out FileInformation info);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetFileInformationByHandleEx(KernelHandle file, int kind, out AttributeTag tag, uint length);
        [DllImport("kernel32.dll", SetLastError = true)] internal static extern uint GetFileType(KernelHandle file);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] internal static extern uint GetFinalPathNameByHandle(KernelHandle file, StringBuilder path, uint length, uint flags);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool ReadFile(KernelHandle file, byte[] buffer, uint length, out uint read, IntPtr overlapped);
        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool CreateProcessAsUser(KernelHandle token, string application, StringBuilder command, IntPtr processAttributes, IntPtr threadAttributes, [MarshalAs(UnmanagedType.Bool)] bool inheritHandles, uint flags, IntPtr environment, string directory, ref StartupInfo startup, out ProcessInformation info);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool AssignProcessToJobObject(KernelHandle job, IntPtr process);
        [DllImport("kernel32.dll", SetLastError = true)] internal static extern uint ResumeThread(IntPtr thread);
        [DllImport("kernel32.dll", SetLastError = true)] internal static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetExitCodeProcess(IntPtr process, out uint exitCode);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool TerminateProcess(IntPtr process, uint code);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool CreateHardLink(string link, string existing, IntPtr attributes);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] [return: MarshalAs(UnmanagedType.I1)] internal static extern bool CreateSymbolicLink(string link, string target, uint flags);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool DuplicateHandle(IntPtr sourceProcess, KernelHandle source, IntPtr targetProcess, out KernelHandle target, uint access, [MarshalAs(UnmanagedType.Bool)] bool inherit, uint options);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool InitializeProcThreadAttributeList(IntPtr attributes, uint count, uint flags, ref UIntPtr bytes);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool UpdateProcThreadAttribute(IntPtr attributes, uint flags, UIntPtr kind, IntPtr value, UIntPtr size, IntPtr previous, IntPtr returned);
        [DllImport("kernel32.dll")] internal static extern void DeleteProcThreadAttributeList(IntPtr attributes);
        [DllImport("advapi32.dll", EntryPoint = "CreateProcessAsUserW", CharSet = CharSet.Unicode, SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool CreateProcessAsUserEx(KernelHandle token, string application, StringBuilder command, IntPtr processAttributes, IntPtr threadAttributes, [MarshalAs(UnmanagedType.Bool)] bool inheritHandles, uint flags, IntPtr environment, string directory, ref StartupInfoEx startup, out ProcessInformation info);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool SetFilePointerEx(KernelHandle file, long distance, out long position, uint method);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool WriteFile(KernelHandle file, byte[] buffer, uint length, out uint written, IntPtr overlapped);
    }
}
