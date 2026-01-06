# 🚀 Smart Money Concepts Trading Bot

A sophisticated multi-timeframe trading system implementing Smart Money Concepts (SMC) strategies with advanced filtering and risk management. The system detects Break of Structure (BOS) and Change of Character (CHOCH) patterns using institutional trading principles.

## 🎯 Overview

This trading bot implements a comprehensive SMC-based strategy that:

- **Detects High-Quality Structure Events**: Identifies BOS and CHOCH patterns using market structure analysis
- **Multi-Timeframe Confirmation**: Uses 1H for trend, 15M for entries, and 1M for execution confirmation
- **Advanced Filtering**: Implements BOS follow-through validation and expansion/distribution filters
- **Point-in-Time Backtesting**: Candle-by-candle simulation with zero look-ahead bias
- **Risk Management**: ATR-based stop losses, position sizing, and configurable risk-reward ratios

## 🏗️ Trading Strategy Workflow

### Phase 1: Multi-Timeframe Analysis

**1H Timeframe - Trend Detection**
- Dual window analysis (12h/24h) with swing point detection
- Trend classification: Uptrend, Downtrend, or Sideways
- Strength scoring based on slope-to-volatility ratio

**15M Timeframe - Entry Signal Generation**
- Market structure building using swing highs/lows
- BOS/CHOCH pattern detection with confidence scoring
- Structure quality assessment (width, time, integrity)

### Phase 2: Event Detection & Filtering

**BOS (Break of Structure) Detection**
- Identifies when price breaks previous swing high/low
- Confidence calculation based on:
  - Price break strength
  - Structure quality and width
  - Time since structure formation
  - Intermediate point validation

**CHOCH (Change of Character) Detection**
- Detects trend reversals (uptrend → downtrend or vice versa)
- Higher confidence threshold (0.65 vs 0.5 for BOS)
- Validates true reversals vs structural continuations

**Trend Alignment Filter**
- Compares 1H trend vs 15M trend vs event direction
- Applies probabilistic alignment matrix
- Relaxed rules for CHOCH (reversal signals)
- Stricter rules for BOS (continuation signals)

### Phase 3: BOS Follow-Through Validation

**Displacement Check**
- Validates minimum displacement from broken level
- Threshold: 0.5 ATR minimum
- Rejects weak BOS with insufficient price movement

**Candle Body Quality**
- Checks BOS candle body-to-range ratio
- Threshold: 0.6 (60% body ratio minimum)
- Filters out weak candles with long wicks and small bodies

### Phase 4: Retracement Confirmation

**Pullback to Broken Level**
- Waits for price to retrace to broken structure level
- Tolerance: 1.2 ATR from broken level
- Validates price acceptance at the level

**Reversal Candle Pattern**
- Bullish: Bullish engulfing, hammer, strong green candle
- Bearish: Bearish engulfing, shooting star, strong red candle
- Confirms institutional interest at the level

### Phase 5: Expansion vs Distribution Filter

**Market Expansion Detection**
- Checks if market is expanding after structure event
- Uses 3 measurable signals (ANY 2 must pass):
  1. **Range Expansion**: Recent candles cover 1.3x more range than prior
  2. **Momentum Expansion**: Average body ratio > 0.55
  3. **Speed Expansion**: Displacement > 1.2 ATR
- Rejects trades during distribution/chop phases

### Phase 6: 1M Confirmation

**Asymmetric Confirmation Logic**
- **BOS**: Requires micro BOS (break of recent 1M swing)
- **CHOCH**: Allows momentum OR volume OR micro BOS
- Body size and volume filters for quality confirmation

### Phase 7: Trade Execution

**Position Sizing**
- Risk-based position calculation (default: 1% risk per trade)
- ATR-based stop loss placement (3.0x ATR multiplier)
- Risk-reward ratio: 2:1 (configurable)

**Trade Management**
- Stop loss: Entry ± (ATR × multiplier)
- Take profit: Entry ± (Stop loss distance × RR ratio)
- Real-time monitoring with point-in-time price updates

## 🔑 Key Algorithms & Techniques

### Market Structure Analysis
- **Swing Point Detection**: Uses scipy.signal.find_peaks with prominence factor
- **Structure Classification**: HH (Higher High), HL (Higher Low), LH (Lower High), LL (Lower Low)
- **Pattern Validation**: Time and price width validation to avoid noise

### Confidence Scoring
- **Multi-Factor Analysis**: Combines price break strength, structure quality, time factors
- **Quality Score Integration**: Normalized 0-4 scale integrated into confidence
- **Event-Specific Adjustments**: Different thresholds for BOS vs CHOCH

### Trend Detection
- **Dual Window Selection**: Evaluates multiple lookback periods
- **Swing Pattern Analysis**: Recent swing sequence override
- **Strength Normalization**: 0-1 strength metric for probabilistic gating

### Expansion Detection
- **Range Comparison**: Statistical comparison of recent vs prior candle ranges
- **Momentum Analysis**: Body ratio calculation across multiple candles
- **Speed Measurement**: Displacement relative to ATR

## 🚀 Quick Start

### Installation

```bash
# Create virtual environment
python -m venv trading-bot-env

# Activate virtual environment
# Windows:
trading-bot-env\Scripts\activate
# Linux/Mac:
source trading-bot-env/bin/activate

# Install dependencies
pip install -r requirement/requirements_backtester.txt
```

