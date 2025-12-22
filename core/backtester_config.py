#!/usr/bin/env python3
"""
Configuration file for BOS/CHOCH Backtester
Easily adjust parameters without modifying the main code
"""

# Trading Parameters
TRADING_CONFIG = {
    "initial_capital": 10000,        # Starting capital in USD
    "risk_per_trade": 0.005,        # 0.5% risk per trade (0.005 = 0.5%)
    "reward_risk_ratio": 2.0,       # 2:1 reward to risk ratio
    "max_trade_duration": 48,       # Maximum trade duration in hours
    "confidence_threshold": 0.7,    # Minimum confidence for A+ entries (0.0-1.0)
    "stop_loss_atr_multiplier": 2.0, # ATR multiplier for stop loss placement
}

# Data Configuration
DATA_CONFIG = {
    "symbol": "XAUUSD_H1.csv",      # Symbol to backtest
    "days_back": 90,                # Number of days of historical data
    "timeframe": "1H",              # Timeframe for analysis
}

# Risk Management
RISK_CONFIG = {
    "max_open_trades": 3,           # Maximum number of simultaneous trades
    "max_daily_loss": 0.05,         # Maximum daily loss (5% of capital)
    "max_total_drawdown": 0.25,     # Maximum total drawdown (25% of capital)
    "correlation_threshold": 0.7,   # Maximum correlation between open trades
}

# Performance Metrics
METRICS_CONFIG = {
    "calculate_sharpe": True,       # Calculate Sharpe ratio
    "calculate_sortino": True,      # Calculate Sortino ratio
    "calculate_calmar": True,       # Calculate Calmar ratio
    "calculate_var": True,          # Calculate Value at Risk
    "var_confidence": 0.95,         # VaR confidence level
}

# Chart Configuration
CHART_CONFIG = {
    "theme": "plotly_dark",         # Chart theme (plotly_dark, plotly_white, etc.)
    "height": 800,                  # Default chart height
    "width": 1200,                  # Default chart width
    "output_format": "html",        # Output format (html, png, svg)
    "output_directory": "generated_backtest_plots",
}

# Entry Filtering
ENTRY_FILTERS = {
    "min_volume": 1000,             # Minimum volume requirement
    "min_volatility": 0.01,         # Minimum volatility (ATR %)
    "max_volatility": 0.05,         # Maximum volatility (ATR %)
    "trend_alignment": True,        # Require trend alignment
    "support_resistance": True,     # Consider support/resistance levels
    "news_filter": False,           # Filter out news events (if available)
}

# Advanced Settings
ADVANCED_CONFIG = {
    "slippage": 0.0001,             # Slippage per trade (0.0001 = 1 pip)
    "commission": 0.0001,           # Commission per trade (0.0001 = 1 pip)
    "spread": 0.0002,               # Spread cost (0.0002 = 2 pips)
    "fill_rate": 0.95,              # Fill rate assumption (0.95 = 95%)
    "partial_fills": True,          # Allow partial fills
    "market_impact": True,          # Consider market impact
}

# Optimization Settings
OPTIMIZATION_CONFIG = {
    "optimize_parameters": False,    # Run parameter optimization
    "optimization_method": "grid",   # grid, genetic, bayesian
    "parameter_ranges": {
        "confidence_threshold": [0.6, 0.7, 0.8, 0.9],
        "risk_per_trade": [0.01, 0.02, 0.03, 0.04],
        "reward_risk_ratio": [1.5, 2.0, 2.5, 3.0],
        "stop_loss_atr_multiplier": [1.5, 2.0, 2.5, 3.0],
    },
    "optimization_metric": "sharpe_ratio",  # sharpe_ratio, profit_factor, total_return
    "cross_validation": True,       # Use cross-validation
    "cv_folds": 5,                  # Number of cross-validation folds
}

# Reporting Configuration
REPORT_CONFIG = {
    "generate_summary": True,        # Generate summary report
    "generate_charts": True,         # Generate all charts
    "generate_csv": True,            # Export results to CSV
    "generate_pdf": False,           # Generate PDF report (requires additional packages)
    "include_trade_log": True,       # Include detailed trade log
    "include_risk_metrics": True,    # Include risk metrics
    "include_performance_metrics": True, # Include performance metrics
}

