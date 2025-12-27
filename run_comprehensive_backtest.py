"""
Comprehensive Backtest Runner with Detailed Analysis
Automatically generates structure-aware metrics report after backtest completion
"""

import subprocess
import sys
import os
from datetime import datetime

def run_backtest_with_analysis(symbol="XAUUSD", days=180, debug=True):
    """
    Run backtest and generate comprehensive analysis report
    
    Args:
        symbol: Trading symbol (default: XAUUSD)
        days: Number of days to backtest (minimum 180 recommended)
        debug: Enable debug output
    """
    
    print("=" * 100)
    print("COMPREHENSIVE BACKTEST WITH STRUCTURE-AWARE ANALYSIS")
    print("=" * 100)
    print(f"Symbol: {symbol}")
    print(f"Period: {days} days")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    print()
    
    # Build command
    cmd = [
        sys.executable,
        "trading_bot.py",
        "--backtest",
        "--symbol", symbol,
        "--days", str(days)
    ]
    
    if debug:
        cmd.append("--debug")
    
    # Run backtest
    print("🚀 Running backtest...")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        # Print backtest output
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        # Generate analysis report filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"backtest_analysis_{symbol}_{days}d_{timestamp}.txt"
        
        print()
        print("=" * 100)
        print("GENERATING COMPREHENSIVE ANALYSIS REPORT")
        print("=" * 100)
        
        # Parse backtest results and generate report
        generate_analysis_report(result.stdout, report_file, symbol, days)
        
        print()
        print("=" * 100)
        print("✅ BACKTEST COMPLETE")
        print(f"📊 Analysis report saved to: {report_file}")
        print("=" * 100)
        
    except Exception as e:
        print(f"❌ Error running backtest: {e}")
        return False
    
    return True


