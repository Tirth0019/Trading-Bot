import pandas as pd
from typing import List, Dict, Tuple, Optional

# Import consolidated utility functions
from .utils import detect_swing_points_dataframe

# Backward compatibility alias
def detect_swing_points_scipy(df: pd.DataFrame, prominence_factor: float = 7.5) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Detects swing points using scipy (now uses consolidated utility function).
    
    This function is kept for backward compatibility.
    New code should use detect_swing_points_dataframe() from utils module.
    """
    return detect_swing_points_dataframe(df, prominence_factor)

def build_market_structure(df: pd.DataFrame, prominence_factor: float = 7.5) -> List[Dict]:
    """
    FIXED: Builds and classifies the market structure (HH, LH, HL, LL) chronologically.
    Now properly adds ALL structure points, including the first ones.
    """
    swing_highs, swing_lows = detect_swing_points_scipy(df, prominence_factor)
    all_swings = pd.concat([swing_highs, swing_lows]).sort_index()

    if len(all_swings) < 2:
        return []

    structure = []
    last_high: Optional[Dict] = None
    last_low: Optional[Dict] = None

    for timestamp, row in all_swings.iterrows():
        price = row['price']
        point_type = row['type']
        
        classification = None
        
        if point_type == 'high':
            if last_high:
                # Compare with previous high
                classification = "HH" if price > last_high['price'] else "LH"
            else:
                # FIXED: First high gets a default classification
                classification = "HH"  # Assume first high is HH
            
            # Update last_high
            last_high = {'timestamp': timestamp, 'price': price}
            
        else:  # point_type == 'low'
            if last_low:
                # Compare with previous low
                classification = "HL" if price > last_low['price'] else "LL"
            else:
                # FIXED: First low gets a default classification
                classification = "LL"  # Assume first low is LL
            
            # Update last_low
            last_low = {'timestamp': timestamp, 'price': price}
        
        # FIXED: Always add to structure (no more filtering out first points)
        structure.append({
            "timestamp": timestamp,
            "type": classification,
            "price": price
        })
            
    return structure

def get_market_analysis(df: pd.DataFrame, prominence_factor: float = 7.5, trend_window: int = 4) -> Dict:
    """
    Main function to get market structure and confirm the current trend.
    """
    structure = build_market_structure(df, prominence_factor)
    
    trend = "sideways"
    if len(structure) >= trend_window:
        recent_structure = structure[-trend_window:]
        types = [p['type'] for p in recent_structure]
        
        is_uptrend = "HH" in types and "HL" in types and "LL" not in types
        is_downtrend = "LL" in types and "LH" in types and "HH" not in types

        if is_uptrend:
            trend = "uptrend"
        elif is_downtrend:
            trend = "downtrend"

    swing_highs, swing_lows = detect_swing_points_scipy(df, prominence_factor)
    
    return {
        "trend": trend,
        "structure": structure,
        "swing_highs": list(swing_highs.reset_index().to_records(index=False)),
        "swing_lows": list(swing_lows.reset_index().to_records(index=False))
    }