import yfinance as yf
import pandas as pd

def ema(s,p): return s.ewm(span=p, adjust=False).mean()
def atr(df,p=30):
    tr = pd.concat([df['High']-df['Low'], (df['High']-df['Close'].shift()).abs(), (df['Low']-df['Close'].shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/p, adjust=False).mean()

print("Loading Gold...")
data = yf.download("GC=F", period="1y", interval="1d", auto_adjust=True)
if data.empty: data = yf.download("XAUUSD=X", period="1y", interval="1d", auto_adjust=True)
data.columns = [c[0] if isinstance(c, tuple) else c for c in data.columns]

data['ATR']=atr(data,30)
data['EMA30']=ema(data['Close'],30)
data['PH']=data['High'][(data['High'].shift(5)<data['High'])&(data['High'].shift(-5)<data['High'])]
data['PL']=data['Low'][(data['Low'].shift(5)>data['Low'])&(data['Low'].shift(-5)>data['Low'])]

trades=[]
for i in range(10,len(data)-10):
    r=data.iloc[i]
    if pd.isna(r['PH']) and pd.isna(r['PL']): continue
    buy = not pd.isna(r['PL']) and r['Close']>r['EMA30']
    sell= not pd.isna(r['PH']) and r['Close']<r['EMA30']
    if not buy and not sell: continue
    entry=r['Close']; atr_v=r['ATR']
    tp = entry+atr_v*2.0 if buy else entry-atr_v*2.0
    sl = entry-atr_v*1.0 if buy else entry+atr_v*1.0
    for _,f in data.iloc[i+1:i+11].iterrows():
        if buy:
            if f['Low']<=sl: trades.append(0); break
            if f['High']>=tp: trades.append(1); break
        else:
            if f['High']>=sl: trades.append(0); break
            if f['Low']<=tp: trades.append(1); break

wr = sum(trades)/len(trades)*100 if trades else 0
md=f"# RESULTS AG5 v15.2-C\n\nTrades: {len(trades)}\nWinrate: {wr:.2f}%\n\n> นี่คือไฟล์ที่ main จะอัปเดตเองว่าอันไหนแม่นสุด\n"
open("RESULTS_AG5.md","w",encoding="utf-8").write(md)
print(md)