#!/usr/bin/env python3
"""
🚀 CENTRALIZED TRADING BOT SYSTEM
Single entry point for all trading bot functionality

Usage:
    python trading_bot.py --symbol XAUUSD --days 60
    python trading_bot.py --backtest --symbol EURUSD --risk 0.02
    python trading_bot.py --analyze --symbol GBPUSD
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any
import warnings

# Add core to path
sys.path.insert(0, str(Path(__file__).parent))

from core.trading_executor import MultiTimeframeTradingExecutor
from core.data_loader import load_and_resample
from core.backtester import IntegratedBacktester
import pandas as pd

warnings.filterwarnings('ignore')


class TradingBot:
    """
    🎯 CENTRALIZED TRADING BOT SYSTEM
    
    Single unified interface for all trading bot functionality:
    - Backtesting
    - Strategy execution
    - Market analysis
    - Performance reporting
    """
    
    def __init__(self, 
                 symbol: str = "XAUUSD",
                 risk_per_trade: float = 0.01,
                 confidence_threshold: float = 0.6,
                 atr_multiplier: float = 2.5,
                 risk_reward_ratio: float = 2.0):
        """
        Initialize the centralized trading bot.
        
        Args:
            symbol: Trading symbol (e.g., 'XAUUSD', 'EURUSD')
            risk_per_trade: Risk percentage per trade (default: 0.01 = 1%)
            confidence_threshold: Minimum confidence for signals (default: 0.6)
            atr_multiplier: ATR multiplier for stop loss (default: 2.5)
            risk_reward_ratio: Risk-reward ratio (default: 2.0)
        """
        self.symbol = symbol.upper()
        self.risk_per_trade = risk_per_trade
        self.confidence_threshold = confidence_threshold
        self.atr_multiplier = atr_multiplier
        self.risk_reward_ratio = risk_reward_ratio
        
        # Initialize executor
        self.executor = MultiTimeframeTradingExecutor(
            symbol=self.symbol,
            risk_per_trade=risk_per_trade,
            confidence_threshold=confidence_threshold,
            atr_multiplier=atr_multiplier,
            risk_reward_ratio=risk_reward_ratio
        )
        
        # Initialize backtester
        # Initialize backtester
        self.backtester = IntegratedBacktester(
            symbol=self.symbol,
            risk_per_trade=risk_per_trade,
            confidence_threshold=confidence_threshold,
            atr_multiplier=atr_multiplier,
            executor=self.executor
        )
    
    def run_backtest(self, 
                    data_file: Optional[str] = None,
                    days_back: int = 60) -> Dict[str, Any]:
        """
        Run a complete backtest on historical data.
        
        Args:
            data_file: Path to CSV data file (auto-detects if None)
            days_back: Number of days to analyze (default: 60)
            
        Returns:
            Dictionary with backtest results
        """
        print("=" * 70)
        print("[START] CENTRALIZED TRADING BOT - BACKTEST MODE")
        print("=" * 70)
        
        # Auto-detect data file if not provided
        if data_file is None:
            data_file = self._find_data_file()
            if data_file is None:
                return {"error": "No data file found"}
        
        print(f"\n[INFO] Configuration:")
        print(f"   Symbol: {self.symbol}")
        print(f"   Data File: {data_file}")
        print(f"   Days Back: {days_back}")
        print(f"   Risk per Trade: {self.risk_per_trade:.1%}")
        print(f"   Confidence Threshold: {self.confidence_threshold}")
        print(f"   ATR Multiplier: {self.atr_multiplier}")
        print(f"   Risk-Reward Ratio: {self.risk_reward_ratio}:1")
        print()
        
        # Run backtest
        self.backtester.days_back = days_back
        results = self.backtester.run_backtest(data_file)
        
        return results or {}
    
    def analyze_market(self,
                      data_file: Optional[str] = None,
                      days_back: int = 30) -> Dict[str, Any]:
        """
        Analyze market structure and trends without executing trades.
        
        Args:
            data_file: Path to CSV data file (auto-detects if None)
            days_back: Number of days to analyze (default: 30)
            
        Returns:
            Dictionary with market analysis results
        """
        print("=" * 70)
        print("🔍 CENTRALIZED TRADING BOT - MARKET ANALYSIS MODE")
        print("=" * 70)
        
        # Auto-detect data file if not provided
        if data_file is None:
            data_file = self._find_data_file()
            if data_file is None:
                return {"error": "No data file found"}
        
        print(f"\n📊 Analyzing {self.symbol} market structure...")
        print(f"   Data File: {data_file}")
        print(f"   Days Back: {days_back}")
        print()
        
        # Load and resample data
        resampled_data = load_and_resample(data_file, days_back=days_back)
        
        # Analyze trends
        data_1h = resampled_data.get('1H')
        data_15m = resampled_data.get('15M')
        
        if data_1h is None or data_15m is None:
            return {"error": "Missing required timeframe data"}
        
        # Get trends
        trend_1h = self.executor.analyze_1h_trend(data_1h)
        trend_15m = self.executor.analyze_1h_trend(data_15m.tail(100))  # Use 1H method on 15M
        
        # Find A+ entries
        a_plus_events = self.executor.find_a_plus_entries_15m(data_15m, trend_1h)
        
        analysis = {
            "symbol": self.symbol,
            "trend_1h": trend_1h,
            "trend_15m": trend_15m,
            "a_plus_events_count": len(a_plus_events),
            "a_plus_events": [
                {
                    "type": event.event_type.value,
                    "direction": event.direction,
                    "timestamp": str(event.timestamp),
                    "price": event.price,
                    "confidence": event.confidence
                }
                for event in a_plus_events[:10]  # Limit to first 10
            ]
        }
        
        # Display results
        print(f"\nMarket Analysis Results:")
        print(f"   1H Trend: {trend_1h}")
        print(f"   15M Trend: {trend_15m}")
        print(f"   A+ Events Found: {len(a_plus_events)}")
        
        if a_plus_events:
            print(f"\n   Recent A+ Events:")
            for i, event in enumerate(a_plus_events[:5], 1):
                print(f"   {i}. {event.event_type.value} {event.direction} @ {event.timestamp} "
                      f"(conf: {event.confidence:.2f})")
        
        return analysis
    
    def run_strategy(self,
                    data_file: Optional[str] = None,
                    days_back: int = 30) -> Dict[str, Any]:
        """
        Run the full trading strategy (same as backtest but with different interface).
        
        Args:
            data_file: Path to CSV data file (auto-detects if None)
            days_back: Number of days to analyze (default: 30)
            
        Returns:
            Dictionary with strategy results
        """
        return self.run_backtest(data_file, days_back)
    
    def _find_data_file(self) -> Optional[str]:
        """Auto-detect data file based on symbol."""
        data_dir = Path("data")
        if not data_dir.exists():
            return None
        
        # Try different timeframes (M1 is most common)
        timeframes = ["M1", "H1", "M15", "D1"]
        
        for tf in timeframes:
            data_file = data_dir / f"{self.symbol}_{tf}.csv"
            if data_file.exists():
                return str(data_file)
        
        # If symbol-specific file not found, try common symbols
        common_symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"]
        for symbol in common_symbols:
            for tf in timeframes:
                data_file = data_dir / f"{symbol}_{tf}.csv"
                if data_file.exists():
                    self.symbol = symbol  # Update symbol to match found file
                    return str(data_file)
        
        return None
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return {
            "symbol": self.symbol,
            "risk_per_trade": self.risk_per_trade,
            "confidence_threshold": self.confidence_threshold,
            "atr_multiplier": self.atr_multiplier,
            "risk_reward_ratio": self.risk_reward_ratio
        }
    
    def update_config(self, **kwargs):
        """Update configuration parameters."""
        if "symbol" in kwargs:
            self.symbol = kwargs["symbol"].upper()
        if "risk_per_trade" in kwargs:
            self.risk_per_trade = kwargs["risk_per_trade"]
        if "confidence_threshold" in kwargs:
            self.confidence_threshold = kwargs["confidence_threshold"]
        if "atr_multiplier" in kwargs:
            self.atr_multiplier = kwargs["atr_multiplier"]
        if "risk_reward_ratio" in kwargs:
            self.risk_reward_ratio = kwargs["risk_reward_ratio"]
        
        # Reinitialize with new config
        self.executor = MultiTimeframeTradingExecutor(
            symbol=self.symbol,
            risk_per_trade=self.risk_per_trade,
            confidence_threshold=self.confidence_threshold,
            atr_multiplier=self.atr_multiplier,
            risk_reward_ratio=self.risk_reward_ratio
        )
        
        self.backtester = IntegratedBacktester(
            symbol=self.symbol,
            risk_per_trade=self.risk_per_trade,
            confidence_threshold=self.confidence_threshold,
            atr_multiplier=self.atr_multiplier,
            executor=self.executor
        )


def main():
    """Main entry point with command-line interface."""
    parser = argparse.ArgumentParser(
        description="Centralized Trading Bot System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run backtest on XAUUSD
  python trading_bot.py --backtest --symbol XAUUSD --days 60
  
  # Analyze market structure
  python trading_bot.py --analyze --symbol EURUSD
  
  # Custom risk settings
  python trading_bot.py --backtest --symbol GBPUSD --risk 0.02 --confidence 0.7
        """
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--backtest", action="store_true", help="Run backtest")
    mode_group.add_argument("--analyze", action="store_true", help="Analyze market structure")
    mode_group.add_argument("--strategy", action="store_true", help="Run trading strategy")
    
    # Common arguments
    parser.add_argument("--symbol", type=str, default="XAUUSD", help="Trading symbol (default: XAUUSD)")
    parser.add_argument("--days", type=int, default=60, help="Days to analyze (default: 60)")
    parser.add_argument("--risk", type=float, default=0.01, help="Risk per trade (default: 0.01 = 1%%)")
    parser.add_argument("--confidence", type=float, default=0.6, help="Confidence threshold (default: 0.6)")
    parser.add_argument("--atr", type=float, default=1.5, help="ATR multiplier (default: 1.5)")
    parser.add_argument("--rr", type=float, default=1.5, help="Risk-reward ratio (default: 1.5)")
    parser.add_argument("--data", type=str, default=None, help="Path to data file (auto-detects if not provided)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # Initialize bot
    bot = TradingBot(
        symbol=args.symbol,
        risk_per_trade=args.risk,
        confidence_threshold=args.confidence,
        atr_multiplier=args.atr,
        risk_reward_ratio=args.rr
    )
    
    # Execute based on mode
    if args.backtest or args.strategy:
        results = bot.run_backtest(data_file=args.data, days_back=args.days)
    elif args.analyze:
        results = bot.analyze_market(data_file=args.data, days_back=args.days)
    else:
        parser.print_help()
        return
    
    # Exit with appropriate code
    if "error" in results:
        print(f"\n Error: {results['error']}")
        sys.exit(1)
    else:
        print("\n Operation completed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()

