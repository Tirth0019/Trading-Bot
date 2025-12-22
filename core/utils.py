"""
Core utility functions for the trading bot.
Consolidates common functions to eliminate code duplication.
"""

import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from typing import Tuple, List, Optional
from functools import lru_cache


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculates the Average True Range (ATR).
    
    This is the consolidated ATR calculation function used throughout the codebase.
    Handles both lowercase and capitalized column names for compatibility.
    
    Args:
        df: DataFrame with OHLC data (columns: Open/High/Low/Close or open/high/low/close)
        period: ATR period (default: 14)
    
    Returns:
        Series with ATR values
    """
    # Handle both lowercase and capitalized column names
    high_col = 'High' if 'High' in df.columns else 'high'
    low_col = 'Low' if 'Low' in df.columns else 'low'
    close_col = 'Close' if 'Close' in df.columns else 'close'
    
    if high_col not in df.columns or low_col not in df.columns or close_col not in df.columns:
        raise ValueError(f"DataFrame must contain {high_col}, {low_col}, and {close_col} columns")
    
    high = df[high_col]
    low = df[low_col]
    close = df[close_col]
    prev_close = close.shift(1)
    
    # Calculate True Range
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    
    # Return ATR as rolling mean
    return tr.rolling(window=period).mean()


def detect_swing_points(df: pd.DataFrame, 
                       window: int = 3, 
                       prominence_factor: Optional[float] = None) -> Tuple[List[Tuple[pd.Timestamp, float]], List[Tuple[pd.Timestamp, float]]]:
    """
    Detects swing highs and lows using scipy.signal.find_peaks.
    
    This is the consolidated swing point detection function used throughout the codebase.
    Uses ATR-based prominence for better signal quality.
    
    Args:
        df: DataFrame with OHLC data (columns: Open/High/Low/Close or open/high/low/close)
        window: Minimum distance between swing points (default: 3)
        prominence_factor: Multiplier for ATR-based prominence. If None, uses 0.20 * ATR
    
    Returns:
        Tuple of (swing_highs, swing_lows) where each is a list of (timestamp, price) tuples
    """
    # Handle both lowercase and capitalized column names
    high_col = 'High' if 'High' in df.columns else 'high'
    low_col = 'Low' if 'Low' in df.columns else 'low'
    
    if high_col not in df.columns or low_col not in df.columns:
        raise ValueError(f"DataFrame must contain {high_col} and {low_col} columns")
    
    # Calculate ATR for dynamic prominence
    atr = calculate_atr(df).mean()
    
    # Set prominence based on ATR
    if prominence_factor is None:
        # Default: 20% of ATR
        required_prominence = atr * 0.20 if atr > 0 else (df[high_col].max() - df[low_col].min()) * 0.01
    else:
        # Custom prominence factor (e.g., 7.5 * ATR for structure_builder)
        required_prominence = atr * prominence_factor if atr > 0 else (df[high_col].max() - df[low_col].min()) * 0.01
    
    # Find peaks (highs) and troughs (lows)
    high_indices, _ = find_peaks(df[high_col], prominence=required_prominence, distance=window)
    low_indices, _ = find_peaks(-df[low_col], prominence=required_prominence, distance=window)
    
    # Format output as list of (timestamp, price) tuples
    swing_highs = [(df.index[i], df[high_col].iloc[i]) for i in high_indices]
    swing_lows = [(df.index[i], df[low_col].iloc[i]) for i in low_indices]
    
    return swing_highs, swing_lows


def detect_swing_points_dataframe(df: pd.DataFrame, 
                                  prominence_factor: float = 7.5) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Detects swing points and returns as DataFrames (for compatibility with structure_builder).
    
    This is a wrapper around detect_swing_points() that returns DataFrames instead of tuples.
    Maintains backward compatibility with code that expects DataFrame output.
    
    Args:
        df: DataFrame with OHLC data
        prominence_factor: Multiplier for ATR-based prominence (default: 7.5)
    
    Returns:
        Tuple of (swing_highs_df, swing_lows_df) DataFrames with 'price' and 'type' columns
    """
    swing_highs, swing_lows = detect_swing_points(df, prominence_factor=prominence_factor)
    
    # Convert to DataFrames
    if swing_highs:
        swing_highs_df = pd.DataFrame({
            'price': [price for _, price in swing_highs],
            'type': 'high'
        }, index=[ts for ts, _ in swing_highs])
    else:
        swing_highs_df = pd.DataFrame(columns=['price', 'type'])
    
    if swing_lows:
        swing_lows_df = pd.DataFrame({
            'price': [price for _, price in swing_lows],
            'type': 'low'
        }, index=[ts for ts, _ in swing_lows])
    else:
        swing_lows_df = pd.DataFrame(columns=['price', 'type'])
    
    return swing_highs_df, swing_lows_df


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizes column names to capitalized format (Open, High, Low, Close, Volume).
    
    Args:
        df: DataFrame with potentially lowercase column names
    
    Returns:
        DataFrame with normalized capitalized column names
    """
    column_mapping = {
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    }
    
    df = df.copy()
    df.columns = [column_mapping.get(col.lower(), col) for col in df.columns]
    
    return df


@lru_cache(maxsize=128)
def cached_atr(df_hash: int, period: int) -> float:
    """
    Cached ATR calculation for repeated calculations on same data.
    Note: This requires passing a hash of the DataFrame, which is a simplified caching approach.
    For production, consider using a more sophisticated caching mechanism.
    """
    # This is a placeholder - actual implementation would need to store DataFrames
    # For now, this demonstrates the caching pattern
    pass