# Notification Settings
NOTIFICATION_CONFIG = {
    "email_notifications": False,    # Send email notifications
    "email_address": "",             # Email address for notifications
    "telegram_notifications": False, # Send Telegram notifications
    "telegram_bot_token": "",        # Telegram bot token
    "telegram_chat_id": "",          # Telegram chat ID
    "discord_notifications": False,  # Send Discord notifications
    "discord_webhook": "",           # Discord webhook URL
}

# Logging Configuration
LOGGING_CONFIG = {
    "log_level": "INFO",             # DEBUG, INFO, WARNING, ERROR
    "log_to_file": True,             # Log to file
    "log_to_console": True,          # Log to console
    "log_file": "backtester.log",    # Log file name
    "max_log_size": 10,              # Maximum log file size in MB
    "backup_count": 5,               # Number of backup log files
}

# Example configurations for different strategies
STRATEGY_PRESETS = {
    "conservative": {
        "risk_per_trade": 0.01,      # 1% risk per trade
        "reward_risk_ratio": 1.5,    # 1.5:1 reward to risk
        "confidence_threshold": 0.8,  # Higher confidence requirement
        "max_open_trades": 2,        # Fewer simultaneous trades
    },
    "aggressive": {
        "risk_per_trade": 0.05,      # 5% risk per trade
        "reward_risk_ratio": 3.0,    # 3:1 reward to risk
        "confidence_threshold": 0.6,  # Lower confidence requirement
        "max_open_trades": 5,        # More simultaneous trades
    },
    "balanced": {
        "risk_per_trade": 0.005,     # 0.5% risk per trade
        "reward_risk_ratio": 2.0,    # 2:1 reward to risk
        "confidence_threshold": 0.7,  # Medium confidence requirement
        "max_open_trades": 3,        # Medium number of trades
    }
}

def get_config(preset_name: str = None) -> dict:
    """Get configuration with optional preset override"""
    config = {
        "trading": TRADING_CONFIG.copy(),
        "data": DATA_CONFIG.copy(),
        "risk": RISK_CONFIG.copy(),
        "metrics": METRICS_CONFIG.copy(),
        "charts": CHART_CONFIG.copy(),
        "entry_filters": ENTRY_FILTERS.copy(),
        "advanced": ADVANCED_CONFIG.copy(),
        "optimization": OPTIMIZATION_CONFIG.copy(),
        "reporting": REPORT_CONFIG.copy(),
        "notifications": NOTIFICATION_CONFIG.copy(),
        "logging": LOGGING_CONFIG.copy(),
    }
    
    if preset_name and preset_name in STRATEGY_PRESETS:
        preset = STRATEGY_PRESETS[preset_name]
        config["trading"].update(preset)
        print(f"✅ Applied '{preset_name}' strategy preset")
    
    return config

def print_config_summary(config: dict):
    """Print a summary of the current configuration"""
    print("\n📋 BACKTESTER CONFIGURATION SUMMARY")
    print("=" * 50)
    
    trading = config["trading"]
    print(f"💰 Capital: ${trading['initial_capital']:,.2f}")
    print(f"⚠️  Risk per trade: {trading['risk_per_trade']*100:.1f}%")
    print(f"📈 Reward/Risk: {trading['reward_risk_ratio']:.1f}:1")
    print(f"🎯 Confidence threshold: {trading['confidence_threshold']}")
    print(f"⏱️  Max trade duration: {trading['max_trade_duration']} hours")
    print(f"🛡️  Stop loss ATR multiplier: {trading['stop_loss_atr_multiplier']}")
    
    data = config["data"]
    print(f"📊 Symbol: {data['symbol']}")
    print(f"📅 Data period: {data['days_back']} days")
    print(f"⏰ Timeframe: {data['timeframe']}")
    
    print("=" * 50)

if __name__ == "__main__":
    # Example usage
    config = get_config("balanced")
    print_config_summary(config)
