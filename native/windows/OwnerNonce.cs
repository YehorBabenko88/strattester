// Atomic, persistent owner nonce consumption. Claim never deletes a claim,
// including when validation, writing or flushing fails after FILE_CREATE.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

namespace StratTester.Native {
 internal static class OwnerNonce {
  const uint ReadControl=0x20000, Synchronize=0x100000, ReadAttributes=0x80;
  const uint FileOpen=1, FileCreate=2, DirectoryFile=1, NonDirectoryFile=0x40;
  const uint Synchronous=0x20, OpenReparsePoint=0x200000, WriteThrough=2;
  const uint DontReparse=0x1000, CaseInsensitive=0x40;
  static readonly SecurityIdentifier SystemSid=new SecurityIdentifier("S-1-5-18");
  static readonly SecurityIdentifier AdminSid=new SecurityIdentifier("S-1-5-32-544");

  internal static void Claim(string ledgerRoot,string nonceHex64,string authorizationSha256) {
   ValidateHex(nonceHex64);ValidateHex(authorizationSha256);ValidatePath(ledgerRoot);
   using(var root=PinRoot(ledgerRoot))
   using(var receipt=CreateReceipt(root,nonceHex64)) {
    // Persist the empty tombstone before attempting a receipt. A terminated
    // caller or a later write/flush failure must not make this nonce reusable.
    Flush(receipt);
    byte[] bytes=Encoding.ASCII.GetBytes("STRATTESTER_OWNER_NONCE_V1\nnonce="+nonceHex64+"\nauthorization_sha256="+authorizationSha256+"\n");
    uint written;
    if(!Native.WriteFile(receipt,bytes,(uint)bytes.Length,out written,IntPtr.Zero)||written!=bytes.Length)
     throw new IOException("Nonce receipt write failed; nonce remains consumed");
    Flush(receipt);
    Native.FileInformation info=CheckObject(receipt,false,ledgerRoot+"\\"+nonceHex64+".claim");
    if(info.SizeHigh!=0||info.SizeLow!=bytes.Length)throw new IOException("Nonce receipt length changed; nonce remains consumed");
    CheckSecurity(receipt,root.User,true);
    long position;
    if(!Native.SetFilePointerEx(receipt,0,out position,0))throw new IOException("Nonce receipt seek");
    byte[] actual=new byte[bytes.Length];uint read;
    if(!Native.ReadFile(receipt,actual,(uint)actual.Length,out read,IntPtr.Zero)||read!=bytes.Length)
     throw new IOException("Nonce receipt verification failed; nonce remains consumed");
    for(int i=0;i<bytes.Length;i++)if(bytes[i]!=actual[i])throw new IOException("Nonce receipt mismatch; nonce remains consumed");
   }
  }

  static void ValidateHex(string value) {
   if(value==null||!Regex.IsMatch(value,"\\A[0-9a-f]{64}\\z"))throw new FormatException("Lowercase SHA256/nonce required");
  }
  static void ValidateComponent(string part) {
   if(String.IsNullOrEmpty(part)||part=="."||part==".."||part.EndsWith(".")||part.EndsWith(" "))throw new FormatException("Unsafe path component");
   foreach(char c in part)if(c<32||"\\/:*?\"<>|".IndexOf(c)>=0)throw new FormatException("Unsafe path character");
   string stem=part.Split('.')[0].TrimEnd(' ').ToUpperInvariant();
   if(stem=="CON"||stem=="PRN"||stem=="AUX"||stem=="NUL"||stem=="CONIN$"||stem=="CONOUT$"||
      (stem.Length==4&&(stem.StartsWith("COM")||stem.StartsWith("LPT"))&&"123456789¹²³".IndexOf(stem[3])>=0))
    throw new FormatException("Device alias");
  }
  static void ValidatePath(string path) {
   if(String.IsNullOrEmpty(path)||path.Length<4||path.Length>160||!((path[0]>='A'&&path[0]<='Z')||(path[0]>='a'&&path[0]<='z'))||path[1]!=':'||path[2]!='\\')
    throw new FormatException("Canonical local ledger path required");
   foreach(string part in path.Substring(3).Split('\\'))ValidateComponent(part);
   if(!String.Equals(Path.GetFullPath(path),path,StringComparison.OrdinalIgnoreCase))throw new FormatException("Path normalization");
  }

