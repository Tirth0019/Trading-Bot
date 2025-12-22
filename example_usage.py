#!/usr/bin/env python3
"""
📚 EXAMPLE USAGE - Centralized Trading Bot

This file demonstrates how to use the centralized trading bot system.
"""

from trading_bot import TradingBot


def example_1_simple_backtest():
    """Example 1: Simple backtest"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Simple Backtest")
    print("="*70)
    
    bot = TradingBot(symbol="XAUUSD")
    results = bot.run_backtest(days_back=60)
    
    print(f"\nResults: {results.get('total_pnl', 0):.2f} P&L")


def example_2_custom_config():
    """Example 2: Custom configuration"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Custom Configuration")
    print("="*70)
    
    bot = TradingBot(
        symbol="EURUSD",
        risk_per_trade=0.02,      # 2% risk
        confidence_threshold=0.7,  # Higher confidence
        atr_multiplier=3.0,       # Wider stops
        risk_reward_ratio=2.5     # Better R:R
    )
    
    results = bot.run_backtest(days_back=90)
    print(f"\nResults: {results.get('total_pnl', 0):.2f} P&L")


def example_3_market_analysis():
    """Example 3: Market analysis without trading"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Market Analysis")
    print("="*70)
    
    bot = TradingBot(symbol="GBPUSD")
    analysis = bot.analyze_market(days_back=30)
    
    print(f"\n1H Trend: {analysis.get('trend_1h')}")
    print(f"A+ Events: {analysis.get('a_plus_events_count', 0)}")


def example_4_multiple_symbols():
    """Example 4: Test multiple symbols"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Multiple Symbols")
    print("="*70)
    
    symbols = ["XAUUSD", "EURUSD", "GBPUSD"]
    
    for symbol in symbols:
        print(f"\n📊 Testing {symbol}...")
        bot = TradingBot(symbol=symbol)
        results = bot.run_backtest(days_back=30)
        
        pnl = results.get('total_pnl', 0)
        trades = results.get('trades_closed', 0)
        print(f"   P&L: ${pnl:.2f}, Trades: {trades}")


def example_5_config_update():
    """Example 5: Update configuration dynamically"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Dynamic Configuration")
    print("="*70)
    
    bot = TradingBot(symbol="XAUUSD")
    
    # Get current config
    config = bot.get_config()
    print(f"\nCurrent Config: {config}")
    
    # Update config
    bot.update_config(risk_per_trade=0.02, confidence_threshold=0.7)
    
    # Get updated config
    config = bot.get_config()
    print(f"Updated Config: {config}")


if __name__ == "__main__":
    print("🚀 CENTRALIZED TRADING BOT - EXAMPLES")
    print("="*70)
    
    # Run examples
    try:
        example_1_simple_backtest()
    except Exception as e:
        print(f"Example 1 failed: {e}")
    
    try:
        example_3_market_analysis()
    except Exception as e:
        print(f"Example 3 failed: {e}")
    
    try:
        example_5_config_update()
    except Exception as e:
        print(f"Example 5 failed: {e}")
    
    print("\n" + "="*70)
    print("✅ Examples completed!")
    print("="*70)
    print("\n💡 Tip: Run 'python trading_bot.py --help' for command-line usage")

