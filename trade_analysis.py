"""
Comprehensive Trade Analysis Module
Generates detailed structure-aware metrics for trading system optimization
"""

import pandas as pd
import json
from typing import List, Dict
from datetime import datetime
from collections import defaultdict


class TradeAnalyzer:
    """Analyzes trade logs and generates comprehensive metrics"""
    
    def __init__(self, trade_logs: List[Dict]):
        self.trade_logs = trade_logs
        self.df = pd.DataFrame(trade_logs) if trade_logs else pd.DataFrame()
    
    def generate_comprehensive_report(self, output_file: str = None):
        """Generate complete analysis report with all requested metrics"""
        
        if self.df.empty:
            return "No trades to analyze"
        
        report = []
        report.append("=" * 100)
        report.append("COMPREHENSIVE TRADE ANALYSIS REPORT")
        report.append("=" * 100)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Trades Analyzed: {len(self.df)}")
        report.append("")
        
        # 1. EVENT TYPE BREAKDOWN
        report.append(self._event_type_breakdown())
        
        # 2. DISTANCE METRICS ANALYSIS
        report.append(self._distance_metrics_analysis())
        
        # 3. TIME-TO-OUTCOME METRICS
        report.append(self._time_to_outcome_analysis())
        
        # 4. REGIME SEGMENTATION
        report.append(self._regime_segmentation_analysis())
        
        # 5. PULLBACK QUALITY ANALYSIS
        report.append(self._pullback_quality_analysis())
        
        # 6. DETAILED TRADE LOG TABLE
        report.append(self._detailed_trade_table())
        
        report_text = "\n".join(report)
        
        # Save to file if specified
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            print(f"\n📊 Comprehensive analysis saved to: {output_file}")
        
        return report_text
    
    def _event_type_breakdown(self) -> str:
        """A. Breakdown by Event Type (MANDATORY)"""
        lines = []
        lines.append("=" * 100)
        lines.append("A. EVENT TYPE BREAKDOWN")
        lines.append("=" * 100)
        
        for event_type in ['CHOCH', 'BOS']:
            df_event = self.df[self.df['event_type'] == event_type]
            
            if len(df_event) == 0:
                lines.append(f"\n{event_type} Trades: No trades")
                continue
            
            lines.append(f"\n{event_type} Trades:")
            lines.append(f"  Total Trades: {len(df_event)}")
            
            if 'outcome' in df_event.columns:
                wins = len(df_event[df_event['outcome'] == 'WIN'])
                losses = len(df_event[df_event['outcome'] == 'LOSS'])
                win_rate = (wins / len(df_event) * 100) if len(df_event) > 0 else 0
                lines.append(f"  Win Rate: {win_rate:.1f}% ({wins}W / {losses}L)")
            
            if 'rr_actual' in df_event.columns:
                avg_r = df_event['rr_actual'].mean()
                lines.append(f"  Average R: {avg_r:.2f}")
            
            if 'reached_tp1' in df_event.columns:
                tp1_pct = (df_event['reached_tp1'].sum() / len(df_event) * 100)
                lines.append(f"  % Reaching TP1: {tp1_pct:.1f}%")
            
            if 'bars_to_outcome' in df_event.columns:
                quick_invalidation = len(df_event[df_event['bars_to_outcome'] < 5])
                quick_inv_pct = (quick_invalidation / len(df_event) * 100)
                lines.append(f"  % Invalidated Immediately (<5 candles): {quick_inv_pct:.1f}%")
        
        lines.append("")
        return "\n".join(lines)
    
    def _distance_metrics_analysis(self) -> str:
        """B. Distance Metrics (CRITICAL)"""
        lines = []
        lines.append("=" * 100)
        lines.append("B. DISTANCE METRICS ANALYSIS")
        lines.append("=" * 100)
        
        metrics = [
            ('distance_to_bos_level', 'Entry → BOS Level'),
            ('distance_to_htf_eq', 'Entry → HTF Equilibrium'),
            ('distance_to_htf_extreme', 'Entry → HTF Range Extreme'),
            ('sl_distance_atr', 'SL Distance (in ATR)')
        ]
        
        for col, label in metrics:
            if col in self.df.columns:
                lines.append(f"\n{label}:")
                lines.append(f"  Mean: {self.df[col].mean():.2f}")
                lines.append(f"  Median: {self.df[col].median():.2f}")
                lines.append(f"  Min: {self.df[col].min():.2f}")
                lines.append(f"  Max: {self.df[col].max():.2f}")
                
                # Win/Loss comparison
                if 'outcome' in self.df.columns:
                    wins = self.df[self.df['outcome'] == 'WIN'][col].mean()
                    losses = self.df[self.df['outcome'] == 'LOSS'][col].mean()
                    lines.append(f"  Winners Avg: {wins:.2f}")
                    lines.append(f"  Losers Avg: {losses:.2f}")
        
        lines.append("")
        return "\n".join(lines)
    
    def _time_to_outcome_analysis(self) -> str:
        """C. Time-to-Outcome Metrics"""
        lines = []
        lines.append("=" * 100)
        lines.append("C. TIME-TO-OUTCOME METRICS")
        lines.append("=" * 100)
        
        if 'bars_to_outcome' in self.df.columns:
            lines.append(f"\nCandles to Outcome:")
            lines.append(f"  Mean: {self.df['bars_to_outcome'].mean():.1f}")
            lines.append(f"  Median: {self.df['bars_to_outcome'].median():.1f}")
            
            if 'outcome' in self.df.columns:
                tp_bars = self.df[self.df['outcome'] == 'WIN']['bars_to_outcome'].mean()
                sl_bars = self.df[self.df['outcome'] == 'LOSS']['bars_to_outcome'].mean()
                lines.append(f"  Winners (Candles to TP): {tp_bars:.1f}")
                lines.append(f"  Losers (Candles to SL): {sl_bars:.1f}")
                
                # Pattern identification
                if sl_bars < 10:
                    lines.append(f"  ⚠️  Pattern: Losing trades fail FAST → Bad entry logic")
                elif sl_bars > 30:
                    lines.append(f"  ⚠️  Pattern: Losing trades fail SLOW → HTF bias wrong")
        
        if 'bars_to_first_adverse' in self.df.columns:
            lines.append(f"\nCandles to First Adverse Move:")
            lines.append(f"  Mean: {self.df['bars_to_first_adverse'].mean():.1f}")
        
        lines.append("")
        return "\n".join(lines)
    
    def _regime_segmentation_analysis(self) -> str:
        """D. Regime Segmentation"""
        lines = []
        lines.append("=" * 100)
        lines.append("D. REGIME SEGMENTATION")
        lines.append("=" * 100)
        
        # HTF Trend breakdown
        if 'htf_trend' in self.df.columns:
            lines.append("\nHTF Trend Breakdown:")
            for trend in ['Up', 'Down', 'Range']:
                df_trend = self.df[self.df['htf_trend'] == trend]
                if len(df_trend) > 0:
                    win_rate = 0
                    if 'outcome' in df_trend.columns:
                        wins = len(df_trend[df_trend['outcome'] == 'WIN'])
                        win_rate = (wins / len(df_trend) * 100)
                    lines.append(f"  {trend}: {len(df_trend)} trades, Win Rate: {win_rate:.1f}%")
        
        # ATR Regime breakdown
        if 'atr_regime' in self.df.columns:
            lines.append("\nATR Regime Breakdown:")
            for regime in ['High', 'Normal', 'Low']:
                df_regime = self.df[self.df['atr_regime'] == regime]
                if len(df_regime) > 0:
                    win_rate = 0
                    if 'outcome' in df_regime.columns:
                        wins = len(df_regime[df_regime['outcome'] == 'WIN'])
                        win_rate = (wins / len(df_regime) * 100)
                    lines.append(f"  {regime} ATR: {len(df_regime)} trades, Win Rate: {win_rate:.1f}%")
        
        # Event Type x Regime Matrix
        if 'event_type' in self.df.columns and 'htf_trend' in self.df.columns:
            lines.append("\nEvent Type × HTF Trend Matrix:")
            for event in ['CHOCH', 'BOS']:
                for trend in ['Up', 'Down', 'Range']:
                    df_combo = self.df[(self.df['event_type'] == event) & (self.df['htf_trend'] == trend)]
                    if len(df_combo) > 0:
                        win_rate = 0
                        if 'outcome' in df_combo.columns:
                            wins = len(df_combo[df_combo['outcome'] == 'WIN'])
                            win_rate = (wins / len(df_combo) * 100)
                        lines.append(f"  {event} in {trend}: {len(df_combo)} trades, WR: {win_rate:.1f}%")
        
        lines.append("")
        return "\n".join(lines)
    
    def _pullback_quality_analysis(self) -> str:
        """E. Pullback Quality"""
        lines = []
        lines.append("=" * 100)
        lines.append("E. PULLBACK QUALITY ANALYSIS")
        lines.append("=" * 100)
        
        # Retracement percentage breakdown
        if 'retrace_pct' in self.df.columns:
            lines.append("\nRetracement % Breakdown:")
            bins = [(0, 38), (38, 50), (50, 62), (62, 70), (70, 100)]
            bin_labels = ['<38%', '38-50%', '50-62%', '62-70%', '>70%']
            
            for (low, high), label in zip(bins, bin_labels):
                df_bin = self.df[(self.df['retrace_pct'] >= low) & (self.df['retrace_pct'] < high)]
                if len(df_bin) > 0:
                    win_rate = 0
                    if 'outcome' in df_bin.columns:
                        wins = len(df_bin[df_bin['outcome'] == 'WIN'])
                        win_rate = (wins / len(df_bin) * 100)
                    lines.append(f"  {label}: {len(df_bin)} trades, Win Rate: {win_rate:.1f}%")
        
        # Entry location breakdown
        if 'entry_location' in self.df.columns:
            lines.append("\nEntry Location Breakdown:")
            for location in ['Discount', 'Equilibrium', 'Premium']:
                df_loc = self.df[self.df['entry_location'] == location]
                if len(df_loc) > 0:
                    win_rate = 0
                    if 'outcome' in df_loc.columns:
                        wins = len(df_loc[df_loc['outcome'] == 'WIN'])
                        win_rate = (wins / len(df_loc) * 100)
                    lines.append(f"  {location}: {len(df_loc)} trades, Win Rate: {win_rate:.1f}%")
                    
                    # Warning for BOS above 50%
                    if location == 'Premium':
                        bos_premium = df_loc[df_loc['event_type'] == 'BOS']
                        if len(bos_premium) > 0:
                            lines.append(f"    ⚠️  BOS at Premium: {len(bos_premium)} trades (mathematically bad)")
        
        lines.append("")
        return "\n".join(lines)
    
    def _detailed_trade_table(self) -> str:
        """Detailed trade-by-trade table"""
        lines = []
        lines.append("=" * 100)
        lines.append("F. DETAILED TRADE LOG")
        lines.append("=" * 100)
        lines.append("")
        
        # Select key columns for display
        display_cols = [
            'timestamp', 'event_type', 'direction', 'entry_price', 'outcome',
            'rr_actual', 'htf_trend', 'atr_regime', 'entry_location', 'bars_to_outcome'
        ]
        
        available_cols = [col for col in display_cols if col in self.df.columns]
        
        if available_cols:
            lines.append(self.df[available_cols].to_string(index=False))
        
        lines.append("")
        lines.append("=" * 100)
        lines.append("END OF REPORT")
        lines.append("=" * 100)
        
        return "\n".join(lines)
    
    def export_to_csv(self, filename: str):
        """Export detailed trade logs to CSV"""
        if not self.df.empty:
            self.df.to_csv(filename, index=False)
            print(f"📁 Detailed trade log exported to: {filename}")
