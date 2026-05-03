import yfinance as yf
import pandas as pd
import pytz

def check_intraday_hit():
    ticker = "NVDA"
    start = "2026-03-26"
    end = "2026-03-28"
    
    print(f"Fetching intraday data for {ticker} on {start}...")
    df = yf.download(ticker, start=start, end=end, interval="1m", prepost=True)
    
    if df.empty:
        print("No intraday data found.")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    eastern = pytz.timezone("US/Eastern")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(eastern)
    else:
        df.index = df.index.tz_convert(eastern)

    # Signal: 11:59:11 PT -> 14:59:11 ET
    signal_time_et = pd.Timestamp("2026-03-26 14:59:11", tz=eastern)
    rth_close_et = pd.Timestamp("2026-03-26 16:00:00", tz=eastern)
    
    pre_signal = df[df.index <= signal_time_et]
    post_signal_rth = df[(df.index > signal_time_et) & (df.index <= rth_close_et)]
    post_signal_ah = df[df.index > rth_close_et]
    
    print(f"\n### NVDA Session Analysis (March 26) ###")
    print(f"Pre-Signal High: {pre_signal['High'].max():.2f}")
    if not post_signal_rth.empty:
        print(f"Post-Signal RTH High (Until 16:00): {post_signal_rth['High'].max():.2f}")
    else:
        print("No RTH data after signal.")
        
    if not post_signal_ah.empty:
        print(f"After Hours High: {post_signal_ah['High'].max():.2f}")

    target_trigger = 176.48 - 1.0 # 175.48
    
    if (not post_signal_rth.empty) and (post_signal_rth['High'].max() >= target_trigger):
        print(">>> HIT IN RTH AFTER SIGNAL")
    else:
        print(">>> NO HIT IN RTH AFTER SIGNAL")
        
        # Check March 27 (Next Trading Day)
        mar_27 = df[df.index.date == pd.Timestamp("2026-03-27").date()]
        if not mar_27.empty:
            print(f"March 27 RTH High: {mar_27[mar_27.index.time < pd.Timestamp('16:00').time()]['High'].max():.2f}")
            print(f"March 27 RTH Low: {mar_27[mar_27.index.time < pd.Timestamp('16:00').time()]['Low'].max():.2f}")
            
        # Check March 30 (Next Monday)
        print("Fetching March 30 data...")
        df_30 = yf.download(ticker, start="2026-03-30", end="2026-04-02", interval="1h")
        if not df_30.empty:
            if isinstance(df_30.columns, pd.MultiIndex): df_30.columns = df_30.columns.get_level_values(0)
            print(f"March 31 High: {df_30[df_30.index.date == pd.Timestamp('2026-03-31').date()]['High'].max():.2f}")

if __name__ == "__main__":
    check_intraday_hit()