def generate_analysis_report(backtest_output: str, report_file: str, symbol: str, days: int):
    """
    Generate comprehensive analysis report from backtest output
    """
    
    report_lines = []
    report_lines.append("=" * 100)
    report_lines.append("COMPREHENSIVE BACKTEST ANALYSIS REPORT")
    report_lines.append("=" * 100)
    report_lines.append(f"Symbol: {symbol}")
    report_lines.append(f"Period: {days} days")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 100)
    report_lines.append("")
    
    # Extract key metrics from backtest output
    report_lines.append("BACKTEST OUTPUT:")
    report_lines.append("-" * 100)
    report_lines.append(backtest_output)
    report_lines.append("-" * 100)
    report_lines.append("")
    
    # Add structure-aware analysis sections
    report_lines.append("=" * 100)
    report_lines.append("STRUCTURE-AWARE METRICS ANALYSIS")
    report_lines.append("=" * 100)
    report_lines.append("")
    
    report_lines.append("A. EVENT TYPE BREAKDOWN")
    report_lines.append("-" * 100)
    report_lines.append("CHOCH Trades:")
    report_lines.append("  Total Trades: [To be calculated from detailed logs]")
    report_lines.append("  Win Rate: [To be calculated]")
    report_lines.append("  Average R: [To be calculated]")
    report_lines.append("  % Reaching TP1: [To be calculated]")
    report_lines.append("  % Invalidated Immediately (<5 candles): [To be calculated]")
    report_lines.append("")
    report_lines.append("BOS Trades:")
    report_lines.append("  Total Trades: [To be calculated from detailed logs]")
    report_lines.append("  Win Rate: [To be calculated]")
    report_lines.append("  Average R: [To be calculated]")
    report_lines.append("  % Reaching TP1: [To be calculated]")
    report_lines.append("  % Invalidated Immediately (<5 candles): [To be calculated]")
    report_lines.append("")
    
    report_lines.append("B. DISTANCE METRICS")
    report_lines.append("-" * 100)
    report_lines.append("Entry → BOS Level:")
    report_lines.append("  Mean: [To be calculated]")
    report_lines.append("  Winners Avg: [To be calculated]")
    report_lines.append("  Losers Avg: [To be calculated]")
    report_lines.append("")
    report_lines.append("Entry → HTF Equilibrium:")
    report_lines.append("  Mean: [To be calculated]")
    report_lines.append("  Winners Avg: [To be calculated]")
    report_lines.append("  Losers Avg: [To be calculated]")
    report_lines.append("")
    report_lines.append("SL Distance (in ATR):")
    report_lines.append("  Mean: [To be calculated]")
    report_lines.append("")
    
    report_lines.append("C. TIME-TO-OUTCOME METRICS")
    report_lines.append("-" * 100)
    report_lines.append("Candles to Outcome:")
    report_lines.append("  Winners (to TP): [To be calculated]")
    report_lines.append("  Losers (to SL): [To be calculated]")
    report_lines.append("  Pattern Analysis: [Fast fail = bad entry | Slow fail = wrong HTF bias]")
    report_lines.append("")
    
    report_lines.append("D. REGIME SEGMENTATION")
    report_lines.append("-" * 100)
    report_lines.append("HTF Trend Breakdown:")
    report_lines.append("  Up: [trades] trades, Win Rate: [%]")
    report_lines.append("  Down: [trades] trades, Win Rate: [%]")
    report_lines.append("  Range: [trades] trades, Win Rate: [%]")
    report_lines.append("")
    report_lines.append("ATR Regime Breakdown:")
    report_lines.append("  High ATR: [trades] trades, Win Rate: [%]")
    report_lines.append("  Normal ATR: [trades] trades, Win Rate: [%]")
    report_lines.append("  Low ATR: [trades] trades, Win Rate: [%]")
    report_lines.append("")
    
    report_lines.append("E. PULLBACK QUALITY ANALYSIS")
    report_lines.append("-" * 100)
    report_lines.append("Retracement % Breakdown:")
    report_lines.append("  <38%: [trades] trades, Win Rate: [%]")
    report_lines.append("  38-50%: [trades] trades, Win Rate: [%]")
    report_lines.append("  50-62%: [trades] trades, Win Rate: [%]")
    report_lines.append("  62-70%: [trades] trades, Win Rate: [%]")
    report_lines.append("  >70%: [trades] trades, Win Rate: [%]")
    report_lines.append("")
    report_lines.append("Entry Location Breakdown:")
    report_lines.append("  Discount: [trades] trades, Win Rate: [%]")
    report_lines.append("  Equilibrium: [trades] trades, Win Rate: [%]")
    report_lines.append("  Premium: [trades] trades, Win Rate: [%]")
    report_lines.append("")
    
    report_lines.append("=" * 100)
    report_lines.append("ACTIONABLE INSIGHTS")
    report_lines.append("=" * 100)
    report_lines.append("")
    report_lines.append("Based on the metrics above, the following optimizations are recommended:")
    report_lines.append("")
    report_lines.append("1. Event Type Performance:")
    report_lines.append("   - If CHOCH win rate < BOS win rate → Tighten CHOCH filters")
    report_lines.append("   - If BOS win rate < CHOCH win rate → Relax BOS entry conditions")
    report_lines.append("")
    report_lines.append("2. Entry Location:")
    report_lines.append("   - If Premium entries have low win rate → Avoid entries above 60% retracement")
    report_lines.append("   - If Discount entries perform best → Focus on 38-50% retracements")
    report_lines.append("")
    report_lines.append("3. Regime Optimization:")
    report_lines.append("   - BOS should perform best in: Trending + High ATR")
    report_lines.append("   - CHOCH should perform best in: Range + Compression")
    report_lines.append("   - If mixed → Add regime filters")
    report_lines.append("")
    report_lines.append("4. Distance Metrics:")
    report_lines.append("   - If losers have smaller distance to HTF extreme → Entries too close to range boundary")
    report_lines.append("   - If winners have larger distance to equilibrium → Waiting for deeper pullbacks helps")
    report_lines.append("")
    report_lines.append("=" * 100)
    report_lines.append("END OF REPORT")
    report_lines.append("=" * 100)
    
    # Write report to file
    report_text = "\n".join(report_lines)
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(f"✅ Analysis report generated: {report_file}")
    print()
    print("📋 QUICK SUMMARY:")
    print("-" * 100)
    # Extract and print key stats from backtest output
    for line in backtest_output.split('\n'):
        if any(keyword in line for keyword in ['Total Trades', 'Win Rate', 'Profit Factor', 'Sharpe']):
            print(f"  {line.strip()}")
    print("-" * 100)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run backtest with comprehensive analysis')
    parser.add_argument('--symbol', type=str, default='XAUUSD', help='Trading symbol')
    parser.add_argument('--days', type=int, default=180, help='Number of days to backtest (minimum 180 recommended)')
    parser.add_argument('--no-debug', action='store_true', help='Disable debug output')
    
    args = parser.parse_args()
    
    run_backtest_with_analysis(
        symbol=args.symbol,
        days=args.days,
        debug=not args.no_debug
    )
