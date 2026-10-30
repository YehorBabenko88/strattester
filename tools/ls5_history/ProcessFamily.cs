using System;
using System.Text;
using System.Runtime.InteropServices;
using System.ComponentModel;
using System.Collections.Generic;
public static class ResearchProcessFamily {
 [StructLayout(LayoutKind.Sequential)] struct Counters {public uint cb,faults;public UIntPtr peak,working,qpp,qp,qnpp,qnp,page,peakpage;}
 [StructLayout(LayoutKind.Sequential)] struct Basic {public IntPtr reserved,peb,r2a,r2b,pid,parent;}
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] struct Entry {
  public uint size,usage,pid;public UIntPtr heap;public uint module,threads,parent;public int priority;public uint flags;
  [MarshalAs(UnmanagedType.ByValTStr,SizeConst=260)] public string executable;
 }
 public sealed class Observation {public int Pid,ParentPid,ExitCode,SessionId;public string Created,Exited,Image,Liveness;public double CpuSeconds;public ulong PeakBytes,WorkingBytes;public bool HasExited,SessionValid;}
 public sealed class Edge {public int Pid,ParentPid;}
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetProcessTimes(IntPtr h,out long c,out long e,out long k,out long u);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool K32GetProcessMemoryInfo(IntPtr h,ref Counters c,uint size);
 [DllImport("kernel32.dll",SetLastError=true)] static extern uint GetProcessId(IntPtr h);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetExitCodeProcess(IntPtr h,out uint code);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool ProcessIdToSessionId(uint pid,out uint session);
 [DllImport("user32.dll",ExactSpelling=true,SetLastError=true)] static extern uint GetWindowThreadProcessId(IntPtr hwnd,out uint pid);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool TerminateProcess(IntPtr h,uint code);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool QueryFullProcessImageName(IntPtr h,uint flags,StringBuilder text,ref uint capacity);
 [DllImport("ntdll.dll")] static extern int NtQueryInformationProcess(IntPtr h,int cls,ref Basic basic,int length,out int returned);
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr CreateToolhelp32Snapshot(uint flags,uint pid);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,ExactSpelling=true,SetLastError=true)] static extern bool Process32FirstW(IntPtr h,ref Entry entry);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,ExactSpelling=true,SetLastError=true)] static extern bool Process32NextW(IntPtr h,ref Entry entry);
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
 [DllImport("kernel32.dll",SetLastError=true)] static extern uint WaitForSingleObject(IntPtr h,uint milliseconds);
 public static string DecodeLiveness(uint result){return result==0?"EXITED":result==258?"RUNNING":"UNKNOWN";}
 public static string ResolveLiveness(string before,string after){
  if((before!="RUNNING"&&before!="EXITED")||(after!="RUNNING"&&after!="EXITED")||(before=="EXITED"&&after=="RUNNING"))return "UNKNOWN";
  return after;
 }
 static string ProbeLiveness(IntPtr h){
  if(h==IntPtr.Zero||h==new IntPtr(-1))throw new InvalidOperationException("RESOURCE_UNVERIFIED_LIVENESS_INVALID_HANDLE");
  uint result=WaitForSingleObject(h,0);int error=result==uint.MaxValue?Marshal.GetLastWin32Error():0;
  string state=DecodeLiveness(result);
  if(state=="UNKNOWN")throw new InvalidOperationException(result==uint.MaxValue?"RESOURCE_UNVERIFIED_LIVENESS_WAIT_FAILED":"RESOURCE_UNVERIFIED_LIVENESS_WAIT_RESULT");
  return state;
 }
 public static void Stop(IntPtr h){if(!TerminateProcess(h,1))throw new Win32Exception(Marshal.GetLastWin32Error());}
 public static int WindowOwner(ulong hwnd){uint pid;if(hwnd==0||hwnd>long.MaxValue||GetWindowThreadProcessId(new IntPtr((long)hwnd),out pid)==0||pid==0)throw new InvalidOperationException("CONSOLE_WINDOW_OWNER_UNAVAILABLE");return (int)pid;}
 public static Observation Read(IntPtr h){return Read(h,true);}
 public static Observation Read(IntPtr h,bool includeIdentity){
  string before=ProbeLiveness(h);
  long c,e,k,u;uint code;
  if(!GetProcessTimes(h,out c,out e,out k,out u)||!GetExitCodeProcess(h,out code))throw new Win32Exception(Marshal.GetLastWin32Error());
  var m=new Counters();m.cb=(uint)Marshal.SizeOf(typeof(Counters));
  if(!K32GetProcessMemoryInfo(h,ref m,m.cb))throw new Win32Exception(Marshal.GetLastWin32Error());
  var b=new Basic();string image=null;
  if(includeIdentity){int returned;
   if(NtQueryInformationProcess(h,0,ref b,Marshal.SizeOf(typeof(Basic)),out returned)!=0)throw new InvalidOperationException("PARENT_QUERY_UNAVAILABLE");
   uint cap=32768;var text=new StringBuilder((int)cap);
   if(!QueryFullProcessImageName(h,0,text,ref cap))throw new Win32Exception(Marshal.GetLastWin32Error());image=text.ToString();
  }
  uint pid=GetProcessId(h);if(pid==0)throw new Win32Exception(Marshal.GetLastWin32Error());
  uint session=0;bool sessionValid=false;
  if(includeIdentity && before=="RUNNING" && ProcessIdToSessionId(pid,out session)){
   long c2,e2,k2,u2;sessionValid=GetProcessTimes(h,out c2,out e2,out k2,out u2)&&c2==c&&ProbeLiveness(h)=="RUNNING";
  }
  string after=ProbeLiveness(h);string state=ResolveLiveness(before,after);
  if(state=="UNKNOWN")throw new InvalidOperationException("RESOURCE_UNVERIFIED_LIVENESS_TRANSITION");
  // Process signals only once. Refresh counters and exit code after a running-to-exited race.
  if(before=="RUNNING" && state=="EXITED"){
   long c3,e3,k3,u3;uint code3;
   if(!GetProcessTimes(h,out c3,out e3,out k3,out u3)||!GetExitCodeProcess(h,out code3))throw new InvalidOperationException("RESOURCE_UNVERIFIED_LIVENESS_FINAL_TIMES");
   if(c3!=c||ProbeLiveness(h)!="EXITED")throw new InvalidOperationException("RESOURCE_UNVERIFIED_LIVENESS_FINAL_IDENTITY");
   var final=new Counters();final.cb=(uint)Marshal.SizeOf(typeof(Counters));
   if(!K32GetProcessMemoryInfo(h,ref final,final.cb))throw new InvalidOperationException("RESOURCE_UNVERIFIED_LIVENESS_FINAL_MEMORY");
   e=e3;k=k3;u=u3;code=code3;m=final;sessionValid=false;
  }
  return new Observation {Pid=(int)pid,ParentPid=b.parent.ToInt32(),Created=c.ToString(System.Globalization.CultureInfo.InvariantCulture),Exited=state=="EXITED"?e.ToString(System.Globalization.CultureInfo.InvariantCulture):null,HasExited=state=="EXITED",Liveness=state,ExitCode=unchecked((int)code),Image=image,CpuSeconds=(k+u)/10000000.0,PeakBytes=m.peak.ToUInt64(),WorkingBytes=m.working.ToUInt64(),SessionId=(int)session,SessionValid=sessionValid};
 }
 public static Edge[] Snapshot(){
  var h=CreateToolhelp32Snapshot(2,0);if(h==new IntPtr(-1))throw new Win32Exception(Marshal.GetLastWin32Error());
  try{var rows=new List<Edge>();var e=new Entry();e.size=(uint)Marshal.SizeOf(typeof(Entry));
   if(!Process32FirstW(h,ref e))throw new Win32Exception(Marshal.GetLastWin32Error());
   do{rows.Add(new Edge{Pid=(int)e.pid,ParentPid=(int)e.parent});}while(Process32NextW(h,ref e));
   if(Marshal.GetLastWin32Error()!=18)throw new Win32Exception(Marshal.GetLastWin32Error());
   return rows.ToArray();
  }finally{CloseHandle(h);}
 }
}
