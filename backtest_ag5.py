import yfinance as yf
import pandas as pd
import os, glob, re
from datetime import datetime

def ema(s,p):
    return s.ewm(span=p, adjust=False).mean()

def atr(df,p=30):
    # True Range
    hl = df['High']-df['Low']
    hc = (df['High']-df['Close'].shift()).abs()
    lc = (df['Low']-df['Close'].shift()).abs()
    tr = pd.concat([hl,hc,lc], axis=1).max(axis=1)
    return tr.ewm(alpha=1/p, adjust=False).mean()

def find_pivots(df, left=5, right=5):
    ph = pd.Series([float('nan')]*len(df), index=df.index)
    pl = pd.Series([float('nan')]*len(df), index=df.index)
    for i in range(left, len(df)-right):
        h_window = df['High'].iloc[i-left:i+right+1]
        l_window = df['Low'].iloc[i-left:i+right+1]
        if df['High'].iloc[i] == h_window.max():
            ph.iloc[i] = df['High'].iloc[i]
        if df['Low'].iloc[i] == l_window.min():
            pl.iloc[i] = df['Low'].iloc[i]
    return ph, pl

def parse_params(pine_path):
    # default ของ C
    tp, sl = 2.0, 1.0
    try:
        txt = open(pine_path, 'r', errors='ignore').read()
        # วิธีง่ายสุดให้คุณใส่คอมเมนต์บนสุดของไฟล์ pine แบบนี้ // TP:2.5 SL:1.0
        m = re.search(r'TP\s*[:=]\s*([\d\.]+).*SL\s*[:=]\s*([\d\.]+)', txt, re.I)
        if m:
            tp = float(m.group(1)); sl = float(m.group(2))
            return tp, sl
        # ถ้าไม่มีคอมเมนต์ พยายามเดาจากโค้ด
        # หา tp =... atr*X
        lines = txt.lower().splitlines()
        for line in lines:
            if 'tp' in line and 'atr' in line:
                nums = re.findall(r"([\d\.]+)", line)
                for n in nums:
                    v=float(n)
                    if 0.5 <= v <= 10:
                        tp=v; break
            if line.strip().startswith('sl') or 'sl =' in line or 'sl=' in line:
                if 'atr' in line:
                    nums = re.findall(r"([\d\.]+)", line)
                    for n in nums:
                        v=float(n)
                        if 0.5 <= v <= 10:
                            sl=v; break
        # mapping ตามชื่อไฟล์เผื่อยังไม่มีค่า
        name = os.path.basename(pine_path).upper()
        if tp==2.0 and sl==1.0:
            if '-D' in name: tp=2.5
            elif '-E' in name: sl=1.5
            elif '-F' in name: tp=3.0
            elif '-G' in name: tp=2.0; sl=0.8
    except: pass
    return tp, sl

def run_backtest(data, tp_mult, sl_mult):
    trades=[]
    for i in range(10, len(data)-10):
        r=data.iloc[i]
        if pd.isna(r['PH']) and pd.isna(r['PL']): continue
        buy = (not pd.isna(r['PL'])) and r['Close'] > r['EMA30']
        sell = (not pd.isna(r['PH'])) and r['Close'] < r['EMA30']
        if not buy and not sell: continue
        entry=r['Close']; atr_v=r['ATR']
        if pd.isna(atr_v): continue
        tp = entry + atr_v*tp_mult if buy else entry - atr_v*tp_mult
        sl = entry - atr_v*sl_mult if buy else entry + atr_v*sl_mult
        for _, f in data.iloc[i+1:i+11].iterrows():
            if buy:
                if f['Low'] <= sl: trades.append(0); break
                if f['High'] >= tp: trades.append(1); break
            else:
                if f['High'] >= sl: trades.append(0); break
                if f['Low'] <= tp: trades.append(1); break
    wr = sum(trades)/len(trades)*100 if trades else 0
    return trades, wr

print("Loading Gold...")
data=None
for interval in ["4h","1h"]:
    try:
        d=yf.download("GC=F", period="1y", interval=interval, auto_adjust=True)
        if not d.empty and len(d)>100:
            data=d; break
    except: pass
if data is None or data.empty:
    data=yf.download("XAUUSD=X", period="1y", interval="4h", auto_adjust=True)

# flatten multiindex
if isinstance(data.columns, pd.MultiIndex):
    data.columns = [c[0] for c in data.columns]

data['ATR']=atr(data,30)
data['EMA30']=ema(data['Close'],30)
ph, pl = find_pivots(data,5,5)
data['PH']=ph
data['PL']=pl

pine_files = glob.glob("strategy/*.pine") + glob.glob("strategy/*.pinescript")

results=[]
if not pine_files:
    # fallback แบบเดิม
    trades, wr = run_backtest(data, 2.0, 1.0)
    results.append({"version":"AG5_v15.2-C","trades":len(trades),"wr":wr,"tp":2.0,"sl":1.0})
else:
    for pf in pine_files:
        ver = os.path.splitext(os.path.basename(pf))[0]
        tp, sl = parse_params(pf)
        trades, wr = run_backtest(data, tp, sl)
        results.append({"version":ver,"trades":len(trades),"wr":wr,"tp":tp,"sl":sl,"path":pf})

results = sorted(results, key=lambda x: x['wr'], reverse=True)

now = datetime.now().strftime("%Y-%m-%d %H:%M")
md = f"# RESULTS AG5 - Leaderboard\n\n"
md += f"Updated: {now} | Data: GC=F 1Y {interval} | Trades counted 10 bars ahead\n\n"
md += f"| Rank | Version | Trades | Winrate | TP x ATR | SL x ATR |\n"
md += f"|---|---|---|---|---|---|\n"
for i, r in enumerate(results,1):
    crown = " 👑" if i==1 else ""
    md += f"| {i} | {r['version']}{crown} | {r['trades']} | {r['wr']:.2f}% | {r['tp']} | {r['sl']} |\n"

md += f"\n---\n\n"
md += f"**Champion: {results[0]['version']} - {results[0]['wr']:.2f}%**\n\n"
md += f"วิธีใช้: ใส่ `// TP:2.5 SL:1.2` ไว้บรรทัดแรกของไฟล์.pine ในโฟลเดอร์ strategy/ แล้ว push ได้เลย\n"

open("RESULTS_AG5.md","w",encoding="utf-8").write(md)
print(md)