import pandas as pd
import numpy as np
import requests
import streamlit as st
import time
from datetime import datetime

# Cache data fetching to avoid redundant API calls
@st.cache_data(ttl=60)  # Cache data for 60 seconds
def fetch_data(symbol, interval, limit=100):
    url = f"https://api.coingecko.com/api/v3/coins/{symbol}/market_chart"
    params = {"vs_currency": "usd", "days": "1", "interval": interval}
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        time.sleep(1)  # Prevent rate limiting
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if "prices" not in data:
            return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
        
        prices = data["prices"]
        ohlc = pd.DataFrame(prices, columns=["datetime", "close"])
        ohlc["datetime"] = pd.to_datetime(ohlc["datetime"], unit="ms")
        ohlc["open"] = ohlc["close"].shift(1)
        ohlc["high"] = ohlc["close"].rolling(window=2).max()
        ohlc["low"] = ohlc["close"].rolling(window=2).min()
        ohlc["volume"] = np.nan  # Volume not available in CoinGecko API
        return ohlc.dropna()
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
coins = ['bitcoin', 'ethereum', 'ripple', 'cardano', 'binancecoin', 'solana', 'polkadot', 'dogecoin', 'matic-network', 'shiba-inu']
timeframes = ['hourly', 'daily']

# Streamlit UI
st.title("Multi-Coin Trading Signals (CoinGecko API)")
selected_coins = st.multiselect("Select coins to analyze", options=coins, default=['bitcoin', 'ethereum'])
st.write("Trading signals for selected coins and all timeframes:")

for coin in selected_coins:
    st.subheader(f"Signals for {coin.capitalize()}")
    for tf in timeframes:
        df = fetch_data(coin, tf)
        signal, price, timestamp = update_signals(df)
        
        if signal and price:
            st.write(f"Timeframe: {tf} | Signal: {signal} | Price: {price} | Time: {timestamp}")
        else:
            st.write(f"Timeframe: {tf} | No signal.")