### Basic Usage

```bash
# Run backtest on XAUUSD (45 days)
python trading_bot.py --backtest --symbol XAUUSD --days 45

# Analyze market structure
python trading_bot.py --analyze --symbol EURUSD --days 30

# Custom risk settings
python trading_bot.py --backtest --symbol XAUUSD --days 60 --risk 0.02 --confidence 0.7
```

### Command Line Options

```
--backtest          Run backtest mode
--analyze           Analyze market structure only
--symbol SYMBOL     Trading symbol (default: XAUUSD)
--days N            Days to analyze (default: 60)
--risk FLOAT        Risk per trade (default: 0.01 = 1%)
--confidence FLOAT  Confidence threshold (default: 0.6)
--atr FLOAT         ATR multiplier for stops (default: 2.5)
--rr FLOAT          Risk-reward ratio (default: 2.0)
--debug             Enable debug logging
```

## ⚙️ Configuration

### Key Parameters

**Risk Management**
- `risk_per_trade`: 0.01 (1% risk per trade)
- `atr_multiplier`: 3.0 (ATR multiplier for stop loss)
- `risk_reward_ratio`: 2.0 (2:1 reward to risk)

**Filter Thresholds**
- `confidence_threshold`: 0.7 (Minimum confidence for A+ entries)
- `MIN_BOS_DISPLACEMENT_ATR`: 0.5 (Minimum BOS displacement)
- `MIN_BOS_BODY_RATIO`: 0.6 (Minimum BOS candle body ratio)
- `CHOCH_REVERSAL_ALLOW`: 0.65 (CHOCH confidence threshold)

**Expansion Filter**
- Range expansion: 1.3x prior range
- Momentum expansion: 0.55 body ratio
- Speed expansion: 1.2 ATR displacement

## 📊 Performance Metrics

The system tracks and reports:

**Core Metrics**
- Total signals generated
- Trades executed
- Win rate
- Average R-multiple
- Total P&L

**Filter Effectiveness**
- BOS rejections (displacement, body ratio)
- Expansion filter rejections
- Funnel metrics (events → aligned → retracement → confirmed → executed)

**Trade Quality**
- Winning vs losing trades
- Average trade duration
- Risk-adjusted returns

## 🔧 Technical Architecture

### Core Components

**MultiTimeframeTradingExecutor**
- Main strategy execution engine
- Implements all filtering and confirmation logic
- Manages trade lifecycle

**MarketStructureAnalyzer**
- BOS/CHOCH pattern detection
- Confidence and quality scoring
- Structure validation

**RiskManager**
- ATR calculation
- Position sizing
- Stop loss and take profit computation

**IntegratedBacktester**
- Point-in-time backtesting wrapper
- Results aggregation and reporting
- Performance analytics

### Design Principles

1. **No Look-Ahead Bias**: All analysis uses only historical data up to current candle
2. **Multi-Timeframe Confirmation**: Multiple timeframes must align for entry
3. **Quality Over Quantity**: Strict filtering for high-probability setups
4. **Risk-First Approach**: Position sizing based on risk, not account size
5. **Institutional Logic**: Follows Smart Money Concepts principles

## 📈 Strategy Features

### Advanced Filtering System

1. **BOS Follow-Through Validation**
   - Ensures BOS has meaningful displacement
   - Validates candle body quality
   - Prevents fake/terminal BOS trades

2. **Expansion vs Distribution Filter**
   - Distinguishes expanding markets from choppy/distribution phases
   - Multi-signal validation (range, momentum, speed)
   - Prevents trades during compression

3. **Trend Alignment Matrix**
   - Probabilistic alignment scoring
   - Relaxed rules for reversals (CHOCH)
   - Stricter rules for continuations (BOS)

4. **Retracement Confirmation**
   - Validates price acceptance at broken level
   - Reversal candle pattern recognition
   - Institutional entry logic

### Risk Management

- **ATR-Based Stops**: Dynamic stop placement based on volatility
- **Fixed Risk Sizing**: Consistent risk percentage per trade
- **Risk-Reward Optimization**: Configurable RR ratios
- **Drawdown Protection**: Maximum loss limits

## 🎯 Expected Results

After implementing all filters, you should see:

- **Trades**: Reduced count (30-50% fewer, but higher quality)
- **Win Rate**: Significantly improved
- **Avg R**: Higher R-multiples per trade
- **Fast Losses**: Eliminated (<5 candle losses)
- **CHOCH Spam**: Drastically reduced

## ⚠️ Important Notes

- **Past performance does not guarantee future results**
- **Always use proper risk management**
- **Never risk more than you can afford to lose**
- **This is for educational and research purposes**

## 📚 Additional Documentation

For detailed workflow documentation, see:
- `WORKFLOW_README.md` - Complete workflow and architecture details
- `QUICK_START.md` - Quick start guide with examples

## 🔮 Future Enhancements

- Entry location quality optimization
- Advanced position management (trailing stops, partial profits)
- Multi-asset portfolio backtesting
- Machine learning integration for pattern recognition

---

**Happy Trading!** 🚀

Remember: The goal is consistent, high-quality trades, not high trade frequency.
