    
    def _log_trade_metrics(self, trade: TradeExecution, signal: TradeSignal, 
                          data_1h: pd.DataFrame, data_15m: pd.DataFrame,
                          current_time: pd.Timestamp):
        """
        Log comprehensive trade metrics for analysis
        Captures all structure-aware metrics requested for optimization
        """
        try:
            # Calculate ATR for distance metrics
            atr_15m = self.risk_manager.calculate_atr(data_15m)
            current_atr = atr_15m.iloc[-1] if len(atr_15m) > 0 else 20.0
            
            # Get HTF trend
            htf_trend = self._get_htf_trend_classification(data_1h, current_time)
            
            # Get ATR regime
            atr_regime = self._get_atr_regime(atr_15m)
            
            # Calculate HTF structure metrics
            htf_metrics = self._calculate_htf_structure_metrics(data_1h, trade.entry_price, signal.direction)
            
            # Calculate pullback quality
            pullback_metrics = self._calculate_pullback_metrics(data_15m, signal, trade.entry_price)
            
            # Create comprehensive trade log
            trade_log = {
                # Basic Info
                "timestamp": str(current_time),
                "event_type": signal.event_type,
                "direction": signal.direction,
                
                # Price Levels
                "entry_price": trade.entry_price,
                "sl_price": trade.stop_loss,
                "tp_price": trade.take_profit,
                "rr": signal.risk_reward if hasattr(signal, 'risk_reward') else 2.0,
                
                # Distance Metrics
                "distance_to_bos_level": htf_metrics.get('distance_to_bos', 0),
                "distance_to_htf_eq": htf_metrics.get('distance_to_eq', 0),
                "distance_to_htf_extreme": htf_metrics.get('distance_to_extreme', 0),
                "sl_distance_atr": abs(trade.entry_price - trade.stop_loss) / current_atr if current_atr > 0 else 0,
                
                # Regime Classification
                "htf_trend": htf_trend,
                "atr_regime": atr_regime,
                
                # Pullback Quality
                "retrace_pct": pullback_metrics.get('retrace_pct', 0),
                "entry_location": pullback_metrics.get('entry_location', 'Unknown'),
                
                # Outcome Metrics (to be filled on trade close)
                "outcome": None,
                "rr_actual": None,
                "bars_to_outcome": None,
                "bars_to_first_adverse": None,
                "reached_tp1": None,
                "max_favorable_excursion": None,
                "max_adverse_excursion": None,
                
                # Trade ID for tracking
                "trade_id": id(trade)
            }
            
            self.detailed_trade_logs.append(trade_log)
            
        except Exception as e:
            print(f"⚠️  Error logging trade metrics: {e}")
    
    def _get_htf_trend_classification(self, data_1h: pd.DataFrame, current_time: pd.Timestamp) -> str:
        """Classify HTF trend as Up/Down/Range"""
        try:
            # Use existing trend detection
            trend_1h = self.analyze_1h_trend(data_1h, current_time)
            
            if trend_1h == "uptrend":
                return "Up"
            elif trend_1h == "downtrend":
                return "Down"
            else:
                return "Range"
        except:
            return "Unknown"
    
    def _get_atr_regime(self, atr_series: pd.Series) -> str:
        """Classify ATR regime as High/Normal/Low"""
        try:
            if len(atr_series) < 20:
                return "Normal"
            
            current_atr = atr_series.iloc[-1]
            atr_mean = atr_series.iloc[-50:].mean() if len(atr_series) >= 50 else atr_series.mean()
            atr_std = atr_series.iloc[-50:].std() if len(atr_series) >= 50 else atr_series.std()
            
            if current_atr > atr_mean + atr_std:
                return "High"
            elif current_atr < atr_mean - atr_std:
                return "Low"
            else:
                return "Normal"
        except:
            return "Normal"
    
    def _calculate_htf_structure_metrics(self, data_1h: pd.DataFrame, entry_price: float, direction: str) -> Dict:
        """Calculate distance metrics relative to HTF structure"""
        try:
            # Get recent highs and lows for range calculation
            recent_data = data_1h.iloc[-50:] if len(data_1h) >= 50 else data_1h
            
            htf_high = recent_data['High'].max()
            htf_low = recent_data['Low'].min()
            htf_eq = (htf_high + htf_low) / 2
            
            # Distance to equilibrium
            distance_to_eq = abs(entry_price - htf_eq)
            
            # Distance to extreme (high for sells, low for buys)
            if direction == "SELL":
                distance_to_extreme = abs(entry_price - htf_high)
            else:
                distance_to_extreme = abs(entry_price - htf_low)
            
            # Distance to BOS level (approximate as last swing)
            distance_to_bos = 0
            if len(recent_data) > 5:
                if direction == "SELL":
                    distance_to_bos = abs(entry_price - recent_data['High'].iloc[-5:].max())
                else:
                    distance_to_bos = abs(entry_price - recent_data['Low'].iloc[-5:].min())
            
            return {
                'distance_to_eq': distance_to_eq,
                'distance_to_extreme': distance_to_extreme,
                'distance_to_bos': distance_to_bos
            }
        except:
            return {'distance_to_eq': 0, 'distance_to_extreme': 0, 'distance_to_bos': 0}
    
    def _calculate_pullback_metrics(self, data_15m: pd.DataFrame, signal: TradeSignal, entry_price: float) -> Dict:
        """Calculate pullback quality metrics"""
        try:
            # Get recent swing for retracement calculation
            recent_data = data_15m.iloc[-20:] if len(data_15m) >= 20 else data_15m
            
            if signal.direction == "SELL":
                impulse_high = recent_data['High'].max()
                impulse_low = recent_data['Low'].min()
                retrace_pct = ((entry_price - impulse_low) / (impulse_high - impulse_low) * 100) if impulse_high > impulse_low else 50
            else:
                impulse_high = recent_data['High'].max()
                impulse_low = recent_data['Low'].min()
                retrace_pct = ((impulse_high - entry_price) / (impulse_high - impulse_low) * 100) if impulse_high > impulse_low else 50
            
            # Classify entry location
            if retrace_pct < 40:
                entry_location = "Discount"
            elif retrace_pct > 60:
                entry_location = "Premium"
            else:
                entry_location = "Equilibrium"
            
            return {
                'retrace_pct': retrace_pct,
                'entry_location': entry_location
            }
        except:
            return {'retrace_pct': 50, 'entry_location': 'Unknown'}
