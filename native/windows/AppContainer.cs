// Component-only LPAC construction. No network, registry, COM or device capabilities.
// Microsoft: https://learn.microsoft.com/windows/win32/secauthz/implementing-an-appcontainer
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;

namespace StratTester.Native {
    internal sealed class AppContainerProfile : IDisposable {
        internal static string VerificationPhase = "INITIAL";
        internal readonly string Name;
        internal readonly string SidText;
        internal IntPtr Sid;
        internal readonly string Folder;
        private bool created;
        internal AppContainerProfile() {
            Name = "StratTester.Probe." + Guid.NewGuid().ToString("N");
            int result = SandboxNative.CreateAppContainerProfile(Name, Name, "Disposable component fixture", IntPtr.Zero, 0, out Sid);
            if (result < 0) Marshal.ThrowExceptionForHR(result);
            created = true;
            try {
                SidText = new SecurityIdentifier(Sid).Value;
                IntPtr folder;
                result = SandboxNative.GetAppContainerFolderPath(SidText, out folder);
                if (result < 0) Marshal.ThrowExceptionForHR(result);
                try { Folder = Marshal.PtrToStringUni(folder); }
                finally { Marshal.FreeCoTaskMem(folder); }
                if (String.IsNullOrEmpty(Folder) || !Directory.Exists(Folder)) throw new IOException("Missing profile folder");
                // The default profile is writable. This experiment has stdout-only
                // output, so replace every existing profile DACL before admission.
                string packageRoot = Folder;
                if (String.Equals(Path.GetFileName(Folder.TrimEnd('\\')), "AC", StringComparison.OrdinalIgnoreCase)) packageRoot = Path.GetDirectoryName(Folder);
                if (!String.Equals(Path.GetFileName(packageRoot), Name, StringComparison.OrdinalIgnoreCase) && !String.Equals(Path.GetFileName(packageRoot), SidText, StringComparison.OrdinalIgnoreCase))
                    throw new IOException("Unexpected package root");
                ProtectTree(packageRoot, true);
            } catch { Dispose(); throw; }
        }
        internal void GrantReadTree(string root) {
            // Caller must supply a newly created owned fixture, never a caller path.
            ProtectTree(root, true);
        }
        private void ProtectTree(string path, bool directory) {
            if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) throw new IOException("Reparse fixture refused");
            var user = WindowsIdentity.GetCurrent().User;
            var system = new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null);
            var package = new SecurityIdentifier(SidText);
            if (directory) {
                var acl = new DirectorySecurity();
                acl.SetAccessRuleProtection(true, false);
                acl.AddAccessRule(new FileSystemAccessRule(user, FileSystemRights.FullControl, InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
                acl.AddAccessRule(new FileSystemAccessRule(system, FileSystemRights.FullControl, InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
                acl.AddAccessRule(new FileSystemAccessRule(package, FileSystemRights.ReadAndExecute, InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
                Directory.SetAccessControl(path, acl);
                foreach (string child in Directory.GetFileSystemEntries(path)) ProtectTree(child, Directory.Exists(child));
            } else {
                var acl = new FileSecurity(); acl.SetAccessRuleProtection(true, false);
                acl.AddAccessRule(new FileSystemAccessRule(user, FileSystemRights.FullControl, AccessControlType.Allow));
                acl.AddAccessRule(new FileSystemAccessRule(system, FileSystemRights.FullControl, AccessControlType.Allow));
                acl.AddAccessRule(new FileSystemAccessRule(package, FileSystemRights.ReadAndExecute, AccessControlType.Allow));
                File.SetAccessControl(path, acl);
            }
        }
        internal void VerifyToken(IntPtr process) {
            VerificationPhase = "OPEN_CHILD_TOKEN";
            KernelHandle token;
            if (!Native.OpenProcessToken(process, 8 | 2, out token)) throw new Win32Exception(Marshal.GetLastWin32Error());
            using (token) {
                VerificationPhase = "QUERY_APP_CONTAINER"; int app = ReadScalar(token, 29);
                VerificationPhase = "CHECK_LPAC_AUTHORIZATION"; bool lpac = IsLpac(token);
                VerificationPhase = "QUERY_CAPABILITIES"; int caps = ReadScalar(token, 30);
                if (app != 1 || !lpac || caps != 0)
                    throw new InvalidOperationException("Not zero-capability LPAC");
                VerificationPhase = "QUERY_PACKAGE_SID";
                IntPtr data = ReadToken(token, 31);
                try {
                    IntPtr sid = Marshal.ReadIntPtr(data);
                    if (sid == IntPtr.Zero || new SecurityIdentifier(sid).Value != SidText) throw new InvalidOperationException("Wrong package identity");
                } finally { Marshal.FreeHGlobal(data); }
                VerificationPhase = "QUERY_CHILD_PRIVILEGES"; ResearchSandbox.VerifyResearchPrivileges(token);
            }
            uint flags;
            VerificationPhase = "QUERY_CHILD_POLICY";
            if (!SandboxNative.GetProcessMitigationPolicy(process, 13, out flags, new UIntPtr(4)) || (flags & 1) != 1)
                throw new InvalidOperationException("Child process policy missing");
            VerificationPhase = "QUERY_WIN32K_LOCKDOWN";
            if (!SandboxNative.GetProcessMitigationPolicy(process, 4, out flags, new UIntPtr(4)) || flags != 1)
                throw new InvalidOperationException("Win32k lockdown missing");
            VerificationPhase = "TOKEN_VERIFIED";
        }
        internal static bool IsLpac(KernelHandle primary) {
            // Class 46 is not a supported GetTokenInformation contract on the
            // hosted OS (ERROR_INVALID_PARAMETER even for a real LPAC). Verify
            // the documented authorization distinction instead: AAP must not
            // grant access, while ARAP must grant the same requested read right.
            KernelHandle token;
            if (!SandboxNative.DuplicateToken(primary, 2, out token)) throw new Win32Exception(Marshal.GetLastWin32Error());
            using (token) return !PackageAccess(token, "S-1-15-2-1") && PackageAccess(token, "S-1-15-2-2");
        }
        private static bool PackageAccess(KernelHandle token, string sid) {
            IntPtr descriptor; uint length;
            if (!SandboxNative.ConvertStringSecurityDescriptorToSecurityDescriptor("O:SYG:SYD:(A;;0x1;;;WD)(A;;0x1;;;" + sid + ")", 1, out descriptor, out length)) throw new Win32Exception(Marshal.GetLastWin32Error());
            IntPtr privileges = Marshal.AllocHGlobal(1024);
            try {
                var mapping = new SandboxNative.GenericMapping { Read = 1, Write = 2, Execute = 4, All = 7 };
                uint bytes = 1024, granted; bool access;
                if (!SandboxNative.AccessCheck(descriptor, token, 1, ref mapping, privileges, ref bytes, out granted, out access)) throw new Win32Exception(Marshal.GetLastWin32Error());
                return access && (granted & 1) == 1;
            } finally { Marshal.FreeHGlobal(privileges); SandboxNative.LocalFree(descriptor); }
        }
        internal static int ReadScalar(KernelHandle token, int kind) {
            IntPtr data = ReadToken(token, kind);
            try { return Marshal.ReadInt32(data); } finally { Marshal.FreeHGlobal(data); }
        }
        private static IntPtr ReadToken(KernelHandle token, int kind) {
            uint bytes;
            Native.GetTokenInformation(token, kind, IntPtr.Zero, 0, out bytes);
            if (bytes < 4 || bytes > 1048576 || Marshal.GetLastWin32Error() != 122) throw new Win32Exception(Marshal.GetLastWin32Error());
            IntPtr data = Marshal.AllocHGlobal((int)bytes);
            if (!Native.GetTokenInformation(token, kind, data, bytes, out bytes)) { Marshal.FreeHGlobal(data); throw new Win32Exception(Marshal.GetLastWin32Error()); }
            return data;
        }
        public void Dispose() {
            // No profile deletion until the owning engine has waited for child death.
            if (created) { int hr = SandboxNative.DeleteAppContainerProfile(Name); if (hr < 0) Marshal.ThrowExceptionForHR(hr); created = false; }
            if (Sid != IntPtr.Zero) { SandboxNative.FreeSid(Sid); Sid = IntPtr.Zero; }
        }
    }

    internal sealed class SandboxAttributes : IDisposable {
        internal IntPtr List;
        private readonly List<IntPtr> values = new List<IntPtr>();
        private bool initialized;
        internal SandboxAttributes(AppContainerProfile profile, KernelHandle job, IntPtr[] handles) {
            UIntPtr bytes = UIntPtr.Zero;
            Native.InitializeProcThreadAttributeList(IntPtr.Zero, 6, 0, ref bytes);
            if (bytes.ToUInt64() == 0 || bytes.ToUInt64() > 1048576) throw new Win32Exception(Marshal.GetLastWin32Error());
            List = Marshal.AllocHGlobal((int)bytes.ToUInt64());
            try {
                if (!Native.InitializeProcThreadAttributeList(List, 6, 0, ref bytes)) throw new Win32Exception(Marshal.GetLastWin32Error());
                initialized = true;
                Add(0x20009, new SandboxNative.SecurityCapabilities { AppContainerSid = profile.Sid, Capabilities = IntPtr.Zero, CapabilityCount = 0, Reserved = 0 });
                Add(0x2000f, 1u); // PROCESS_CREATION_ALL_APPLICATION_PACKAGES_OPT_OUT
                Add(0x2000e, 1u); // PROCESS_CREATION_CHILD_PROCESS_RESTRICTED
                AddPointers(0x20002, handles); // Explicit handles only, no ambient inheritance.
                AddPointers(0x2000d, new IntPtr[] { job.DangerousGetHandle() }); // Atomic job admission.
                Add(0x20007, 0x10000000UL); // Headless worker: disable Win32k system calls.
            } catch { Dispose(); throw; }
        }
        private void Add<T>(uint key, T value) where T : struct {
            int size = Marshal.SizeOf(typeof(T)); IntPtr data = Marshal.AllocHGlobal(size); values.Add(data);
            Marshal.StructureToPtr(value, data, false); Update(key, data, size);
        }
        private void AddPointers(uint key, IntPtr[] handles) {
            int size = checked(IntPtr.Size * handles.Length); IntPtr data = Marshal.AllocHGlobal(size); values.Add(data);
            for (int i = 0; i < handles.Length; i++) Marshal.WriteIntPtr(data, i * IntPtr.Size, handles[i]);
            Update(key, data, size);
        }
        private void Update(uint key, IntPtr value, int bytes) {
            if (!Native.UpdateProcThreadAttribute(List, 0, new UIntPtr(key), value, new UIntPtr((uint)bytes), IntPtr.Zero, IntPtr.Zero)) throw new Win32Exception(Marshal.GetLastWin32Error());
        }
        public void Dispose() {
            if (initialized) { Native.DeleteProcThreadAttributeList(List); initialized = false; }
            if (List != IntPtr.Zero) { Marshal.FreeHGlobal(List); List = IntPtr.Zero; }
            foreach (IntPtr value in values) Marshal.FreeHGlobal(value); values.Clear();
        }
    }

    internal static class SandboxNative {
        [StructLayout(LayoutKind.Sequential)] internal struct SecurityCapabilities { internal IntPtr AppContainerSid, Capabilities; internal uint CapabilityCount, Reserved; }
        [StructLayout(LayoutKind.Sequential)] internal struct SecurityAttributes { internal uint Size; internal IntPtr Descriptor; [MarshalAs(UnmanagedType.Bool)] internal bool Inherit; }
        [StructLayout(LayoutKind.Sequential)] internal struct GenericMapping { internal uint Read, Write, Execute, All; }
        [DllImport("userenv.dll", CharSet = CharSet.Unicode)] internal static extern int CreateAppContainerProfile(string name, string displayName, string description, IntPtr capabilities, uint count, out IntPtr sid);
        [DllImport("userenv.dll", CharSet = CharSet.Unicode)] internal static extern int DeleteAppContainerProfile(string name);
        [DllImport("userenv.dll", CharSet = CharSet.Unicode)] internal static extern int GetAppContainerFolderPath(string sid, out IntPtr folder);
        [DllImport("advapi32.dll")] internal static extern IntPtr FreeSid(IntPtr sid);
        [DllImport("advapi32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool DuplicateToken(KernelHandle source, int level, out KernelHandle impersonation);
        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool ConvertStringSecurityDescriptorToSecurityDescriptor(string text, uint revision, out IntPtr descriptor, out uint length);
        [DllImport("advapi32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool AccessCheck(IntPtr descriptor, KernelHandle token, uint desired, ref GenericMapping mapping, IntPtr privileges, ref uint bytes, out uint granted, [MarshalAs(UnmanagedType.Bool)] out bool status);
        [DllImport("kernel32.dll")] internal static extern IntPtr LocalFree(IntPtr memory);
        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool LookupPrivilegeValue(string system, string name, out long luid);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetProcessMitigationPolicy(IntPtr process, int policy, out uint value, UIntPtr bytes);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool CreatePipe(out KernelHandle read, out KernelHandle write, ref SecurityAttributes security, uint bytes);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool SetHandleInformation(KernelHandle handle, uint mask, uint flags);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool TerminateJobObject(KernelHandle job, uint code);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetProcessTimes(IntPtr process, out long created, out long exited, out long kernel, out long user);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetProcessHandleCount(IntPtr process, out uint count);
    }
}
