#!/usr/bin/env python3
"""
STEP-BY-STEP DEBUG SCRIPT
Tests each component individually with detailed output
"""

import sys
import os
from pathlib import Path
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, str(Path(__file__).parent))

from core.data_loader import load_and_resample
from core.trading_executor import MultiTimeframeTradingExecutor
from core.structure_builder import build_market_structure

print("=" * 80)
print("STEP-BY-STEP DEBUG - DETAILED ANALYSIS")
print("=" * 80)

# Step 1: Load data
print("\n[STEP 1] Loading data...")
data_file = "data/XAUUSD_M1.csv"
resampled_data = load_and_resample(data_file, days_back=30)
data_1h = resampled_data.get('1H')
data_15m = resampled_data.get('15M')
print(f"[OK] Data loaded: 1H={len(data_1h)} candles, 15M={len(data_15m)} candles")

# Step 2: Check 1H trend
print("\n[STEP 2] Analyzing 1H trend...")
executor = MultiTimeframeTradingExecutor(symbol="XAUUSD", confidence_threshold=0.3)
trend_1h = executor.analyze_1h_trend(data_1h)
print(f"[OK] 1H Trend: {trend_1h}")

# Step 3: Build structure on 15M
print("\n[STEP 3] Building market structure on 15M...")
structure = build_market_structure(data_15m, prominence_factor=1.5)
print(f"[OK] Structure points: {len(structure)}")

# Step 4: Get events
print("\n[STEP 4] Detecting market events...")
events = executor.market_analyzer.get_market_events(structure)
print(f"[OK] Total events: {len(events)}")

# Step 5: Filter by confidence
print("\n[STEP 5] Filtering by confidence (threshold=0.3)...")
conf_filtered = [e for e in events if e.confidence >= 0.3]
print(f"[OK] Events with confidence >= 0.3: {len(conf_filtered)}")

# Step 6: Check trend alignment for each event
print("\n[STEP 6] Checking trend alignment...")
aligned_events = []
for event in conf_filtered:
    aligned = executor._is_trend_aligned_enhanced(event, trend_1h, data_15m)
    if aligned:
        aligned_events.append(event)
    print(f"   Event: {event.event_type.value} {event.direction} @ {event.timestamp}")
    print(f"      Confidence: {event.confidence:.3f}")
    print(f"      Trend aligned: {aligned}")
    
    # Show 15M trend for this event (using same logic as _is_trend_aligned_enhanced)
    recent_15m = data_15m[data_15m.index <= event.timestamp].tail(50)
    from core.trend_detector import detect_trend, detect_swing_points
    swing_highs, swing_lows = detect_swing_points(recent_15m, window=2)
    trend_15m = detect_trend(swing_highs, swing_lows)
    print(f"      15M trend at event time: {trend_15m}")
    
    # Show why it's being rejected
    if event.direction in ["BUY", "Bullish"]:
        should_pass = (trend_1h == "uptrend" and trend_15m == "uptrend") or \
                     (trend_1h == "sideways" and trend_15m == "uptrend") or \
                     (trend_1h == "uptrend" and trend_15m == "sideways")
        print(f"      Should pass (Bullish): {should_pass} (1H={trend_1h}, 15M={trend_15m})")
    elif event.direction in ["SELL", "Bearish"]:
        should_pass = (trend_1h == "downtrend" and trend_15m == "downtrend") or \
                     (trend_1h == "sideways" and trend_15m == "downtrend") or \
                     (trend_1h == "downtrend" and trend_15m == "sideways")
        print(f"      Should pass (Bearish): {should_pass} (1H={trend_1h}, 15M={trend_15m})")
    print()

print(f"[OK] Events passing trend alignment: {len(aligned_events)}")

# Step 7: Final A+ entries
print("\n[STEP 7] Getting A+ entries (full method)...")
a_plus = executor.find_a_plus_entries_15m(data_15m, trend_1h)
print(f"[OK] A+ Events found: {len(a_plus)}")

if len(a_plus) > 0:
    print("\n[SUCCESS] Sample A+ events:")
    for i, event in enumerate(a_plus[:5]):
        print(f"   {i+1}. {event.event_type.value} {event.direction} @ {event.timestamp}")
        print(f"      Confidence: {event.confidence:.3f}")
else:
    print("\n[ISSUE] No A+ events found!")
    print("   Breakdown:")
    print(f"      Total events: {len(events)}")
    print(f"      Confidence filtered: {len(conf_filtered)}")
    print(f"      Trend aligned: {len(aligned_events)}")
    print(f"      Final A+ entries: {len(a_plus)}")
    
    if len(conf_filtered) > 0 and len(aligned_events) == 0:
        print("\n   [ROOT CAUSE] Trend alignment is filtering out all events!")
        print(f"   1H trend is '{trend_1h}' which may be too strict")

print("\n" + "=" * 80)
print("DEBUG COMPLETE")
print("=" * 80)

