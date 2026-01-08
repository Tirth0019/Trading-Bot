import pandas as pd  # type: ignore
import numpy as np  # type: ignore
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
    broken_level: Optional[Dict] = None  # Store broken level info for BOS follow-through validation
    context: Optional[Dict] = None  # Store additional context (market phase, etc.)

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

        # --- BOS FOLLOW-THROUGH PARAMETERS ---
        self.MIN_BOS_DISPLACEMENT_ATR = 0.5   # conservative, can tune later
        self.MIN_BOS_BODY_RATIO = 0.6         # body / candle range

        # Latest 1H trend strength (0–1, based on slope/vol); used for soft gating
        self._last_trend_strength_1h: float = 1.0
        
        # --- HARD STRUCTURE LOCK STATE ---
        self._last_major_event_type: str | None = None     # "CHOCH" or "BOS"
        self._last_major_event_direction: str | None = None  # "Bullish" / "Bearish"
        self._last_choch_level: float | None = None  # Track last CHOCH broken level for de-duplication
        
        # --- CHOCH-BOS CONFIRMATION STATE (Institutional Filter) ---
        self._last_choch_direction: str | None = None  # Direction of last CHOCH
        self._bos_confirmed_after_choch: bool = False  # True only after BOS confirms CHOCH direction
        
        # --- CHOCH COOLDOWN STATE (Fix explosion loop) ---
        self._last_choch_timestamp: pd.Timestamp | None = None  # Track last CHOCH timestamp for cooldown
        self._last_choch_price: float | None = None  # Track last CHOCH price for cooldown
        self.CHOCH_COOLDOWN_CANDLES: int = 6  # Cooldown window in 15M candles (4-8 range, using 6)
        
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
        
        # Detailed trade logging for analysis
        self.detailed_trade_logs: List[Dict] = []  # Comprehensive metrics per trade
        
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
            'processed_candles': 0,
            'bos_rejected_displacement': 0,  # Track BOS rejections by displacement
            'bos_rejected_body_ratio': 0,     # Track BOS rejections by body ratio
            'bos_rejected_other': 0,         # Track other BOS rejections
            'rejected_distribution': 0,       # Track expansion/distribution filter rejections
            # Retracement debug counters (STEP 5)
            'retracement_reject_no_expansion': 0,
            'retracement_reject_expired': 0,
            'retracement_reject_too_shallow': 0,
            'retracement_reject_too_deep': 0,
            'retracement_reject_no_reversal': 0
        }
        
        # --- RETRACEMENT WINDOW STATE (STEP 1) ---
        self._pending_choch: Dict | None = None  # Track pending CHOCH awaiting retracement
        self._retracement_window_candles: int = 12  # 12 x 15M = 3 hours window
        
        # DEBUG: Confirm executor persistence
        print("Executor initialized", id(self))
        
        # FINAL SAFEGUARD: Prevent accidental re-initialization
        assert not hasattr(self, "_initialized"), "❌ CRITICAL ERROR: Executor re-initialized! Singleton pattern violated."
        self._initialized = True
        
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
        RETRACEMENT WINDOW LOGIC: Check retracement within a time window, not immediately.
        
        STEP 1-5 Implementation:
        - Window-based retracement (not immediate)
        - Requires expansion before retracement
        - Relaxed depth for XAUUSD (0.25-0.382)
        - Checks for touch (not just close)
        - Debug counters for failure reasons
        
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
        
        # --- STEP 3: Retracement requires expansion FIRST ---
        # Check if expansion happened since CHOCH (required before retracement)
        if event.event_type == EventType.CHOCH:
            event_time = event.timestamp
            # Get data after CHOCH
            post_choch_data = data_15m_current[
                (data_15m_current.index > event_time) & 
                (data_15m_current.index <= current_time)
            ]
            
            if len(post_choch_data) >= 6:
                # Calculate ATR for expansion check
                atr_series = self.risk_manager.calculate_atr(data_15m_current)
                if atr_series is not None and len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]):
                    atr_value = atr_series.iloc[-1]
                    
                    # Find event index in 15M data
                    event_idx = None
                    for idx, ts in enumerate(data_15m_current.index):
                        if ts >= event_time:
                            event_idx = idx
                            break
                    
                    if event_idx is not None:
                        # Check expansion (reuse existing expansion logic)
                        is_expanding = self.is_market_expanding(data_15m_current, event_idx, atr_value)
                        if not is_expanding:
                            self.stats['retracement_reject_no_expansion'] += 1
                            if hasattr(self, 'debug') and self.debug:
                                print(f"    Retracement REJECTED: No expansion seen since CHOCH")
                            return False
        
        # --- STEP 1: Window-based retracement (not immediate) ---
        # Get ATR for tolerance calculation
        atr_series = self.risk_manager.calculate_atr(data_15m_current)
        if atr_series is None or len(atr_series) == 0 or pd.isna(atr_series.iloc[-1]):
            return False
        
        current_atr = atr_series.iloc[-1]
        
        # --- STEP 2: Relaxed retracement depth for XAUUSD (0.25-0.382) ---
        # For XAUUSD: shallow retraces are common, use 0.25-0.382 range
        min_retrace_ratio = 0.25  # Minimum retracement depth
        max_retrace_ratio = 0.382  # Maximum retracement depth (Fibonacci)
        tolerance = current_atr * 0.5  # Reduced tolerance for gold (was 1.2)
        
        # Get recent price data after the event but before current time
        event_time = event.timestamp
        
        # Calculate window expiry (12 candles = 3 hours)
        event_idx = None
        for idx, ts in enumerate(data_15m_current.index):
            if ts >= event_time:
                event_idx = idx
                break
        
        if event_idx is None:
            return False
        
        # Check if window expired
        current_idx = len(data_15m_current) - 1
        candles_since = current_idx - event_idx
        if candles_since > self._retracement_window_candles:
            self.stats['retracement_reject_expired'] += 1
            if hasattr(self, 'debug') and self.debug:
                print(f"    Retracement REJECTED: Window expired ({candles_since}/{self._retracement_window_candles} candles)")
            return False
        
        # Get candles in window
        window_data = data_15m_current[
            (data_15m_current.index > event_time) & 
            (data_15m_current.index <= current_time)
        ]
        
        if window_data.empty:
            return False
        
        # --- BOS: Allow immediate continuation (bypass retracement for strong BOS) ---
        if event.event_type == EventType.BOS:
            trend_strength_1h = getattr(self, "_last_trend_strength_1h", 1.0)
            if trend_strength_1h > 0.6 and event.confidence >= 0.6:
                return True  # Strong BOS bypasses retracement
        
        # --- STEP 4: Check for touch (not just close) ---
        # --- STEP 2: Validate retracement depth (25-38.2% for XAUUSD) ---
        broken_level = event.price
        retracement_found = False
        retracement_candle_idx = None
        
        # Calculate move size from CHOCH to validate retracement depth
        if event.direction in ["BUY", "Bullish"]:
            # Bullish CHOCH: price broke up, calculate move up, then retrace down
            move_size = window_data['High'].max() - broken_level
            if move_size > 0:
                min_retrace_target = broken_level + (move_size * min_retrace_ratio)
                max_retrace_target = broken_level + (move_size * max_retrace_ratio)
            else:
                # No move yet, just check if price touched broken level
                min_retrace_target = broken_level - tolerance
                max_retrace_target = broken_level + tolerance
        else:  # Bearish
            # Bearish CHOCH: price broke down, calculate move down, then retrace up
            move_size = broken_level - window_data['Low'].min()
            if move_size > 0:
                min_retrace_target = broken_level - (move_size * max_retrace_ratio)  # Max retrace = deeper
                max_retrace_target = broken_level - (move_size * min_retrace_ratio)  # Min retrace = shallower
            else:
                # No move yet, just check if price touched broken level
                min_retrace_target = broken_level - tolerance
                max_retrace_target = broken_level + tolerance
        
        # Find retracement to target level (touch check, not close)
        # For CHOCH: Price must retrace to broken level within 25-38.2% depth
        for i, (_, candle) in enumerate(window_data.iterrows()):
            # Check if price TOUCHED the retracement target (within tolerance)
            # Touch means: Low <= level <= High (candle body touched level)
            if event.direction in ["BUY", "Bullish"]:
                # Bullish: price should retrace DOWN to broken level
                # Check if low touched the retracement range
                if (candle['Low'] <= max_retrace_target + tolerance and 
                    candle['High'] >= min_retrace_target - tolerance):
                    # Validate it's not too deep (below min_retrace_target)
                    if candle['Low'] >= min_retrace_target - tolerance:
                        retracement_found = True
                        retracement_candle_idx = i
                        break
                    else:
                        # Too deep retracement
                        self.stats['retracement_reject_too_deep'] += 1
                        if hasattr(self, 'debug') and self.debug:
                            print(f"    Retracement REJECTED: Too deep (Low: {candle['Low']:.2f}, Target: {min_retrace_target:.2f}-{max_retrace_target:.2f})")
            else:  # Bearish
                # Bearish: price should retrace UP to broken level
                # Check if high touched the retracement range
                if (candle['High'] >= min_retrace_target - tolerance and 
                    candle['Low'] <= max_retrace_target + tolerance):
                    # Validate it's not too deep (above max_retrace_target)
                    if candle['High'] <= max_retrace_target + tolerance:
                        retracement_found = True
                        retracement_candle_idx = i
                        break
                    else:
                        # Too deep retracement
                        self.stats['retracement_reject_too_deep'] += 1
                        if hasattr(self, 'debug') and self.debug:
                            print(f"    Retracement REJECTED: Too deep (High: {candle['High']:.2f}, Target: {min_retrace_target:.2f}-{max_retrace_target:.2f})")
        
        if not retracement_found:
            if candles_since >= 3:  # Only log if we've had a few candles
                self.stats['retracement_reject_too_shallow'] += 1
                if hasattr(self, 'debug') and self.debug:
                    print(f"    Retracement REJECTED: Too shallow or no touch yet ({candles_since} candles since event)")
            return False
        
        # --- STEP 6: Reaction Confirmation (15M) - NOT Reversal ---
        # CHOCH retracement doesn't guarantee reversal on 15M
        # Reversal happens on 5M/1M - 15M just needs to show "level respect" (reaction)
        
        # Get the retracement candle and next candle for reaction check
        if retracement_candle_idx is None:
            return False
        
        retracement_candle = window_data.iloc[retracement_candle_idx]
        
        # Check for reaction (not reversal) - just means "price respected the level"
        reaction_confirmed = self._has_reaction_at_level(retracement_candle, broken_level, tolerance, event.direction)
        
        # If we have a next candle, also check it for reaction
        if retracement_candle_idx < len(window_data) - 1:
            next_candle = window_data.iloc[retracement_candle_idx + 1]
            reaction_confirmed = reaction_confirmed or self._has_reaction_at_level(next_candle, broken_level, tolerance, event.direction)
        
        if not reaction_confirmed:
            self.stats['retracement_reject_no_reversal'] += 1  # Keep counter name for consistency
            if hasattr(self, 'debug') and self.debug:
                print(f"    Retracement REJECTED: No reaction at level (price didn't respect level)")
        
        return reaction_confirmed
        
    def _is_trend_aligned_enhanced(self, event: MarketEvent, trend_1h: str, data_15m: pd.DataFrame) -> bool:
        """
        Enhanced trend alignment check: 1H + 15M trends must match.
        
        CRITICAL LOGIC:
        - CHOCH (reversal): Skip HTF alignment - trend change expected
        - BOS (continuation): Require HTF alignment - continuation trade
        """
        # CRITICAL FIX: CHOCH bypasses HTF alignment (trend change signal)
        if event.event_type == EventType.CHOCH:
            return True  # Allow CHOCH to pass - alignment will confirm after BOS
        
        # BOS requires HTF alignment (continuation trade)
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
    

    
    def _has_reaction_at_level(self, candle: pd.Series, level: float, tolerance: float, direction: str) -> bool:
        """
        STEP 6: Check for reaction at level (15M) - NOT reversal.
        
        Reaction means "price respected the level" - any of:
        - Long wick (rejection)
        - Inside bar (consolidation)
        - Small body (momentum slowdown)
        - Failed continuation (price didn't break through)
        
        This is less strict than reversal - just checks if level was respected.
        True reversal logic belongs in 1M confirmation.
        
        Args:
            candle: Candle to check
            level: Broken level (CHOCH/BOS level)
            tolerance: Price tolerance
            direction: Event direction ("BUY"/"Bullish" or "SELL"/"Bearish")
            
        Returns:
            True if reaction is confirmed
        """
        # Check if candle is near the level
        if not (candle['Low'] <= level + tolerance and candle['High'] >= level - tolerance):
            return False
        
        candle_range = candle['High'] - candle['Low']
        if candle_range == 0:
            return False
        
        candle_body = abs(candle['Close'] - candle['Open'])
        body_ratio = candle_body / candle_range
        
        # Calculate wick sizes
        if candle['Close'] > candle['Open']:  # Bullish candle
            upper_wick = candle['High'] - candle['Close']
            lower_wick = candle['Open'] - candle['Low']
        else:  # Bearish candle
            upper_wick = candle['High'] - candle['Open']
            lower_wick = candle['Close'] - candle['Low']
        
        upper_wick_ratio = upper_wick / candle_range if candle_range > 0 else 0
        lower_wick_ratio = lower_wick / candle_range if candle_range > 0 else 0
        
        # Tier 1 - Reaction Conditions (ANY of these):
        # 1. Long rejection wick (price rejected the level)
        if direction in ["BUY", "Bullish"]:
            # Bullish: long lower wick = rejection of lower prices
            if lower_wick_ratio > 0.4:
                return True
        else:  # Bearish
            # Bearish: long upper wick = rejection of higher prices
            if upper_wick_ratio > 0.4:
                return True
        
        # 2. Small body (momentum slowdown - indecisive at level)
        if body_ratio < 0.3:
            return True
        
        # 3. Inside bar (consolidation at level)
        # Note: This requires previous candle, so we'll check in the calling function
        # For now, small body is a proxy for inside bar behavior
        
        # 4. Failed continuation (price touched level but didn't break through)
        if direction in ["BUY", "Bullish"]:
            # Bullish: price touched level from above but didn't break below
            if candle['Low'] <= level + tolerance and candle['Close'] >= level - tolerance:
                return True
        else:  # Bearish
            # Bearish: price touched level from below but didn't break above
            if candle['High'] >= level - tolerance and candle['Close'] <= level + tolerance:
                return True
        
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
    
    def is_market_expanding(self, df_15m: pd.DataFrame, event_index: int, atr_value: float) -> bool:
        """
        Checks if market is in expansion phase after structure event.
        
        Uses 3 measurable signals (ANY 2 must pass):
        1. Range Expansion: Recent candles cover more range than before
        2. Momentum Expansion: Candle bodies are large (not wicks)
        3. Speed Expansion: Price moves quickly away from structure
        
        Args:
            df_15m: 15M timeframe DataFrame
            event_index: Index of the structure event candle
            atr_value: Current ATR value for speed calculation
            
        Returns:
            True if market is expanding (at least 2 of 3 conditions pass), False otherwise
        """
        lookback = 6  # candles after event
        
        # Check if we have enough data
        if event_index + lookback >= len(df_15m):
            return False
        
        if event_index - lookback < 0:
            return False
        
        # Get recent candles (after event) and prior candles (before event)
        recent = df_15m.iloc[event_index + 1 : event_index + 1 + lookback]
        prior = df_15m.iloc[event_index - lookback : event_index]
        
        if len(recent) < lookback or len(prior) < lookback:
            return False
        
        # --- 1. Range Expansion ---
        recent_range = (recent["High"] - recent["Low"]).mean()
        prior_range = (prior["High"] - prior["Low"]).mean()
        range_expansion = recent_range > 1.3 * prior_range if prior_range > 0 else False
        
        # --- 2. Momentum Expansion ---
        body_ratio = (recent["Close"] - recent["Open"]).abs() / (recent["High"] - recent["Low"])
        # Avoid division by zero
        body_ratio = body_ratio.replace([np.inf, -np.inf], 0).fillna(0)
        momentum_expansion = body_ratio.mean() > 0.55
        
        # --- 3. Speed Expansion ---
        displacement = abs(recent["Close"].iloc[-1] - recent["Open"].iloc[0])
        speed_expansion = displacement > 1.2 * atr_value if atr_value > 0 else False
        
        # Count how many conditions passed
        passed = sum([
            range_expansion,
            momentum_expansion,
            speed_expansion
        ])
        
        return passed >= 2
    
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
            take_profit_pips=self.stop_loss_pips * self.risk_reward_ratio,
            broken_level=event.broken_level,  # Store broken level for BOS follow-through validation
            context={}  # Initialize context for market phase tracking
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
            # DEBUG: Verify Lock State
            print(
                "LOCK CHECK",
                signal.event_type,
                signal.direction,
                self._last_major_event_type,
                self._last_major_event_direction
            )
            
            if (
                self._last_major_event_type == "CHOCH"
                and self._last_major_event_direction == signal.direction
            ):
                print(
                    f" EXECUTION LOCK: {signal.direction} CHOCH rejected "
                    f"(Waiting for BOS to unlock structure)"
                )
                return None
            
            # --- INSTITUTIONAL FILTER: CHOCH-BOS CONFIRMATION ---
            # Rule: Only trade CHOCH after BOS confirms the new direction
            if not self._bos_confirmed_after_choch:
                print(
                    f"  CHOCH-BOS FILTER: {signal.direction} CHOCH rejected "
                    f"(Waiting for BOS to confirm CHOCH direction)"
                )
                return None

        # --------------------------------------------------
        # BOS FOLLOW-THROUGH VALIDATION (CRITICAL)
        # --------------------------------------------------
        if signal.event_type == EventType.BOS.value:
            if signal.broken_level is None:
                print("[REJECT] BOS REJECTED (No broken level data)")
                return None
            
            bos_level = signal.broken_level.get("price")
            if bos_level is None:
                print("[REJECT] BOS REJECTED (Invalid broken level)")
                return None
            
            # Get BOS candle from 15M data
            bos_candle = None
            close_price = None
            if self._resampled_data is not None:
                data_15m = self._resampled_data.get('15M')
                if data_15m is not None and not data_15m.empty:
                    # Get candle at or just after the event timestamp
                    event_candles = data_15m.loc[data_15m.index >= signal.timestamp]
                    if not event_candles.empty:
                        bos_candle = event_candles.iloc[0]
                        close_price = bos_candle['Close']
            
            if close_price is None:
                print("[REJECT] BOS REJECTED (Cannot get BOS candle)")
                return None
            
            # Get ATR from 15M data (prefer 15M, fallback to 1M)
            atr = None
            if self._resampled_data is not None:
                data_15m = self._resampled_data.get('15M')
                if data_15m is not None and not data_15m.empty:
                    data_pre_entry = data_15m.loc[data_15m.index <= signal.timestamp]
                    atr_series = self.risk_manager.calculate_atr(data_pre_entry)
                    if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]):
                        atr = atr_series.iloc[-1]
            
            # Fallback to 1M ATR if 15M not available
            if atr is None:
                atr_1m_series = self.risk_manager.calculate_atr(data_1m)
                if len(atr_1m_series) > 0 and not pd.isna(atr_1m_series.iloc[-1]):
                    atr = atr_1m_series.iloc[-1]
            
            if atr is None or atr == 0:
                print("[REJECT] BOS REJECTED (ATR unavailable)")
                return None
            
            displacement = abs(close_price - bos_level)
            
            # ❌ Reject weak BOS (no displacement)
            if displacement < self.MIN_BOS_DISPLACEMENT_ATR * atr:
                self.stats['bos_rejected_displacement'] += 1
                print(
                    f"[REJECT] BOS REJECTED (Weak Displacement) | "
                    f"Disp={displacement:.2f}, ATR={atr:.2f}, Required={self.MIN_BOS_DISPLACEMENT_ATR * atr:.2f}"
                )
                return None
            
            # Candle structure check (acceptance)
            if bos_candle is not None:
                candle_range = bos_candle['High'] - bos_candle['Low']
                candle_body = abs(bos_candle['Close'] - bos_candle['Open'])
                
                body_ratio = candle_body / candle_range if candle_range > 0 else 0
                
                if body_ratio < self.MIN_BOS_BODY_RATIO:
                    self.stats['bos_rejected_body_ratio'] += 1
                    print(
                        f"[REJECT] BOS REJECTED (Weak Candle Body) | "
                        f"BodyRatio={body_ratio:.2f}, Required={self.MIN_BOS_BODY_RATIO:.2f}"
                    )
                    return None

        # --------------------------------------------------
        # EXPANSION vs DISTRIBUTION FILTER (STEP B)
        # --------------------------------------------------
        # Check if market is expanding after structure event (AFTER retracement, BEFORE 1M confirmation)
        if self._resampled_data is not None:
            data_15m = self._resampled_data.get('15M')
            if data_15m is not None and not data_15m.empty:
                # Find event index in 15M data
                event_timestamp = signal.timestamp
                # Get data up to and including the event
                data_15m_up_to_event = data_15m.loc[data_15m.index <= event_timestamp]
                
                if len(data_15m_up_to_event) > 0:
                    # Find the index of the event candle (last candle <= event timestamp)
                    event_index = len(data_15m_up_to_event) - 1
                    
                    # Get ATR for expansion check
                    atr_15m = None
                    atr_series = self.risk_manager.calculate_atr(data_15m_up_to_event)
                    if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]):
                        atr_15m = atr_series.iloc[-1]
                    
                    # Fallback to 1M ATR if 15M not available
                    if atr_15m is None:
                        atr_1m_series = self.risk_manager.calculate_atr(data_1m)
                        if len(atr_1m_series) > 0 and not pd.isna(atr_1m_series.iloc[-1]):
                            atr_15m = atr_1m_series.iloc[-1]
                    
                    if atr_15m is not None and atr_15m > 0:
                        # Check expansion using full 15M dataframe (need future candles)
                        # For point-in-time, we need to use data up to current execution time
                        # But for execute_trade, we can use all available data
                        is_expanding = self.is_market_expanding(data_15m, event_index, atr_15m)
                        
                        if not is_expanding:
                            self.stats['rejected_distribution'] += 1
                            print("[REJECT] REJECTED: Market not expanding (Distribution/Chop)")
                            # Store context for debugging
                            if signal.context is None:
                                signal.context = {}
                            signal.context["market_phase"] = "DISTRIBUTION"
                            return None
                        else:
                            # Store context for debugging
                            if signal.context is None:
                                signal.context = {}
                            signal.context["market_phase"] = "EXPANSION"

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
        
        # Unlock structure on BOS (Reset state)
        if signal.event_type == EventType.BOS.value:
            self._last_major_event_type = None
            self._last_major_event_direction = None
            self._last_choch_level = None  # Reset CHOCH level on BOS
            # Reset CHOCH cooldown on BOS
            self._last_choch_price = None
            self._last_choch_timestamp = None
            
            # --- CHOCH-BOS CONFIRMATION: BOS confirms CHOCH direction ---
            if self._last_choch_direction == signal.direction:
                self._bos_confirmed_after_choch = True
                print(f"BOS confirmed CHOCH direction ({signal.direction}) - CHOCH trades now allowed")
        
        # Track CHOCH for BOS confirmation requirement
        if signal.event_type == EventType.CHOCH.value:
            self._last_choch_direction = signal.direction
            self._bos_confirmed_after_choch = False  # Reset - need new BOS to confirm
            print(f"CHOCH detected ({signal.direction}) - Waiting for BOS confirmation")
        
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
            # DEBUG: Verify Lock State
            print(
                "LOCK CHECK",
                signal.event_type,
                signal.direction,
                self._last_major_event_type,
                self._last_major_event_direction
            )

            if (
                self._last_major_event_type == "CHOCH"
                and self._last_major_event_direction == signal.direction
            ):
                print(
                    f" EXECUTION LOCK: {signal.direction} CHOCH rejected "
                    f"(Waiting for BOS to unlock structure)"
                )
                return None
            
            # --- INSTITUTIONAL FILTER: CHOCH-BOS CONFIRMATION ---
            # Rule: Only trade CHOCH after BOS confirms the new direction
            if not self._bos_confirmed_after_choch:
                print(
                    f"  CHOCH-BOS FILTER: {signal.direction} CHOCH rejected "
                    f"(Waiting for BOS to confirm CHOCH direction)"
                )
                return None

        # --------------------------------------------------
        # BOS FOLLOW-THROUGH VALIDATION (CRITICAL)
        # --------------------------------------------------
        if signal.event_type == EventType.BOS.value:
            if signal.broken_level is None:
                print("[REJECT] BOS REJECTED (No broken level data)")
                return None
            
            bos_level = signal.broken_level.get("price")
            if bos_level is None:
                print("[REJECT] BOS REJECTED (Invalid broken level)")
                return None
            
            # Get BOS candle from 15M data
            bos_candle = None
            close_price = None
            if self._resampled_data is not None:
                data_15m = self._resampled_data.get('15M')
                if data_15m is not None and not data_15m.empty:
                    # Get 15M data up to current time only
                    data_15m_current = data_15m.loc[data_15m.index <= current_time]
                    # Get candle at or just after the event timestamp
                    event_candles = data_15m_current.loc[data_15m_current.index >= signal.timestamp]
                    if not event_candles.empty:
                        bos_candle = event_candles.iloc[0]
                        close_price = bos_candle['Close']
            
            if close_price is None:
                print("[REJECT] BOS REJECTED (Cannot get BOS candle)")
                return None
            
            # Get ATR from 15M data (prefer 15M, fallback to 1M)
            atr = None
            if self._resampled_data is not None:
                data_15m = self._resampled_data.get('15M')
                if data_15m is not None and not data_15m.empty:
                    data_15m_current = data_15m.loc[data_15m.index <= current_time]
                    data_pre_entry = data_15m_current.loc[data_15m_current.index <= signal.timestamp]
                    atr_series = self.risk_manager.calculate_atr(data_pre_entry)
                    if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]):
                        atr = atr_series.iloc[-1]
            
            # Fallback to 1M ATR if 15M not available
            if atr is None:
                atr_1m_series = self.risk_manager.calculate_atr(data_1m_current)
                if len(atr_1m_series) > 0 and not pd.isna(atr_1m_series.iloc[-1]):
                    atr = atr_1m_series.iloc[-1]
            
            if atr is None or atr == 0:
                print("[REJECT] BOS REJECTED (ATR unavailable)")
                return None
            
            displacement = abs(close_price - bos_level)
            
            # ❌ Reject weak BOS (no displacement)
            if displacement < self.MIN_BOS_DISPLACEMENT_ATR * atr:
                self.stats['bos_rejected_displacement'] += 1
                print(
                    f"[REJECT] BOS REJECTED (Weak Displacement) | "
                    f"Disp={displacement:.2f}, ATR={atr:.2f}, Required={self.MIN_BOS_DISPLACEMENT_ATR * atr:.2f}"
                )
                return None
            
            # Candle structure check (acceptance)
            if bos_candle is not None:
                candle_range = bos_candle['High'] - bos_candle['Low']
                candle_body = abs(bos_candle['Close'] - bos_candle['Open'])
                
                body_ratio = candle_body / candle_range if candle_range > 0 else 0
                
                if body_ratio < self.MIN_BOS_BODY_RATIO:
                    self.stats['bos_rejected_body_ratio'] += 1
                    print(
                        f"[REJECT] BOS REJECTED (Weak Candle Body) | "
                        f"BodyRatio={body_ratio:.2f}, Required={self.MIN_BOS_BODY_RATIO:.2f}"
                    )
                    return None

        # --------------------------------------------------
        # EXPANSION vs DISTRIBUTION FILTER (STEP B)
        # --------------------------------------------------
        # Check if market is expanding after structure event (AFTER retracement, BEFORE 1M confirmation)
        if self._resampled_data is not None:
            data_15m = self._resampled_data.get('15M')
            if data_15m is not None and not data_15m.empty:
                # Get 15M data up to current time only (point-in-time)
                data_15m_current = data_15m.loc[data_15m.index <= current_time]
                
                # Find event index in 15M data
                event_timestamp = signal.timestamp
                # Get data up to and including the event
                data_15m_up_to_event = data_15m_current.loc[data_15m_current.index <= event_timestamp]
                
                if len(data_15m_up_to_event) > 0:
                    # Find the index in the current data (point-in-time)
                    event_index = len(data_15m_up_to_event) - 1
                    
                    # Get ATR for expansion check
                    atr_15m = None
                    atr_series = self.risk_manager.calculate_atr(data_15m_up_to_event)
                    if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]):
                        atr_15m = atr_series.iloc[-1]
                    
                    # Fallback to 1M ATR if 15M not available
                    if atr_15m is None:
                        atr_1m_series = self.risk_manager.calculate_atr(data_1m_current)
                        if len(atr_1m_series) > 0 and not pd.isna(atr_1m_series.iloc[-1]):
                            atr_15m = atr_1m_series.iloc[-1]
                    
                    if atr_15m is not None and atr_15m > 0:
                        # Check expansion using point-in-time data only
                        is_expanding = self.is_market_expanding(data_15m_current, event_index, atr_15m)
                        
                        if not is_expanding:
                            self.stats['rejected_distribution'] += 1
                            print("[REJECT] REJECTED: Market not expanding (Distribution/Chop)")
                            # Store context for debugging
                            if signal.context is None:
                                signal.context = {}
                            signal.context["market_phase"] = "DISTRIBUTION"
                            return None
                        else:
                            # Store context for debugging
                            if signal.context is None:
                                signal.context = {}
                            signal.context["market_phase"] = "EXPANSION"

        # --- CHANGE #2: Allow BOS-only entries to bypass 1M (selectively) ---
        # Rule: If BOS confidence ≥ 0.75 and Expansion = TRUE, allow direct entry WITHOUT 1M confirmation
        bypass_1m_confirmation = False
        if signal.event_type == EventType.BOS.value:
            if signal.confidence >= 0.75:
                # Check if expansion filter passed (market_phase should be "EXPANSION")
                if signal.context and signal.context.get("market_phase") == "EXPANSION":
                    bypass_1m_confirmation = True
                    if self.debug:
                        print(f"[BYPASS] BOS confidence {signal.confidence:.2f} + Expansion = TRUE -> Skipping 1M confirmation")
        
        # Get entry price - either from 1M confirmation or use signal price if bypassing
        if bypass_1m_confirmation:
            # Use signal price directly (or first available 1M candle close)
            future_candles = data_1m_current[
                (data_1m_current.index > signal.timestamp) & 
                (data_1m_current.index <= current_time)
            ]
            if not future_candles.empty:
                actual_entry_price = future_candles.iloc[0]['Close']
            else:
                actual_entry_price = signal.price  # Fallback to signal price
        else:
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
        
        # Unlock structure on BOS (Reset state)
        if signal.event_type == EventType.BOS.value:
            self._last_major_event_type = None
            self._last_major_event_direction = None
            self._last_choch_level = None  # Reset CHOCH level on BOS
            # Reset CHOCH cooldown on BOS
            self._last_choch_price = None
            self._last_choch_timestamp = None
            
            # --- CHOCH-BOS CONFIRMATION: BOS confirms CHOCH direction ---
            if self._last_choch_direction == signal.direction:
                self._bos_confirmed_after_choch = True
                print(f"BOS confirmed CHOCH direction ({signal.direction}) - CHOCH trades now allowed")
        
        # Track CHOCH for BOS confirmation requirement
        if signal.event_type == EventType.CHOCH.value:
            self._last_choch_direction = signal.direction
            self._bos_confirmed_after_choch = False  # Reset - need new BOS to confirm
            print(f"CHOCH detected ({signal.direction}) - Waiting for BOS confirmation")
        
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
        
        # Verify Confirmation using new ANY ONE logic
        # --- CONDITION 1: Strong impulse candle (body ≥ 50%) ---
        condition_1_strong_impulse = False
        if signal_direction == "BUY":
            condition_1_strong_impulse = is_green and body_ratio >= 0.5
        elif signal_direction == "SELL":
            condition_1_strong_impulse = is_red and body_ratio >= 0.5
        
        # --- CONDITION 2: Momentum continuation (2 consecutive closes in direction) ---
        condition_2_momentum = False
        future_candles = data_1m_current[data_1m_current.index > confirmation_candle.name]
        if len(future_candles) >= 1:
            candle_2 = future_candles.iloc[0]
            if signal_direction == "BUY":
                condition_2_momentum = (is_green and candle_2['Close'] > candle_2['Open'] and
                                        candle_2['Close'] > confirmation_candle['Close'])
            elif signal_direction == "SELL":
                condition_2_momentum = (is_red and candle_2['Close'] < candle_2['Open'] and
                                       candle_2['Close'] < confirmation_candle['Close'])
        
        # --- CONDITION 3: Rejection wick at retracement level ---
        condition_3_rejection = False
        candle_range = confirmation_candle['High'] - confirmation_candle['Low']
        if signal_direction == "BUY":
            lower_wick = min(confirmation_candle['Open'], confirmation_candle['Close']) - confirmation_candle['Low']
            upper_wick = confirmation_candle['High'] - max(confirmation_candle['Open'], confirmation_candle['Close'])
            if candle_range > 0:
                lower_wick_ratio = lower_wick / candle_range
                condition_3_rejection = lower_wick_ratio > 0.3 and (upper_wick / candle_range) < 0.2
        elif signal_direction == "SELL":
            upper_wick = confirmation_candle['High'] - max(confirmation_candle['Open'], confirmation_candle['Close'])
            lower_wick = min(confirmation_candle['Open'], confirmation_candle['Close']) - confirmation_candle['Low']
            if candle_range > 0:
                upper_wick_ratio = upper_wick / candle_range
                condition_3_rejection = upper_wick_ratio > 0.3 and (lower_wick / candle_range) < 0.2
        
        # --- CONDITION 4: No opposite BOS in last N candles (passive confirmation) ---
        condition_4_no_opposite = True  # Default to True
        if len(recent_1m) >= 5:
            if signal_direction == "BUY":
                if swings_low:
                    recent_low = swings_low[-1][1]
                    if confirmation_candle['Low'] < recent_low:
                        condition_4_no_opposite = False
            elif signal_direction == "SELL":
                if swings_high:
                    recent_high = swings_high[-1][1]
                    if confirmation_candle['High'] > recent_high:
                        condition_4_no_opposite = False
        
        # ANY ONE condition passes
        is_confirmed = condition_1_strong_impulse or condition_2_momentum or condition_3_rejection or condition_4_no_opposite
                
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
        REDEFINED: Execution-grade 1M confirmation - ANY ONE condition passes
        
        Conditions (ANY ONE):
        1. Strong impulse candle (body ≥ 50%)
        2. Momentum continuation (2 consecutive closes in direction)
        3. Rejection wick at retracement level
        4. No opposite BOS in last N candles (passive confirmation)
        
        Args:
            data_1m_current: 1M data up to current time only
            signal_direction: "BUY" or "SELL"
            entry_time: Timestamp of the entry signal
            current_time: Current timestamp
            event_type: "BOS" or "CHOCH"
            
        Returns:
            True if ANY ONE confirmation condition is met, False otherwise
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
        
        # Direction confirmation
        is_green = next_candle['Close'] > next_candle['Open']
        is_red = next_candle['Close'] < next_candle['Open']
        
        # --- CONDITION 1: Strong impulse candle (body ≥ 50%) ---
        condition_1_strong_impulse = False
        if signal_direction == "BUY":
            condition_1_strong_impulse = is_green and body_ratio >= 0.5
        elif signal_direction == "SELL":
            condition_1_strong_impulse = is_red and body_ratio >= 0.5
        
        # --- CONDITION 2: Momentum continuation (2 consecutive closes in direction) ---
        condition_2_momentum = False
        if len(future_candles) >= 2:
            candle_1 = future_candles.iloc[0]
            candle_2 = future_candles.iloc[1]
            if signal_direction == "BUY":
                condition_2_momentum = (candle_1['Close'] > candle_1['Open'] and 
                                        candle_2['Close'] > candle_2['Open'] and
                                        candle_2['Close'] > candle_1['Close'])
            elif signal_direction == "SELL":
                condition_2_momentum = (candle_1['Close'] < candle_1['Open'] and 
                                       candle_2['Close'] < candle_2['Open'] and
                                       candle_2['Close'] < candle_1['Close'])
        
        # --- CONDITION 3: Rejection wick at retracement level ---
        condition_3_rejection = False
        if signal_direction == "BUY":
            # Lower wick should be significant (rejection of lower prices)
            lower_wick = min(next_candle['Open'], next_candle['Close']) - next_candle['Low']
            upper_wick = next_candle['High'] - max(next_candle['Open'], next_candle['Close'])
            if candle_range > 0:
                lower_wick_ratio = lower_wick / candle_range
                # Strong rejection: lower wick > 30% of range, upper wick < 20%
                condition_3_rejection = lower_wick_ratio > 0.3 and (upper_wick / candle_range) < 0.2
        elif signal_direction == "SELL":
            # Upper wick should be significant (rejection of higher prices)
            upper_wick = next_candle['High'] - max(next_candle['Open'], next_candle['Close'])
            lower_wick = min(next_candle['Open'], next_candle['Close']) - next_candle['Low']
            if candle_range > 0:
                upper_wick_ratio = upper_wick / candle_range
                # Strong rejection: upper wick > 30% of range, lower wick < 20%
                condition_3_rejection = upper_wick_ratio > 0.3 and (lower_wick / candle_range) < 0.2
        
        # --- CONDITION 4: No opposite BOS in last N candles (passive confirmation) ---
        condition_4_no_opposite = True  # Default to True (no opposite BOS found)
        recent_1m = data_1m_current[data_1m_current.index < next_candle.name].tail(20)
        if len(recent_1m) >= 5:
            swings_high, swings_low = detect_swing_points(recent_1m, window=3)
            if signal_direction == "BUY":
                # Check if there's a bearish BOS (break of swing low) in recent candles
                if swings_low:
                    recent_low = swings_low[-1][1]
                    # Check if price broke below recent low (opposite BOS)
                    if next_candle['Low'] < recent_low:
                        condition_4_no_opposite = False
            elif signal_direction == "SELL":
                # Check if there's a bullish BOS (break of swing high) in recent candles
                if swings_high:
                    recent_high = swings_high[-1][1]
                    # Check if price broke above recent high (opposite BOS)
                    if next_candle['High'] > recent_high:
                        condition_4_no_opposite = False
        
        # --- ANY ONE condition passes ---
        if condition_1_strong_impulse or condition_2_momentum or condition_3_rejection or condition_4_no_opposite:
            if self.debug:
                reasons = []
                if condition_1_strong_impulse:
                    reasons.append("strong_impulse")
                if condition_2_momentum:
                    reasons.append("momentum")
                if condition_3_rejection:
                    reasons.append("rejection")
                if condition_4_no_opposite:
                    reasons.append("no_opposite_BOS")
                print(f"OK 1M CONFIRM ({event_type}): {', '.join(reasons)} - {next_candle.name}")
            return True
        else:
            if self.debug:
                print(f"REJECT 1M ({event_type}): no confirmation conditions met - {next_candle.name}")
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
        print(f"Starting PROPER Multi-Timeframe Trading Strategy for {self.symbol}")
        print(f"Analyzing {days_back} days of data")
        print("PROPER BACKTESTING: Candle-by-candle simulation")
        
        # Load and resample data
        print("Loading and resampling data...")
        resampled_data = load_and_resample(data_file, days_back=days_back)
        self._resampled_data = resampled_data
        
        # Initialize results
        # Initialize/Reset results
        self.stats = {
            'total_events': 0,
            'aligned_events': 0,
            'retracement_events': 0,
            'confirmed_1m_events': 0,
            'processed_candles': 0,
            'bos_rejected_displacement': 0,  # Track BOS rejections by displacement
            'bos_rejected_body_ratio': 0,     # Track BOS rejections by body ratio
            'bos_rejected_other': 0,          # Track other BOS rejections
            'rejected_distribution': 0,       # Track expansion/distribution filter rejections
            # Retracement debug counters (STEP 5)
            'retracement_reject_no_expansion': 0,
            'retracement_reject_expired': 0,
            'retracement_reject_too_shallow': 0,
            'retracement_reject_too_deep': 0,
            'retracement_reject_no_reversal': 0
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
            print(" Missing required timeframe data")
            return results
        
        # PROPER BACKTESTING: Get min/max timestamps for backtesting
        start_time = max(data_1h.index[0], data_15m.index[0], data_1m.index[0])
        end_time = min(data_1h.index[-1], data_15m.index[-1], data_1m.index[-1])
        
        print(f" Backtesting from {start_time} to {end_time}")
        print(" Processing 15M candles (entry timeframe) candle-by-candle...")
        
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
                    
                    # NOTE: CHOCH cooldown is now handled at structure generation level
                    # in smart_money_concepts.py - no late-stage filtering needed here
                    
                    print(f"\n NEW {event.event_type.value} - {event.direction} entry at {current_timestamp}")
                    print(f"   Confidence: {event.confidence:.2f}")
                    print(f"   Price: {event.price:.5f}")
                    
                    # STEP 3: Check retracement confirmation with historical data only
                    if self.check_retracement_confirmation_point_in_time(event, current_15m_data, current_timestamp):
                        print("    Retracement confirmation passed")
                        self.stats['retracement_events'] += 1
                        
                        # STEP 4: Generate trade signal (entry price will be determined at execution)
                        signal = self.generate_trade_signal(event, trend_1h, current_candle['Close'])
                        
                        if signal is None:
                            print("    Failed to generate trade signal")
                            continue
                        
                        results['signals_generated'] += 1
                        self.signals.append(signal)
                        
                        print(f"    Signal generated: {signal.direction} (entry price will be determined at execution)")
                        
                        # STEP 5: Execute trade with historical 1M data only
                        trade = self.execute_trade_point_in_time(signal, 10000, hist_1m, current_timestamp)
                        
                        if trade:
                            results['trades_executed'] += 1
                            self.stats['confirmed_1m_events'] += 1
                            print(f"    Trade executed: {trade.position_size:.2f} units")
                        else:
                            print("    Waiting for 1M confirmation...")
                    else:
                        print("    Waiting for retracement confirmation...")
            
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
        print(f"\n PROPER BACKTESTING COMPLETE!")
        print(f" Results Summary:")
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
            
        print("\nDetailed Funnel Metrics:")
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
