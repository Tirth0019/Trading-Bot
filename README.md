# 🚀 BOS/CHOCH Trading Bot Backtester

A comprehensive backtesting system for Smart Money Concepts (SMC) trading strategies, specifically designed for Break of Structure (BOS) and Change of Character (CHOCH) patterns. This system generates detailed P/L ratio charts, measures trading accuracy, and provides comprehensive performance analytics.

## 📋 Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Core Features](#core-features)
- [File Structure](#file-structure)
- [Installation & Setup](#installation--setup)
- [Quick Start Guide](#quick-start-guide)
- [Configuration Options](#configuration-options)
- [Output & Reports](#output--reports)
- [Performance Metrics](#performance-metrics)
- [Trading Strategy Details](#trading-strategy-details)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## 🎯 Overview

The BOS/CHOCH Trading Bot Backtester is a sophisticated system that:

- **Identifies A+ Entry Signals**: Automatically detects high-confidence BOS and CHOCH patterns using advanced market structure analysis
- **Simulates Real Trading**: Executes trades with realistic risk management, position sizing, and exit strategies
- **Generates Comprehensive Reports**: Creates interactive HTML charts showing P/L ratios, accuracy metrics, and performance analytics
- **Provides Risk Management**: Implements ATR-based stop-losses, position sizing, and drawdown protection
- **Supports Multiple Strategies**: Offers conservative, aggressive, and balanced trading presets

## 🏗️ System Architecture

The system is built with a modular architecture consisting of:

- **Core Analysis Engine**: Market structure detection and BOS/CHOCH pattern recognition
- **Backtesting Engine**: Trade simulation with realistic market conditions
- **Visualization System**: Interactive Plotly-based charts and dashboards
- **Configuration Management**: Centralized parameter control with strategy presets
- **Data Processing**: Efficient handling of multi-timeframe market data

## ⭐ Core Features

### 🎯 A+ Entry Detection
- **Confidence Scoring**: Multi-factor analysis for entry quality assessment
- **Pattern Recognition**: Automatic BOS and CHOCH pattern identification
- **Trend Alignment**: Ensures entries align with overall market direction
- **Filtering System**: Configurable thresholds for signal quality

### 💼 Risk Management
- **ATR-Based Stop Losses**: Dynamic stop-loss placement using Average True Range
- **Position Sizing**: Risk-based position calculation (default: 2% risk per trade)
- **Reward/Risk Ratios**: Configurable profit targets (default: 2:1)
- **Drawdown Protection**: Maximum loss limits and correlation controls

### 📊 Performance Analytics
- **Win Rate Analysis**: Detailed breakdown of winning vs. losing trades
- **Profit Factor**: Ratio of gross profits to gross losses
- **Sharpe Ratio**: Risk-adjusted return measurement
- **Maximum Drawdown**: Peak-to-trough capital decline analysis
- **Monthly Returns**: Performance breakdown by time periods

### 📈 Visualization & Reporting
- **Interactive Charts**: Plotly-based HTML visualizations
- **Comprehensive Dashboard**: All metrics in a single view
- **P/L Analysis**: Cumulative returns and trade-by-trade performance
- **Entry Type Comparison**: BOS vs CHOCH performance analysis
- **Risk Metrics**: Drawdown curves and equity analysis

## 📁 File Structure

```
Trading Bot/
├── 📊 Core_Analysis_Files/           # Core analysis and utility modules
│   ├── core/                         # Market structure and pattern detection
│   │   ├── smart_money_concepts.py   # BOS/CHOCH pattern detection
│   │   ├── structure_builder.py      # Market structure analysis
│   │   ├── data_loader.py            # Data loading and resampling
│   │   ├── pattern_recognition.py    # Pattern recognition algorithms
│   │   ├── trend_detector.py         # Trend detection and analysis
│   │   ├── pivot_detector.py         # Pivot point identification
│   │   ├── pattern_clustering.py     # Pattern clustering algorithms
│   │   └── candlestick_patterns.py   # Candlestick pattern detection
│   └── utils/                        # Visualization and utility functions
│       ├── level_plotter.py          # Support/resistance visualization
│       ├── pattern_plotter.py        # Pattern charting
│       ├── candlestick_plotter.py    # Price action charts
│       ├── structure_trend_plotter.py # Trend analysis charts
│       ├── trend_plotter.py          # Trend visualization
│
├── 🧪 Testing_Examples/              # Testing and example files
│   ├── test_backtester.py            # Backtester functionality tests
│   ├── test_bos_choch_plot.py       # BOS/CHOCH plotting tests
│   ├── test_pattern_recognition.py   # Pattern recognition tests
│   ├── test_candlestick_patterns.py  # Candlestick pattern tests
│   ├── test_improved_patterns.py    # Improved pattern tests
│   ├── test_bos_choch_plot_light.py # Light theme plotting tests
│   ├── test_bos_choch_plot_light_simple.py # Simple light theme tests
│   ├── simple_structure_test.py      # Structure analysis tests
│   ├── detailed_bos_choch_analysis.py # Detailed BOS/CHOCH analysis
│   ├── verify_bos_choch.py          # BOS/CHOCH verification
│   ├── pattern_movements.py         # Pattern movement analysis
│   └── tests/                        # Additional test modules
│
├── ⚙️ Configuration_Main_System/     # Main system and configuration
│   ├── backtester.py                 # Main backtesting engine
│   ├── backtester_config.py          # Configuration management
│   ├── requirements_backtester.txt   # Python dependencies for backtester
│   └── requirements_patterns.txt     # Python dependencies for patterns
│
├── 📈 Generated_Reports/             # All generated charts and reports
│   ├── generated_backtest_plots/     # Backtester HTML charts
│   ├── generated_plots/              # Pattern analysis charts
│   ├── generated_light_theme_plots/  # Light theme charts
│   └── generated_improved_plots/     # Improved analysis charts
│
├── 📚 Documentation/                  # Comprehensive documentation
│   ├── README.md                     # Main system documentation
│   ├── BACKTESTER_README.md          # Detailed backtester guide
│   ├── BOS_CHOCH_VERIFICATION_REPORT.md # BOS/CHOCH verification report
│   ├── IMPROVED_BOS_CHOCH_ANALYSIS.md # Improved analysis documentation
│   ├── PATTERN_RECOGNITION_IMPROVEMENTS.md # Pattern improvements guide
│   ├── THEME_COMPARISON_SUMMARY.md   # Theme comparison documentation
│   └── candlestick_patterns_guide.md # Candlestick patterns guide
│
├── 📊 Data/                          # Market data files
│   ├── XAUUSD_*.csv                 # Gold data (M1, M5, M15, M30, H1, H4, D1)
│   ├── BTCUSD_*.csv                 # Bitcoin data (M1, M5, M15, M30, H1, H4, D1)
│   ├── EURUSD_*.csv                 # Euro data (M1, M5, M15, M30, H1, H4, D1)
│   ├── GBPUSD_*.csv                 # Pound data (M1, M5, M15, M30, H1, H4, D1)
│   └── USDJPY_*.csv                 # Yen data (M1, M5, M15, M30, H1, H4, D1)
│
├── 🗂️ Original_Files/                # Original file locations (preserved)
│   ├── core/                         # Original core directory
│   ├── utils/                        # Original utils directory
│   ├── docs/                         # Original docs directory
│   ├── tests/                        # Original tests directory
│   ├── generated_*/                  # Original generated directories
│   └── *.py                          # Original Python files
│
└── 📄 Project Files                  # Project configuration
    ├── .gitignore                    # Git ignore rules
    ├── README.md                     # This comprehensive guide
    └── trading-bot-env/              # Python virtual environment
```

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8+ 
- Windows 10/11 (tested on Windows 10.0.26100)
- 4GB+ RAM recommended
- Internet connection for data loading

### Installation Steps

1. **Navigate to the Project Directory**
   ```bash
   cd "D:\Code\Trading Bot"
   ```

2. **Install Dependencies**
   ```bash
   pip install -r "Configuration_Main_System\requirements_backtester.txt"
   pip install -r "Configuration_Main_System\requirements_patterns.txt"
   ```

3. **Verify Installation**
   ```bash
   python "Testing_Examples\test_backtester.py"
   ```

### Required Dependencies
```
pandas>=1.5.0          # Data manipulation and analysis
numpy>=1.21.0          # Numerical computing
plotly>=5.0.0          # Interactive charting
scipy>=1.9.0           # Scientific computing
scikit-learn>=1.1.0    # Machine learning utilities
matplotlib>=3.5.0      # Basic plotting
seaborn>=0.11.0        # Statistical visualization
```

## 🎯 Quick Start Guide

### 🚀 **CENTRALIZED SYSTEM** (Recommended)

The trading bot now has a **single entry point** for all functionality:

```bash
# Run backtest
python trading_bot.py --backtest --symbol XAUUSD

# Analyze market
python trading_bot.py --analyze --symbol EURUSD

# See all options
python trading_bot.py --help
```

**See `QUICK_START.md` for detailed usage guide.**

### 1. Basic Backtest Run (Legacy)
```bash
python core/backtester.py
```

This will:
- Load 60 days of XAUUSD H1 data
- Detect A+ entries (confidence ≥ 70%)
- Execute simulated trades with risk management
- Generate comprehensive HTML reports
- Open the main dashboard automatically

### 2. Custom Configuration
```python
from Configuration_Main_System.backtester_config import get_config

# Load aggressive strategy
config = get_config("aggressive")

# Modify specific parameters
config['trading']['risk_per_trade'] = 0.05  # 5% risk per trade
config['trading']['stop_loss_atr_multiplier'] = 3.0  # Wider stops
```

### 3. Data Analysis Only
```python
from Testing_Examples.test_bos_choch_plot import main
main()  # Run pattern detection without backtesting
```

### 4. Pattern Recognition Testing
```python
python "Testing_Examples\test_pattern_recognition.py"
```

### 5. Candlestick Pattern Analysis
```python
python "Testing_Examples\test_candlestick_patterns.py"
```

## ⚙️ Configuration Options

### Trading Parameters (`Configuration_Main_System/backtester_config.py`)

#### Strategy Presets
- **Conservative**: 1% risk, 1.5:1 reward/risk, 80% confidence threshold
- **Balanced**: 2% risk, 2:1 reward/risk, 70% confidence threshold  
- **Aggressive**: 5% risk, 3:1 reward/risk, 60% confidence threshold

#### Risk Management
```python
TRADING_CONFIG = {
    "initial_capital": 10000,        # Starting capital in USD
    "risk_per_trade": 0.02,         # 2% risk per trade
    "reward_risk_ratio": 2.0,       # 2:1 reward to risk ratio
    "max_trade_duration": 48,       # Maximum trade duration in hours
    "confidence_threshold": 0.7,    # Minimum confidence for A+ entries
    "stop_loss_atr_multiplier": 2.0, # ATR multiplier for stop loss
}
```

#### Data Configuration
```python
DATA_CONFIG = {
    "symbol": "XAUUSD_H1.csv",      # Symbol to backtest
    "days_back": 60,                # Number of days of historical data
    "timeframe": "1H",              # Timeframe for analysis
}
```

## 📊 Output & Reports

### Generated Files
The system creates reports in the `Generated_Reports/` directory containing:

1. **`generated_backtest_plots/`** - Main backtester dashboard and charts
2. **`generated_plots/`** - Pattern analysis and BOS/CHOCH charts
3. **`generated_light_theme_plots/`** - Light theme versions of charts
4. **`generated_improved_plots/`** - Enhanced analysis charts

### Dashboard Sections
- **Equity Curve**: Account balance over time
- **Drawdown Analysis**: Peak-to-trough capital decline
- **Trade Distribution**: P&L histogram and statistics
- **Monthly Returns**: Performance by month (heatmap)
- **Entry Type Performance**: BOS vs CHOCH success rates
- **Performance Summary**: Overall win rate gauge

## 📈 Performance Metrics

### Key Performance Indicators (KPIs)

#### Profitability Metrics
- **Total P&L**: Absolute dollar gain/loss
- **Total Return**: Percentage return on initial capital
- **Profit Factor**: Ratio of gross profits to gross losses
- **Average Win/Loss**: Mean performance of winning/losing trades

#### Risk Metrics
- **Maximum Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted return measure
- **Win Rate**: Percentage of profitable trades
- **Average Trade Duration**: Mean time in trades

## 🎯 Trading Strategy Details

### A+ Entry Criteria

#### Confidence Thresholds
- **Minimum Confidence**: 70% (configurable)
- **Pattern Quality**: Based on multiple technical factors
- **Trend Alignment**: Must align with overall market direction
- **Volume Confirmation**: Optional volume-based filtering

#### BOS (Break of Structure) Entries
- **Bullish BOS**: Higher High (HH) breaking previous resistance
- **Bearish BOS**: Lower Low (LL) breaking previous support
- **Confidence Factors**: 
  - Strength of break
  - Volume confirmation
  - Previous structure quality
  - Market context alignment

#### CHOCH (Change of Character) Entries
- **Bullish CHOCH**: Break above downtrend resistance
- **Bearish CHOCH**: Break below uptrend support
- **Confidence Factors**:
  - Trend strength before change
  - Break magnitude
  - Support/resistance quality
  - Market momentum shift

## 🔧 API Reference

### Main Classes

#### `BOSCHOCHBacktester`
Main backtesting engine class located in `Configuration_Main_System/backtester.py`.

```python
class BOSCHOCHBacktester:
    def __init__(self, 
                 initial_capital: float = 10000,
                 risk_per_trade: float = 0.02,
                 reward_risk_ratio: float = 2.0,
                 max_trade_duration: int = 48,
                 confidence_threshold: float = 0.7,
                 stop_loss_atr_multiplier: float = 2.0):
```

**Key Methods:**
- `run_backtest(data, events)`: Execute complete backtest
- `calculate_statistics()`: Generate performance metrics
- `execute_trade(event, data, index)`: Execute individual trade
- `check_exit_conditions(data, index)`: Monitor exit conditions

#### `MarketStructureAnalyzer`
Detects BOS and CHOCH patterns located in `Core_Analysis_Files/core/smart_money_concepts.py`.

```python
class MarketStructureAnalyzer:
    def __init__(self, confidence_threshold: float = 0.7):
```

**Key Methods:**
- `get_market_events(structure)`: Detect market events
- `_get_trend_state(structure, index)`: Analyze trend context
- `_calculate_confidence(event, structure)`: Score event confidence

## 🚨 Troubleshooting

### Common Issues & Solutions

#### 1. Import Errors
**Problem**: Module not found errors
**Solution**: Ensure all dependencies are installed
```bash
pip install -r "Configuration_Main_System\requirements_backtester.txt"
```

#### 2. Data Loading Issues
**Problem**: No data loaded for timeframe
**Solution**: Check data file exists and format
```bash
# Verify data file exists
dir "Data\XAUUSD_H1.csv"

# Check file format (should have OHLCV columns)
type "Data\XAUUSD_H1.csv" | findstr "Open,High,Low,Close,Volume"
```

#### 3. Chart Generation Errors
**Problem**: HTML files not created
**Solution**: Check write permissions and disk space
```bash
# Check directory permissions
dir "Generated_Reports"

# Verify disk space
dir
```

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

### Code Style
- Follow PEP 8 Python style guidelines
- Use type hints for all function parameters
- Add docstrings for all classes and methods
- Include error handling for edge cases

### Testing
Run the test suite before submitting changes:
```bash
python "Testing_Examples\test_backtester.py"
python "Testing_Examples\test_pattern_recognition.py"
python "Testing_Examples\test_candlestick_patterns.py"
```

## 📞 Support & Contact

### Getting Help
1. **Check Documentation**: Review this README and files in `Documentation/`
2. **Run Tests**: Verify system functionality with test files
3. **Check Logs**: Review any generated log files for error details
4. **Review Configuration**: Ensure parameters are set correctly

### Feature Requests
- Submit detailed feature requests with use cases
- Include example data or scenarios
- Specify expected behavior and outputs

### Bug Reports
When reporting bugs, include:
- Python version and OS details
- Complete error messages and stack traces
- Steps to reproduce the issue
- Sample data if applicable

## 📄 License

This project is provided as-is for educational and research purposes. Use at your own risk in live trading environments.

## 🔮 Future Enhancements

### Planned Features
- **Multi-Asset Support**: Backtest multiple symbols simultaneously
- **Portfolio Optimization**: Risk parity and correlation analysis
- **Machine Learning Integration**: AI-powered entry/exit signals
- **Real-Time Trading**: Live market connection and execution
- **Advanced Analytics**: Monte Carlo simulations and stress testing

### Performance Improvements
- **Parallel Processing**: Multi-threaded backtesting for large datasets
- **Memory Optimization**: Efficient data handling for long timeframes
- **Caching System**: Store and reuse calculation results
- **Cloud Integration**: Distributed backtesting on cloud platforms

---

## 📋 **File Organization Summary**

This project has been reorganized according to the README structure:

- **📊 Core_Analysis_Files/**: All core analysis modules and utilities
- **🧪 Testing_Examples/**: All testing files and examples
- **⚙️ Configuration_Main_System/**: Main system files and configuration
- **📈 Generated_Reports/**: All generated charts and reports
- **📚 Documentation/**: Comprehensive documentation
- **📊 Data/**: Market data files
- **🗂️ Original_Files/**: Original file locations (preserved)

**🎯 Happy Trading!** 

Remember: Past performance does not guarantee future results. Always use proper risk management and never risk more than you can afford to lose.
