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
    event_type: str  # NEW: explicit event type (BOS/CHOCH)
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

        # Soft-gating thresholds for trend alignment (probabilistic-style)
        # CHOCH: how confident reversal must be to allow going against prior HTF bias
        self.CHOCH_REVERSAL_ALLOW: float = 0.65   # was 0.75
        # BOS: how confident continuation must be when one TF is sideways
        self.BOS_RELAXED_ALLOW: float = 0.50      # was ~0.55
        # BOS in sideways/sideways conditions
        self.SIDEWAYS_BOS_ALLOW: float = 0.60     # was ~0.65

        # Latest 1H trend strength (0–1, based on slope/vol); used for soft gating
        self._last_trend_strength_1h: float = 1.0
        
        # --- HARD STRUCTURE LOCK STATE ---
        self._last_major_event_type: str | None = None     # "CHOCH" or "BOS"
        self._last_major_event_direction: str | None = None  # "Bullish" / "Bearish"
        
        # Initialize analyzers
        self.market_analyzer = MarketStructureAnalyzer(config={"confidence_thresholds": {"BOS": confidence_threshold, "CHOCH": confidence_threshold}})
        self.risk_manager = RiskManager(risk_per_trade=risk_per_trade,
                                        atr_period=atr_period,
                                        atr_multiplier=atr_multiplier)
        
        # Track trades and signals
        self.signals: List[TradeSignal] = []
        self.executed_trades: List[TradeExecution] = []
        self.open_trades: List[TradeExecution] = []
        self._resampled_data: Optional[Dict[str, pd.DataFrame]] = None
        
        # Caching for performance optimization
        self._trend_cache: Dict[str, str] = {}  # Cache for 1H trends
        self._trend_cache_15m: Dict[str, str] = {}  # Cache for 15M trends
        self._structure_cache: Dict[str, List] = {}  # Cache for market structures
        self._atr_cache: Dict[str, pd.Series] = {}  # Cache for ATR calculations
        
        # Statistics collection
        self.stats = {
            'total_events': 0,
            'aligned_events': 0,
            'retracement_events': 0,
            'confirmed_1m_events': 0,
            'processed_candles': 0
        }
        
    def _select_trend_with_windows(self, df: pd.DataFrame, windows: List[int], swing_window: int) -> str:
        """
        Backward-compatible wrapper: returns only trend direction.
        """
        trend, _ = self._select_trend_with_windows_with_strength(df, windows, swing_window)
        return trend

    def _select_trend_with_windows_with_strength(
        self, df: pd.DataFrame, windows: List[int], swing_window: int
    ) -> Tuple[str, float]:
        """
        Evaluate multiple lookback windows and pick the trend with the better score
        (slope / volatility), plus a normalized strength metric in [0, 1].
        Also apply a recent-swing override to avoid excessive
        'sideways' classifications in choppy data.
        """
        if df.empty:
            return "sideways", 0.0

        best_trend = "sideways"
        best_score = -float("inf")

        for w in windows:
            if len(df) < w:
                continue
            tail = df.tail(w)
            swing_highs, swing_lows = detect_swing_points(tail, window=swing_window)
            trend = detect_trend(swing_highs, swing_lows)

            closes = tail["Close"]
            slope = (closes.iloc[-1] - closes.iloc[0]) / max(1, w)
            vol = closes.pct_change().std() or 1e-8
            score = slope / vol
            if trend == "sideways":
                score *= 0.7  # lighter penalty so mild trends beat flat noise

            if score > best_score:
                best_score = score
                best_trend = trend

        # Recent-swing override: look at the last 6 swings to infer direction
        look_swings = min(60, len(df))
        tail_swings = df.tail(look_swings)
        sh, sl = detect_swing_points(tail_swings, window=swing_window)
        swing_df = []
        for ts, p in sh:
            swing_df.append((ts, p, "high"))
        for ts, p in sl:
            swing_df.append((ts, p, "low"))
        swing_df = sorted(swing_df, key=lambda x: x[0])
        if len(swing_df) >= 4:
            ups = downs = 0
            for i in range(1, len(swing_df)):
                cur = swing_df[i]
                prev = swing_df[i - 1]
                if cur[2] == prev[2]:
                    if cur[1] > prev[1]:
                        ups += 1
                    elif cur[1] < prev[1]:
                        downs += 1
            if ups >= downs + 1:
                best_trend = "uptrend"
            elif downs >= ups + 1:
                best_trend = "downtrend"

        # If still sideways, bias by overall return of the latest longest window
        if best_trend == "sideways" and len(df) >= min(windows):
            overall_tail = df.tail(max(windows))
            start_price = overall_tail["Close"].iloc[0]
            end_price = overall_tail["Close"].iloc[-1]
            overall_ret = (end_price - start_price) / max(1e-8, abs(start_price))
            if overall_ret > 0.001:  # >0.1% move
                best_trend = "uptrend"
            elif overall_ret < -0.001:  # <-0.1% move
                best_trend = "downtrend"

        # Normalize strength from score; clamp to [0,1]
        strength = 0.0
        if best_trend != "sideways":
            strength = min(1.0, max(0.0, abs(best_score) / 3.0))

        return best_trend, strength

    def analyze_1h_trend(self, data_1h: pd.DataFrame, use_cache: bool = True) -> str:
        """
        Analyze 1H trend using dual windows:
          - 12-hour window (12 bars)
          - 24-hour window (24 bars)
        Picks the one with better slope/vol score (cleaner trend).
        """
        if data_1h.empty or len(data_1h) < 20:
            return "sideways"

        if use_cache:
            cache_key = f"{data_1h.index[-1]}_{len(data_1h)}"
            if cache_key in self._trend_cache:
                # When using cache, keep last known strength as-is
                return self._trend_cache[cache_key]

        trend, strength = self._select_trend_with_windows_with_strength(
            data_1h,
            windows=[12, 24],   # 12h (faster), 24h (cleaner)
            swing_window=3
        )

        if use_cache:
            cache_key = f"{data_1h.index[-1]}_{len(data_1h)}"
            self._trend_cache[cache_key] = trend
            if len(self._trend_cache) > 1000:
                oldest_key = next(iter(self._trend_cache))
                del self._trend_cache[oldest_key]

        # Store strength for alignment logic
        self._last_trend_strength_1h = strength

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
        
        # Track total events for stats
        if hasattr(self, 'stats'):
            self.stats['total_events'] += len(events)
        
        for event in events:
            if event.confidence >= self.confidence_threshold:
                # Check trend alignment (1H + 15M trends must match)
                if self._is_trend_aligned_enhanced(event, trend_1h, data_15m):
                    # NOTE: Retracement confirmation is now done separately in point-in-time processing
                    a_plus_events.append(event)
        
        # Track aligned events for stats
        if hasattr(self, 'stats'):
            self.stats['aligned_events'] += len(a_plus_events)
        
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
        
        # Ensure 15M data covers the event and extends past it
        if data_15m_current.index.min() > event.timestamp:
            return False
        if data_15m_current.index.max() <= event.timestamp:
            return False
            
        # FIX 1: Removed outdated timestamp check that prevented retracement evaluation
        # (check_retracement must check FUTURE candles, which requires current_time > event.timestamp)

        # --- HARD BYPASS FOR STRONG BOS CONTINUATION ---
        # 1️⃣ Normalize event type (Must use event.event_type as observed in codebase)
        event_type_str = str(event.event_type).lower()
        is_bos = "bos" in event_type_str

        if is_bos:
            trend_strength_1h = getattr(self, "_last_trend_strength_1h", 1.0)
            # DEBUG PRINT
            # print(f"DEBUG: BOS Check - Strength: {trend_strength_1h:.2f}, Conf: {event.confidence:.2f}")
            if trend_strength_1h > 0.6 and event.confidence >= 0.6:
                return True


        
        # Get ATR for tolerance calculation using RiskManager
        atr_series = self.risk_manager.calculate_atr(data_15m_current)
        if atr_series is None or len(atr_series) == 0 or pd.isna(atr_series.iloc[-1]):
            return False
        
        current_atr = atr_series.iloc[-1]
        tolerance = current_atr * 1.2  # Increased from 0.5 to 1.2 ATR tolerance (REALISTIC)
        
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
        
    def _is_trend_aligned_enhanced(self, event: MarketEvent, trend_1h: str, data_15m: pd.DataFrame) -> bool:
        """
        Enhanced trend alignment check: 1H + 15M trends must match.
        Relaxed rules for sideways markets and CHOCH (reversal) events,
        while keeping BOS (continuation) stricter but still allowing
        slightly relaxed alignment.
        """
        # Analyze 15M trend using dual windows (12h = 48 bars, 24h = 96 bars)
        if len(data_15m) < 20:
            return False

        cache_key_15m = f"{data_15m.index[-1]}_{len(data_15m)}"
        if cache_key_15m in self._trend_cache_15m:
            trend_15m = self._trend_cache_15m[cache_key_15m]
        else:
            trend_15m = self._select_trend_with_windows(
                data_15m,
                windows=[48, 96],  # 12h and 24h of 15M bars
                swing_window=2
            )
            self._trend_cache_15m[cache_key_15m] = trend_15m
            if len(self._trend_cache_15m) > 1000:
                oldest_key = next(iter(self._trend_cache_15m))
                del self._trend_cache_15m[oldest_key]

        # Soft notion of HTF trend strength (0–1) from last 1H analysis
        trend_strength_1h = getattr(self, "_last_trend_strength_1h", 1.0)
        strong_down = trend_1h == "downtrend" and trend_strength_1h > 0.6
        strong_up = trend_1h == "uptrend" and trend_strength_1h > 0.6
        strong_trend = strong_down or strong_up

        is_bull = event.direction in ["BUY", "Bullish"]
        is_bear = event.direction in ["SELL", "Bearish"]
        is_choch = event.event_type == EventType.CHOCH
        is_bos = event.event_type == EventType.BOS

        # Helper: allow if both clearly align
        def aligned(up: bool) -> bool:
            if up:
                return trend_1h == "uptrend" and trend_15m == "uptrend"
            else:
                return trend_1h == "downtrend" and trend_15m == "downtrend"

        # Helper: relaxed alignment when one tf is sideways
        def relaxed(up: bool) -> bool:
            if up:
                return (trend_1h == "sideways" and trend_15m == "uptrend") or \
                       (trend_1h == "uptrend" and trend_15m == "sideways")
            else:
                return (trend_1h == "sideways" and trend_15m == "downtrend") or \
                       (trend_1h == "downtrend" and trend_15m == "sideways")

        # Helper: sideways-sideways allowance for strong events
        def sideways_high_confidence() -> bool:
            return trend_1h == "sideways" and trend_15m == "sideways" and event.confidence >= 0.5

        # CHOCH (reversal) – be more permissive (trend change signal)
        if is_choch:
            if is_bull:
                if aligned(True) or relaxed(True) or sideways_high_confidence():
                    # Only block if clear, strong opposite HTF trend
                    return not (strong_down and trend_15m == "downtrend")
                # Allow reversal against current strong 1H only if 15M flips hard with high confidence
                if strong_down and trend_15m == "uptrend" and event.confidence >= self.CHOCH_REVERSAL_ALLOW:
                    return True
            if is_bear:
                if aligned(False) or relaxed(False) or sideways_high_confidence():
                    return not (strong_up and trend_15m == "uptrend")
                if strong_up and trend_15m == "downtrend" and event.confidence >= self.CHOCH_REVERSAL_ALLOW:
                    return True
            return False

        # BOS (continuation) – keep stricter, but allow relaxed if confidence high
        if is_bos:
            if is_bull:
                # In a strong HTF uptrend/downtrend, BOS is continuation – allow more easily
                if strong_trend and event.confidence >= self.BOS_RELAXED_ALLOW:
                    return True
                if aligned(True):
                    return True
                if relaxed(True) and event.confidence >= self.BOS_RELAXED_ALLOW:
                    return True
                # Allow sideways+sideways only for very strong BOS
                if sideways_high_confidence() and event.confidence >= self.SIDEWAYS_BOS_ALLOW:
                    return True
                return False
            if is_bear:
                if strong_trend and event.confidence >= self.BOS_RELAXED_ALLOW:
                    return True
                if aligned(False):
                    return True
                if relaxed(False) and event.confidence >= self.BOS_RELAXED_ALLOW:
                    return True
                if sideways_high_confidence() and event.confidence >= self.SIDEWAYS_BOS_ALLOW:
                    return True
                return False

        # Fallback for any other event types (treat like BOS strict)
        if is_bull:
            return aligned(True) or (relaxed(True) and event.confidence >= 0.7)
        if is_bear:
            return aligned(False) or (relaxed(False) and event.confidence >= 0.7)

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
            
        # FIX 3: Removed faulty fallback that referenced undefined 'event' variable
        
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
            event_type=event.event_type.value,  # NEW
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
        # --- HARD STRUCTURE LOCK (EXECUTION LEVEL) ---
        # Rule: Only ONE CHOCH per structure leg. Must wait for BOS to unlock.
        
        # NOTE: signal.event_type is a string ("BOS" or "CHOCH"), so we compare with .value
        if signal.event_type == EventType.CHOCH.value:
            if (
                self._last_major_event_type == "CHOCH"
                and self._last_major_event_direction == signal.direction
            ):
                print(
                    f"🔒 EXECUTION LOCK: {signal.direction} CHOCH rejected "
                    f"(Waiting for BOS to unlock structure)"
                )
                return None

        # Wait for 1M confirmation
        if not self.confirm_1m_signal(data_1m, signal.direction, signal.timestamp, signal.event_type):
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
                    start_market_price = signal.entry_price
                    stop_loss, take_profit = self.risk_manager.compute_stop_and_target_from_atr(
                        start_market_price,
                        signal.direction,
                        atr_value,
                        self.risk_reward_ratio,
                        self.symbol
                    )

        # IMPROVED: Reduced risk sizing (1% instead of 2%)
        risk_amount = self.risk_manager.risk_amount_for_balance(account_balance)
        stop_loss_distance = abs(signal.entry_price - stop_loss)
        if stop_loss_distance == 0:
            return None
        position_size = self.risk_manager.calculate_position_size(
            entry_price=signal.entry_price,
            stop_loss=stop_loss,
            risk_amount=risk_amount,
            account_balance=account_balance,
            symbol=self.symbol
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
        
        # --- UPDATE STRUCTURE STATE AFTER SUCCESSFUL EXECUTION ---
        self._last_major_event_type = signal.event_type
        self._last_major_event_direction = signal.direction
        
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
        # --- HARD STRUCTURE LOCK (EXECUTION LEVEL) ---
        # Rule: Only ONE CHOCH per structure leg. Must wait for BOS to unlock.
        
        # NOTE: signal.event_type is a string ("BOS" or "CHOCH"), so we compare with .value
        if signal.event_type == EventType.CHOCH.value:
            if (
                self._last_major_event_type == "CHOCH"
                and self._last_major_event_direction == signal.direction
            ):
                print(
                    f"🔒 EXECUTION LOCK: {signal.direction} CHOCH rejected "
                    f"(Waiting for BOS to unlock structure)"
                )
                return None

        # CRITICAL FIX: Get the actual entry price from 1M confirmation candle
        confirmation_candle = self._get_confirmation_candle_price(data_1m_current, signal.direction, signal.timestamp, current_time, signal.event_type)
        if confirmation_candle is None:
            return None
        
        actual_entry_price = confirmation_candle['Close']  # Use close of confirmation candle
        
        # Wait for 1M confirmation with current data only
        if not self.confirm_1m_signal_point_in_time(data_1m_current, signal.direction, signal.timestamp, current_time, signal.event_type):
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
                            actual_entry_price,
                            signal.direction,
                            atr_value,
                            self.risk_reward_ratio,
                            self.symbol
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
        
        # --- UPDATE STRUCTURE STATE AFTER SUCCESSFUL EXECUTION ---
        self._last_major_event_type = signal.event_type
        self._last_major_event_direction = signal.direction
        
        return trade
    
    def _get_confirmation_candle_price(self, 
                                     data_1m_current: pd.DataFrame, 
                                     signal_direction: str, 
                                     entry_time: pd.Timestamp,
                                     current_time: pd.Timestamp,
                                     event_type: str = "BOS") -> Optional[pd.Series]:
        """
        Get the actual confirmation candle price using Asymmetric Logic
        
        Args:
            data_1m_current: 1M data up to current time only
            signal_direction: BUY or SELL
            entry_time: When the signal was generated
            current_time: Current timestamp
            event_type: BOS or CHOCH
            
        Returns:
            Confirmation candle data or None if not found
        """
        # Find 1M candles after the entry signal time
        future_candles = data_1m_current[data_1m_current.index > entry_time]
        if future_candles.empty:
            return None
        
        # Get the first 1M candle that occurred after the entry signal time
        confirmation_candle = future_candles.iloc[0]
        
        # Apply the same logic as confirm_1m_signal
        
        # Check if this candle WOULD confirm the signal
        is_confirmed = False
        
        # Calculate candle metrics
        candle_range = confirmation_candle['High'] - confirmation_candle['Low']
        body_size = abs(confirmation_candle['Close'] - confirmation_candle['Open'])
        body_ratio = body_size / candle_range if candle_range > 0 else 0
        
        # Volume filter
        volume_confirmation = True
        if 'Volume' in data_1m_current.columns and data_1m_current['Volume'].sum() > 0:
            recent_volume = data_1m_current['Volume'].tail(20).mean()
            volume_ratio = confirmation_candle['Volume'] / recent_volume if recent_volume > 0 else 1
            volume_confirmation = volume_ratio >= 1.1
            
        # Direction
        is_green = confirmation_candle['Close'] > confirmation_candle['Open']
        is_red = confirmation_candle['Close'] < confirmation_candle['Open']
        
        # Micro BOS check
        has_micro_bos = False
        recent_1m = data_1m_current[data_1m_current.index < confirmation_candle.name].tail(30)
        if len(recent_1m) >= 5:
            swings_high, swings_low = detect_swing_points(recent_1m, window=3)
            if signal_direction == "BUY":
                if swings_high:
                    recent_high = swings_high[-1][1]
                    if confirmation_candle['Close'] > recent_high:
                        has_micro_bos = True
            elif signal_direction == "SELL":
                 if swings_low:
                    recent_low = swings_low[-1][1]
                    if confirmation_candle['Close'] < recent_low:
                        has_micro_bos = True
        
        # Verify Confirmation
        if event_type == "CHOCH":
            if signal_direction == "BUY":
                is_momentum = is_green and (body_ratio >= 0.3 or volume_confirmation)
                is_confirmed = is_momentum or has_micro_bos
            elif signal_direction == "SELL":
                is_momentum = is_red and (body_ratio >= 0.3 or volume_confirmation)
                is_confirmed = is_momentum or has_micro_bos
        else: # BOS
            if signal_direction == "BUY":
                is_confirmed = has_micro_bos
            elif signal_direction == "SELL":
                is_confirmed = has_micro_bos
                
        if not is_confirmed:
            return None
            
        return confirmation_candle
    
    def confirm_1m_signal_point_in_time(self, 
                                       data_1m_current: pd.DataFrame, 
                                       signal_direction: str, 
                                       entry_time: pd.Timestamp,
                                       current_time: pd.Timestamp,
                                       event_type: str = "BOS") -> bool:
        """
        IMPROVED: Asymmetric 1M signal confirmation (Weaker for CHOCH, Stronger for BOS)
        
        Args:
            data_1m_current: 1M data up to current time only
            signal_direction: "BUY" or "SELL"
            entry_time: Timestamp of the entry signal
            current_time: Current timestamp
            event_type: "BOS" or "CHOCH"
            
        Returns:
            True if confirmation is valid, False otherwise
        """
        if data_1m_current.empty or len(data_1m_current) < 20:
            return False
        
        # Get the first 1M candle after entry time but before current time
        future_candles = data_1m_current[
            (data_1m_current.index > entry_time) & 
            (data_1m_current.index <= current_time)
        ]
        if future_candles.empty:
            return False
        
        next_candle = future_candles.iloc[0]
        
        # Calculate candle metrics
        candle_range = next_candle['High'] - next_candle['Low']
        body_size = abs(next_candle['Close'] - next_candle['Open'])
        body_ratio = body_size / candle_range if candle_range > 0 else 0
        
        # Volume filter
        volume_confirmation = True
        if 'Volume' in data_1m_current.columns and data_1m_current['Volume'].sum() > 0:
            recent_volume = data_1m_current['Volume'].tail(20).mean()
            volume_ratio = next_candle['Volume'] / recent_volume if recent_volume > 0 else 1
            volume_confirmation = volume_ratio >= 1.1

        # --- 1M DISPLACEMENT FILTER (CHOCH ONLY) ---
        if event_type == "CHOCH":
            # RE-INTRODUCED: 1M Displacement Logic
            # Lookahead 8 minutes (candles) to measure momentum
            
            # Using data_1m_current: We need candles strictly AFTER the entry time.
            # But point-in-time constraints mean we might not have all 8 candles yet if current_time is close to entry.
            # However, logic dictates we should check what we have or wait? 
            # Given instructions: "validate_choch_displacement ... if >= 0.6"
            
            # Get candles after entry
            post_entry_candles = data_1m_current[data_1m_current.index > entry_time]
            lookahead_limit = 8
            
            # If we don't have enough data yet, we might want to wait, or check what we have.
            # Assuming we check what is available up to current_time (point-in-time correctness).
            lookahead = post_entry_candles.iloc[:lookahead_limit] # Up to 8 candles
            
            # Only proceed if we have at least 1-2 candles to measure SOMETHING
            if not lookahead.empty:
                # Calculate ATR on 1M
                atr_1m_series = self.risk_manager.calculate_atr(data_1m_current)
                atr_1m = atr_1m_series.iloc[-1] if (atr_1m_series is not None and not atr_1m_series.empty) else 0.0
                
                if atr_1m > 0:
                    max_move = 0.0
                    entry_price_ref = next_candle['Open'] # Or use the signal price if available? 
                    # The function signature has no price, but we have next_candle (the confirmation candle).
                    # Better to use the Open of the first confirmation candle as proxy for "CHOCH Price" level 
                    # or better yet, simply measure from the start of the move. 
                    # User pseudo-code: "choch_price". 
                    # Let's use the first available candle Open or Close.
                    ref_price = next_candle['Open'] 
                    
                    if signal_direction == "BUY" or signal_direction == "Bullish":
                        max_high = lookahead["High"].max()
                        max_move = max_high - ref_price
                    else:
                        min_low = lookahead["Low"].min()
                        max_move = ref_price - min_low
                        
                    displacement = max_move / atr_1m
                    
                    displacement = max_move / atr_1m
                    
                    # LOGGING as requested
                    log_msg = [
                        f"🔍 CHOCH @ {entry_time} | Dir: {signal_direction}",
                        f"   ATR_1M: {atr_1m:.5f} | MaxMove: {max_move:.5f}",
                        f"   Displacement: {displacement:.2f} (Req: 0.6)"
                    ]
                    
                    # Write to file directly to bypass stdout issues
                    try:
                        with open("choch_debug.log", "a", encoding="utf-8") as f:
                            for msg in log_msg:
                                f.write(msg + "\n")
                                print(msg) # Still print for console users
                    except Exception:
                        pass # Ignore file write errors
                    
                    if displacement >= 0.6:
                         print("   Result: PASS ✅")
                         with open("choch_debug.log", "a", encoding="utf-8") as f: f.write("   Result: PASS ✅\n")
                    else:
                         print("   Result: FAIL ❌")
                         with open("choch_debug.log", "a", encoding="utf-8") as f: f.write("   Result: FAIL ❌\n")
                         return False # Enforce filter
        
        # Direction confirmation
        is_green = next_candle['Close'] > next_candle['Open']
        is_red = next_candle['Close'] < next_candle['Open']
        
        # --- ASYMMETRIC LOGIC ---
        
        # Helper: Check for micro BOS (break of recent 1M swing)
        has_micro_bos = False
        # Get recent 1M data before the confirmation candle
        recent_1m = data_1m_current[data_1m_current.index < next_candle.name].tail(30)
        if len(recent_1m) >= 5:
            swings_high, swings_low = detect_swing_points(recent_1m, window=3)
            
            if signal_direction == "BUY":
                # Check for break of recent swing high
                if swings_high:
                    recent_high = swings_high[-1][1] # (timestamp, price)
                    if next_candle['Close'] > recent_high:
                        has_micro_bos = True
                        
            elif signal_direction == "SELL":
                 # Check for break of recent swing low
                if swings_low:
                    recent_low = swings_low[-1][1]
                    if next_candle['Close'] < recent_low:
                        has_micro_bos = True
        
        # CHOCH Logic: Allow if (Momentum OR Volume OR Micro BOS)
        if event_type == "CHOCH":
            if signal_direction == "BUY":
                is_momentum = is_green and (body_ratio >= 0.3 or volume_confirmation)
                if has_micro_bos:
                    print(f"✅ 1M CONFIRM (CHOCH): micro BOS - {next_candle.name}")
                    return True
                elif is_momentum:
                    print(f"✅ 1M CONFIRM (CHOCH): micro momentum - {next_candle.name}")
                    return True
                else:
                    print(f"❌ 1M REJECT (CHOCH) - {next_candle.name}")
                    return False
            elif signal_direction == "SELL":
                is_momentum = is_red and (body_ratio >= 0.3 or volume_confirmation)
                if has_micro_bos:
                    print(f"✅ 1M CONFIRM (CHOCH): micro BOS - {next_candle.name}")
                    return True
                elif is_momentum:
                    print(f"✅ 1M CONFIRM (CHOCH): micro momentum - {next_candle.name}")
                    return True
                else:
                    print(f"❌ 1M REJECT (CHOCH) - {next_candle.name}")
                    return False

        # BOS Logic: Require Micro BOS (Structure)
        else: # BOS or others
            if signal_direction == "BUY":
                if has_micro_bos:
                    print(f"✅ 1M CONFIRM (BOS): micro BOS - {next_candle.name}")
                    return True
                else:
                    print(f"❌ 1M REJECT (BOS): no BOS - {next_candle.name}")
                    return False
            elif signal_direction == "SELL":
                if has_micro_bos:
                    print(f"✅ 1M CONFIRM (BOS): micro BOS - {next_candle.name}")
                    return True
                else:
                    print(f"❌ 1M REJECT (BOS): no BOS - {next_candle.name}")
                    return False

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
        # Initialize/Reset results
        self.stats = {
            'total_events': 0,
            'aligned_events': 0,
            'retracement_events': 0,
            'confirmed_1m_events': 0,
            'processed_candles': 0
        }

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
        
        # OPTIMIZATION: Pre-compute 1H trend for each timestamp to avoid repeated calculations
        # We'll update trend only when we have enough new data
        last_trend_update_idx = 0
        trend_1h = "sideways"
        
        # PROPER BACKTESTING: Iterate through 15M candles (entry timeframe)
        for idx, (current_timestamp, current_candle) in enumerate(data_15m.loc[start_time:end_time].iterrows()):
            
            self.stats['processed_candles'] += 1
            
            # Get historical data available UP TO the current timestamp (NO FUTURE DATA)
            hist_1h = data_1h.loc[data_1h.index < current_timestamp]
            hist_15m = data_15m.loc[data_15m.index < current_timestamp]
            hist_1m = data_1m.loc[data_1m.index < current_timestamp]
            
            # Skip if not enough historical data for analysis
            if len(hist_1h) < 20 or len(hist_15m) < 20 or len(hist_1m) < 20:
                continue
            
            # OPTIMIZATION: Update 1H trend only every 4 candles (1 hour) instead of every candle
            # This reduces redundant calculations while maintaining accuracy
            if idx - last_trend_update_idx >= 4 or idx == 0:
                trend_1h = self.analyze_1h_trend(hist_1h, use_cache=True)
                last_trend_update_idx = idx
            
            # STEP 2: Check for A+ entries on 15M (include current candle)
            # We check for events on the most recent 15M candle (current_candle)
            current_15m_data = pd.concat([hist_15m, current_candle.to_frame().T])
            # Stats for total/aligned events are updated inside this method
            a_plus_events = self.find_a_plus_entries_15m(current_15m_data, trend_1h)
            
            # Process events that occurred on the current timestamp
            for event in a_plus_events:
                # FIX 2: Check for ANY unconfirmed event in the past (not just 'now')
                # Retracement takes time, so we must check T+1, T+2...
                if event.timestamp < current_timestamp:
                    
                    # Deduplication: Don't re-process events we already have signals for
                    event_id = f"{event.event_type.value} - {event.direction}"
                    already_signaled = False
                    for s in self.signals:
                        if s.timestamp == event.timestamp and s.timeframe_15m_entry == event_id:
                            already_signaled = True
                            break
                    if already_signaled:
                        continue
                        
                    # Also skip if event is too old (> 2 days) to avoid performance degradation
                    if (current_timestamp - event.timestamp).total_seconds() > 172800:
                         continue
                    print(f"\n🎯 NEW {event.event_type.value} - {event.direction} entry at {current_timestamp}")
                    print(f"   Confidence: {event.confidence:.2f}")
                    print(f"   Price: {event.price:.5f}")
                    
                    # STEP 3: Check retracement confirmation with historical data only
                    if self.check_retracement_confirmation_point_in_time(event, current_15m_data, current_timestamp):
                        print("   ✅ Retracement confirmation passed")
                        self.stats['retracement_events'] += 1
                        
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
                            self.stats['confirmed_1m_events'] += 1
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
            
            # Calculate Avg R
            total_r = 0
            for trade in self.executed_trades:
                if trade.status == "CLOSED" and trade.pnl is not None and trade.stop_loss is not None:
                    risk = abs(trade.entry_price - trade.stop_loss) * trade.position_size
                    if risk > 0:
                        r_multiple = trade.pnl / risk
                        total_r += r_multiple
            
            avg_r = total_r / results['trades_closed']
            print(f"   Avg R: {avg_r:.2f}R")
            
        print("\n📊 Detailed Funnel Metrics:")
        print(f"   1. Total Events: {self.stats['total_events']}")
        print(f"   2. Events Passing Alignment: {self.stats['aligned_events']}")
        print(f"   3. Events After Retracement: {self.stats['retracement_events']}")
        print(f"   4. Events After 1M Confirmation: {self.stats['confirmed_1m_events']}")
        print(f"   5. Final Trades Executed: {results['trades_executed']}")
        
        return results
    
    def _build_market_structure(self, data: pd.DataFrame) -> List:
        """Build market structure from price data using proper structure builder"""
        from .structure_builder import build_market_structure
        
        # Use lower prominence factor for better signal detection
        prominence_factor = 1.5  # Much lower than default 7.5
        structure = build_market_structure(data, prominence_factor=prominence_factor)
        
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
