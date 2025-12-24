
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# Add core to path
sys.path.insert(0, ".")
from core.trading_executor import MultiTimeframeTradingExecutor, TradeSignal

def verify_logic():
    print("🧪 Verifying Displacement Filter Logic...")
    
    # 1. Mock Executor
    executor = MultiTimeframeTradingExecutor()
    executor.risk_manager = MagicMock()
    # Mock ATR to return fixed value 1.0
    mock_atr_series = pd.Series([1.0] * 100)
    executor.risk_manager.calculate_atr = MagicMock(return_value=mock_atr_series)
    executor.risk_manager.compute_stop_and_target_from_atr = MagicMock(return_value=(1990.0, 2010.0))
    executor.risk_manager.risk_amount_for_balance = MagicMock(return_value=100.0)
    executor.risk_manager.calculate_position_size = MagicMock(return_value=1.0)
    
    # 2. Mock Data (1M)
    # Create 20 candles. 
    # Index 10 is entry time. 
    # Next 8 candles (11-18) are lookahead.
    
    dates = [datetime(2025, 1, 1, 12, i) for i in range(30)]
    data = {
        'Open': [2000.0] * 30,
        'High': [2005.0] * 30,
        'Low': [1995.0] * 30,
        'Close': [2000.0] * 30,
        'Volume': [100] * 30
    }
    df_1m = pd.DataFrame(data, index=dates)
    
    # Scenario A: PASS (Displacement >= 0.6)
    # Signal Direction: BUY
    # Entry Price: 2000.0
    # ATR: 1.0
    # Need Max High - Entry >= 0.6 * 1.0 = 0.6
    # So High needs to calculate to >= 2000.6
    
    pass_df = df_1m.copy()
    # Set high of candle 12 (2 mins after entry) to 2001.0 (Displacement = 1.0)
    pass_df.loc[dates[12], 'High'] = 2001.0
    pass_df.loc[dates[12], 'Close'] = 2001.0 # Green candle for momentum
    
    entry_time = dates[10]
    current_time = dates[25] # Plenty of time passed
    
    # Pass Signal
    signal_pass = TradeSignal(
        timestamp=entry_time,
        price=2000.0,
        direction="BUY",
        event_type="CHOCH",
        confidence=0.8,
        timeframe="15M"
    )
    
    print("\n--- TEST 1: Should PASS (High Displacment) ---")
    executor.open_trades = [] # Clear
    result_pass = executor.confirm_1m_signal_point_in_time(
        signal=signal_pass,
        data_1m=pass_df,
        current_time=current_time,
        account_balance=10000
    )
    
    # Check log file
    try:
        with open("choch_debug.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            print("LOG CONTENT (TAIL):")
            for line in lines[-5:]:
                print(line.strip())
            
            if "Result: PASS ✅" in "".join(lines[-5:]):
                print("✅ Test 1 Passed: Correctly logged PASS")
            else:
                print("❌ Test 1 Failed: Did not log PASS")
    except Exception as e:
        print(f"❌ Test 1 Failed: Could not read log ({e})")

    # Scenario B: FAIL (Low Displacement)
    # High only 2000.4 (Displacement 0.4 < 0.6)
    fail_df = df_1m.copy()
    fail_df.loc[dates[12], 'High'] = 2000.4
    
    print("\n--- TEST 2: Should FAIL (Low Displacment) ---")
    result_fail = executor.confirm_1m_signal_point_in_time(
        signal=signal_pass,
        data_1m=fail_df,
        current_time=current_time,
        account_balance=10000
    )
    
    if result_fail is None:
         print("✅ Test 2 Passed: correctly returned None (filtered)")
    else:
         print("❌ Test 2 Failed: Trade executed despite low displacement")

    # Check log file again
    try:
        with open("choch_debug.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            print("LOG CONTENT (TAIL):")
            for line in lines[-5:]:
                print(line.strip())
            
            if "Result: FAIL ❌" in "".join(lines[-5:]):
                print("✅ Test 2 passed log check")
            else:
                print("❌ Test 2 failed log check")
    except Exception as e:
        print(f"❌ Test 2 Failed: Could not read log ({e})")

if __name__ == "__main__":
    verify_logic()
