// Windows native admission broker. No research process creation path exists.
// Prepared Win32 components are NOT enforcement evidence; see README.md.
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using Microsoft.Win32.SafeHandles;

namespace StratTester.Native {
    internal static class Broker {
        internal const string Missing = "owner_signature_verifier,filesystem_confinement,network_egress,output_bounds,disposable_vm_verification";
        public static int Main(string[] args) {
            if (args.Length > 0 && args[0] == "--selftest-native") {
                // Operational accident guard only, never trust evidence.
                if (args.Length != 2 || args[1] != "COMPONENT_TESTS_ONLY" ||
                    Environment.GetEnvironmentVariable("GITHUB_ACTIONS") != "true" ||
                    Environment.GetEnvironmentVariable("RUNNER_ENVIRONMENT") != "github-hosted" ||
                    Environment.GetEnvironmentVariable("RUNNER_OS") != "Windows") {
                    Console.WriteLine("{\"status\":\"REFUSED\",\"reason\":\"DISPOSABLE_HOSTED_VM_REQUIRED\",\"research_process_created\":false}");
                    return 78;
                }
                try {
                    ComponentTests.Run();
                    Console.WriteLine("{\"status\":\"COMPONENT_API_TESTS_PASS\",\"token_privileges_remaining\":0,\"job_limits_queried\":true,\"native_enforcement\":false,\"research_process_created\":false}");
                    return 0;
                } catch (Exception) {
                    Console.WriteLine("{\"status\":\"COMPONENT_API_TESTS_FAIL\",\"native_enforcement\":false,\"research_process_created\":false}");
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
    }

    internal sealed class KernelHandle : SafeHandleZeroOrMinusOneIsInvalid {
        public KernelHandle() : base(true) { }
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
        internal static void Run() {
            using (var token = PreparedComponents.CreatePrivilegeRemovedToken()) {
                IntPtr p = Native.ReadTokenPrivileges(token);
                try {
                    if (Marshal.ReadInt32(p) != 0) throw new InvalidOperationException("Privileges remain");
                } finally { Marshal.FreeHGlobal(p); }
            }
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
                    if (!Native.QueryInformationJobObject(job, 15, p, (uint)size, out returned)) throw new Win32Exception(Marshal.GetLastWin32Error());
                    var cpu = (Native.CpuRate)Marshal.PtrToStructure(p, typeof(Native.CpuRate));
                    if (cpu.ControlFlags != 5 || cpu.CpuRateValue != 1000) throw new InvalidOperationException("CPU query mismatch");
                } finally { Marshal.FreeHGlobal(p); }
            }
        }
    }

    internal static class Native {
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
    }
}
