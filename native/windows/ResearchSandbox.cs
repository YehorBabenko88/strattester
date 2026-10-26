// Disposable hosted-only engine. There is deliberately no public research launch API.
using System;
using System.ComponentModel;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace StratTester.Native {
    internal sealed class SandboxLimits {
        internal readonly ulong MemoryBytes;
        internal readonly uint CpuRate;
        internal readonly long CpuTime100ns;
        internal readonly int WallMilliseconds, OutputBytes;
        internal SandboxLimits(ulong memory, uint cpu, long time, int wall, int output) {
            if (memory < 67108864 || memory > 1073741824 || cpu < 1 || cpu > 10000 || time < 100000 || time > 600000000 || wall < 100 || wall > 60000 || output < 1 || output > 1048576)
                throw new ArgumentOutOfRangeException();
            MemoryBytes = memory; CpuRate = cpu; CpuTime100ns = time; WallMilliseconds = wall; OutputBytes = output;
        }
    }
    internal sealed class SandboxResult {
        internal uint ExitCode;
        internal string StopReason, Output;
        internal int OutputBytes;
        internal long UserTime100ns, KernelTime100ns, WallMilliseconds;
        internal ulong PeakJobMemory;
        internal bool TokenVerified, JobVerified;
    }
    internal sealed class SandboxEnvironment : IDisposable {
        internal IntPtr Block;
        internal SandboxEnvironment(string readOnlyProfile) {
            string windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
            string[] values = { "GITHUB_ACTIONS=true", "LOCALAPPDATA=" + readOnlyProfile, "RUNNER_ENVIRONMENT=github-hosted", "RUNNER_OS=Windows", "SystemRoot=" + windows, "TEMP=" + readOnlyProfile, "TMP=" + readOnlyProfile, "WINDIR=" + windows };
            foreach (string value in values) if (value.IndexOf('\0') >= 0) throw new ArgumentException("Environment NUL");
            Block = Marshal.StringToHGlobalUni(String.Join("\0", values) + "\0");
        }
        public void Dispose() { if (Block != IntPtr.Zero) { Marshal.FreeHGlobal(Block); Block = IntPtr.Zero; } }
    }
    internal static class ResearchSandbox {
        internal static string Phase = "INITIAL";
        internal static uint LastProcessId;
        // This is an owned fixture API, not an authorization boundary. It is only
        // reachable through --selftest-sandbox after the disposable-host guard.
        internal static SandboxResult RunOwned(AppContainerProfile profile, string image, string[] arguments,
            LockedInput input, SandboxLimits limits, CancellationToken cancellation, Action admitted) {
            if (!Broker.HostedVm()) throw new InvalidOperationException("Disposable VM required");
            if (input == null || limits == null || profile == null || !Path.IsPathRooted(image)) throw new ArgumentException("Admission required");
            KernelHandle inheritedInput;
            if (!Native.DuplicateHandle(Native.GetCurrentProcess(), input.Leaf, Native.GetCurrentProcess(), out inheritedInput, 0x80000000u, true, 0)) throw new Win32Exception(Marshal.GetLastWin32Error());
            using (inheritedInput)
            using (var runtimeSeal = SealedRuntime.Open(Path.GetDirectoryName(image)))
            using (var token = CreateResearchToken())
            using (var job = PreparedComponents.CreateBoundedJob(limits.MemoryBytes, limits.CpuRate, limits.CpuTime100ns))
            using (var environment = new SandboxEnvironment(profile.Folder)) {
                KernelHandle outputRead, outputWrite;
                var security = new SandboxNative.SecurityAttributes { Size = (uint)Marshal.SizeOf(typeof(SandboxNative.SecurityAttributes)), Inherit = true };
                if (!SandboxNative.CreatePipe(out outputRead, out outputWrite, ref security, 4096)) throw new Win32Exception(Marshal.GetLastWin32Error());
                using (outputRead) using (outputWrite) {
                    if (!SandboxNative.SetHandleInformation(outputRead, 1, 0)) throw new Win32Exception(Marshal.GetLastWin32Error());
                    long position;
                    if (!Native.SetFilePointerEx(inheritedInput, 0, out position, 0) || position != 0) throw new Win32Exception(Marshal.GetLastWin32Error());
                    using (var attributes = new SandboxAttributes(profile, job, new IntPtr[] { inheritedInput.DangerousGetHandle(), outputWrite.DangerousGetHandle() })) {
                        var startup = new Native.StartupInfoEx { Attributes = attributes.List };
                        startup.Startup.Size = (uint)Marshal.SizeOf(typeof(Native.StartupInfoEx));
                        startup.Startup.Flags = 0x100;
                        startup.Startup.StdInput = inheritedInput.DangerousGetHandle(); startup.Startup.StdOutput = outputWrite.DangerousGetHandle(); startup.Startup.StdError = outputWrite.DangerousGetHandle();
                        var command = new StringBuilder(Quote(image)); foreach (string arg in arguments) command.Append(" ").Append(Quote(arg));
                        Native.ProcessInformation child;
                        Phase = "CREATE_SUSPENDED_LPAC";
                        if (!Native.CreateProcessAsUserEx(token, image, command, IntPtr.Zero, IntPtr.Zero, true, 0x4 | 0x80000 | 0x08000000 | 0x400, environment.Block, Path.GetDirectoryName(image), ref startup, out child))
                            throw new Win32Exception(Marshal.GetLastWin32Error());
                        LastProcessId = child.ProcessId;
                        Thread reader = null;
                        var result = new SandboxResult { StopReason = "EXIT" };
                        var capture = new BoundedCapture(outputRead, limits.OutputBytes, job);
                        var timer = Stopwatch.StartNew();
                        try {
                            Phase = "VERIFY_BEFORE_RESUME";
                            profile.VerifyToken(child.Process); result.TokenVerified = true;
                            bool assigned;
                            if (!Native.IsProcessInJob(child.Process, job.DangerousGetHandle(), out assigned) || !assigned) throw new InvalidOperationException("Atomic job admission failed");
                            VerifyJob(job, limits); result.JobVerified = true;
                            outputWrite.Dispose(); inheritedInput.Dispose();
                            reader = new Thread(capture.Read) { IsBackground = true }; reader.Start();
                            if (admitted != null) admitted();
                            if (cancellation.IsCancellationRequested) { result.StopReason = "CANCELLED"; SandboxNative.TerminateJobObject(job, 124); }
                            else {
                                if (Native.ResumeThread(child.Thread) == UInt32.MaxValue) throw new Win32Exception(Marshal.GetLastWin32Error());
                                Phase = "RUNNING";
                                while (true) {
                                    uint waited = Native.WaitForSingleObject(child.Process, 10);
                                    if (waited == 0) break;
                                    if (waited != 258) throw new Win32Exception(Marshal.GetLastWin32Error());
                                    if (capture.Exceeded) { result.StopReason = "OUTPUT_LIMIT"; SandboxNative.TerminateJobObject(job, 122); break; }
                                    if (cancellation.IsCancellationRequested) { result.StopReason = "CANCELLED"; SandboxNative.TerminateJobObject(job, 124); break; }
                                    if (timer.ElapsedMilliseconds >= limits.WallMilliseconds) { result.StopReason = "WALL_LIMIT"; SandboxNative.TerminateJobObject(job, 123); break; }
                                }
                            }
                            if (Native.WaitForSingleObject(child.Process, 5000) != 0) throw new InvalidOperationException("Child did not terminate");
                            if (reader != null && !reader.Join(5000)) throw new InvalidOperationException("Output pipe did not close");
                            if (capture.Error != null) throw new IOException("Output capture failed", capture.Error);
                            if (capture.Exceeded) result.StopReason = "OUTPUT_LIMIT";
                            if (!Native.GetExitCodeProcess(child.Process, out result.ExitCode)) throw new Win32Exception(Marshal.GetLastWin32Error());
                            long created, exited;
                            if (!SandboxNative.GetProcessTimes(child.Process, out created, out exited, out result.KernelTime100ns, out result.UserTime100ns)) throw new Win32Exception(Marshal.GetLastWin32Error());
                            result.PeakJobMemory = ReadJob(job).PeakJobMemoryUsed.ToUInt64();
                            result.Output = Encoding.UTF8.GetString(capture.Bytes()); result.OutputBytes = capture.Count; result.WallMilliseconds = timer.ElapsedMilliseconds;
                            Phase = "CHILD_REAPED";
                            return result;
                        } finally {
                            // This direct handle covers failures before/at admission;
                            // the job also has kill-on-close and one active process.
                            SandboxNative.TerminateJobObject(job, 125); Native.TerminateProcess(child.Process, 125);
                            Native.WaitForSingleObject(child.Process, 5000);
                            outputWrite.Dispose();
                            if (reader != null && reader.IsAlive) { outputRead.Dispose(); reader.Join(5000); }
                            Native.CloseHandle(child.Thread); Native.CloseHandle(child.Process);
                        }
                    }
                }
            }
        }
        private static KernelHandle CreateResearchToken() {
            KernelHandle original;
            if (!Native.OpenProcessToken(Native.GetCurrentProcess(), 0x0002 | 0x0008 | 0x0001 | 0x0020, out original)) throw new Win32Exception(Marshal.GetLastWin32Error());
            using (original) {
                KernelHandle restricted;
                // Preserve only the API's deliberate SeChangeNotify exception:
                // bypass traverse checking, never file read/list/write access.
                // No shared ancestor ACL is changed to let the runtime traverse.
                if (!Native.CreateRestrictedToken(original, 1, 0, IntPtr.Zero, 0, IntPtr.Zero, 0, IntPtr.Zero, out restricted)) throw new Win32Exception(Marshal.GetLastWin32Error());
                try { VerifyResearchPrivileges(restricted); return restricted; } catch { restricted.Dispose(); throw; }
            }
        }
        internal static void VerifyResearchPrivileges(KernelHandle token) {
            long expected;
            if (!SandboxNative.LookupPrivilegeValue(null, "SeChangeNotifyPrivilege", out expected)) throw new Win32Exception(Marshal.GetLastWin32Error());
            IntPtr data = Native.ReadTokenPrivileges(token);
            try {
                if (Marshal.ReadInt32(data) != 1 || Marshal.ReadInt64(data, 4) != expected || (Marshal.ReadInt32(data, 12) & 2) == 0 || (Marshal.ReadInt32(data, 12) & ~3) != 0)
                    throw new InvalidOperationException("Research privilege allowlist mismatch");
            } finally { Marshal.FreeHGlobal(data); }
        }
        private sealed class SealedRuntime : IDisposable {
            private readonly List<LockedInput> files = new List<LockedInput>();
            internal static SealedRuntime Open(string root) {
                var result = new SealedRuntime();
                try { ulong total = 0; result.Walk(root, ref total); if (result.files.Count == 0) throw new IOException("Empty runtime"); return result; }
                catch { result.Dispose(); throw; }
            }
            private void Walk(string directory, ref ulong total) {
                if ((File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0) throw new IOException("Runtime reparse refused");
                string[] entries = Directory.GetFileSystemEntries(directory); Array.Sort(entries, StringComparer.Ordinal);
                foreach (string entry in entries) {
                    FileAttributes attributes = File.GetAttributes(entry);
                    if ((attributes & FileAttributes.ReparsePoint) != 0) throw new IOException("Runtime reparse refused");
                    if ((attributes & FileAttributes.Directory) != 0) { Walk(entry, ref total); continue; }
                    if (files.Count >= 128) throw new IOException("Runtime count exceeded");
                    var file = LockedInput.Open(entry, 167772160); files.Add(file); total = checked(total + file.Length);
                    if (total > 268435456) throw new IOException("Runtime size exceeded");
                }
            }
            public void Dispose() { for (int i = files.Count - 1; i >= 0; i--) files[i].Dispose(); files.Clear(); }
        }
        private sealed class BoundedCapture {
            private readonly KernelHandle pipe, job;
            private readonly byte[] buffer;
            internal volatile bool Exceeded;
            internal Exception Error;
            internal int Count;
            internal BoundedCapture(KernelHandle pipe, int maximum, KernelHandle job) { this.pipe = pipe; this.job = job; buffer = new byte[maximum]; }
            internal void Read() {
                try {
                    byte[] chunk = new byte[4096];
                    while (true) {
                        uint read;
                        if (!Native.ReadFile(pipe, chunk, (uint)chunk.Length, out read, IntPtr.Zero)) {
                            int error = Marshal.GetLastWin32Error(); if (error == 109 || error == 232) break; throw new Win32Exception(error);
                        }
                        if (read == 0) break;
                        int remaining = buffer.Length - Count;
                        int take = Math.Min(remaining, (int)read); Buffer.BlockCopy(chunk, 0, buffer, Count, take); Count += take;
                        if (read > remaining) { Exceeded = true; SandboxNative.TerminateJobObject(job, 122); break; }
                    }
                } catch (Exception error) { Error = error; SandboxNative.TerminateJobObject(job, 125); }
            }
            internal byte[] Bytes() { byte[] bytes = new byte[Count]; Buffer.BlockCopy(buffer, 0, bytes, 0, Count); return bytes; }
        }
        private static Native.ExtendedLimits ReadJob(KernelHandle job) {
            int size = Marshal.SizeOf(typeof(Native.ExtendedLimits)); IntPtr data = Marshal.AllocHGlobal(size);
            try { uint returned; if (!Native.QueryInformationJobObject(job, 9, data, (uint)size, out returned)) throw new Win32Exception(Marshal.GetLastWin32Error()); return (Native.ExtendedLimits)Marshal.PtrToStructure(data, typeof(Native.ExtendedLimits)); }
            finally { Marshal.FreeHGlobal(data); }
        }
        private static void VerifyJob(KernelHandle job, SandboxLimits limits) {
            var actual = ReadJob(job);
            if (actual.Basic.ActiveProcessLimit != 1 || actual.Basic.LimitFlags != (0x2000 | 0x200 | 0x8 | 0x2) || actual.JobMemoryLimit.ToUInt64() != limits.MemoryBytes || actual.Basic.PerProcessUserTimeLimit != limits.CpuTime100ns) throw new InvalidOperationException("Job limits mismatch");
            int size = Marshal.SizeOf(typeof(Native.CpuRate)); IntPtr data = Marshal.AllocHGlobal(size);
            try {
                uint returned; if (!Native.QueryInformationJobObject(job, 15, data, (uint)size, out returned)) throw new Win32Exception(Marshal.GetLastWin32Error());
                var cpu = (Native.CpuRate)Marshal.PtrToStructure(data, typeof(Native.CpuRate));
                if (cpu.ControlFlags != 5 || cpu.CpuRateValue != limits.CpuRate) throw new InvalidOperationException("CPU rate mismatch");
            } finally { Marshal.FreeHGlobal(data); }
        }
        internal static string Quote(string value) {
            if (value == null || value.IndexOf('\0') >= 0) throw new ArgumentException("Invalid argument");
            var result = new StringBuilder("\""); int slashes = 0;
            foreach (char c in value) {
                if (c == '\\') { slashes++; continue; }
                if (c == '"') result.Append('\\', slashes * 2 + 1).Append(c);
                else result.Append('\\', slashes).Append(c);
                slashes = 0;
            }
            return result.Append('\\', slashes * 2).Append('"').ToString();
        }
    }
}