  sealed class PinnedRoot:IDisposable {
   internal readonly List<KernelHandle> Handles=new List<KernelHandle>();
   internal SecurityIdentifier User;internal string Path;internal uint Volume;
   internal KernelHandle Leaf {get{return Handles[Handles.Count-1];}}
   public void Dispose(){for(int i=Handles.Count-1;i>=0;i--)Handles[i].Dispose();Handles.Clear();}
  }
  static PinnedRoot PinRoot(string path) {
   var root=new PinnedRoot();
   try {
    using(var identity=WindowsIdentity.GetCurrent()){root.User=identity.User;if(root.User==null)throw new IOException("Broker SID unavailable");}
    root.Path=path;string current=path.Substring(0,3);
    if(GetDriveType(current)!=3)throw new IOException("Local fixed disk required");
    var drive=Native.CreateFile(current,ReadControl|ReadAttributes|Synchronize|0x20,1,IntPtr.Zero,3,0x2200000,IntPtr.Zero);
    if(drive.IsInvalid){drive.Dispose();throw new Win32Exception(Marshal.GetLastWin32Error());}
    root.Handles.Add(drive);root.Volume=CheckObject(drive,true,current).Volume;CheckSecurity(drive,root.User,false);
    var fs=new StringBuilder(32);uint serial,maximum,flags;
    if(!GetVolumeInformationByHandle(drive,null,0,out serial,out maximum,out flags,fs,(uint)fs.Capacity)||fs.ToString()!="NTFS"||(flags&8)==0)
     throw new IOException("Persistent NTFS ACL ledger required");
    string[] parts=path.Substring(3).Split('\\');
    for(int i=0;i<parts.Length;i++) {
     // Every descent is relative to the retained parent, never a reconstructed
     // path. No write/delete sharing; OBJ_DONT_REPARSE has no fallback.
     var next=Relative(root.Leaf,parts[i],ReadControl|ReadAttributes|Synchronize|0x20,FileOpen,DirectoryFile|Synchronous|OpenReparsePoint,IntPtr.Zero);
     root.Handles.Add(next);current=System.IO.Path.Combine(current,parts[i]);
     if(CheckObject(next,true,current).Volume!=root.Volume)throw new IOException("Volume changed");
     CheckSecurity(next,root.User,i==parts.Length-1);
    }
    return root;
   }catch{root.Dispose();throw;}
  }

  static Native.FileInformation CheckObject(KernelHandle handle,bool directory,string expected) {
   Native.FileInformation info;Native.AttributeTag tag;
   if(!Native.GetFileInformationByHandle(handle,out info)||Native.GetFileType(handle)!=1||
      !Native.GetFileInformationByHandleEx(handle,9,out tag,(uint)Marshal.SizeOf(typeof(Native.AttributeTag)))||
      (info.Attributes&0x400)!=0||tag.Tag!=0||(tag.Attributes&0x400)!=0||((info.Attributes&0x10)!=0)!=directory)
    throw new IOException("Disk/reparse/type rejected");
   if(!directory&&info.Links!=1)throw new IOException("Hardlink alias rejected");
   var name=new StringBuilder(1024);uint length=Native.GetFinalPathNameByHandle(handle,name,(uint)name.Capacity,0);
   if(length==0||length>=name.Capacity||!String.Equals(name.ToString().TrimEnd('\\'),("\\\\?\\"+expected).TrimEnd('\\'),StringComparison.OrdinalIgnoreCase))
    throw new IOException("Noncanonical final path");
   return info;
  }

