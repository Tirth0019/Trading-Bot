"""
🎯 CENTRALIZED TRADING BOT CORE MODULE

This module provides a unified interface to all trading bot functionality.
"""

from .trading_executor import MultiTimeframeTradingExecutor
from .backtester import IntegratedBacktester
from .data_loader import load_and_resample
from .smart_money_concepts import MarketStructureAnalyzer, MarketEvent, EventType
from .risk_manager import RiskManager
from .trend_detector import detect_trend, detect_swing_points
from .structure_builder import build_market_structure, get_market_analysis
from .utils import calculate_atr, detect_swing_points as detect_swings

__all__ = [
    'MultiTimeframeTradingExecutor',
    'IntegratedBacktester',
    'load_and_resample',
    'MarketStructureAnalyzer',
    'MarketEvent',
    'EventType',
    'RiskManager',
    'detect_trend',
    'detect_swing_points',
    'build_market_structure',
    'get_market_analysis',
    'calculate_atr',
    'detect_swings'
]
