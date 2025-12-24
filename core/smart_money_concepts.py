import pandas as pd
from typing import List, Dict, Literal, Optional, Union
from dataclasses import dataclass
from enum import Enum

# --- Data Structures for Clarity ---
class SwingType(Enum):
    HH = "HH"
    HL = "HL"
    LH = "LH"
    LL = "LL"

class EventType(Enum):
    BOS = "BOS"
    CHOCH = "CHOCH"

@dataclass
class StructurePoint:
    timestamp: pd.Timestamp
    price: float
    swing_type: SwingType

@dataclass
class MarketEvent:
    event_type: EventType
    direction: Literal["Bullish", "Bearish"]
    timestamp: pd.Timestamp
    price: float
    confidence: float
    broken_level: Dict
    context: Dict
    description: str

# --- The Enhanced Logic Engine ---
class MarketStructureAnalyzer:
    def __init__(self, config: Optional[Dict] = None, lookback_period: int = 5):
        """
        Initialize with dictionary-based configuration for better modularity.
        
        Args:
            config: Dictionary containing configuration parameters. If None, uses defaults.
            lookback_period: Number of periods to look back for trend analysis
        """
        # Default configuration
        default_config = {
            "confidence_thresholds": {
                "BOS": 0.5,
                "CHOCH": 0.65
            },
            "structure_validation": {
                "min_structure_width": 0.0010,
                "min_time_width_hours": 2.0
            }
        }
        
        # Merge with provided config
        if config is None:
            config = {}
        
        self.config = {**default_config, **config}
        self.lookback_period = lookback_period
        
        # Extract commonly used values for backward compatibility
        self.confidence_threshold = self.config["confidence_thresholds"]["BOS"]
        self.choch_confidence_threshold = self.config["confidence_thresholds"]["CHOCH"]
        self.min_structure_width = self.config["structure_validation"]["min_structure_width"]
        self.min_time_width_hours = self.config["structure_validation"]["min_time_width_hours"]
        
        # STRUCTURE STATE LOCK: Prevent multiple CHOCH detections per structure leg
        self._structure_state = None  # None, "CHOCH", or "BOS"

    def get_confidence_threshold(self, event_type: str) -> float:
        """Get confidence threshold for specific event type"""
        return self.config["confidence_thresholds"].get(event_type, 0.5)

    def _find_last_swing(self, structure: List[StructurePoint], swing_type: SwingType, before_index: int) -> Optional[StructurePoint]:
        """Find the most recent swing of specified type before given index"""
        for i in range(before_index - 1, -1, -1):
            if structure[i].swing_type == swing_type:
                return structure[i]
        return None

    def _find_all_swings(self, structure: List[StructurePoint], swing_type: SwingType, before_index: int, limit: int = 3) -> List[StructurePoint]:
        """Find multiple swings of specified type for better pattern recognition"""
        swings = []
        for i in range(before_index - 1, -1, -1):
            if structure[i].swing_type == swing_type:
                swings.append(structure[i])
                if len(swings) >= limit:
                    break
        return swings

    def _get_trend_state(self, structure: List[StructurePoint], current_index: int) -> Literal["uptrend", "downtrend", "sideways"]:
        """
        Simplified, purely backward-looking trend detection.
        Only analyzes recent market structure without CHOCH overrides.
        CHOCH detection and trend decision-making should be handled by trading_executor.
        """
        if current_index < 3:
            return "sideways"
        
        # Look at recent swings for trend analysis
        lookback = min(self.lookback_period, current_index)
        recent_swings = structure[max(0, current_index - lookback):current_index]
        
        if len(recent_swings) < 2:
            return "sideways"
        
        # Count swing patterns in recent history
        hh_count = sum(1 for s in recent_swings if s.swing_type == SwingType.HH)
        hl_count = sum(1 for s in recent_swings if s.swing_type == SwingType.HL)
        ll_count = sum(1 for s in recent_swings if s.swing_type == SwingType.LL)
        lh_count = sum(1 for s in recent_swings if s.swing_type == SwingType.LH)
        
        # Simple trend logic based on swing patterns
        bullish_signals = hh_count + hl_count
        bearish_signals = ll_count + lh_count
        
        # Check for clear uptrend patterns (higher highs and higher lows)
        if (hh_count > 0 and hl_count > 0) or (bullish_signals > bearish_signals and hh_count > 0):
            return "uptrend"
        # Check for clear downtrend patterns (lower highs and lower lows)
        elif (ll_count > 0 and lh_count > 0) or (bearish_signals > bullish_signals and ll_count > 0):
            return "downtrend"
        # Check recent sequence for immediate trend
        elif len(recent_swings) >= 2:
            last_two = [s.swing_type for s in recent_swings[-2:]]
            if SwingType.HH in last_two or SwingType.HL in last_two:
                return "uptrend"
            elif SwingType.LL in last_two or SwingType.LH in last_two:
                return "downtrend"
        
        return "sideways"

    def _calculate_confidence(self, current_point: StructurePoint, broken_level: StructurePoint, 
                            intermediate_point: Optional[StructurePoint] = None, event_type: EventType = None) -> float:
        """Enhanced confidence calculation with integrated quality scoring"""
        base_confidence = 0.6
        
        # Price break strength
        price_break = abs(current_point.price - broken_level.price)
        if price_break > 50:  # Significant break (adjust based on instrument)
            base_confidence += 0.2
        elif price_break < 10:  # Weak break
            base_confidence -= 0.2
        
        # Time factor - more recent breaks are more reliable
        time_diff = (current_point.timestamp - broken_level.timestamp).total_seconds() / 3600  # hours
        if time_diff < 24:  # Within 24 hours
            base_confidence += 0.1
        elif time_diff > 168:  # More than a week
            base_confidence -= 0.1
        
        # Structure integrity and quality check
        if intermediate_point:
            # Check if intermediate point properly separates the levels
            if current_point.swing_type in [SwingType.HH, SwingType.LL]:
                structure_integrity = abs(intermediate_point.price - broken_level.price) / abs(current_point.price - broken_level.price)
                if structure_integrity > 0.3:  # Good separation
                    base_confidence += 0.1
                
                # Check minimum structure width to avoid noise
                structure_width = abs(intermediate_point.price - broken_level.price)
                if structure_width < self.min_structure_width:
                    base_confidence -= 0.3  # Penalize tight structures (noise)
                elif structure_width > self.min_structure_width * 3:
                    base_confidence += 0.1  # Reward wide, meaningful structures
        
        # Event-specific confidence adjustments
        if event_type == EventType.CHOCH:
            # CHOCH requires higher confidence - deeper retracements and stronger reversals
            if price_break < 15:  # Weak CHOCH break
                base_confidence -= 0.15
            elif price_break > 50:  # Strong CHOCH break
                base_confidence += 0.2
            
            # Check for consolidation before CHOCH (price should have moved away from broken level)
            if intermediate_point:
                consolidation_distance = abs(intermediate_point.price - broken_level.price)
                if consolidation_distance > price_break * 0.3:  # Good consolidation
                    base_confidence += 0.15
        
        elif event_type == EventType.BOS:
            # BOS should have clear momentum continuation
            if price_break < 10:  # Weak BOS break
                base_confidence -= 0.1
            elif price_break > 50:  # Strong BOS break
                base_confidence += 0.15
            
            # Bonus for deep retracement (HL very close to LL)
            if intermediate_point and current_point.swing_type == SwingType.HH:
                retracement_depth = abs(intermediate_point.price - broken_level.price)
                if retracement_depth > price_break * 0.4:  # Deep retracement
                    base_confidence += 0.1
        
        # Calculate quality score and integrate it into confidence
        quality_score = 0
        if price_break > 30:  # Strong price break
            quality_score += 1
        if event_type == EventType.CHOCH and intermediate_point:  # Clean QML
            quality_score += 1
        if intermediate_point and abs(intermediate_point.price - broken_level.price) > price_break * 0.3:  # Deep retracement
            quality_score += 1
        if time_diff < 48:  # Recent event
            quality_score += 1
        
        # Normalize quality score (0-4 scale) and integrate into confidence
        normalized_quality = quality_score / 4.0
        
        # Integrate quality score into confidence (quality acts as a multiplier)
        # High quality events get a confidence boost, low quality events get penalized
        quality_multiplier = 0.5 + (normalized_quality * 0.5)  # Range: 0.5 to 1.0
        final_confidence = base_confidence * quality_multiplier
        
        return min(1.0, max(0.1, final_confidence))

    def _calculate_quality_score(self, current_point: StructurePoint, broken_level: StructurePoint, 
                               intermediate_point: Optional[StructurePoint] = None, event_type: EventType = None) -> float:
        """Calculate quality score separately for strategy logic"""
        quality_score = 0
        
        # Price break strength
        price_break = abs(current_point.price - broken_level.price)
        if price_break > 30:  # Strong price break
            quality_score += 1
        
        # Event-specific quality factors
        if event_type == EventType.CHOCH and intermediate_point:  # Clean QML
            quality_score += 1
        
        # Structure quality
        if intermediate_point and abs(intermediate_point.price - broken_level.price) > price_break * 0.3:  # Deep retracement
            quality_score += 1
        
        # Time factor
        time_diff = (current_point.timestamp - broken_level.timestamp).total_seconds() / 3600  # hours
        if time_diff < 48:  # Recent event
            quality_score += 1
        
        # Normalize quality score (0-4 scale)
        return quality_score / 4.0

    def _validate_pattern(self, pattern_type: str, current: StructurePoint, 
                         previous_extreme: StructurePoint, intermediate: Optional[StructurePoint] = None,
                         trend_state: Optional[str] = None) -> bool:
        """
        Consolidated pattern validation for both BOS and CHOCH patterns.
        
        Args:
            pattern_type: "BOS" or "CHOCH"
            current: Current swing point
            previous_extreme: Previous extreme (HH for BOS, broken level for CHOCH)
            intermediate: Intermediate point (required for BOS, None for CHOCH)
            trend_state: Trend state (required for CHOCH, None for BOS)
        """
        if pattern_type == "BOS":
            return self._validate_bos_pattern(current, previous_extreme, intermediate)
        elif pattern_type == "CHOCH":
            return self._validate_choch_pattern(current, previous_extreme, trend_state)
        else:
            return False

    def _validate_bos_pattern(self, current: StructurePoint, previous_extreme: StructurePoint, 
                            intermediate: StructurePoint) -> bool:
        """Enhanced BOS pattern validation with comprehensive structure quality checks"""
        # Ensure proper sequence timing
        if not (previous_extreme.timestamp < intermediate.timestamp < current.timestamp):
            return False
        
        # Comprehensive structure width validation (price + time)
        if not self._validate_structure_width(current, previous_extreme, intermediate):
            return False  # Structure too narrow in price or time
        
        # Validate price relationships
        if current.swing_type == SwingType.HH:
            return (intermediate.swing_type == SwingType.HL and 
                   intermediate.price < previous_extreme.price and
                   current.price > previous_extreme.price)
        elif current.swing_type == SwingType.LL:
            return (intermediate.swing_type == SwingType.LH and 
                   intermediate.price > previous_extreme.price and
                   current.price < previous_extreme.price)
        
        return False

    def _validate_choch_pattern(self, current: StructurePoint, broken_level: StructurePoint, 
                              trend_state: str) -> bool:
        """CORRECTED CHOCH pattern validation - only true trend reversals"""
        # Comprehensive structure width validation (price + time)
        if not self._validate_structure_width(current, broken_level):
            return False  # Structure too narrow in price or time
        
        if trend_state == "uptrend" and current.swing_type == SwingType.LL:
            # For bearish CHOCH: LL breaking below the last HL in uptrend
            return (broken_level.swing_type == SwingType.HL and 
                   current.price < broken_level.price)
        elif trend_state == "downtrend" and current.swing_type == SwingType.HH:
            # For bullish CHOCH: HH breaking above the last LH in downtrend  
            return (broken_level.swing_type == SwingType.LH and 
                   current.price > broken_level.price)
        
        # REMOVED: LH and HL cases are not true CHOCH - they are structural continuations
        # A true CHOCH must be a new extreme (HH or LL) breaking the previous swing's structural point
        
        return False

    def _validate_structure_width(self, current: StructurePoint, previous: StructurePoint, 
                                 intermediate: Optional[StructurePoint] = None) -> bool:
        """
        Comprehensive structure width validation using both price and time dimensions.
        This ensures we only detect meaningful structures, not noise.
        """
        # Price-based structure width validation
        price_width = abs(current.price - previous.price)
        if price_width < self.min_structure_width:
            return False  # Price structure too narrow
        
        # Time-based structure width validation
        time_width_hours = abs((current.timestamp - previous.timestamp).total_seconds()) / 3600
        if time_width_hours < self.min_time_width_hours:
            return False  # Time structure too narrow
        
        # If intermediate point exists, validate the full structure
        if intermediate:
            # Check intermediate to previous width
            intermediate_prev_width = abs(intermediate.price - previous.price)
            intermediate_prev_time = abs((intermediate.timestamp - previous.timestamp).total_seconds()) / 3600
            
            # Check intermediate to current width
            intermediate_current_width = abs(current.price - intermediate.price)
            intermediate_current_time = abs((current.timestamp - intermediate.timestamp).total_seconds()) / 3600
            
            # All segments should have meaningful width
            if (intermediate_prev_width < self.min_structure_width * 0.5 or 
                intermediate_current_width < self.min_structure_width * 0.5 or
                intermediate_prev_time < self.min_time_width_hours * 0.5 or
                intermediate_current_time < self.min_time_width_hours * 0.5):
                return False
        
        return True

    def _get_dynamic_choch_threshold(self, current: StructurePoint, broken_level: StructurePoint, 
                                   trend_state: str) -> float:
        """
        Dynamic CHOCH confidence threshold based on market conditions.
        This helps adapt to different market volatility and structure quality.
        """
        base_threshold = self.get_confidence_threshold("CHOCH")
        
        # Calculate price break strength
        price_break = abs(current.price - broken_level.price)
        
        # Adjust threshold based on price break strength
        if price_break < 0.0005:  # Very weak break (less than 5 pips)
            return base_threshold + 0.1  # Make it harder
        elif price_break > 0.005:  # Strong break (more than 50 pips)
            return base_threshold - 0.05  # Make it easier
        
        # Adjust based on trend state
        if trend_state == "sideways":
            return base_threshold + 0.05  # Sideways markets need stronger signals
        
        return base_threshold



    def get_market_events(self, structure_data: Union[List[Dict], List[StructurePoint]]) -> List[MarketEvent]:
        """
        OPTIMIZED market event detection with O(n) complexity.
        POINT-IN-TIME SAFE: Only uses historical data, no look-ahead bias.
        Confirmation logic should be handled by the trading executor.
        
        Args:
            structure_data: List of either Dict (with 'timestamp', 'price', 'type') 
                          or StructurePoint objects
        """
        if len(structure_data) < 4:
            return []
        
        # Handle both dict and StructurePoint inputs
        structure = []
        for p in structure_data:
            if isinstance(p, StructurePoint):
                # Already a StructurePoint, use directly
                structure.append(p)
            elif isinstance(p, dict):
                # Convert dict to StructurePoint
                structure.append(StructurePoint(
                    pd.Timestamp(p["timestamp"]), 
                    p["price"], 
                    SwingType(p["type"])
                ))
            else:
                raise ValueError(f"Unsupported structure point type: {type(p)}")
        events = []

        # OPTIMIZATION: Track last swing points as we iterate (O(n) instead of O(n²))
        last_hh = None
        last_hl = None
        last_lh = None
        last_ll = None
        prev_hh = None  # Previous HH for BOS detection
        prev_ll = None  # Previous LL for BOS detection
        
        # STRUCTURE LOCKING: Track last broken level to prevent duplicate CHOCHs
        last_choch_level = None  # timestamp of the broken structural point
        last_choch_direction = None

        for i in range(1, len(structure)):  # Start from index 1 to process all swing points
            current = structure[i]
            trend_before = self._get_trend_state(structure, i)
            
            # Debug print (remove in production)
            # print(f"Index {i}: {current.swing_type.value} @ {current.price:.2f} - Trend: {trend_before}")
            
            # OPTIMIZATION: Update tracking variables BEFORE detection logic
            if current.swing_type == SwingType.HH:
                prev_hh = last_hh  # Store previous HH
                last_hh = current
            elif current.swing_type == SwingType.HL:
                last_hl = current
            elif current.swing_type == SwingType.LH:
                last_lh = current
            elif current.swing_type == SwingType.LL:
                prev_ll = last_ll  # Store previous LL
                last_ll = current

            # --- CHOCH Detection (Priority over BOS) ---
            choch_detected = False
            
            # 🔒 STRUCTURE STATE LOCK: Prevent CHOCH detection if already in CHOCH state
            if self._structure_state == "CHOCH":
                pass  # Skip CHOCH detection entirely - wait for BOS to reset
            else:
                # CORRECTED CHOCH detection - only true trend reversals
                    if trend_before == "uptrend":
                        # Bearish CHOCH: Must be a new LL breaking below previous HL
                        if current.swing_type == SwingType.LL:
                            if last_hl and current.price < last_hl.price:
                                # This is a true CHOCH - trend change from bullish to bearish
                                
                                # Prevent duplicate CHOCH on same structure
                                if last_choch_level == last_hl.timestamp and last_choch_direction == "Bearish":
                                    choch_detected = True
                                    continue
                                
                                if last_hh:  # QML level
                                    confidence = self._calculate_confidence(current, last_hl, last_hh, EventType.CHOCH)
                                    quality_score = self._calculate_quality_score(current, last_hl, last_hh, EventType.CHOCH)
                                    dynamic_threshold = self._get_dynamic_choch_threshold(current, last_hl, trend_before)
                                    if confidence >= dynamic_threshold:  # Dynamic threshold for CHOCH
                                        events.append(MarketEvent(
                                        event_type=EventType.CHOCH,
                                        direction="Bearish",
                                        timestamp=current.timestamp,
                                        price=current.price,
                                        confidence=confidence,
                                        broken_level={"name": "SBR", "timestamp": last_hl.timestamp, "price": last_hl.price},
                                        context={
                                            "a_plus_entry": {"name": "QML", "timestamp": last_hh.timestamp, "price": last_hh.price},
                                            "quality_score": quality_score,
                                            "structure_width": abs(last_hh.price - last_hl.price)
                                        },
                                        description=f"Bearish CHOCH: {current.swing_type.value} @ {current.price:.2f} broke uptrend support @ {last_hl.price:.2f}"
                                    ))
                                    choch_detected = True
                                    
                                    # Update Structure Lock
                                    last_choch_level = last_hl.timestamp
                                    last_choch_direction = "Bearish"
                                    
                                    # 🔒 LOCK STRUCTURE AFTER CHOCH
                                    self._structure_state = "CHOCH"
                
                    elif trend_before == "downtrend":
                        # Bullish CHOCH: Must be a new HH breaking above previous LH
                        if current.swing_type == SwingType.HH:
                            if last_lh and current.price > last_lh.price:
                                # This is a true CHOCH - trend change from bearish to bullish
                                
                                # Prevent duplicate CHOCH on same structure
                                if last_choch_level == last_lh.timestamp and last_choch_direction == "Bullish":
                                    choch_detected = True
                                    continue

                                if last_ll:  # QML level
                                    confidence = self._calculate_confidence(current, last_lh, last_ll, EventType.CHOCH)
                                    quality_score = self._calculate_quality_score(current, last_lh, last_ll, EventType.CHOCH)
                                    dynamic_threshold = self._get_dynamic_choch_threshold(current, last_lh, trend_before)
                                    if confidence >= dynamic_threshold:  # Dynamic threshold for CHOCH
                                        events.append(MarketEvent(
                                            event_type=EventType.CHOCH,
                                            direction="Bullish",
                                            timestamp=current.timestamp,
                                            price=current.price,
                                            confidence=confidence,
                                            broken_level={"name": "RBS", "timestamp": last_lh.timestamp, "price": last_lh.price},
                                            context={
                                                "a_plus_entry": {"name": "QML", "timestamp": last_ll.timestamp, "price": last_ll.price},
                                                "quality_score": quality_score,
                                                "structure_width": abs(last_ll.price - last_lh.price)
                                            },
                                            description=f"Bullish CHOCH: {current.swing_type.value} @ {current.price:.2f} broke downtrend resistance @ {last_lh.price:.2f}"
                                        ))
                                        choch_detected = True
                                        
                                        # Update Structure Lock
                                        last_choch_level = last_lh.timestamp
                                        last_choch_direction = "Bullish"
                                        
                                        # 🔒 LOCK STRUCTURE AFTER CHOCH
                                        self._structure_state = "CHOCH"

            # --- OPTIMIZED BOS Detection (Only if no CHOCH detected) ---
            if not choch_detected and current.swing_type == SwingType.HH:
                # Look for previous HH to break
                if prev_hh and current.price > prev_hh.price:
                    # Find intermediate low between the highs (use last_hl if it's between prev_hh and current)
                    intermediate_low = None
                    if last_hl and last_hl.timestamp > prev_hh.timestamp:
                        intermediate_low = last_hl
                    
                    if intermediate_low and self._validate_bos_pattern(current, prev_hh, intermediate_low):
                        confidence = self._calculate_confidence(current, prev_hh, intermediate_low, EventType.BOS)
                        quality_score = self._calculate_quality_score(current, prev_hh, intermediate_low, EventType.BOS)
                        if confidence >= self.get_confidence_threshold("BOS"):
                            events.append(MarketEvent(
                                event_type=EventType.BOS,
                                direction="Bullish",
                                timestamp=current.timestamp,
                                price=current.price,
                                confidence=confidence,
                                broken_level={"name": "TJL1", "timestamp": prev_hh.timestamp, "price": prev_hh.price},
                                context={
                                    "a_plus_entry": {"name": "TJL2", "timestamp": intermediate_low.timestamp, "price": intermediate_low.price},
                                    "quality_score": quality_score,
                                    "structure_width": abs(intermediate_low.price - prev_hh.price)
                                },
                                description=f"Bullish BOS: HH @ {current.price:.2f} broke previous HH @ {prev_hh.price:.2f}"
                            ))
                            
                            # 🔓 RESET STRUCTURE STATE ON BOS
                            self._structure_state = None

            elif not choch_detected and current.swing_type == SwingType.LL:
                # Look for previous LL to break
                if prev_ll and current.price < prev_ll.price:
                    # Find intermediate high between the lows (use last_lh if it's between prev_ll and current)
                    intermediate_high = None
                    if last_lh and last_lh.timestamp > prev_ll.timestamp:
                        intermediate_high = last_lh
                    
                    if intermediate_high and self._validate_bos_pattern(current, prev_ll, intermediate_high):
                        confidence = self._calculate_confidence(current, prev_ll, intermediate_high, EventType.BOS)
                        quality_score = self._calculate_quality_score(current, prev_ll, intermediate_high, EventType.BOS)
                        if confidence >= self.get_confidence_threshold("BOS"):
                            events.append(MarketEvent(
                                event_type=EventType.BOS,
                                direction="Bearish",
                                timestamp=current.timestamp,
                                price=current.price,
                                confidence=confidence,
                                broken_level={"name": "TJL1", "timestamp": prev_ll.timestamp, "price": prev_ll.price},
                                context={
                                    "a_plus_entry": {"name": "TJL2", "timestamp": intermediate_high.timestamp, "price": intermediate_high.price},
                                    "quality_score": quality_score,
                                    "structure_width": abs(intermediate_high.price - prev_ll.price)
                                },
                                description=f"Bearish BOS: LL @ {current.price:.2f} broke previous LL @ {prev_ll.price:.2f}"
                            ))
                            
                            # 🔓 RESET STRUCTURE STATE ON BOS
                            self._structure_state = None

        # Return all events - let trading_executor handle duplicate filtering and decision-making
        return events

    def get_high_quality_events(self, structure_data: List[Dict], min_quality_threshold: float = 0.7) -> List[MarketEvent]:
        """
        Get only high-quality events based on quality score threshold.
        This provides fine-grained control for strategy logic.
        
        Args:
            structure_data: Market structure data
            min_quality_threshold: Minimum quality score (0.0 to 1.0)
        """
        all_events = self.get_market_events(structure_data)
        return [event for event in all_events 
                if event.context.get("quality_score", 0.0) >= min_quality_threshold]


    def debug_analysis(self, structure_data: List[Dict], focus_index: int = None) -> None:
        """Debug method to understand what's happening at specific points"""
        if len(structure_data) < 4:
            print("Not enough data for analysis")
            return
        
        structure = [StructurePoint(pd.Timestamp(p["timestamp"]), p["price"], SwingType(p["type"])) 
                    for p in structure_data]
        
        print(f"\n=== DEBUG ANALYSIS ===")
        print(f"Total structure points: {len(structure)}")
        
        if focus_index is None:
            # Show trend states for all points
            for i in range(2, min(10, len(structure))):  # First 10 points
                current = structure[i]
                trend = self._get_trend_state(structure, i)
                print(f"Index {i}: {current.swing_type.value} @ {current.price:.2f} on {current.timestamp} - Trend: {trend}")
        else:
            # Focus on specific index
            if focus_index < len(structure):
                current = structure[focus_index]
                trend = self._get_trend_state(structure, focus_index)
                print(f"\nFOCUS - Index {focus_index}: {current.swing_type.value} @ {current.price:.2f} - Trend: {trend}")
                
                # Show recent history
                lookback = min(6, focus_index)
                recent = structure[max(0, focus_index - lookback):focus_index]
                print(f"Recent history ({len(recent)} points):")
                for j, point in enumerate(recent):
                    print(f"  {focus_index - len(recent) + j}: {point.swing_type.value} @ {point.price:.2f} on {point.timestamp}")
                
                # Check for potential CHOCH
                if trend == "uptrend":
                    last_hl = self._find_last_swing(structure, SwingType.HL, focus_index)
                    if last_hl:
                        print(f"Last HL: {last_hl.price:.2f} on {last_hl.timestamp}")
                        if current.price < last_hl.price:
                            print(f"*** SHOULD BE CHOCH: {current.swing_type.value} @ {current.price:.2f} broke HL @ {last_hl.price:.2f}")
        
        print("=== END DEBUG ===\n")

    def get_event_statistics(self, events: List[MarketEvent]) -> Dict:
        """Get statistics about detected events"""
        if not events:
            return {"total": 0}
        
        stats = {
            "total": len(events),
            "bos_count": len([e for e in events if e.event_type == EventType.BOS]),
            "choch_count": len([e for e in events if e.event_type == EventType.CHOCH]),
            "bullish_count": len([e for e in events if e.direction == "Bullish"]),
            "bearish_count": len([e for e in events if e.direction == "Bearish"]),
            "avg_confidence": sum(e.confidence for e in events) / len(events),
            "high_confidence_count": len([e for e in events if e.confidence > 0.7])
        }
        
        return stats
