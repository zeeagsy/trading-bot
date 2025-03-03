import pandas as pd
import numpy as np
import requests
import streamlit as st
import time
from datetime import datetime

# Free CryptoCompare API Key (Replace with your own if needed)
API_KEY = "your_free_api_key_here"

# Cache data fetching to avoid redundant API calls
@st.cache_data(ttl=60)  # Cache data for 60 seconds
def fetch_data(symbol, interval, limit=100):
    url = f"https://min-api.cryptocompare.com/data/v2/histominute" if interval == "hourly" else f"https://min-api.cryptocompare.com/data/v2/histoday"
    params = {
        "fsym": symbol.upper(),
        "tsym": "USD",
        "limit": limit,
        "api_key": API_KEY
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        time.sleep(1)  # Prevent rate limiting
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if "Data" not in data or "Data" not in data["Data"]:
            return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
        
        prices = data["Data"]["Data"]
        ohlc = pd.DataFrame(prices)
        ohlc["datetime"] = pd.to_datetime(ohlc["time"], unit="s")
        return ohlc[["datetime", "open", "high", "low", "close", "volumeto"]].rename(columns={"volumeto": "volume"})
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
timeframes = ['hourly', 'daily']

# Streamlit UI
st.title("Multi-Coin Trading Signals (CryptoCompare API)")
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
