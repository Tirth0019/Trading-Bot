#!/usr/bin/env python3
"""
COMPREHENSIVE DEBUG PIPELINE
Systematically debug each component from data loading to execution
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Add core to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("COMPREHENSIVE DEBUG PIPELINE - STEP BY STEP")
print("=" * 80)


# ============================================================================
# STEP 1: DATA LOADING AND CLEANING
# ============================================================================
def debug_step_1_data_loading():
    """Step 1: Debug data loading and resampling"""
    print("\n" + "=" * 80)
    print("STEP 1: DATA LOADING AND CLEANING")
    print("=" * 80)
    
    from core.data_loader import load_and_resample
    
    # Test data file
    data_file = "data/XAUUSD_M1.csv"
    
    if not os.path.exists(data_file):
        print(f"[ERROR] Data file not found: {data_file}")
        return None
    
    print(f"\n[INFO] Loading data from: {data_file}")
    
    try:
        # Load and resample
        resampled_data = load_and_resample(data_file, days_back=30)
        
        print(f"[OK] Data loaded successfully!")
        print(f"\n[INFO] Available timeframes:")
        for tf, df in resampled_data.items():
            if df is not None and not df.empty:
                print(f"   {tf:>6}: {len(df):>6} candles | "
                      f"Range: {df.index[0]} to {df.index[-1]}")
                print(f"          Columns: {list(df.columns)}")
                print(f"          Sample data:")
                print(f"          {df.head(2).to_string()}")
                print()
            else:
                print(f"   {tf:>6}: [ERROR] No data")
        
        # Check for required timeframes
        required = ['1H', '15M', '1M']
        missing = [tf for tf in required if tf not in resampled_data or 
                  resampled_data[tf] is None or resampled_data[tf].empty]
        
        if missing:
            print(f"[WARNING] Missing required timeframes: {missing}")
        else:
            print(f"[OK] All required timeframes available: {required}")
        
        # Check data quality
        print(f"\n[INFO] Data Quality Checks:")
        for tf in required:
            if tf in resampled_data and resampled_data[tf] is not None:
                df = resampled_data[tf]
                print(f"\n   {tf} Timeframe:")
                print(f"      Rows: {len(df)}")
                print(f"      Null values: {df.isnull().sum().sum()}")
                print(f"      Duplicates: {df.index.duplicated().sum()}")
                print(f"      Price range: {df['Low'].min():.5f} - {df['High'].max():.5f}")
                print(f"      Volume: {df['Volume'].sum():.0f}")
                
                # Check for invalid data
                invalid = (df['High'] < df['Low']).sum()
                if invalid > 0:
                    print(f"      [WARNING] Invalid candles (High < Low): {invalid}")
                else:
                    print(f"      [OK] All candles valid")
        
        return resampled_data
        
    except Exception as e:
        print(f"[ERROR] Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================================
# STEP 2: MARKET STRUCTURE BUILDING
# ============================================================================
def debug_step_2_structure_building(resampled_data):
    """Step 2: Debug market structure building"""
    print("\n" + "=" * 80)
    print("STEP 2: MARKET STRUCTURE BUILDING")
    print("=" * 80)
    
    if resampled_data is None:
        print("[ERROR] No data available from Step 1")
        return None
    
    from core.structure_builder import build_market_structure, detect_swing_points_scipy
    
    data_15m = resampled_data.get('15M')
    if data_15m is None or data_15m.empty:
        print("[ERROR] No 15M data available")
        return None
    
    print(f"\n[INFO] Testing with 15M data ({len(data_15m)} candles)")
    
    try:
        # Test swing point detection
        print(f"\n[STEP] Step 2.1: Swing Point Detection")
        swing_highs, swing_lows = detect_swing_points_scipy(data_15m, prominence_factor=1.5)
        
        print(f"   Swing Highs: {len(swing_highs)}")
        print(f"   Swing Lows: {len(swing_lows)}")
        
        if len(swing_highs) > 0:
            print(f"   Sample swing highs:")
            for i, (ts, row) in enumerate(swing_highs.head(3).iterrows()):
                print(f"      {i+1}. {ts}: {row['price']:.5f}")
        
        if len(swing_lows) > 0:
            print(f"   Sample swing lows:")
            for i, (ts, row) in enumerate(swing_lows.head(3).iterrows()):
                print(f"      {i+1}. {ts}: {row['price']:.5f}")
        
        if len(swing_highs) == 0 and len(swing_lows) == 0:
            print(f"   [WARNING] No swing points detected!")
            print(f"   [TIP] Try reducing prominence_factor (currently 1.5)")
            return None
        
        # Test structure building
        print(f"\n[STEP] Step 2.2: Market Structure Building")
        structure = build_market_structure(data_15m, prominence_factor=1.5)
        
        print(f"   Structure Points: {len(structure)}")
        
        if len(structure) > 0:
            print(f"   Sample structure points:")
            for i, point in enumerate(structure[:5]):
                print(f"      {i+1}. {point['timestamp']}: {point['type']} @ {point['price']:.5f}")
            
            # Count structure types
            types = {}
            for point in structure:
                types[point['type']] = types.get(point['type'], 0) + 1
            print(f"\n   Structure breakdown:")
            for stype, count in types.items():
                print(f"      {stype}: {count}")
        else:
            print(f"   [WARNING] No structure points generated!")
            return None
        
        return structure
        
    except Exception as e:
        print(f"[ERROR] Error building structure: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================================
# STEP 3: BOS/CHOCH DETECTION
# ============================================================================
def debug_step_3_bos_choch_detection(structure):
    """Step 3: Debug BOS/CHOCH detection"""
    print("\n" + "=" * 80)
    print("STEP 3: BOS/CHOCH DETECTION")
    print("=" * 80)
    
    if structure is None or len(structure) == 0:
        print("[ERROR] No structure available from Step 2")
        return None
    
    from core.smart_money_concepts import MarketStructureAnalyzer, StructurePoint, SwingType
    
    try:
        # Convert structure to StructurePoint objects
        print(f"\n[STEP] Converting structure to StructurePoint objects...")
        structure_points = []
        for point in structure:
            swing_type_map = {
                'HH': SwingType.HH,
                'HL': SwingType.HL,
                'LH': SwingType.LH,
                'LL': SwingType.LL
            }
            structure_points.append(StructurePoint(
                timestamp=pd.Timestamp(point['timestamp']),
                price=point['price'],
                swing_type=swing_type_map[point['type']]
            ))
        
        print(f"   Converted {len(structure_points)} structure points")
        
        # Initialize analyzer
        print(f"\n[STEP] Step 3.1: Initializing MarketStructureAnalyzer")
        analyzer = MarketStructureAnalyzer(config={
            "confidence_thresholds": {
                "BOS": 0.3,  # Low threshold for debugging
                "CHOCH": 0.4
            }
        })
        print(f"   [OK] Analyzer initialized")
        print(f"   BOS threshold: {analyzer.get_confidence_threshold('BOS')}")
        print(f"   CHOCH threshold: {analyzer.get_confidence_threshold('CHOCH')}")
        
        # Get market events
        print(f"\n[STEP] Step 3.2: Detecting Market Events")
        events = analyzer.get_market_events(structure_points)
        
        print(f"   Total events detected: {len(events)}")
        
        if len(events) > 0:
            print(f"\n   Sample events:")
            for i, event in enumerate(events[:5]):
                print(f"      {i+1}. {event.event_type.value} {event.direction} @ {event.timestamp}")
                print(f"         Price: {event.price:.5f}, Confidence: {event.confidence:.3f}")
                print(f"         Description: {event.description}")
        else:
            print(f"   [WARNING] No events detected!")
            print(f"   [TIP] Try:")
            print(f"      - Lowering confidence thresholds")
            print(f"      - Using more data (increase days_back)")
            print(f"      - Checking structure quality")
        
        # Filter by confidence
        print(f"\n[STEP] Step 3.3: Filtering by Confidence")
        high_conf_events = [e for e in events if e.confidence >= 0.6]
        print(f"   Events with confidence >= 0.6: {len(high_conf_events)}")
        
        medium_conf_events = [e for e in events if 0.3 <= e.confidence < 0.6]
        print(f"   Events with confidence 0.3-0.6: {len(medium_conf_events)}")
        
        low_conf_events = [e for e in events if e.confidence < 0.3]
        print(f"   Events with confidence < 0.3: {len(low_conf_events)}")
        
        return events
        
    except Exception as e:
        print(f"[ERROR] Error detecting BOS/CHOCH: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================================
# STEP 4: TREND DETECTION
# ============================================================================
def debug_step_4_trend_detection(resampled_data):
    """Step 4: Debug trend detection"""
    print("\n" + "=" * 80)
    print("STEP 4: TREND DETECTION")
    print("=" * 80)
    
    if resampled_data is None:
        print("[ERROR] No data available")
        return None
    
    from core.trend_detector import detect_trend, detect_swing_points
    from core.trading_executor import MultiTimeframeTradingExecutor
    
    data_1h = resampled_data.get('1H')
    if data_1h is None or data_1h.empty:
        print("[ERROR] No 1H data available")
        return None
    
    print(f"\n[INFO] Testing with 1H data ({len(data_1h)} candles)")
    
    try:
        # Method 1: Using trend_detector
        print(f"\n[STEP] Step 4.1: Using trend_detector module")
        swing_highs, swing_lows = detect_swing_points(data_1h.tail(50), window=3)
        trend = detect_trend(swing_highs, swing_lows)
        
        print(f"   Swing highs: {len(swing_highs)}")
        print(f"   Swing lows: {len(swing_lows)}")
        print(f"   Detected trend: {trend}")
        
        # Method 2: Using trading_executor
        print(f"\n[STEP] Step 4.2: Using trading_executor.analyze_1h_trend()")
        executor = MultiTimeframeTradingExecutor(symbol="XAUUSD")
        trend_executor = executor.analyze_1h_trend(data_1h)
        
        print(f"   Detected trend: {trend_executor}")
        
        if trend != trend_executor:
            print(f"   [WARNING] Trend mismatch! trend_detector: {trend}, executor: {trend_executor}")
        else:
            print(f"   [OK] Trends match")
        
        return trend_executor
        
    except Exception as e:
        print(f"[ERROR] Error detecting trend: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================================
# STEP 5: SIGNAL GENERATION
# ============================================================================
def debug_step_5_signal_generation(resampled_data, trend_1h):
    """Step 5: Debug signal generation"""
    print("\n" + "=" * 80)
    print("STEP 5: SIGNAL GENERATION")
    print("=" * 80)
    
    if resampled_data is None:
        print("[ERROR] No data available")
        return None
    
    from core.trading_executor import MultiTimeframeTradingExecutor
    
    data_15m = resampled_data.get('15M')
    if data_15m is None or data_15m.empty:
        print("[ERROR] No 15M data available")
        return None
    
    print(f"\n[INFO] Testing with 15M data ({len(data_15m)} candles)")
    print(f"   1H Trend: {trend_1h}")
    
    try:
        executor = MultiTimeframeTradingExecutor(
            symbol="XAUUSD",
            confidence_threshold=0.3  # Low threshold for debugging
        )
        
        print(f"\n[STEP] Step 5.1: Finding A+ Entries")
        a_plus_events = executor.find_a_plus_entries_15m(data_15m, trend_1h)
        
        print(f"   A+ Events found: {len(a_plus_events)}")
        
        if len(a_plus_events) > 0:
            print(f"\n   Sample A+ events:")
            for i, event in enumerate(a_plus_events[:5]):
                print(f"      {i+1}. {event.event_type.value} {event.direction} @ {event.timestamp}")
                print(f"         Price: {event.price:.5f}, Confidence: {event.confidence:.3f}")
        else:
            print(f"   [WARNING] No A+ events found!")
            print(f"   [TIP] Possible issues:")
            print(f"      - Confidence threshold too high (current: {executor.confidence_threshold})")
            print(f"      - Trend alignment issue")
            print(f"      - Not enough structure points")
            print(f"      - Market conditions not suitable")
        
        return a_plus_events
        
    except Exception as e:
        print(f"[ERROR] Error generating signals: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================================
# MAIN DEBUG FUNCTION
# ============================================================================
def main():
    """Run complete debug pipeline"""
    
    # Step 1: Data Loading
    resampled_data = debug_step_1_data_loading()
    
    if resampled_data is None:
        print("\n[ERROR] Pipeline stopped at Step 1: Data loading failed")
        return
    
    # Step 2: Structure Building
    structure = debug_step_2_structure_building(resampled_data)
    
    # Step 3: BOS/CHOCH Detection
    events = debug_step_3_bos_choch_detection(structure)
    
    # Step 4: Trend Detection
    trend_1h = debug_step_4_trend_detection(resampled_data)
    
    # Step 5: Signal Generation
    signals = debug_step_5_signal_generation(resampled_data, trend_1h)
    
    # Summary
    print("\n" + "=" * 80)
    print("[SUMMARY] DEBUG PIPELINE SUMMARY")
    print("=" * 80)
    print(f"[OK] Data loaded: {resampled_data is not None}")
    print(f"[OK] Structure built: {structure is not None and len(structure) > 0 if structure else False}")
    print(f"[OK] Events detected: {len(events) if events else 0}")
    print(f"[OK] Trend detected: {trend_1h if trend_1h else 'None'}")
    print(f"[OK] Signals generated: {len(signals) if signals else 0}")
    
    if signals and len(signals) == 0:
        print("\n[RECOMMENDATIONS]:")
        print("   1. Lower confidence_threshold (try 0.3 or 0.4)")
        print("   2. Increase days_back for more data")
        print("   3. Try different symbols (EURUSD, GBPUSD)")
        print("   4. Check prominence_factor in structure building")
        print("   5. Verify data quality and completeness")


if __name__ == "__main__":
    main()

