import pandas as pd
import numpy as np
import requests
import streamlit as st
import time
from datetime import datetime

# Cache data fetching to avoid redundant API calls
@st.cache_data(ttl=60)  # Cache data for 60 seconds
def fetch_data(symbol, interval, limit=100):
    api_endpoints = [
        "https://api.binance.com/api/v3/klines",
        "https://api1.binance.com/api/v3/klines",
        "https://api2.binance.com/api/v3/klines"
    ]

    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    headers = {'User-Agent': 'Mozilla/5.0'}

    for url in api_endpoints:
        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()  # Raises an HTTPError for bad responses

            data = response.json()
            if not isinstance(data, list) or len(data) == 0:
                return pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])

            o, h, l, c, v = zip(*[(float(d[1]), float(d[2]), float(d[3]), float(d[4]), float(d[5])) for d in data])
            datetime_values = pd.to_datetime([d[0] for d in data], unit='ms')

            return pd.DataFrame({'datetime': datetime_values, 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v})

        except requests.exceptions.HTTPError as e:
            st.error(f"HTTP Error {response.status_code} for {symbol} ({interval}): {e}")
        except requests.exceptions.RequestException as e:
            st.error(f"Request Error for {symbol} ({interval}): {e}")
        except Exception as e:
            st.error(f"Unexpected Error: {e}")

        time.sleep(1)  # Wait 1 second before trying next API endpoint

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
