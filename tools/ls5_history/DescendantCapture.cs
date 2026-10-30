using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class DescendantCapture {
 public sealed class Record {
  public int pid; public int? parent_pid,session_id,exit_code;public string created,image,liveness;
  public double? cpu_seconds;public ulong? peak_ram_bytes;public string[] errors;
 }
 [StructLayout(LayoutKind.Sequential)] struct Basic {public IntPtr reserved,peb,r2a,r2b,pid,parent;}
 [StructLayout(LayoutKind.Sequential)] struct Counters {public uint cb,faults;public UIntPtr peak,working,qpp,qp,qnpp,qnp,page,peakpage;}
 [DllImport("kernel32.dll",SetLastError=true)] static extern SafeProcessHandle OpenProcess(uint access,bool inherit,uint pid);
 [DllImport("kernel32.dll",SetLastError=true)] static extern uint GetProcessId(SafeProcessHandle h);
 [DllImport("kernel32.dll",SetLastError=true)] static extern uint WaitForSingleObject(SafeProcessHandle h,uint ms);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetProcessTimes(SafeProcessHandle h,out long c,out long e,out long k,out long u);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetExitCodeProcess(SafeProcessHandle h,out uint code);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool QueryFullProcessImageName(SafeProcessHandle h,uint flags,StringBuilder text,ref uint cap);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool ProcessIdToSessionId(uint pid,out uint session);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool K32GetProcessMemoryInfo(SafeProcessHandle h,ref Counters c,uint size);
 [DllImport("ntdll.dll")] static extern int NtQueryInformationProcess(SafeProcessHandle h,int cls,ref Basic b,int size,out int returned);
 [DllImport("kernel32.dll",EntryPoint="WaitForSingleObject",SetLastError=true)] static extern uint WaitOwned(IntPtr h,uint ms);
 public static string OwnedLiveness(IntPtr h){if(h==IntPtr.Zero||h==new IntPtr(-1))return "UNKNOWN";uint r=WaitOwned(h,0);return r==0?"EXITED":r==258?"RUNNING":"UNKNOWN";}
 public static Record Inspect(uint pid){
  var r=new Record{pid=(int)pid,liveness="UNKNOWN"};var errors=new List<string>();
  using(var h=OpenProcess(0x101000,false,pid)){
   if(h.IsInvalid){r.errors=new[]{"OPEN_FAILED"};return r;}
   uint held=GetProcessId(h);if(held!=pid){errors.Add("HANDLE_PID_MISMATCH");r.errors=errors.ToArray();return r;}
   uint first=WaitForSingleObject(h,0);if(first!=0&&first!=258)errors.Add("WAIT_FAILED_OR_UNKNOWN");
   long c,e,k,u;
   if(GetProcessTimes(h,out c,out e,out k,out u)){r.created=c.ToString(System.Globalization.CultureInfo.InvariantCulture);r.cpu_seconds=(k+u)/10000000.0;}else errors.Add("TIMES_UNAVAILABLE");
   var b=new Basic();int ret;
   if(NtQueryInformationProcess(h,0,ref b,Marshal.SizeOf(typeof(Basic)),out ret)==0)r.parent_pid=b.parent.ToInt32();else errors.Add("PARENT_UNAVAILABLE");
   uint capacity=32768;var text=new StringBuilder((int)capacity);
   if(QueryFullProcessImageName(h,0,text,ref capacity)){if(text.Length<=1024)r.image=text.ToString();else errors.Add("IMAGE_BOUND");}else errors.Add("IMAGE_UNAVAILABLE");
   var m=new Counters();m.cb=(uint)Marshal.SizeOf(typeof(Counters));if(K32GetProcessMemoryInfo(h,ref m,m.cb))r.peak_ram_bytes=m.peak.ToUInt64();else errors.Add("MEMORY_UNAVAILABLE");
   uint last=WaitForSingleObject(h,0);r.liveness=last==0?"EXITED":last==258?"RUNNING":"UNKNOWN";
   if(last!=0&&last!=258)errors.Add("WAIT_FAILED_OR_UNKNOWN");
   if(first==0&&last==258){r.liveness="UNKNOWN";errors.Add("WAIT_REVERSAL");}
   if(first==258&&last==0){errors.Add("EXIT_DURING_INSPECTION_METRICS_NOT_FINAL");}
   if(last==0){uint exit;if(GetExitCodeProcess(h,out exit))r.exit_code=unchecked((int)exit);else errors.Add("EXIT_CODE_UNAVAILABLE");}
   // Session lookup is PID-based; accept it only bracketed by live retained identity.
   if(first==258&&last==258){uint session;long c2,e2,k2,u2;
    if(ProcessIdToSessionId(pid,out session)&&GetProcessTimes(h,out c2,out e2,out k2,out u2)&&r.created==c2.ToString(System.Globalization.CultureInfo.InvariantCulture)&&WaitForSingleObject(h,0)==258)r.session_id=(int)session;
    else errors.Add("SESSION_UNVERIFIED");
   }else errors.Add("SESSION_UNVERIFIED_AFTER_EXIT");
  }
  r.errors=errors.ToArray();return r;
 }
}

