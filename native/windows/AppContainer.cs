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
                ProtectTree(Folder, true);
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
            KernelHandle token;
            if (!Native.OpenProcessToken(process, 8, out token)) throw new Win32Exception(Marshal.GetLastWin32Error());
            using (token) {
                if (ReadScalar(token, 29) != 1 || ReadScalar(token, 46) != 1 || ReadScalar(token, 30) != 0)
                    throw new InvalidOperationException("Not zero-capability LPAC");
                IntPtr data = ReadToken(token, 31);
                try {
                    IntPtr sid = Marshal.ReadIntPtr(data);
                    if (sid == IntPtr.Zero || new SecurityIdentifier(sid).Value != SidText) throw new InvalidOperationException("Wrong package identity");
                } finally { Marshal.FreeHGlobal(data); }
                data = Native.ReadTokenPrivileges(token);
                try { if (Marshal.ReadInt32(data) != 0) throw new InvalidOperationException("Child privileges remain"); }
                finally { Marshal.FreeHGlobal(data); }
            }
            uint flags;
            if (!SandboxNative.GetProcessMitigationPolicy(process, 13, out flags, new UIntPtr(4)) || (flags & 1) != 1)
                throw new InvalidOperationException("Child process policy missing");
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
            Native.InitializeProcThreadAttributeList(IntPtr.Zero, 5, 0, ref bytes);
            if (bytes.ToUInt64() == 0 || bytes.ToUInt64() > 1048576) throw new Win32Exception(Marshal.GetLastWin32Error());
            List = Marshal.AllocHGlobal((int)bytes.ToUInt64());
            try {
                if (!Native.InitializeProcThreadAttributeList(List, 5, 0, ref bytes)) throw new Win32Exception(Marshal.GetLastWin32Error());
                initialized = true;
                Add(0x20009, new SandboxNative.SecurityCapabilities { AppContainerSid = profile.Sid, Capabilities = IntPtr.Zero, CapabilityCount = 0, Reserved = 0 });
                Add(0x2000f, 1u); // PROCESS_CREATION_ALL_APPLICATION_PACKAGES_OPT_OUT
                Add(0x2000e, 1u); // PROCESS_CREATION_CHILD_PROCESS_RESTRICTED
                AddPointers(0x20002, handles); // Explicit handles only, no ambient inheritance.
                AddPointers(0x2000d, new IntPtr[] { job.DangerousGetHandle() }); // Atomic job admission.
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
        [DllImport("userenv.dll", CharSet = CharSet.Unicode)] internal static extern int CreateAppContainerProfile(string name, string displayName, string description, IntPtr capabilities, uint count, out IntPtr sid);
        [DllImport("userenv.dll", CharSet = CharSet.Unicode)] internal static extern int DeleteAppContainerProfile(string name);
        [DllImport("userenv.dll", CharSet = CharSet.Unicode)] internal static extern int GetAppContainerFolderPath(string sid, out IntPtr folder);
        [DllImport("advapi32.dll")] internal static extern IntPtr FreeSid(IntPtr sid);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetProcessMitigationPolicy(IntPtr process, int policy, out uint value, UIntPtr bytes);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool CreatePipe(out KernelHandle read, out KernelHandle write, ref SecurityAttributes security, uint bytes);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool SetHandleInformation(KernelHandle handle, uint mask, uint flags);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool TerminateJobObject(KernelHandle job, uint code);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetProcessTimes(IntPtr process, out long created, out long exited, out long kernel, out long user);
        [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetProcessHandleCount(IntPtr process, out uint count);
    }
}
