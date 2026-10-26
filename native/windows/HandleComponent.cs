using System;
using System.Collections;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Security.Cryptography;

namespace StratTester.Native {
    // Explicit Unicode allowlist; no CI tokens, credentials, PATH or COMSPEC.
    // The operational guard variables never constitute research authorization.
    internal sealed class ProbeEnvironment : IDisposable {
        internal IntPtr Block;
        private static readonly string[] Names = { "GITHUB_ACTIONS", "RUNNER_ENVIRONMENT", "RUNNER_OS", "SystemRoot", "TEMP", "TMP", "WINDIR" };
        internal ProbeEnvironment() {
            string windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
            string temp = Path.GetTempPath();
            if (String.IsNullOrEmpty(windows) || windows.IndexOf('\0') >= 0 || temp.IndexOf('\0') >= 0) throw new InvalidOperationException("Invalid probe environment");
            string[] entries = { "GITHUB_ACTIONS=true", "RUNNER_ENVIRONMENT=github-hosted", "RUNNER_OS=Windows", "SystemRoot=" + windows,
                "TEMP=" + temp, "TMP=" + temp, "WINDIR=" + windows };
            Block = Marshal.StringToHGlobalUni(String.Join("\0", entries) + "\0");
        }
        internal static bool IsMinimal() {
            foreach (DictionaryEntry item in Environment.GetEnvironmentVariables()) {
                bool allowed = false;
                foreach (string name in Names) if (String.Equals((string)item.Key, name, StringComparison.OrdinalIgnoreCase)) allowed = true;
                if (!allowed) return false;
            }
            return true;
        }
        public void Dispose() { if (Block != IntPtr.Zero) { Marshal.FreeHGlobal(Block); Block = IntPtr.Zero; } }
    }