  static bool Trusted(SecurityIdentifier sid,SecurityIdentifier user) {return sid==user||sid==SystemSid||sid==AdminSid;}
  static void CheckSecurity(KernelHandle handle,SecurityIdentifier user,bool strict) {
   IntPtr owner,group,dacl,sacl,descriptor;
   uint error=GetSecurityInfo(handle,1,5,out owner,out group,out dacl,out sacl,out descriptor);
   if(error!=0)throw new Win32Exception((int)error);
   try {
    uint length=GetSecurityDescriptorLength(descriptor);if(length<20||length>65536)throw new IOException("ACL budget");
    byte[] bytes=new byte[length];Marshal.Copy(descriptor,bytes,0,bytes.Length);var sd=new RawSecurityDescriptor(bytes,0);
    if(sd.DiscretionaryAcl==null||(sd.ControlFlags&ControlFlags.DiscretionaryAclPresent)==0)throw new IOException("Null/missing DACL");
    if(strict&&((sd.ControlFlags&ControlFlags.DiscretionaryAclProtected)==0||!Trusted(sd.Owner,user)))throw new IOException("Protected owner ledger DACL required");
    bool ownerGrant=false;
    foreach(GenericAce generic in sd.DiscretionaryAcl) {
     var ace=generic as CommonAce;
     if(ace==null||ace.IsCallback)throw new IOException("Unsupported ACL entry");
     if((ace.AceFlags&AceFlags.InheritOnly)!=0)continue;
     if(ace.AceQualifier==AceQualifier.AccessDenied)continue;
     if(ace.AceQualifier!=AceQualifier.AccessAllowed)throw new IOException("Unsupported ACL qualifier");
     uint mask=unchecked((uint)ace.AccessMask);
     // Ancestors must not let an untrusted principal delete/replace this
     // protected ledger between calls. Inherit-only creator ACEs do not apply.
     uint destructive=0x10000000|0x40000000|0x10000|0x40000|0x80000|0x40|0x100;
     if(!Trusted(ace.SecurityIdentifier,user)&&(strict||((mask&destructive)!=0)))throw new IOException("Unsafe ledger/ancestor ACL");
     if(ace.SecurityIdentifier==user&&((mask&0x10000000)!=0||(mask&0x1f01ff)==0x1f01ff))ownerGrant=true;
    }
    if(strict&&!ownerGrant)throw new IOException("Explicit broker full-control grant required");
   }finally{LocalFree(descriptor);}
  }

