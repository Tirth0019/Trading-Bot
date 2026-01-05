#!/usr/bin/env python3
"""
INTEGRATED BACKTESTER - Uses MultiTimeframeTradingExecutor
Replaces the simple strategy with your sophisticated multi-timeframe system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trading_executor import MultiTimeframeTradingExecutor
from core.data_loader import load_and_resample
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

class IntegratedBacktester:
    """
    Backtester that uses the sophisticated MultiTimeframeTradingExecutor
    """
    
    def __init__(self, 
                 symbol: str = "XAUUSD",
                 risk_per_trade: float = 0.01,
                 confidence_threshold: float = 0.6,
                 atr_multiplier: float = 2.5,
                 days_back: int = 60,
                 executor: MultiTimeframeTradingExecutor = None):  # NEW ARGUMENT
        
        self.symbol = symbol
        self.risk_per_trade = risk_per_trade
        self.confidence_threshold = confidence_threshold
        self.atr_multiplier = atr_multiplier
        self.days_back = days_back
        
        # Initialize the sophisticated trading executor
        if executor is not None:
             # Use the provided executor (Shared Instance)
             self.executor = executor
        else:
            # Fallback (Legacy)
            self.executor = MultiTimeframeTradingExecutor(
                symbol=symbol,
                risk_per_trade=risk_per_trade,
                confidence_threshold=confidence_threshold,
                atr_multiplier=atr_multiplier,
                risk_reward_ratio=2.0
            )
        
        # Store prominence factor for structure building
        self.prominence_factor = 1.5  # Much lower than default 7.5
    
    def run_backtest(self, data_file: str):
        """Run backtest using the sophisticated strategy"""
        
        print(f" Starting Integrated Backtester for {self.symbol}")
        print(f" Using sophisticated MultiTimeframeTradingExecutor")
        print(f" Analyzing last {self.days_back} days")
        print("=" * 60)
        
        # Verify data file exists
        if not os.path.exists(data_file):
            print(f" Data file not found: {data_file}")
            return None
        
        print(f" Data file: {data_file}")
        print("\n Configuration:")
        print(f"   Symbol: {self.symbol}")
        print(f"   Risk per trade: {self.risk_per_trade:.1%}")
        print(f"   Confidence threshold: {self.confidence_threshold}")
        print(f"   ATR multiplier: {self.atr_multiplier}")
        print(f"   Days to analyze: {self.days_back}")
        
        # Run the sophisticated strategy
        print("\n Executing sophisticated multi-timeframe strategy...")
        results = self.executor.run_strategy(data_file, days_back=self.days_back)
        
        # Display results
        self._display_results(results)
        
        return results
    
    def _display_results(self, results):
        """Display comprehensive backtest results"""
        
        print("\n" + "=" * 60)
        print(" BACKTEST RESULTS")
        print("=" * 60)
        
        # Basic metrics
        print(f" Total Signals Generated: {results['signals_generated']}")
        print(f" Trades Executed: {results['trades_executed']}")
        print(f" Trades Closed: {results['trades_closed']}")
        print(f" Total P&L: ${results['total_pnl']:.2f}")
        print(f" Winning Trades: {results['winning_trades']}")
        print(f" Losing Trades: {results['losing_trades']}")
        
        # BOS Follow-Through Filter Stats
        if hasattr(self.executor, 'stats'):
            print(f"\n BOS FOLLOW-THROUGH FILTER STATS:")
            print(f"   BOS Rejected (Weak Displacement): {self.executor.stats.get('bos_rejected_displacement', 0)}")
            print(f"   BOS Rejected (Weak Body Ratio): {self.executor.stats.get('bos_rejected_body_ratio', 0)}")
            print(f"   BOS Rejected (Other): {self.executor.stats.get('bos_rejected_other', 0)}")
            total_bos_rejected = (self.executor.stats.get('bos_rejected_displacement', 0) + 
                                 self.executor.stats.get('bos_rejected_body_ratio', 0) + 
                                 self.executor.stats.get('bos_rejected_other', 0))
            print(f"   Total BOS Rejected: {total_bos_rejected}")
        
        # Calculate additional metrics
        if results['trades_closed'] > 0:
            win_rate = (results['winning_trades'] / results['trades_closed']) * 100
            print(f" Win Rate: {win_rate:.1f}%")
            
            # Performance assessment
            if win_rate >= 50:
                print(" EXCELLENT win rate!")
            elif win_rate >= 40:
                print(" GOOD win rate")
            elif win_rate >= 30:
                print("WARNING: ACCEPTABLE win rate")
            else:
                print(" POOR win rate - needs optimization")
        else:
            print(" Win Rate: N/A (no closed trades)")
        
        # P&L assessment
        if results['total_pnl'] > 0:
            print(" PROFITABLE STRATEGY!")
        elif results['total_pnl'] == 0:
            print(" BREAK-EVEN STRATEGY")
        else:
            print(" LOSING STRATEGY - needs optimization")
        
        # Strategy effectiveness
        if results['signals_generated'] == 0:
            print("\n OPTIMIZATION NEEDED:")
            print("   - No signals generated")
            print("   - Consider reducing confidence_threshold")
            print("   - Check BOS/CHOCH detection parameters")
            print("   - Try different instruments (trending markets)")
        
        elif results['trades_executed'] == 0:
            print("\n OPTIMIZATION NEEDED:")
            print("   - Signals generated but no trades executed")
            print("   - 1M confirmation may be too strict")
            print("   - Retracement confirmation may be too strict")
            print("   - Consider relaxing confirmation parameters")
        
        elif results['trades_closed'] == 0:
            print("\n TRADES STILL OPEN:")
            print("   - Some trades executed but none closed yet")
            print("   - May need longer backtesting period")
            print("   - Check if stops/targets are appropriate")

def main():
    """Main backtesting function"""
    
    # Configuration
    SYMBOL = "XAUUSD"  # Gold usually has good trends
    DAYS_BACK = 60     # 2 months of data
    
    # Test multiple data files
    data_files = [
        f"data/{SYMBOL}_M1.csv",
        "data/EURUSD_M1.csv",
        "data/GBPUSD_M1.csv",
        "data/BTCUSD_M1.csv"
    ]
    
    data_file = None
    for file in data_files:
        if os.path.exists(file):
            data_file = file
            # Update symbol based on found file
            if "EURUSD" in file:
                SYMBOL = "EURUSD"
            elif "GBPUSD" in file:
                SYMBOL = "GBPUSD"
            elif "BTCUSD" in file:
                SYMBOL = "BTCUSD"
            elif "XAUUSD" in file:
                SYMBOL = "XAUUSD"
            break
    
    if data_file is None:
        print(" No data files found!")
        print("Expected files:")
        for file in data_files:
            print(f"   - {file}")
        return
    
    # Initialize integrated backtester
    backtester = IntegratedBacktester(
        symbol=SYMBOL,
        risk_per_trade=0.01,        # 1% risk
        confidence_threshold=0.6,    # Reduced for more signals
        atr_multiplier=2.5,         # Reasonable stops
        days_back=DAYS_BACK
    )
    
    # Run backtest
    results = backtester.run_backtest(data_file)
    
    if results is not None:
        print("\n Backtest completed successfully!")
        
        # Suggestions based on results
        if results.get('trades_closed', 0) > 0:
            print("\n NEXT STEPS:")
            print("   - Review individual trade details")
            print("   - Test with different parameters")
            print("   - Try different time periods")
            print("   - Test on multiple instruments")
    else:
        print("\n Backtest failed")

if __name__ == "__main__":
    main()
