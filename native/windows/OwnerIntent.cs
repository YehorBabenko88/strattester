using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Diagnostics;
using Microsoft.Win32;
namespace StratTester.Native {
 internal sealed class VerifiedOwnerIntent : IDisposable {
  internal readonly Dictionary<string,LockedInput> Inputs=new Dictionary<string,LockedInput>(StringComparer.Ordinal);
  internal readonly List<LockedInput> Locks=new List<LockedInput>();
  internal uint CpuPercent,WallSeconds,MaxProcesses; internal ulong MemoryBytes,OutputBytes;
  internal string Nonce,SourceSha,TreeSha,VmIdentitySha256;
  internal long ExpiresAtNs;
  readonly long startUtc=OwnerIntent.NowNs(),startCounter=Stopwatch.GetTimestamp();
  internal void EnsureFresh(){long now=OwnerClock.EffectiveNow(startUtc,startCounter,OwnerIntent.NowNs(),Stopwatch.GetTimestamp(),Stopwatch.Frequency);if(ExpiresAtNs<now)throw new InvalidOperationException("Owner expired before admission");}
  internal uint RemainingMilliseconds(){EnsureFresh();long now=OwnerClock.EffectiveNow(startUtc,startCounter,OwnerIntent.NowNs(),Stopwatch.GetTimestamp(),Stopwatch.Frequency);long ms=(ExpiresAtNs-now)/1000000;if(ms<1)throw new InvalidOperationException("Owner expiry imminent");return (uint)Math.Min(ms,(long)WallSeconds*1000);}
  public void Dispose(){foreach(var i in Locks)i.Dispose();Locks.Clear();Inputs.Clear();}
 }
 internal static class OwnerIntent {
  const string Domain="STRATTESTER_PHYSICAL_G1_OWNER_V2\0";
  internal static long NowNs(){return checked((DateTime.UtcNow.Ticks-621355968000000000L)*100L);}
  internal static string Hash(byte[] b){using(var s=SHA256.Create())return BitConverter.ToString(s.ComputeHash(b)).Replace("-","").ToLowerInvariant();}
  static string Str(SortedDictionary<string,object> p,string n){var s=p[n] as string;if(s==null)throw new FormatException("String required");return s;}
  static long Num(SortedDictionary<string,object> p,string n){if(!(p[n] is long))throw new FormatException("Integer required");return (long)p[n];}
  static void Hex(string v,int length){if(v==null||v.Length!=length||!Regex.IsMatch(v,"\\A[0-9a-f]+\\z"))throw new FormatException("Hex digest");}
  static void Equal(string a,string b,int length){Hex(a,length);Hex(b,length);if(a!=b)throw new InvalidOperationException("Identity mismatch");}
  static byte[] Read(LockedInput input,int maximum){if(input.Length>(ulong)maximum)throw new IOException("Read budget");long pos;if(!OwnerNative.SetFilePointerEx(input.Leaf,0,out pos,0))throw new IOException("Seek");byte[] b=new byte[(int)input.Length];uint done=0;while(done<b.Length){byte[] chunk=new byte[Math.Min(65536,b.Length-(int)done)];uint n;if(!Native.ReadFile(input.Leaf,chunk,(uint)chunk.Length,out n,IntPtr.Zero)||n==0)throw new IOException("Short read");Buffer.BlockCopy(chunk,0,b,(int)done,(int)n);done+=n;}if(Hash(b)!=input.Sha256)throw new IOException("Locked bytes changed");return b;}
  static LockedInput Pin(VerifiedOwnerIntent a,string path,string sha,ulong cap){Hex(sha,64);var f=LockedInput.Open(path,cap);a.Locks.Add(f);if(f.Sha256!=sha)throw new IOException("Input SHA mismatch");return f;}
  internal static string VmIdentity(){
   string guid;using(var key=Registry.LocalMachine.OpenSubKey("SOFTWARE\\Microsoft\\Cryptography",false)){guid=key==null?null:key.GetValue("MachineGuid") as string;}
   if(String.IsNullOrEmpty(guid))throw new InvalidOperationException("Machine identity unavailable");
   uint n=OwnerNative.GetSystemFirmwareTable(0x52534D42,0,IntPtr.Zero,0);if(n<8||n>1048576)throw new InvalidOperationException("SMBIOS identity unavailable");
   IntPtr p=Marshal.AllocHGlobal((int)n);try{if(OwnerNative.GetSystemFirmwareTable(0x52534D42,0,p,n)!=n)throw new InvalidOperationException("SMBIOS changed");byte[] b=new byte[n];Marshal.Copy(p,b,0,b.Length);return Hash(Encoding.UTF8.GetBytes("STRATTESTER_VM_V2\0"+Environment.MachineName.ToUpperInvariant()+"|"+guid.ToLowerInvariant()+"|"+Hash(b)));}finally{Marshal.FreeHGlobal(p);}
  }
  static void Signature(byte[] key,byte[] message,byte[] signature){
   if(key.Length!=32||signature.Length!=64||message.Length>65536)throw new FormatException("Signature budget");
   if(BitConverter.ToString(key).Replace("-","").ToLowerInvariant()=="3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c")throw new InvalidOperationException("Public fixture owner key");
   byte[] bytes;using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("StratTester.BouncyCastle.dll")){if(stream==null||stream.Length>16777216)throw new InvalidOperationException("Verifier unavailable");using(var m=new MemoryStream()){stream.CopyTo(m);bytes=m.ToArray();}}
   if(Hash(bytes)!=BuildIdentity.CryptoSha256)throw new InvalidOperationException("Verifier integrity");
   var assembly=Assembly.Load(bytes);var kt=assembly.GetType("Org.BouncyCastle.Crypto.Parameters.Ed25519PublicKeyParameters",true);var st=assembly.GetType("Org.BouncyCastle.Crypto.Signers.Ed25519Signer",true);
   object publicKey=Activator.CreateInstance(kt,new object[]{key,0});object signer=Activator.CreateInstance(st);
   st.GetMethod("Init").Invoke(signer,new object[]{false,publicKey});st.GetMethod("BlockUpdate",new Type[]{typeof(byte[]),typeof(int),typeof(int)}).Invoke(signer,new object[]{message,0,message.Length});
   if(!(bool)st.GetMethod("VerifySignature").Invoke(signer,new object[]{signature}))throw new InvalidOperationException("Owner signature rejected");
  }
  internal static VerifiedOwnerIntent Verify(string planPath,string planSha256,string signaturePath,string signatureSha256,string ownerPublicKeyPath,string ownerPublicKeySha256,string expectedSourceSha,string expectedTreeSha,string expectedBinarySha256,string expectedPackageSha256,string expectedVmIdentitySha256,IDictionary<string,string> inputPaths){
   var a=new VerifiedOwnerIntent();try{
    if(BuildIdentity.Dirty)throw new InvalidOperationException("Uncommitted build cannot admit");
    Equal(expectedSourceSha,BuildIdentity.SourceSha,40);Equal(expectedTreeSha,BuildIdentity.TreeSha,40);
    var plan=Pin(a,planPath,planSha256,65536);byte[] raw=Read(plan,65536);var p=OwnerJson.Map(OwnerJson.Parse(raw));if(Hash(OwnerJson.Canonical(p))!=Hash(raw))throw new FormatException("Noncanonical owner JSON");
    OwnerJson.Keys(p,"version","purpose","owner_id","key_id","target_sha","tree_sha","binary_sha256","package_sha256","vm_identity_sha256","input_hashes","issued_at_ns","expires_at_ns","nonce","operations","limits");
    if(Num(p,"version")!=2||Str(p,"purpose")!="PHYSICAL_G1_AUTHORIZATION")throw new FormatException("Owner version/purpose");
    foreach(string name in new string[]{"owner_id","key_id"})if(!Regex.IsMatch(Str(p,name),"\\A[A-Za-z0-9_.:-]{1,128}\\z"))throw new FormatException("Owner identity");
    Equal(Str(p,"target_sha"),expectedSourceSha,40);Equal(Str(p,"tree_sha"),expectedTreeSha,40);Equal(Str(p,"binary_sha256"),expectedBinarySha256,64);Equal(Str(p,"package_sha256"),expectedPackageSha256,64);
    Equal(Str(p,"vm_identity_sha256"),expectedVmIdentitySha256,64);Equal(expectedVmIdentitySha256,VmIdentity(),64);
    Pin(a,Assembly.GetExecutingAssembly().Location,expectedBinarySha256,33554432);
    long now=NowNs(),issued=Num(p,"issued_at_ns"),expires=Num(p,"expires_at_ns");if(issued<1||issued>now||expires<now||expires-issued>600000000000L)throw new InvalidOperationException("Owner expiry");a.ExpiresAtNs=expires;
    Hex(Str(p,"nonce"),64);var ops=p["operations"] as List<object>;if(ops==null||ops.Count!=1||ops[0] as string!="synthetic_cpu_inference")throw new FormatException("Owner operation");
    var limits=OwnerJson.Map(p["limits"]);OwnerJson.Keys(limits,"cpu_percent","memory_bytes","wall_seconds","output_bytes","max_processes");
    string[] names={"cpu_percent","memory_bytes","wall_seconds","output_bytes","max_processes"};long[] caps={10,2147483648L,60,67108864L,1};for(int i=0;i<names.Length;i++){long v=Num(limits,names[i]);if(v<1||v>caps[i])throw new FormatException("Owner resource ceiling");}
    var hashes=OwnerJson.Map(p["input_hashes"]);if(hashes.Count<1||hashes.Count>64||!hashes.ContainsKey("package")||inputPaths==null||inputPaths.Count!=hashes.Count)throw new FormatException("Input roster/package budget");
    ulong charged=0;foreach(var entry in hashes){string path;if(!Regex.IsMatch(entry.Key,"\\A[A-Za-z0-9_-]{1,64}\\z")||!inputPaths.TryGetValue(entry.Key,out path)||!(entry.Value is string))throw new FormatException("Input roster mismatch");var input=Pin(a,path,(string)entry.Value,1073741824);charged+=input.Length;if(charged>1073741824)throw new IOException("Aggregate input budget");a.Inputs.Add(entry.Key,input);}
    Equal(a.Inputs["package"].Sha256,Str(p,"package_sha256"),64);
    var pub=Pin(a,ownerPublicKeyPath,ownerPublicKeySha256,32);var sig=Pin(a,signaturePath,signatureSha256,64);byte[] prefix=Encoding.ASCII.GetBytes(Domain),message=new byte[prefix.Length+raw.Length];Buffer.BlockCopy(prefix,0,message,0,prefix.Length);Buffer.BlockCopy(raw,0,message,prefix.Length,raw.Length);Signature(Read(pub,32),message,Read(sig,64));a.EnsureFresh();
    a.SourceSha=expectedSourceSha;a.TreeSha=expectedTreeSha;a.VmIdentitySha256=expectedVmIdentitySha256;a.Nonce=Str(p,"nonce");a.CpuPercent=(uint)Num(limits,"cpu_percent");a.MemoryBytes=(ulong)Num(limits,"memory_bytes");a.WallSeconds=(uint)Num(limits,"wall_seconds");a.OutputBytes=(ulong)Num(limits,"output_bytes");a.MaxProcesses=1;return a;
   }catch{a.Dispose();throw;}
  }
  internal static int Dispatch(string[] args){try{
   if(args.Length==1&&args[0]=="--selftest-owner-clock"){OwnerClock.SelfTest();Console.WriteLine("{\"clock_tests\":\"PASS\",\"process_created\":false,\"physical_g1\":\"NOT_AUTHORIZED\"}");return 0;}
   if(args.Length==1&&args[0]=="--owner-vm-identity"){Console.WriteLine("{\"vm_identity_sha256\":\""+VmIdentity()+"\",\"source_sha\":\""+BuildIdentity.SourceSha+"\",\"tree_sha\":\""+BuildIdentity.TreeSha+"\",\"process_created\":false}");return 0;}
   if(args.Length!=13)throw new FormatException("Owner arguments");
   using(var binding=LockedInput.Open(args[12],65536)){var values=OwnerJson.Map(OwnerJson.Parse(Read(binding,65536)));var paths=new Dictionary<string,string>(StringComparer.Ordinal);foreach(var row in values){if(!(row.Value is string))throw new FormatException("Input path");paths.Add(row.Key,(string)row.Value);}using(var a=Verify(args[1],args[2],args[3],args[4],args[5],args[6],args[7],args[8],args[9],args[10],args[11],paths)){Console.WriteLine("{\"signature_verified\":true,\"nonce_consumed\":false,\"process_created\":false,\"physical_g1\":\"NOT_AUTHORIZED\"}");return 0;}}
  }catch(Exception e){Console.WriteLine("{\"status\":\"BLOCKED\",\"error_type\":\""+e.GetType().Name+"\",\"process_created\":false,\"physical_g1\":\"NOT_AUTHORIZED\"}");return 78;}}
 }
 internal static class OwnerClock {
  internal static long EffectiveNow(long startUtc,long startTick,long utcNow,long tickNow,long frequency){if(startUtc<1||frequency<1||tickNow<startTick)throw new InvalidOperationException("Clock identity");long elapsed=checked(tickNow-startTick);long ns=checked(elapsed/frequency*1000000000L+elapsed%frequency*1000000000L/frequency);return Math.Max(utcNow,checked(startUtc+ns));}
  internal static void SelfTest(){if(EffectiveNow(1000,0,900,1,1000000000)!=1001||EffectiveNow(1000,0,2000,1,1000000000)!=2000)throw new InvalidOperationException("Clock rollback");long expires=1100;if(EffectiveNow(1000,0,1000,200,1000000000)<=expires)throw new InvalidOperationException("Late admission");}
 }
 internal static class OwnerNative {
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool SetFilePointerEx(KernelHandle h,long distance,out long position,uint method);
  [DllImport("kernel32.dll",SetLastError=true)] internal static extern uint GetSystemFirmwareTable(uint provider,uint id,IntPtr buffer,uint size);
 }
}
