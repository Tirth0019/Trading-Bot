# 🚀 QUICK START GUIDE - CENTRALIZED TRADING BOT

## 📋 **SINGLE ENTRY POINT**

The trading bot is now **fully centralized** with one simple entry point:

```bash
python trading_bot.py
```

---

## 🎯 **BASIC USAGE**

### **1. Run Backtest (Default)**
```bash
# Simple backtest on XAUUSD
python trading_bot.py --backtest --symbol XAUUSD

# Custom configuration
python trading_bot.py --backtest --symbol EURUSD --days 90 --risk 0.02
```

### **2. Analyze Market Structure**
```bash
# Analyze without trading
python trading_bot.py --analyze --symbol GBPUSD

# Analyze with custom settings
python trading_bot.py --analyze --symbol XAUUSD --days 30
```

### **3. Run Trading Strategy**
```bash
# Same as backtest
python trading_bot.py --strategy --symbol XAUUSD --days 60
```

---

## ⚙️ **CONFIGURATION OPTIONS**

### **Command-Line Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `--symbol` | Trading symbol (XAUUSD, EURUSD, etc.) | XAUUSD |
| `--days` | Days to analyze | 60 |
| `--risk` | Risk per trade (0.01 = 1%) | 0.01 |
| `--confidence` | Confidence threshold | 0.6 |
| `--atr` | ATR multiplier for stops | 2.5 |
| `--rr` | Risk-reward ratio | 2.0 |
| `--data` | Path to data file (auto-detects if not provided) | None |

---

## 💻 **PROGRAMMATIC USAGE**

### **Python API:**

```python
from trading_bot import TradingBot

# Initialize bot
bot = TradingBot(
    symbol="XAUUSD",
    risk_per_trade=0.01,
    confidence_threshold=0.6
)

# Run backtest
results = bot.run_backtest(days_back=60)

# Analyze market
analysis = bot.analyze_market(days_back=30)

# Update configuration
bot.update_config(risk_per_trade=0.02, confidence_threshold=0.7)
```

---

## 📊 **EXAMPLES**

### **Example 1: Quick Backtest**
```bash
python trading_bot.py --backtest --symbol XAUUSD --days 60
```

### **Example 2: Conservative Strategy**
```bash
python trading_bot.py --backtest \
    --symbol EURUSD \
    --risk 0.01 \
    --confidence 0.7 \
    --atr 3.0 \
    --days 90
```

### **Example 3: Aggressive Strategy**
```bash
python trading_bot.py --backtest \
    --symbol GBPUSD \
    --risk 0.02 \
    --confidence 0.5 \
    --atr 2.0 \
    --days 30
```

### **Example 4: Market Analysis Only**
```bash
python trading_bot.py --analyze --symbol XAUUSD --days 30
```

---

## 🎯 **WHAT IT DOES**

The centralized system handles:

1. ✅ **Data Loading** - Automatically finds and loads data files
2. ✅ **Multi-Timeframe Analysis** - 1H trend + 15M entries + 1M confirmation
3. ✅ **BOS/CHOCH Detection** - Smart money concepts pattern recognition
4. ✅ **Risk Management** - ATR-based stops and position sizing
5. ✅ **Backtesting** - Point-in-time simulation (no look-ahead bias)
6. ✅ **Performance Reporting** - Comprehensive results and metrics

---

## 📁 **FILE STRUCTURE**

```
Trading Bot/
├── trading_bot.py          # 🎯 SINGLE ENTRY POINT
├── core/                   # Core modules (internal)
│   ├── trading_executor.py
│   ├── backtester.py
│   ├── data_loader.py
│   └── ...
└── data/                   # Market data files
    ├── XAUUSD_M1.csv
    ├── EURUSD_M1.csv
    └── ...
```

---

## 🔧 **TROUBLESHOOTING**

### **No Data File Found:**
- Ensure data files are in the `data/` directory
- Files should be named: `{SYMBOL}_{TIMEFRAME}.csv`
- Example: `XAUUSD_M1.csv`, `EURUSD_H1.csv`

### **Import Errors:**
- Make sure you're in the project root directory
- Install dependencies: `pip install -r requirement/requirements_backtester.txt`

### **No Signals Generated:**
- Try lowering `--confidence` (e.g., 0.5)
- Try different symbols (XAUUSD usually works well)
- Increase `--days` for more data

---

## 📚 **ADVANCED USAGE**

### **Custom Data File:**
```bash
python trading_bot.py --backtest --data "path/to/your/data.csv"
```

### **Multiple Runs:**
```python
from trading_bot import TradingBot

symbols = ["XAUUSD", "EURUSD", "GBPUSD"]

for symbol in symbols:
    bot = TradingBot(symbol=symbol)
    results = bot.run_backtest()
    print(f"{symbol}: {results.get('total_pnl', 0):.2f}")
```

---

## ✅ **SUMMARY**

**Before:** Multiple files, confusing entry points, decentralized system
**After:** Single entry point (`trading_bot.py`), unified API, easy to use

**Just run:**
```bash
python trading_bot.py --backtest --symbol XAUUSD
```

That's it! 🎉