  static byte[] ProtectedDescriptor(SecurityIdentifier user) {
   var sd=new RawSecurityDescriptor("O:"+user.Value+"G:"+user.Value+"D:P(A;;FA;;;"+user.Value+")(A;;FA;;;SY)(A;;FA;;;BA)");
   byte[] bytes=new byte[sd.BinaryLength];sd.GetBinaryForm(bytes,0);return bytes;
  }
  static KernelHandle CreateReceipt(PinnedRoot root,string nonce) {
   ValidateHex(nonce);byte[] sd=ProtectedDescriptor(root.User);IntPtr descriptor=Marshal.AllocHGlobal(sd.Length);
   try {
    Marshal.Copy(sd,0,descriptor,sd.Length);
    // FILE_CREATE atomically fails on every existing object, including empty,
    // partial, directory, reparse and hardlink objects. Never OPEN_IF/overwrite.
    var receipt=Relative(root.Leaf,nonce+".claim",0xC0000000|ReadControl|Synchronize,FileCreate,NonDirectoryFile|Synchronous|OpenReparsePoint|WriteThrough,descriptor);
    try {
     var info=CheckObject(receipt,false,root.Path+"\\"+nonce+".claim");
     if(info.Volume!=root.Volume||info.SizeHigh!=0||info.SizeLow!=0)throw new IOException("New nonce identity mismatch");
     CheckSecurity(receipt,root.User,true);return receipt;
    }catch{receipt.Dispose();throw;}
   }finally{Marshal.FreeHGlobal(descriptor);}
  }
  static KernelHandle Relative(KernelHandle parent,string component,uint access,uint disposition,uint options,IntPtr security) {
   ValidateComponent(component);
   IntPtr text=Marshal.StringToHGlobalUni(component),unicode=IntPtr.Zero;
   try {
    var name=new UnicodeString{Length=checked((ushort)(component.Length*2)),MaximumLength=checked((ushort)(component.Length*2+2)),Buffer=text};
    unicode=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(UnicodeString)));Marshal.StructureToPtr(name,unicode,false);
    var attributes=new ObjectAttributes{Length=(uint)Marshal.SizeOf(typeof(ObjectAttributes)),RootDirectory=parent.DangerousGetHandle(),ObjectName=unicode,Attributes=DontReparse|CaseInsensitive,SecurityDescriptor=security};
    IntPtr result;IoStatus status;
    int code=NtCreateFile(out result,access,ref attributes,out status,IntPtr.Zero,0x80,1,disposition,options,IntPtr.Zero,0);
    if(code!=0){if(result!=IntPtr.Zero&&result!=new IntPtr(-1))Native.CloseHandle(result);throw new IOException("NT relative create/open refused: "+unchecked((uint)code).ToString("x8"));}
    var handle=new KernelHandle(result,true);
    if(handle.IsInvalid||status.Information.ToUInt64()!=(disposition==FileCreate?2UL:1UL)){handle.Dispose();throw new IOException("Unexpected NT disposition");}
    return handle;
   }finally{if(unicode!=IntPtr.Zero)Marshal.FreeHGlobal(unicode);Marshal.FreeHGlobal(text);GC.KeepAlive(parent);}
  }
  static void Flush(KernelHandle handle) {if(!FlushFileBuffers(handle))throw new Win32Exception(Marshal.GetLastWin32Error(),"Nonce flush failed; nonce remains consumed");}

  // Hosted disposable fixtures only. The guard runs before even choosing paths.
  internal static void SelfTest() {
   if(Environment.GetEnvironmentVariable("GITHUB_ACTIONS")!="true"||Environment.GetEnvironmentVariable("RUNNER_ENVIRONMENT")!="github-hosted"||Environment.GetEnvironmentVariable("RUNNER_OS")!="Windows")
    throw new InvalidOperationException("Disposable hosted Windows required");
   string fixture=System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"StratTester-nonce-"+Guid.NewGuid().ToString("N"));
   SecurityIdentifier user;using(var id=WindowsIdentity.GetCurrent())user=id.User;
   var acl=new DirectorySecurity();acl.SetSecurityDescriptorBinaryForm(ProtectedDescriptor(user));
   Directory.CreateDirectory(fixture,acl);
   try {
    string ledger=System.IO.Path.Combine(fixture,"ledger");Directory.CreateDirectory(ledger,acl);
    string nonce=new string('1',64),authorization=new string('a',64);Claim(ledger,nonce,authorization);
    MustFail(delegate{Claim(ledger,nonce,authorization);});
    string receipt=System.IO.Path.Combine(ledger,nonce+".claim");
    if(!File.ReadAllText(receipt).Contains("authorization_sha256="+authorization+"\n"))throw new IOException("Receipt provenance");
    int winners=0;Exception unexpected=null;var start=new ManualResetEvent(false);Thread[] threads=new Thread[8];
    for(int i=0;i<threads.Length;i++)threads[i]=new Thread(delegate(){start.WaitOne();try{Claim(ledger,new string('2',64),authorization);Interlocked.Increment(ref winners);}catch(IOException){}catch(Exception e){Interlocked.CompareExchange(ref unexpected,e,null);}});
    foreach(var thread in threads)thread.Start();start.Set();foreach(var thread in threads)thread.Join();start.Dispose();
    if(unexpected!=null||winners!=1)throw new IOException("Concurrent nonce winner count",unexpected);
    using(var pinned=PinRoot(ledger)) {
     // Real NT-created empty and partial claims model interrupted receipt writes.
     using(var empty=CreateReceipt(pinned,new string('3',64)))Flush(empty);
     using(var partial=CreateReceipt(pinned,new string('4',64))){uint n;byte[] b=Encoding.ASCII.GetBytes("partial");if(!Native.WriteFile(partial,b,(uint)b.Length,out n,IntPtr.Zero)||n!=b.Length)throw new IOException("Partial fixture");Flush(partial);}
     MustFail(delegate{Directory.Move(ledger,ledger+"-moved");});
     string old=Environment.CurrentDirectory;Environment.CurrentDirectory=fixture;
     try{using(var relative=CreateReceipt(pinned,new string('5',64)))Flush(relative);}
     finally{Environment.CurrentDirectory=old;}
     if(File.Exists(System.IO.Path.Combine(fixture,new string('5',64)+".claim")))throw new IOException("Relative root escaped");
     MustFail(delegate{using(var escape=Relative(pinned.Leaf,"..\\escaped",0xC0000000,FileCreate,NonDirectoryFile,IntPtr.Zero)){};});
    }
    foreach(char c in new char[]{'3','4','5'})MustFail(delegate{Claim(ledger,new string(c,64),authorization);});
    InterruptedClaim(ledger,new string('b',64),false);InterruptedClaim(ledger,new string('c',64),true);
    MustFail(delegate{Claim(ledger,new string('b',64),authorization);});MustFail(delegate{Claim(ledger,new string('c',64),authorization);});
    string hardlink=System.IO.Path.Combine(ledger,new string('6',64)+".claim");
    if(!CreateHardLink(hardlink,receipt,IntPtr.Zero))throw new Win32Exception(Marshal.GetLastWin32Error());
    MustFail(delegate{Claim(ledger,new string('6',64),authorization);});
    string unsafeRoot=System.IO.Path.Combine(fixture,"unsafe");var unsafeAcl=new DirectorySecurity();unsafeAcl.SetSecurityDescriptorBinaryForm(ProtectedDescriptor(user));
    unsafeAcl.AddAccessRule(new FileSystemAccessRule(new SecurityIdentifier("S-1-1-0"),FileSystemRights.FullControl,AccessControlType.Allow));Directory.CreateDirectory(unsafeRoot,unsafeAcl);
    MustFail(delegate{Claim(unsafeRoot,new string('7',64),authorization);});
    string junction=System.IO.Path.Combine(fixture,"junction");Directory.CreateDirectory(junction,acl);MakeJunction(junction,ledger);
    try{MustFail(delegate{Claim(junction,new string('8',64),authorization);});}finally{Directory.Delete(junction);}
    foreach(string bad in new string[]{"relative","\\\\?\\C:\\ledger","C:\\NUL","C:\\x:stream","C:\\x\\..\\y"})MustFail(delegate{Claim(bad,new string('9',64),authorization);});
    MustFail(delegate{Claim(ledger,new string('A',64),authorization);});MustFail(delegate{Claim(ledger,new string('9',64),"bad");});
   }finally{Directory.Delete(fixture,true);}
  }
  static void MustFail(Action action){try{action();}catch(IOException){return;}catch(UnauthorizedAccessException){return;}catch(FormatException){return;}throw new InvalidOperationException("Nonce negative control unexpectedly succeeded");}
  static void InterruptedClaim(string ledger,string nonce,bool partial) {
   // A fixture-only helper process invokes the very same private NT creation
   // and flush functions, reports persistence, then is forcibly terminated.
   // No process is created anywhere on the Claim path.
   string binary=typeof(OwnerNonce).Assembly.Location;
   string script=@"
$ErrorActionPreference='Stop'
$flags=[Reflection.BindingFlags]'Static,NonPublic'
$assembly=[Reflection.Assembly]::LoadFile('"+binary.Replace("'","''")+@"')
$type=$assembly.GetType('StratTester.Native.OwnerNonce',$true)
$root=$type.GetMethod('PinRoot',$flags).Invoke($null,@('"+ledger.Replace("'","''")+@"'))
$receipt=$type.GetMethod('CreateReceipt',$flags).Invoke($null,@($root,'"+nonce+@"'))
$type.GetMethod('Flush',$flags).Invoke($null,@($receipt))
";
   if(partial)script+=@"
$bytes=[Text.Encoding]::ASCII.GetBytes('partial')
$arguments=@($receipt,$bytes,[uint32]$bytes.Length,[uint32]0,[IntPtr]::Zero)
$native=$assembly.GetType('StratTester.Native.Native',$true)
if(-not $native.GetMethod('WriteFile',$flags).Invoke($null,$arguments) -or $arguments[3] -ne 7){throw 'partial write'}
$type.GetMethod('Flush',$flags).Invoke($null,@($receipt))
";
   script+="[Console]::Out.WriteLine('CLAIM_PERSISTED');[Console]::Out.Flush();[Threading.Thread]::Sleep(-1)";
   string powershell=System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System),"WindowsPowerShell\\v1.0\\powershell.exe");
   var info=new ProcessStartInfo(powershell,"-NoLogo -NoProfile -NonInteractive -EncodedCommand "+Convert.ToBase64String(Encoding.Unicode.GetBytes(script))){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};
   using(var child=Process.Start(info)) {
    try {
     var ready=child.StandardOutput.ReadLineAsync();
     if(!ready.Wait(15000)||ready.Result!="CLAIM_PERSISTED")throw new IOException("Interrupted claim fixture did not persist");
    }finally{if(!child.HasExited)child.Kill();if(!child.WaitForExit(10000))throw new IOException("Interrupted fixture did not terminate");}
   }
   if(new FileInfo(System.IO.Path.Combine(ledger,nonce+".claim")).Length!=(partial?7:0))throw new IOException("Terminated nonce tombstone changed");
  }
  static void MakeJunction(string junction,string target) {
   byte[] substitute=Encoding.Unicode.GetBytes("\\??\\"+target),print=Encoding.Unicode.GetBytes(target);
   byte[] data=new byte[16+substitute.Length+2+print.Length+2];
   Buffer.BlockCopy(BitConverter.GetBytes(0xA0000003u),0,data,0,4);Buffer.BlockCopy(BitConverter.GetBytes((ushort)(data.Length-8)),0,data,4,2);
   Buffer.BlockCopy(BitConverter.GetBytes((ushort)substitute.Length),0,data,10,2);Buffer.BlockCopy(BitConverter.GetBytes((ushort)(substitute.Length+2)),0,data,12,2);Buffer.BlockCopy(BitConverter.GetBytes((ushort)print.Length),0,data,14,2);
   Buffer.BlockCopy(substitute,0,data,16,substitute.Length);Buffer.BlockCopy(print,0,data,18+substitute.Length,print.Length);
   using(var handle=Native.CreateFile(junction,0x40000000,0,IntPtr.Zero,3,0x2200000,IntPtr.Zero)) {
    uint n;if(handle.IsInvalid||!DeviceIoControl(handle,0x900A4,data,(uint)data.Length,IntPtr.Zero,0,out n,IntPtr.Zero))throw new Win32Exception(Marshal.GetLastWin32Error());
   }
  }

  [StructLayout(LayoutKind.Sequential)] struct UnicodeString {internal ushort Length,MaximumLength;internal IntPtr Buffer;}
  [StructLayout(LayoutKind.Sequential)] struct ObjectAttributes {internal uint Length;internal IntPtr RootDirectory,ObjectName;internal uint Attributes;internal IntPtr SecurityDescriptor,SecurityQualityOfService;}
  [StructLayout(LayoutKind.Sequential)] struct IoStatus {internal IntPtr Status;internal UIntPtr Information;}
  [DllImport("ntdll.dll")] static extern int NtCreateFile(out IntPtr handle,uint access,ref ObjectAttributes attributes,out IoStatus status,IntPtr allocation,uint fileAttributes,uint sharing,uint disposition,uint options,IntPtr ea,uint eaLength);
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] static extern bool FlushFileBuffers(KernelHandle handle);
  [DllImport("advapi32.dll")] static extern uint GetSecurityInfo(KernelHandle handle,uint kind,uint information,out IntPtr owner,out IntPtr group,out IntPtr dacl,out IntPtr sacl,out IntPtr descriptor);
  [DllImport("advapi32.dll")] static extern uint GetSecurityDescriptorLength(IntPtr descriptor);
  [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr memory);
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern uint GetDriveType(string root);
  [DllImport("kernel32.dll",EntryPoint="GetVolumeInformationByHandleW",CharSet=CharSet.Unicode,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] static extern bool GetVolumeInformationByHandle(KernelHandle root,StringBuilder name,uint nameLength,out uint serial,out uint maximum,out uint flags,StringBuilder fileSystem,uint fsLength);
  [DllImport("kernel32.dll",EntryPoint="CreateHardLinkW",CharSet=CharSet.Unicode,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] static extern bool CreateHardLink(string path,string existing,IntPtr attributes);
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] static extern bool DeviceIoControl(KernelHandle handle,uint code,byte[] input,uint inputLength,IntPtr output,uint outputLength,out uint returned,IntPtr overlapped);
 }
}
