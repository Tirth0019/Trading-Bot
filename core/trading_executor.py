import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Literal
from dataclasses import dataclass
from datetime import datetime, timedelta
import warnings

from .trend_detector import detect_trend, detect_swing_points
from .smart_money_concepts import MarketStructureAnalyzer, MarketEvent, EventType
from .data_loader import load_and_resample
from .risk_manager import RiskManager

warnings.filterwarnings('ignore')

@dataclass
class TradeSignal:
    """Represents a complete trade signal with all confirmations"""
    timestamp: pd.Timestamp
    direction: Literal["BUY", "SELL"]
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    timeframe_1h_trend: str
    timeframe_15m_entry: str
    timeframe_1m_confirmation: str
    risk_reward_ratio: float
    stop_loss_pips: float
    take_profit_pips: float

@dataclass
class TradeExecution:
    """Represents an executed trade"""
    signal: TradeSignal
    entry_time: pd.Timestamp
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    status: Literal["OPEN", "CLOSED", "CANCELLED"]
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    exit_reason: Optional[str] = None

class MultiTimeframeTradingExecutor:
    """
    ENHANCED trading executor that implements the advanced multi-timeframe strategy:
    1. Check trend in 1H timeframe
    2. Mark A+ entries in 15M timeframe with retracement confirmation
    3. Confirm retracement followed by reversal candle near level (e.g., bullish engulfing near BOS low)
    4. Enhanced 1M confirmation with body size, volume, and momentum filters
    5. Execute with ATR-based stop loss and 1% risk per trade
    6. Trend alignment: Both 1H and 15M trends must match event direction
    7. Reversal candle patterns: Bullish/Bearish engulfing, Hammer/Shooting Star, Strong body candles
    """
    
    def __init__(self, 
                 symbol: str = "EURUSD",
                 risk_per_trade: float = 0.01,  # 1% risk per trade (reduced from 2%)
                 stop_loss_pips: float = 20.0,  # Legacy SL used if ATR unavailable
                 risk_reward_ratio: float = 2.0,  # 1:2 risk-reward
                 confidence_threshold: float = 0.7,  # A+ entry threshold
                 pip_value: float = 0.0001,  # Standard pip value for major pairs
                 atr_period: int = 14,
                 atr_multiplier: float = 3.0):  # Increased from 2.0 for wider stops
        
        self.symbol = symbol
        self.risk_per_trade = risk_per_trade
        self.stop_loss_pips = stop_loss_pips
        self.risk_reward_ratio = risk_reward_ratio
        self.confidence_threshold = confidence_threshold
        self.pip_value = pip_value
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        
        # Initialize analyzers
        self.market_analyzer = MarketStructureAnalyzer(confidence_threshold=confidence_threshold)
        self.risk_manager = RiskManager(risk_per_trade=risk_per_trade,
                                        atr_period=atr_period,
                                        atr_multiplier=atr_multiplier)
        
        # Track trades and signals
        self.signals: List[TradeSignal] = []
        self.executed_trades: List[TradeExecution] = []
        self.open_trades: List[TradeExecution] = []
        self._resampled_data: Optional[Dict[str, pd.DataFrame]] = None
        
    def analyze_1h_trend(self, data_1h: pd.DataFrame) -> str:
        """
        Analyze trend in 1H timeframe using swing point analysis
        
        Args:
            data_1h: 1H timeframe OHLCV data
            
        Returns:
            Trend direction: "uptrend", "downtrend", or "sideways"
        """
        if data_1h.empty or len(data_1h) < 20:
            return "sideways"
        
        # Use last 50 candles for trend analysis
        recent_data = data_1h.tail(50)
        
        # Detect swing points
        swing_highs, swing_lows = detect_swing_points(recent_data, window=3)
        
        # Determine trend
        trend = detect_trend(swing_highs, swing_lows)
        
        return trend
    
    def find_a_plus_entries_15m(self, data_15m: pd.DataFrame, trend_1h: str) -> List[MarketEvent]:
        """
        Find A+ quality entries in 15M timeframe that align with 1H trend
        FIXED: Now processes point-in-time without look-ahead bias
        
        Args:
            data_15m: 15M timeframe OHLCV data (up to current time only)
            trend_1h: Trend from 1H timeframe
            
        Returns:
            List of high-quality market events (without retracement confirmation - done separately)
        """
        if data_15m.empty or len(data_15m) < 20:
            return []
        
        # Get market structure analysis with current data only
        structure = self._build_market_structure(data_15m)
        
        # Find market events with current data only
        events = self.market_analyzer.get_market_events(structure)
        
        # Filter for A+ quality entries with basic criteria only
        a_plus_events = []
        
        for event in events:
            if event.confidence >= self.confidence_threshold:
                # Check trend alignment (1H + 15M trends must match)
                if self._is_trend_aligned_enhanced(event, trend_1h, data_15m):
                    # NOTE: Retracement confirmation is now done separately in point-in-time processing
                    a_plus_events.append(event)
        
        return a_plus_events
    
    def check_retracement_confirmation_point_in_time(self, 
                                                   event: MarketEvent, 
                                                   data_15m_current: pd.DataFrame,
                                                   current_time: pd.Timestamp) -> bool:
        """
        Check retracement confirmation with point-in-time data only (NO LOOK-AHEAD BIAS)
        
        Args:
            event: Market event to check
            data_15m_current: 15M data up to current time only
            current_time: Current timestamp
            
        Returns:
            True if retracement confirmation is valid, False otherwise
        """
        if len(data_15m_current) < 15:
            return False
        
        # Get ATR for tolerance calculation using RiskManager
        atr_series = self.risk_manager.calculate_atr(data_15m_current)
        if atr_series is None or len(atr_series) == 0 or pd.isna(atr_series.iloc[-1]):
            return False
        
        current_atr = atr_series.iloc[-1]
        tolerance = current_atr * 0.5  # 0.5 ATR tolerance
        
        # Get recent price data after the event but before current time
        event_time = event.timestamp
        recent_data = data_15m_current[
            (data_15m_current.index > event_time) & 
            (data_15m_current.index <= current_time)
        ].tail(15)
        
        if recent_data.empty:
            return False
        
        # Check if price has retraced to the broken level
        broken_level = event.price
        retracement_found = False
        retracement_candle_idx = None
        
        # Find retracement to broken level
        for i, (_, candle) in enumerate(recent_data.iterrows()):
            # Check if price has retraced to the broken level (within tolerance)
            if (candle['Low'] <= broken_level + tolerance and 
                candle['High'] >= broken_level - tolerance):
                retracement_found = True
                retracement_candle_idx = i
                break
        
        if not retracement_found:
            return False
        
        # Now check for reversal candle pattern after retracement
        if retracement_candle_idx is None or retracement_candle_idx >= len(recent_data) - 1:
            return False
        
        # Get the candle after retracement for reversal confirmation
        reversal_candle = recent_data.iloc[retracement_candle_idx + 1]
        prev_candle = recent_data.iloc[retracement_candle_idx]
        
        # Check for reversal patterns based on event direction
        if event.direction in ["BUY", "Bullish"]:
            # For bullish events, look for bullish reversal patterns
            return self._is_bullish_reversal_candle(prev_candle, reversal_candle, broken_level, tolerance)
        elif event.direction in ["SELL", "Bearish"]:
            # For bearish events, look for bearish reversal patterns
            return self._is_bearish_reversal_candle(prev_candle, reversal_candle, broken_level, tolerance)
        
        return False
    
    def confirm_1m_signal(self, 
                          data_1m: pd.DataFrame, 
                          signal_direction: str, 
                          entry_time: pd.Timestamp) -> bool:
        """
        FIXED: Enhanced 1M signal confirmation with corrected logic and momentum filters
        
        Args:
            data_1m: 1M timeframe OHLCV data
            signal_direction: "BUY" or "SELL"
            entry_time: Timestamp of the entry signal
            
        Returns:
            True if confirmation is valid, False otherwise
        """
        if data_1m.empty or len(data_1m) < 20:
            return False
        
        # FIXED: Get the first 1M candle that occurred *after* the entry signal time
        future_candles = data_1m[data_1m.index > entry_time]
        if future_candles.empty:
            return False
        
        next_candle = future_candles.iloc[0]  # Use iloc[0] for robustness
        
        # Calculate candle body size (minimum 30% of total range)
        candle_range = next_candle['High'] - next_candle['Low']
        body_size = abs(next_candle['Close'] - next_candle['Open'])
        body_ratio = body_size / candle_range if candle_range > 0 else 0
        
        # Volume filter (20% above average volume)
        recent_volume = data_1m['Volume'].tail(20).mean()
        volume_ratio = next_candle['Volume'] / recent_volume if recent_volume > 0 else 1
        
        # Determine candle direction
        is_green = next_candle['Close'] > next_candle['Open']
        is_red = next_candle['Close'] < next_candle['Open']
        
        # FIXED: Enhanced confirmation criteria with corrected momentum filters
        if signal_direction == "BUY":
            return (is_green and 
                   body_ratio >= 0.3 and  # Body size filter
                   volume_ratio >= 1.2 and  # Volume filter
                   (next_candle['High'] - next_candle['Close']) <= body_size * 0.2)  # Small upper wick (strong close)
        
        elif signal_direction == "SELL":
            return (is_red and 
                   body_ratio >= 0.3 and  # Body size filter
                   volume_ratio >= 1.2 and  # Volume filter
                   (next_candle['Close'] - next_candle['Low']) <= body_size * 0.2)  # Small lower wick (strong close)
        
        return False
    
    def _is_trend_aligned_enhanced(self, event: MarketEvent, trend_1h: str, data_15m: pd.DataFrame) -> bool:
        """
        Enhanced trend alignment check: 1H + 15M trends must match
        
        Args:
            event: Market event
            trend_1h: 1H timeframe trend
            data_15m: 15M timeframe data
            
        Returns:
            True if both timeframes align with event direction
        """
        # Analyze 15M trend using swing points
        if len(data_15m) < 20:
            return False
        
        # Get recent 15M swing points
        recent_15m = data_15m.tail(20)
        swing_highs, swing_lows = detect_swing_points(recent_15m, window=2)
        trend_15m = detect_trend(swing_highs, swing_lows)
        
        # Check if both timeframes align with event direction
        if event.direction in ["BUY", "Bullish"]:
            return (trend_1h == "uptrend" and trend_15m == "uptrend")
        elif event.direction in ["SELL", "Bearish"]:
            return (trend_1h == "downtrend" and trend_15m == "downtrend")
        
        return False
    

    
    def _is_bullish_reversal_candle(self, prev_candle: pd.Series, reversal_candle: pd.Series, 
                                  broken_level: float, tolerance: float) -> bool:
        """
        Check for bullish reversal candle patterns near BOS/CHOCH level
        
        Args:
            prev_candle: Previous candle (retracement candle)
            reversal_candle: Current candle (potential reversal)
            broken_level: BOS/CHOCH level
            tolerance: Price tolerance
            
        Returns:
            True if bullish reversal pattern is confirmed
        """
        # Check if reversal candle is near the broken level
        if not (reversal_candle['Low'] <= broken_level + tolerance and 
                reversal_candle['High'] >= broken_level - tolerance):
            return False
        
        # Pattern 1: Bullish Engulfing
        if (prev_candle['Close'] < prev_candle['Open'] and  # Previous candle is bearish
            reversal_candle['Close'] > reversal_candle['Open'] and  # Current candle is bullish
            reversal_candle['Open'] < prev_candle['Close'] and  # Current open below previous close
            reversal_candle['Close'] > prev_candle['Open']):  # Current close above previous open
            return True
        
        # Pattern 2: Hammer/Doji with bullish close
        if (reversal_candle['Close'] > reversal_candle['Open'] and  # Bullish candle
            reversal_candle['Close'] > broken_level and  # Close above broken level
            (reversal_candle['High'] - reversal_candle['Close']) <= 
            (reversal_candle['Close'] - reversal_candle['Low']) * 0.5):  # Small upper wick
            return True
        
        # Pattern 3: Strong bullish candle with high close
        if (reversal_candle['Close'] > reversal_candle['Open'] and  # Bullish candle
            reversal_candle['Close'] > broken_level and  # Close above broken level
            (reversal_candle['Close'] - reversal_candle['Open']) >= 
            (reversal_candle['High'] - reversal_candle['Low']) * 0.6):  # Strong body (60%+)
            return True
        
        return False
    
    def _is_bearish_reversal_candle(self, prev_candle: pd.Series, reversal_candle: pd.Series, 
                                  broken_level: float, tolerance: float) -> bool:
        """
        Check for bearish reversal candle patterns near BOS/CHOCH level
        
        Args:
            prev_candle: Previous candle (retracement candle)
            reversal_candle: Current candle (potential reversal)
            broken_level: BOS/CHOCH level
            tolerance: Price tolerance
            
        Returns:
            True if bearish reversal pattern is confirmed
        """
        # Check if reversal candle is near the broken level
        if not (reversal_candle['Low'] <= broken_level + tolerance and 
                reversal_candle['High'] >= broken_level - tolerance):
            return False
        
        # Pattern 1: Bearish Engulfing
        if (prev_candle['Close'] > prev_candle['Open'] and  # Previous candle is bullish
            reversal_candle['Close'] < reversal_candle['Open'] and  # Current candle is bearish
            reversal_candle['Open'] > prev_candle['Close'] and  # Current open above previous close
            reversal_candle['Close'] < prev_candle['Open']):  # Current close below previous open
            return True
        
        # Pattern 2: Shooting Star/Doji with bearish close
        if (reversal_candle['Close'] < reversal_candle['Open'] and  # Bearish candle
            reversal_candle['Close'] < broken_level and  # Close below broken level
            (reversal_candle['Close'] - reversal_candle['Low']) <= 
            (reversal_candle['High'] - reversal_candle['Close']) * 0.5):  # Small lower wick
            return True
        
        # Pattern 3: Strong bearish candle with low close
        if (reversal_candle['Close'] < reversal_candle['Open'] and  # Bearish candle
            reversal_candle['Close'] < broken_level and  # Close below broken level
            (reversal_candle['Open'] - reversal_candle['Close']) >= 
            (reversal_candle['High'] - reversal_candle['Low']) * 0.6):  # Strong body (60%+)
            return True
        
        return False
    

    
    def generate_trade_signal(self, 
                             event: MarketEvent, 
                             trend_1h: str,
                             current_price: float) -> Optional[TradeSignal]:
        """
        Generate a trade signal (entry price will be determined at execution time)
        
        Args:
            event: Market event from 15M timeframe
            trend_1h: Trend from 1H timeframe
            current_price: Current market price (for reference only)
            
        Returns:
            Trade signal or None if invalid
        """
        # Determine trade direction
        if event.direction == "Bullish" and event.event_type == EventType.BOS:
            direction = "BUY"
        elif event.direction == "Bearish" and event.event_type == EventType.BOS:
            direction = "SELL"
        elif event.direction == "Bullish" and event.event_type == EventType.CHOCH:
            direction = "BUY"
        elif event.direction == "Bearish" and event.event_type == EventType.CHOCH:
            direction = "SELL"
        else:
            return None
        
        # Create trade signal (entry price will be set at actual execution time)
        signal = TradeSignal(
            timestamp=event.timestamp,
            direction=direction,
            entry_price=0.0,  # Will be set at execution time based on 1M confirmation
            stop_loss=0.0,    # Will be calculated at execution time with ATR
            take_profit=0.0,  # Will be calculated at execution time with ATR
            confidence=event.confidence,
            timeframe_1h_trend=trend_1h,
            timeframe_15m_entry=f"{event.event_type.value} - {event.direction}",
            timeframe_1m_confirmation="PENDING",
            risk_reward_ratio=self.risk_reward_ratio,
            stop_loss_pips=self.stop_loss_pips,
            take_profit_pips=self.stop_loss_pips * self.risk_reward_ratio
        )
        
        return signal
    
    def execute_trade(self, 
                     signal: TradeSignal, 
                     account_balance: float,
                     data_1m: pd.DataFrame) -> Optional[TradeExecution]:
        """
        Execute a trade after 1M confirmation
        
        Args:
            signal: Complete trade signal
            account_balance: Current account balance
            data_1m: 1M timeframe data for confirmation
            
        Returns:
            Executed trade or None if execution fails
        """
        # Wait for 1M confirmation
        if not self.confirm_1m_signal(data_1m, signal.direction, signal.timestamp):
            return None
        
        # Prefer ATR-based stops from 15M timeframe without lookahead
        stop_loss = signal.stop_loss
        take_profit = signal.take_profit
        if self._resampled_data is not None:
            data_15m = self._resampled_data.get('15M')
            if data_15m is not None and not data_15m.empty:
                data_pre_entry = data_15m.loc[data_15m.index <= signal.timestamp]
                atr_series = self.risk_manager.calculate_atr(data_pre_entry)
                if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]):
                    atr_value = atr_series.iloc[-1]
                    stop_loss, take_profit = self.risk_manager.compute_stop_and_target_from_atr(
                        entry_price=signal.entry_price,
                        direction=signal.direction,
                        atr_value=atr_value,
                        reward_risk_ratio=self.risk_reward_ratio
                    )

        # IMPROVED: Reduced risk sizing (1% instead of 2%)
        risk_amount = self.risk_manager.risk_amount_for_balance(account_balance)
        stop_loss_distance = abs(signal.entry_price - stop_loss)
        if stop_loss_distance == 0:
            return None
        position_size = self.risk_manager.calculate_position_size(
            entry_price=signal.entry_price,
            stop_loss=stop_loss,
            risk_amount=risk_amount
        )
        
        # Create trade execution
        trade = TradeExecution(
            signal=signal,
            entry_time=signal.timestamp,
            entry_price=signal.entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            status="OPEN"
        )
        
        # Update signal confirmation
        signal.timeframe_1m_confirmation = "CONFIRMED"
        
        # Add to open trades
        self.open_trades.append(trade)
        self.executed_trades.append(trade)
        
        return trade
    
    def execute_trade_point_in_time(self, 
                                   signal: TradeSignal, 
                                   account_balance: float,
                                   data_1m_current: pd.DataFrame,
                                   current_time: pd.Timestamp) -> Optional[TradeExecution]:
        """
        Execute a trade with point-in-time data only (NO LOOK-AHEAD BIAS)
        CRITICAL FIX: Entry price determined from actual 1M confirmation candle
        
        Args:
            signal: Trade signal (entry_price will be determined here)
            account_balance: Current account balance
            data_1m_current: 1M data up to current time only
            current_time: Current timestamp
            
        Returns:
            Executed trade or None if execution fails
        """
        # CRITICAL FIX: Get the actual entry price from 1M confirmation candle
        confirmation_candle = self._get_confirmation_candle_price(data_1m_current, signal.direction, signal.timestamp, current_time)
        if confirmation_candle is None:
            return None
        
        actual_entry_price = confirmation_candle['Close']  # Use close of confirmation candle
        
        # Wait for 1M confirmation with current data only
        if not self.confirm_1m_signal_point_in_time(data_1m_current, signal.direction, signal.timestamp, current_time):
            return None
        
        # Calculate ATR-based stops using RiskManager consistently
        stop_loss = 0.0
        take_profit = 0.0
        
        # Use 15M data up to current time for ATR calculation
        if self._resampled_data is not None:
            data_15m = self._resampled_data.get('15M')
            if data_15m is not None and not data_15m.empty:
                # Get 15M data up to current time only
                data_15m_current = data_15m.loc[data_15m.index <= current_time]
                if len(data_15m_current) > 20:  # Ensure enough data for ATR
                    # Use RiskManager for consistent ATR calculation and stop/target computation
                    atr_series = self.risk_manager.calculate_atr(data_15m_current)
                    if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]):
                        atr_value = atr_series.iloc[-1]
                        # Use RiskManager for all risk calculations with ACTUAL entry price
                        risk_result = self.risk_manager.compute_stop_and_target_from_atr(
                            entry_price=actual_entry_price,  # Use actual entry price from 1M candle
                            direction=signal.direction,
                            atr_value=atr_value,
                            reward_risk_ratio=self.risk_reward_ratio,
                            symbol=self.symbol
                        )
                        if risk_result is not None:
                            stop_loss, take_profit = risk_result
        
        # Calculate position size using RiskManager consistently
        risk_amount = self.risk_manager.risk_amount_for_balance(account_balance)
        stop_loss_distance = abs(actual_entry_price - stop_loss)
        if stop_loss_distance == 0:
            return None
        
        # Use RiskManager for all position sizing calculations with ACTUAL entry price
        position_size = self.risk_manager.calculate_position_size(
            entry_price=actual_entry_price,  # Use actual entry price from 1M candle
            stop_loss=stop_loss,
            risk_amount=risk_amount,
            account_balance=account_balance,
            symbol=self.symbol
        )
        
        # CRITICAL FIX: Update signal with actual entry price
        signal.entry_price = actual_entry_price
        signal.stop_loss = stop_loss
        signal.take_profit = take_profit
        
        # Create trade execution with ACTUAL entry price
        trade = TradeExecution(
            signal=signal,
            entry_time=current_time,  # Use current time, not signal time
            entry_price=actual_entry_price,  # Use actual entry price from 1M candle
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            status="OPEN"
        )
        
        # Update signal confirmation
        signal.timeframe_1m_confirmation = "CONFIRMED"
        
        # Add to open trades
        self.open_trades.append(trade)
        self.executed_trades.append(trade)
        
        return trade
    
    def _get_confirmation_candle_price(self, 
                                     data_1m_current: pd.DataFrame, 
                                     signal_direction: str, 
                                     entry_time: pd.Timestamp,
                                     current_time: pd.Timestamp) -> Optional[pd.Series]:
        """
        Get the actual confirmation candle price for realistic entry execution
        
        Args:
            data_1m_current: 1M data up to current time only
            signal_direction: BUY or SELL
            entry_time: When the signal was generated
            current_time: Current timestamp
            
        Returns:
            Confirmation candle data or None if not found
        """
        # Find 1M candles after the entry signal time
        future_candles = data_1m_current[data_1m_current.index > entry_time]
        
        if future_candles.empty:
            return None
        
        # Get the first 1M candle that occurred after the entry signal time
        confirmation_candle = future_candles.iloc[0]
        
        # Apply the same filters as confirm_1m_signal_point_in_time
        # Body size filter
        body_size = abs(confirmation_candle['Close'] - confirmation_candle['Open'])
        candle_range = confirmation_candle['High'] - confirmation_candle['Low']
        body_ratio = body_size / candle_range if candle_range > 0 else 0
        
        if body_ratio < 0.3:  # Body must be at least 30% of candle range
            return None
        
        # Volume filter (if available)
        if 'Volume' in confirmation_candle.index:
            # Simple volume check - would need historical volume for proper ratio
            if confirmation_candle['Volume'] <= 0:
                return None
        
        # Momentum filter
        if signal_direction == "BUY":
            # For BUY: Green candle with small upper wick
            is_green = confirmation_candle['Close'] > confirmation_candle['Open']
            small_upper_wick = (confirmation_candle['High'] - confirmation_candle['Close']) <= body_size * 0.2
            if not (is_green and small_upper_wick):
                return None
        elif signal_direction == "SELL":
            # For SELL: Red candle with small lower wick
            is_red = confirmation_candle['Close'] < confirmation_candle['Open']
            small_lower_wick = (confirmation_candle['Close'] - confirmation_candle['Low']) <= body_size * 0.2
            if not (is_red and small_lower_wick):
                return None
        
        return confirmation_candle
    
    def confirm_1m_signal_point_in_time(self, 
                                       data_1m_current: pd.DataFrame, 
                                       signal_direction: str, 
                                       entry_time: pd.Timestamp,
                                       current_time: pd.Timestamp) -> bool:
        """
        FIXED: Confirm 1M signal with point-in-time data only (NO LOOK-AHEAD BIAS)
        
        Args:
            data_1m_current: 1M data up to current time only
            signal_direction: "BUY" or "SELL"
            entry_time: Timestamp of the entry signal
            current_time: Current timestamp
            
        Returns:
            True if confirmation is valid, False otherwise
        """
        if data_1m_current.empty or len(data_1m_current) < 20:
            return False
        
        # FIXED: Get the first 1M candle after entry time but before current time
        future_candles = data_1m_current[
            (data_1m_current.index > entry_time) & 
            (data_1m_current.index <= current_time)
        ]
        if future_candles.empty:
            return False
        
        next_candle = future_candles.iloc[0]  # Use iloc[0] for robustness
        
        # Calculate candle body size (minimum 30% of total range)
        candle_range = next_candle['High'] - next_candle['Low']
        body_size = abs(next_candle['Close'] - next_candle['Open'])
        body_ratio = body_size / candle_range if candle_range > 0 else 0
        
        # Volume filter (20% above average volume)
        recent_volume = data_1m_current['Volume'].tail(20).mean()
        volume_ratio = next_candle['Volume'] / recent_volume if recent_volume > 0 else 1
        
        # Determine candle direction
        is_green = next_candle['Close'] > next_candle['Open']
        is_red = next_candle['Close'] < next_candle['Open']
        
        # FIXED: Enhanced confirmation criteria with corrected momentum filters
        if signal_direction == "BUY":
            return (is_green and 
                   body_ratio >= 0.3 and  # Body size filter
                   volume_ratio >= 1.2 and  # Volume filter
                   (next_candle['High'] - next_candle['Close']) <= body_size * 0.2)  # Small upper wick (strong close)
        
        elif signal_direction == "SELL":
            return (is_red and 
                   body_ratio >= 0.3 and  # Body size filter
                   volume_ratio >= 1.2 and  # Volume filter
                   (next_candle['Close'] - next_candle['Low']) <= body_size * 0.2)  # Small lower wick (strong close)
        
        return False
    
    def monitor_open_trades_point_in_time(self, 
                                        data_1m_current: pd.DataFrame,
                                        current_time: pd.Timestamp) -> List[TradeExecution]:
        """
        Monitor open trades with point-in-time data only (NO LOOK-AHEAD BIAS)
        
        Args:
            data_1m_current: 1M data up to current time only
            current_time: Current timestamp
            
        Returns:
            List of trades that were closed
        """
        closed_trades = []
        
        if data_1m_current.empty:
            return closed_trades
        
        # Get current price from the most recent candle
        current_price = data_1m_current['Close'].iloc[-1]
        
        for trade in self.open_trades[:]:  # Copy list to avoid modification during iteration
            if trade.status != "OPEN":
                continue
            
            # Check stop loss
            if self._is_stop_loss_hit(trade, current_price):
                trade.status = "CLOSED"
                trade.exit_time = current_time
                trade.exit_price = trade.stop_loss
                trade.pnl = self._calculate_pnl(trade)
                trade.exit_reason = "Stop Loss"
                closed_trades.append(trade)
                self.open_trades.remove(trade)
                continue
            
            # Check take profit
            if self._is_take_profit_hit(trade, current_price):
                trade.status = "CLOSED"
                trade.exit_time = current_time
                trade.exit_price = trade.take_profit
                trade.pnl = self._calculate_pnl(trade)
                trade.exit_reason = "Take Profit"
                closed_trades.append(trade)
                self.open_trades.remove(trade)
                continue
        
        return closed_trades
    
    def monitor_open_trades(self, current_data: Dict[str, pd.DataFrame]) -> List[TradeExecution]:
        """
        Monitor open trades and check for exit conditions
        
        Args:
            current_data: Current market data for all timeframes
            
        Returns:
            List of trades that were closed
        """
        closed_trades = []
        
        for trade in self.open_trades[:]:  # Copy list to avoid modification during iteration
            if trade.status != "OPEN":
                continue
            
            # Check stop loss and take profit
            current_price = self._get_current_price(current_data)
            
            if current_price is None:
                continue
            
            # Check stop loss
            if self._is_stop_loss_hit(trade, current_price):
                trade.status = "CLOSED"
                trade.exit_time = pd.Timestamp.now()
                trade.exit_price = trade.stop_loss
                trade.pnl = self._calculate_pnl(trade)
                trade.exit_reason = "Stop Loss"
                closed_trades.append(trade)
                self.open_trades.remove(trade)
                continue
            
            # Check take profit
            if self._is_take_profit_hit(trade, current_price):
                trade.status = "CLOSED"
                trade.exit_time = pd.Timestamp.now()
                trade.exit_price = trade.take_profit
                trade.pnl = self._calculate_pnl(trade)
                trade.exit_reason = "Take Profit"
                closed_trades.append(trade)
                self.open_trades.remove(trade)
                continue
        
        return closed_trades
    
    def run_strategy(self, 
                    data_file: str,
                    days_back: int = 30) -> Dict:
        """
        PROPER BACKTESTING ENGINE: Candle-by-candle simulation with NO LOOK-AHEAD BIAS
        
        Args:
            data_file: Path to CSV data file
            days_back: Number of days to analyze
            
        Returns:
            Strategy results and statistics
        """
        print(f"🚀 Starting PROPER Multi-Timeframe Trading Strategy for {self.symbol}")
        print(f"📊 Analyzing {days_back} days of data")
        print("⚠️  PROPER BACKTESTING: Candle-by-candle simulation")
        
        # Load and resample data
        print("📈 Loading and resampling data...")
        resampled_data = load_and_resample(data_file, days_back=days_back)
        self._resampled_data = resampled_data
        
        # Initialize results
        results = {
            'signals_generated': 0,
            'trades_executed': 0,
            'trades_closed': 0,
            'total_pnl': 0.0,
            'winning_trades': 0,
            'losing_trades': 0
        }
        
        # Get required timeframes
        data_1h = resampled_data.get('1H')
        data_15m = resampled_data.get('15M')
        data_1m = resampled_data.get('1M')
        
        if data_1h is None or data_15m is None or data_1m is None:
            print("❌ Missing required timeframe data")
            return results
        
        # PROPER BACKTESTING: Get min/max timestamps for backtesting
        start_time = max(data_1h.index[0], data_15m.index[0], data_1m.index[0])
        end_time = min(data_1h.index[-1], data_15m.index[-1], data_1m.index[-1])
        
        print(f"🔄 Backtesting from {start_time} to {end_time}")
        print("📊 Processing 15M candles (entry timeframe) candle-by-candle...")
        
        # PROPER BACKTESTING: Iterate through 15M candles (entry timeframe)
        for current_timestamp, current_candle in data_15m.loc[start_time:end_time].iterrows():
            
            # Get historical data available UP TO the current timestamp (NO FUTURE DATA)
            hist_1h = data_1h.loc[data_1h.index < current_timestamp]
            hist_15m = data_15m.loc[data_15m.index < current_timestamp]
            hist_1m = data_1m.loc[data_1m.index < current_timestamp]
            
            # Skip if not enough historical data for analysis
            if len(hist_1h) < 20 or len(hist_15m) < 20 or len(hist_1m) < 20:
                continue
            
            # STEP 1: Check 1H trend on historical data only
            trend_1h = self.analyze_1h_trend(hist_1h)
            
            # STEP 2: Check for A+ entries on 15M (include current candle)
            # We check for events on the most recent 15M candle (current_candle)
            current_15m_data = hist_15m.append(current_candle.to_frame().T)
            a_plus_events = self.find_a_plus_entries_15m(current_15m_data, trend_1h)
            
            # Process events that occurred on the current timestamp
            for event in a_plus_events:
                if event.timestamp == current_timestamp:
                    print(f"\n🎯 NEW {event.event_type.value} - {event.direction} entry at {current_timestamp}")
                    print(f"   Confidence: {event.confidence:.2f}")
                    print(f"   Price: {event.price:.5f}")
                    
                    # STEP 3: Check retracement confirmation with historical data only
                    if self.check_retracement_confirmation_point_in_time(event, current_15m_data, current_timestamp):
                        print("   ✅ Retracement confirmation passed")
                        
                        # STEP 4: Generate trade signal (entry price will be determined at execution)
                        signal = self.generate_trade_signal(event, trend_1h, current_candle['Close'])
                        
                        if signal is None:
                            print("   ❌ Failed to generate trade signal")
                            continue
                        
                        results['signals_generated'] += 1
                        self.signals.append(signal)
                        
                        print(f"   ✅ Signal generated: {signal.direction} (entry price will be determined at execution)")
                        
                        # STEP 5: Execute trade with historical 1M data only
                        trade = self.execute_trade_point_in_time(signal, 10000, hist_1m, current_timestamp)
                        
                        if trade:
                            results['trades_executed'] += 1
                            print(f"   🚀 Trade executed: {trade.position_size:.2f} units")
                        else:
                            print("   ⏳ Waiting for 1M confirmation...")
                    else:
                        print("   ⏳ Waiting for retracement confirmation...")
            
            # STEP 6: Monitor open trades with current price from the loop
            current_1m_data = data_1m.loc[data_1m.index <= current_timestamp]
            if not current_1m_data.empty:
                closed_trades = self.monitor_open_trades_point_in_time(current_1m_data, current_timestamp)
                
                # Update results with closed trades
                for trade in closed_trades:
                    results['trades_closed'] += 1
                    results['total_pnl'] += trade.pnl or 0
                    
                    if (trade.pnl or 0) > 0:
                        results['winning_trades'] += 1
                    else:
                        results['losing_trades'] += 1
        
        # Print final results
        print(f"\n🎉 PROPER BACKTESTING COMPLETE!")
        print(f"📊 Results Summary:")
        print(f"   Signals Generated: {results['signals_generated']}")
        print(f"   Trades Executed: {results['trades_executed']}")
        print(f"   Trades Closed: {results['trades_closed']}")
        print(f"   Total P&L: ${results['total_pnl']:.2f}")
        print(f"   Winning Trades: {results['winning_trades']}")
        print(f"   Losing Trades: {results['losing_trades']}")
        
        if results['trades_closed'] > 0:
            win_rate = (results['winning_trades'] / results['trades_closed']) * 100
            print(f"   Win Rate: {win_rate:.1f}%")
        
        return results
    
    def _build_market_structure(self, data: pd.DataFrame) -> List:
        """Build market structure from price data"""
        # This is a simplified implementation
        # In practice, you'd use the full market structure builder
        structure = []
        
        # Find swing highs and lows
        swing_highs, swing_lows = detect_swing_points(data, window=3)
        
        # Convert to structure points
        for timestamp, price in swing_highs:
            structure.append({
                'timestamp': timestamp,
                'price': price,
                'type': 'HH'  # Simplified
            })
        
        for timestamp, price in swing_lows:
            structure.append({
                'timestamp': timestamp,
                'price': price,
                'type': 'LL'  # Simplified
            })
        
        # Sort by timestamp
        structure.sort(key=lambda x: x['timestamp'])
        return structure
    
    def _is_trend_aligned(self, event: MarketEvent, trend: str) -> bool:
        """Check if market event aligns with the trend"""
        if trend == "uptrend":
            return event.direction == "Bullish"
        elif trend == "downtrend":
            return event.direction == "Bearish"
        else:  # sideways
            return True  # Allow both directions in sideways market
    
    def _get_current_price(self, data: Dict[str, pd.DataFrame]) -> Optional[float]:
        """Get current price from the most recent data"""
        # Use 1M data for most current price
        data_1m = data.get('1M')
        if data_1m is None or data_1m.empty:
            return None
        
        return data_1m['Close'].iloc[-1]
    
    def _is_stop_loss_hit(self, trade: TradeExecution, current_price: float) -> bool:
        """Check if stop loss is hit"""
        if trade.signal.direction == "BUY":
            return current_price <= trade.stop_loss
        else:  # SELL
            return current_price >= trade.stop_loss
    
    def _is_take_profit_hit(self, trade: TradeExecution, current_price: float) -> bool:
        """Check if take profit is hit"""
        if trade.signal.direction == "BUY":
            return current_price >= trade.take_profit
        else:  # SELL
            return current_price <= trade.take_profit
    
    def _calculate_pnl(self, trade: TradeExecution) -> float:
        """Calculate P&L for a trade"""
        if trade.exit_price is None:
            return 0.0
        
        if trade.signal.direction == "BUY":
            return (trade.exit_price - trade.entry_price) * trade.position_size
        else:  # SELL
            return (trade.entry_price - trade.exit_price) * trade.position_size
