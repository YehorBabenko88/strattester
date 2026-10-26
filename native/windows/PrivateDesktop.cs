// A private, non-visible, low-integrity USER namespace for session-0 LPAC startup.
// No WinSta0, shared service desktop, or existing object DACL is modified.
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;

namespace StratTester.Native {
    internal sealed class PrivateDesktop : IDisposable {
        internal static string Phase = "INITIAL";
        private readonly string name, packageSid, userSid;
        private IntPtr station, desktop;
        internal string Path { get { return name + "\\Default"; } }
        internal PrivateDesktop(string sid) {
            if (!Broker.HostedVm()) throw new InvalidOperationException("Disposable VM required");
            name = "StratTester-" + Guid.NewGuid().ToString("N"); packageSid = sid; userSid = WindowsIdentity.GetCurrent().User.Value;
            IntPtr original = DesktopNative.GetProcessWindowStation();
            if (original == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
            try {
                Phase = "CREATE_PRIVATE_STATION";
                WithDescriptor(0x20327, delegate(ref SandboxNative.SecurityAttributes security) {
                    station = DesktopNative.CreateWindowStation(name, 0, 0xf037f, ref security);
                    if (station == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
                });
                if (!DesktopNative.SetProcessWindowStation(station)) throw new Win32Exception(Marshal.GetLastWin32Error());
                try {
                    Phase = "CREATE_PRIVATE_DESKTOP";
                    WithDescriptor(0xf01ff, delegate(ref SandboxNative.SecurityAttributes security) {
                        desktop = DesktopNative.CreateDesktop("Default", null, IntPtr.Zero, 0, 0xf01ff, ref security);
                        if (desktop == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
                    });
                } finally {
                    if (!DesktopNative.SetProcessWindowStation(original)) throw new Win32Exception(Marshal.GetLastWin32Error());
                }
                Verify();
            } catch { Dispose(); throw; }
        }
        private delegate void DescriptorAction(ref SandboxNative.SecurityAttributes security);
        private void WithDescriptor(uint packageRights, DescriptorAction action) {
            IntPtr descriptor; uint length;
            string sddl = "D:P(A;;GA;;;SY)(A;;GA;;;" + userSid + ")(A;;0x" + packageRights.ToString("x") + ";;;" + packageSid + ")S:(ML;;NW;;;LW)";
            if (!SandboxNative.ConvertStringSecurityDescriptorToSecurityDescriptor(sddl, 1, out descriptor, out length)) throw new Win32Exception(Marshal.GetLastWin32Error());
            try {
                var attributes = new SandboxNative.SecurityAttributes { Size = (uint)Marshal.SizeOf(typeof(SandboxNative.SecurityAttributes)), Descriptor = descriptor, Inherit = false };
                action(ref attributes);
            } finally { SandboxNative.LocalFree(descriptor); }
        }
        internal void Verify() {
            Phase = "QUERY_PRIVATE_STATION"; VerifyObject(station, name, 0x20327, true);
            Phase = "QUERY_PRIVATE_DESKTOP"; VerifyObject(desktop, "Default", 0xf01ff, false);
            Phase = "PRIVATE_NAMESPACE_VERIFIED";
        }
        private void VerifyObject(IntPtr handle, string expectedName, uint packageRights, bool checkInvisible) {
            uint bytes; var objectName = new StringBuilder(256);
            if (!DesktopNative.GetUserObjectName(handle, 2, objectName, (uint)objectName.Capacity * 2, out bytes) || objectName.ToString() != expectedName) throw new InvalidOperationException("Private USER object identity mismatch");
            if (checkInvisible) {
                DesktopNative.UserObjectFlags flags;
                if (!DesktopNative.GetUserObjectFlags(handle, 1, out flags, (uint)Marshal.SizeOf(typeof(DesktopNative.UserObjectFlags)), out bytes)) throw new Win32Exception(Marshal.GetLastWin32Error());
                if ((flags.Flags & 1) != 0 || flags.Inherit != 0) throw new InvalidOperationException("Private station is visible or inheritable");
            }
            uint information = 4 | 16; // DACL + mandatory label; not audit-policy access.
            DesktopNative.GetUserObjectSecurity(handle, ref information, IntPtr.Zero, 0, out bytes);
            if (bytes < 20 || bytes > 65536 || Marshal.GetLastWin32Error() != 122) throw new Win32Exception(Marshal.GetLastWin32Error());
            IntPtr buffer = Marshal.AllocHGlobal((int)bytes);
            try {
                if (!DesktopNative.GetUserObjectSecurity(handle, ref information, buffer, bytes, out bytes)) throw new Win32Exception(Marshal.GetLastWin32Error());
                byte[] raw = new byte[bytes]; Marshal.Copy(buffer, raw, 0, raw.Length);
                var descriptor = new RawSecurityDescriptor(raw, 0);
                if (descriptor.DiscretionaryAcl == null || descriptor.DiscretionaryAcl.Count != 3 || descriptor.SystemAcl == null || descriptor.SystemAcl.Count != 1) throw new InvalidOperationException("Private USER object ACL shape mismatch");
                bool user = false, system = false, package = false;
                foreach (GenericAce ace in descriptor.DiscretionaryAcl) {
                    var allow = ace as CommonAce;
                    if (allow == null || allow.AceQualifier != AceQualifier.AccessAllowed || allow.AceFlags != AceFlags.None) throw new InvalidOperationException("Unexpected USER object ACE");
                    string value = allow.SecurityIdentifier.Value;
                    uint full = checkInvisible ? 0xf037fu : 0xf01ffu;
                    bool fullAccess = unchecked((uint)allow.AccessMask) == 0x10000000 || unchecked((uint)allow.AccessMask) == full;
                    if (value == userSid && fullAccess) user = true;
                    else if (value == "S-1-5-18" && fullAccess) system = true;
                    else if (value == packageSid && unchecked((uint)allow.AccessMask) == packageRights) package = true;
                    else throw new InvalidOperationException("Private USER object grants unknown access");
                }
                GenericAce label = descriptor.SystemAcl[0]; byte[] labelBytes = new byte[label.BinaryLength]; label.GetBinaryForm(labelBytes, 0);
                // Framework 4.7.2 exposes mandatory-label ACEs as CustomAce.
                if (!user || !system || !package || labelBytes.Length != 20 || labelBytes[0] != 17 || labelBytes[1] != 0 || BitConverter.ToUInt32(labelBytes, 4) != 1 || new SecurityIdentifier(labelBytes, 8).Value != "S-1-16-4096")
                    throw new InvalidOperationException("Private USER namespace not low integrity");
            } finally { Marshal.FreeHGlobal(buffer); }
        }
        public void Dispose() {
            if (desktop != IntPtr.Zero) { IntPtr value = desktop; desktop = IntPtr.Zero; if (!DesktopNative.CloseDesktop(value)) throw new Win32Exception(Marshal.GetLastWin32Error()); }
            if (station != IntPtr.Zero) { IntPtr value = station; station = IntPtr.Zero; if (!DesktopNative.CloseWindowStation(value)) throw new Win32Exception(Marshal.GetLastWin32Error()); }
        }
    }
    internal static class DesktopNative {
        [StructLayout(LayoutKind.Sequential)] internal struct UserObjectFlags { internal int Inherit, Reserved; internal uint Flags; }
        [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)] internal static extern IntPtr CreateWindowStation(string name, uint flags, uint access, ref SandboxNative.SecurityAttributes security);
        [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)] internal static extern IntPtr CreateDesktop(string name, string device, IntPtr mode, uint flags, uint access, ref SandboxNative.SecurityAttributes security);
        [DllImport("user32.dll", SetLastError = true)] internal static extern IntPtr GetProcessWindowStation();
        [DllImport("user32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool SetProcessWindowStation(IntPtr station);
        [DllImport("user32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool CloseWindowStation(IntPtr station);
        [DllImport("user32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool CloseDesktop(IntPtr desktop);
        [DllImport("user32.dll", EntryPoint = "GetUserObjectInformationW", CharSet = CharSet.Unicode, SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetUserObjectName(IntPtr handle, int kind, StringBuilder data, uint bytes, out uint returned);
        [DllImport("user32.dll", EntryPoint = "GetUserObjectInformationW", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetUserObjectFlags(IntPtr handle, int kind, out UserObjectFlags data, uint bytes, out uint returned);
        [DllImport("user32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool GetUserObjectSecurity(IntPtr handle, ref uint information, IntPtr data, uint bytes, out uint returned);
    }
}
