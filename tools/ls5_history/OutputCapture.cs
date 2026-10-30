using System;using System.IO;using System.Threading.Tasks;
public static class ResearchOutputCapture {
 public sealed class Budget {public long Bytes;public volatile bool Exceeded;public readonly object Gate=new object();}
 public static Task Pump(Stream input,Stream output,Budget budget){return Task.Run(async()=>{
  var buffer=new byte[8192];int n;
  while((n=await input.ReadAsync(buffer,0,buffer.Length))>0){lock(budget.Gate){
   int keep=(int)Math.Min(n,Math.Max(0,262144-budget.Bytes));
   if(keep>0){output.Write(buffer,0,keep);budget.Bytes+=keep;}if(keep<n)budget.Exceeded=true;
  }}
 });}
}
