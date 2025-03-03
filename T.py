import pandas as pd
import numpy as np
import requests
import streamlit as st
import time
from datetime import datetime

# Cache data fetching to avoid redundant API calls
@st.cache_data(ttl=60)  # Cache data for 60 seconds
def fetch_data(symbol, interval, limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol.upper() + "USDT",
        "interval": interval,
        "limit": limit
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        time.sleep(1)  # Prevent rate limiting
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if not isinstance(data, list) or len(data) == 0 or not isinstance(data[0], list):
            return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
        
        ohlc = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume", "close_time", "quote_asset_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"])
        ohlc = ohlc.astype(float)
        ohlc["datetime"] = pd.to_datetime(ohlc["timestamp"], unit="ms")
        return ohlc[["datetime", "open", "high", "low", "close", "volume"]]
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data for {symbol} ({interval}): {e}")
        return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])

# Update trading signals
def update_signals(df, a=1, c=10):
    if df.empty:
        return "Hold", None, None

    df['high-low'] = df['high'] - df['low']
    df['tr'] = df['high-low'].rolling(window=c, min_periods=1).mean()
    df['atr'] = df['tr']
    df['nLoss'] = a * df['atr']
    df['xATRTrailingStop'] = df['close'] - df['nLoss']
    df['ema'] = df['close'].ewm(span=1, adjust=False).mean()
    df['buy'] = df['close'] > df['xATRTrailingStop']
    df['sell'] = df['close'] < df['xATRTrailingStop']
    df['signal'] = np.where(df['buy'], 'Buy', np.where(df['sell'], 'Sell', 'Hold'))

    latest_signal = df.iloc[-1]
    return latest_signal['signal'], latest_signal['close'], latest_signal['datetime']

# List of coins and timeframes
coins = ['BTC', 'ETH', 'XRP', 'ADA', 'BNB', 'SOL', 'DOT', 'DOGE', 'MATIC', 'SHIB']
timeframes = ['1m', '15m', '1h', '1d']

# Streamlit UI
st.title("Multi-Coin Trading Signals (Binance API)")
selected_coins = st.multiselect("Select coins to analyze", options=coins, default=['BTC', 'ETH'])
st.write("Trading signals for selected coins and all timeframes:")

for coin in selected_coins:
    st.subheader(f"Signals for {coin}")
    for tf in timeframes:
        df = fetch_data(coin, tf)
        signal, price, timestamp = update_signals(df)
        
        if signal and price:
            st.write(f"Timeframe: {tf} | Signal: {signal} | Price: {price} | Time: {timestamp}")
        else:
            st.write(f"Timeframe: {tf} | No signal.")