    internal static class HandleComponent {
        internal static int Probe(string[] args) {
            long inputValue, canaryValue; uint volume, high, low;
            if (args.Length != 7 || args[1] != "COMPONENT_TESTS_ONLY" || !Int64.TryParse(args[2], out inputValue) ||
                !Int64.TryParse(args[3], out canaryValue) || !UInt32.TryParse(args[4], out volume) || !UInt32.TryParse(args[5], out high) || !UInt32.TryParse(args[6], out low) || inputValue <= 0 || canaryValue <= 0) return 111;
            using (var input = new KernelHandle(new IntPtr(inputValue), false))
            using (var canary = new KernelHandle(new IntPtr(canaryValue), false)) {
                Native.FileInformation info;
                if (Native.GetFileInformationByHandle(canary, out info) && info.Volume == volume && info.IndexHigh == high && info.IndexLow == low) return 112;
                byte[] data = new byte[4]; uint count;
                if (!Native.ReadFile(input, data, 4, out count, IntPtr.Zero) || count != 3 || data[0] != 97 || data[1] != 98 || data[2] != 99) return 113;
                // This deliberately attempts a one-byte mutation of the owned
                // disposable fixture. Success is a failure, never isolation.
                long position;
                if (!Native.SetFilePointerEx(input, 0, out position, 0) || position != 0) return 115;
                uint written;
                if (Native.WriteFile(input, new byte[] { 120 }, 1, out written, IntPtr.Zero) || Marshal.GetLastWin32Error() != 5) return 114;
                return 110;
            }
        }
        internal static void Run() {
            string folder = Path.Combine(Path.GetTempPath(), "native-handles-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(folder);
            string inputPath = Path.Combine(folder, "input.txt"), canaryPath = Path.Combine(folder, "canary.txt");
            try {
                File.WriteAllBytes(inputPath, new byte[] { 97, 98, 99 });
                File.WriteAllText(canaryPath, "disposable canary, no credentials");
                using (var locked = LockedInput.Open(inputPath, 3))
                using (var canary = Native.CreateFile(canaryPath, 0xc0000000, 1, IntPtr.Zero, 3, 0x00200000, IntPtr.Zero)) {
                    if (canary.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error());
                    KernelHandle inputDuplicate, canaryDuplicate;
                    if (!Native.DuplicateHandle(Native.GetCurrentProcess(), locked.Leaf, Native.GetCurrentProcess(), out inputDuplicate, 0, true, 2)) throw new Win32Exception(Marshal.GetLastWin32Error());
                    using (inputDuplicate) {
                        if (!Native.DuplicateHandle(Native.GetCurrentProcess(), canary, Native.GetCurrentProcess(), out canaryDuplicate, 0, true, 2)) throw new Win32Exception(Marshal.GetLastWin32Error());
                        using (canaryDuplicate) {
                            long position;
                            if (!Native.SetFilePointerEx(inputDuplicate, 0, out position, 0) || position != 0) throw new Win32Exception(Marshal.GetLastWin32Error());
                            Native.FileInformation canaryId;
                            if (!Native.GetFileInformationByHandle(canaryDuplicate, out canaryId)) throw new Win32Exception(Marshal.GetLastWin32Error());
                            RunOwned(inputDuplicate, canaryDuplicate, canaryId);
                        }
                    }
                }
                using (var file = File.OpenRead(inputPath))
                using (var sha = SHA256.Create()) {
                    if (file.Length != 3 || BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "").ToLowerInvariant() !=
                        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
                        throw new InvalidOperationException("Read-only fixture changed");
                }
            } finally {
                if (File.Exists(inputPath)) File.Delete(inputPath);
                if (File.Exists(canaryPath)) File.Delete(canaryPath);
                if (Directory.Exists(folder)) Directory.Delete(folder);
            }
        }
        private static void RunOwned(KernelHandle input, KernelHandle canary, Native.FileInformation canaryId) {
            UIntPtr bytes = UIntPtr.Zero;
            Native.InitializeProcThreadAttributeList(IntPtr.Zero, 1, 0, ref bytes);
            if (bytes.ToUInt64() == 0 || bytes.ToUInt64() > 1048576) throw new Win32Exception(Marshal.GetLastWin32Error());
            IntPtr attributes = Marshal.AllocHGlobal((int)bytes.ToUInt64()), list = Marshal.AllocHGlobal(IntPtr.Size);
            bool initialized = false;
            try {
                if (!Native.InitializeProcThreadAttributeList(attributes, 1, 0, ref bytes)) throw new Win32Exception(Marshal.GetLastWin32Error());
                initialized = true;
                Marshal.WriteIntPtr(list, input.DangerousGetHandle());
                if (!Native.UpdateProcThreadAttribute(attributes, 0, new UIntPtr(0x20002), list, new UIntPtr((uint)IntPtr.Size), IntPtr.Zero, IntPtr.Zero)) throw new Win32Exception(Marshal.GetLastWin32Error());
                string image = typeof(Broker).Assembly.Location;
                using (var imageLock = File.Open(image, FileMode.Open, FileAccess.Read, FileShare.Read))
                using (var token = PreparedComponents.CreatePrivilegeRemovedToken())
                using (var job = PreparedComponents.CreateBoundedJob(134217728, 1000, 50000000))
                using (var environment = new ProbeEnvironment()) {
                    var startup = new Native.StartupInfoEx { Attributes = attributes };
                    startup.Startup.Size = (uint)Marshal.SizeOf(typeof(Native.StartupInfoEx));
                    string command = "\"" + image + "\" --owned-handle-probe COMPONENT_TESTS_ONLY " + input.DangerousGetHandle().ToInt64() + " " + canary.DangerousGetHandle().ToInt64() + " " + canaryId.Volume + " " + canaryId.IndexHigh + " " + canaryId.IndexLow;
                    Native.ProcessInformation child;
                    if (!Native.CreateProcessAsUserEx(token, image, new StringBuilder(command), IntPtr.Zero, IntPtr.Zero, true,
                        0x4 | 0x80000 | 0x08000000 | 0x400, environment.Block, Path.GetDirectoryName(image), ref startup, out child)) throw new Win32Exception(Marshal.GetLastWin32Error());
                    try {
                        if (!Native.AssignProcessToJobObject(job, child.Process)) throw new Win32Exception(Marshal.GetLastWin32Error());
                        bool assigned;
                        if (!Native.IsProcessInJob(child.Process, job.DangerousGetHandle(), out assigned) || !assigned) throw new InvalidOperationException("Handle probe job assignment failed");
                        if (Native.ResumeThread(child.Thread) == UInt32.MaxValue) throw new Win32Exception(Marshal.GetLastWin32Error());
                        if (Native.WaitForSingleObject(child.Process, 5000) != 0) throw new InvalidOperationException("Handle probe timed out");
                        uint code;
                        if (!Native.GetExitCodeProcess(child.Process, out code) || code != 110) throw new InvalidOperationException("Handle/environment probe failed");
                    } finally {
                        Native.TerminateProcess(child.Process, 125); Native.WaitForSingleObject(child.Process, 5000);
                        Native.CloseHandle(child.Thread); Native.CloseHandle(child.Process);
                    }
                }
            } finally {
                if (initialized) Native.DeleteProcThreadAttributeList(attributes);
                Marshal.FreeHGlobal(attributes); Marshal.FreeHGlobal(list);
            }
        }
    }
}
