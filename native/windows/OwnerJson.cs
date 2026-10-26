// Deliberately narrow canonical ASCII JSON, bounded before allocation.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
namespace StratTester.Native {
 internal sealed class OwnerJson {
  readonly string text; int at, nodes;
  OwnerJson(byte[] bytes) { if(bytes.Length>65536)throw new FormatException("JSON budget");foreach(byte b in bytes)if(b<32||b>126)throw new FormatException("ASCII JSON required");text=Encoding.ASCII.GetString(bytes); }
  internal static object Parse(byte[] bytes) { var p=new OwnerJson(bytes);object o=p.Value(0);if(p.at!=p.text.Length)throw new FormatException("Trailing JSON");return o; }
  char Peek { get { return at<text.Length?text[at]:'\0'; } }
  void Take(char c) { if(Peek!=c)throw new FormatException("JSON syntax");at++; }
  string String() { Take('"');var b=new StringBuilder();while(Peek!='"'){char c=Peek;if(c=='\0'||b.Length>4096)throw new FormatException("JSON string budget");at++;if(c=='\\'){c=Peek;at++;if(c!='\\'&&c!='"')throw new FormatException("JSON escape");}b.Append(c);}at++;return b.ToString(); }
  object Value(int depth) {
   if(depth>8||++nodes>512)throw new FormatException("JSON structure budget");
   if(Peek=='"')return String();
   if(Peek=='{'){at++;var d=new SortedDictionary<string,object>(StringComparer.Ordinal);if(Peek=='}'){at++;return d;}while(true){string k=String();Take(':');if(d.ContainsKey(k)||d.Count>=128)throw new FormatException("Duplicate/budget key");d.Add(k,Value(depth+1));if(Peek=='}'){at++;return d;}Take(',');}}
   if(Peek=='['){at++;var a=new List<object>();if(Peek==']'){at++;return a;}while(true){if(a.Count>=128)throw new FormatException("Array budget");a.Add(Value(depth+1));if(Peek==']'){at++;return a;}Take(',');}}
   int start=at;if(Peek=='-')at++;while(Peek>='0'&&Peek<='9')at++;
   if(at==start||at-start>20)throw new FormatException("Integer required");
   string s=text.Substring(start,at-start);long n;
   if(!Int64.TryParse(s,NumberStyles.AllowLeadingSign,CultureInfo.InvariantCulture,out n)||n.ToString(CultureInfo.InvariantCulture)!=s)throw new FormatException("Noncanonical integer");return n;
  }
  internal static byte[] Canonical(object value) { var b=new StringBuilder();Emit(value,b);return Encoding.ASCII.GetBytes(b.ToString()); }
  static void Emit(object o,StringBuilder b) {
   var s=o as string;if(s!=null){b.Append('"');foreach(char c in s){if(c<32||c>126)throw new FormatException("ASCII string");if(c=='"'||c=='\\')b.Append('\\');b.Append(c);}b.Append('"');return;}
   if(o is long){b.Append(((long)o).ToString(CultureInfo.InvariantCulture));return;}
   var d=o as SortedDictionary<string,object>;if(d!=null){b.Append('{');bool first=true;foreach(var kv in d){if(!first)b.Append(',');first=false;Emit(kv.Key,b);b.Append(':');Emit(kv.Value,b);}b.Append('}');return;}
   var a=o as List<object>;if(a!=null){b.Append('[');for(int i=0;i<a.Count;i++){if(i>0)b.Append(',');Emit(a[i],b);}b.Append(']');return;}throw new FormatException("Unsupported JSON type");
  }
  internal static SortedDictionary<string,object> Map(object value) {var d=value as SortedDictionary<string,object>;if(d==null)throw new FormatException("Object required");return d;}
  internal static void Keys(SortedDictionary<string,object> d,params string[] names) {if(d.Count!=names.Length)throw new FormatException("Object schema");foreach(string n in names)if(!d.ContainsKey(n))throw new FormatException("Object schema");}
 }
}
