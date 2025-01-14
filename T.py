import pandas as pd
import numpy as np
import requests
import time
import streamlit as st

# Fetch data from Binance API
def fetch_data(symbol, interval, limit=100):
    url = 'https://api.binance.com/api/v3/klines'
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list) or len(data) == 0 or not isinstance(data[0], list):
            return pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])

        o, h, l, c, v = zip(*[(float(d[1]), float(d[2]), float(d[3]), float(d[4]), float(d[5])) for d in data])
        datetime = pd.to_datetime([d[0] for d in data], unit='ms')

        return pd.DataFrame({
            'datetime': datetime,
            'open': o,
            'high': h,
            'low': l,
            'close': c,
            'volume': v
        })
    except Exception as e:
        st.error(f"Error fetching data for {symbol} ({interval}): {e}")
        return pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])

# Update signals based on new data
def update_signals(df, a=1, c=10):
    if df.empty:
        return None, None, None

    df['high-low'] = df['high'] - df['low']
    df['high-close_prev'] = np.abs(df['high'] - df['close'].shift(1))
    df['low-close_prev'] = np.abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['high-low', 'high-close_prev', 'low-close_prev']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=c, min_periods=1).mean()

    df['nLoss'] = a * df['atr']
    df['xATRTrailingStop'] = np.nan

    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['xATRTrailingStop'].iloc[i-1] and df['close'].iloc[i-1] > df['xATRTrailingStop'].iloc[i-1]:
            df.loc[i, 'xATRTrailingStop'] = max(df['xATRTrailingStop'].iloc[i-1], df['close'].iloc[i] - df['nLoss'].iloc[i])
        elif df['close'].iloc[i] < df['xATRTrailingStop'].iloc[i-1] and df['close'].iloc[i-1] < df['xATRTrailingStop'].iloc[i-1]:
            df.loc[i, 'xATRTrailingStop'] = min(df['xATRTrailingStop'].iloc[i-1], df['close'].iloc[i] + df['nLoss'].iloc[i])
        elif df['close'].iloc[i] > df['xATRTrailingStop'].iloc[i-1]:
            df.loc[i, 'xATRTrailingStop'] = df['close'].iloc[i] - df['nLoss'].iloc[i]
        else:
            df.loc[i, 'xATRTrailingStop'] = df['close'].iloc[i] + df['nLoss'].iloc[i]

    df['ema'] = df['close'].ewm(span=1, adjust=False).mean()
    df['buy'] = (df['close'] > df['xATRTrailingStop']) & (df['ema'] > df['xATRTrailingStop'])
    df['sell'] = (df['close'] < df['xATRTrailingStop']) & (df['ema'] < df['xATRTrailingStop'])

    df['signal'] = np.nan
    df.loc[df['buy'], 'signal'] = 'Buy'
    df.loc[df['sell'], 'signal'] = 'Sell'

    latest_signal = df.iloc[-1]
    if latest_signal['buy']:
        return 'Buy', latest_signal['close'], latest_signal['datetime']
    elif latest_signal['sell']:
        return 'Sell', latest_signal['close'], latest_signal['datetime']
    else:
        return 'Hold', None, latest_signal['datetime']

# Parameters
coins = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'ADAUSDT', 'BNBUSDT', 'SOLUSDT', 'DOTUSDT', 'DOGEUSDT', 'MATICUSDT', 'SHIBUSDT']
timeframes = ['1m', '15m', '1h', '1d']

# Streamlit UI
st.title("User-Selected Multi-Coin Trading Signals")
selected_coins = st.multiselect("Select coins to analyze", options=coins, default=['BTCUSDT', 'ETHUSDT'])
st.write("Trading signals for selected coins and all timeframes:")

while True:
    # Display data for each selected coin and timeframe
    for coin in selected_coins:
        st.subheader(f"Signals for {coin}")
        for tf in timeframes:
            df = fetch_data(coin, tf)
            signal, price, timestamp = update_signals(df)

            if signal and price:
                st.write(f"Timeframe: {tf} | Signal: {signal} | Price: {price} | Time: {timestamp}")
            else:
                st.write(f"Timeframe: {tf} | No signal.")
    
    # Wait for 60 seconds and refresh the app
    time.sleep(60)
    
