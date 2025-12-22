from __future__ import annotations

import pandas as pd
import warnings
import logging
from typing import Optional, Tuple

# Import base ATR calculation for internal use
from .utils import calculate_atr as _base_calculate_atr


class RiskManager:
    """
    Enhanced risk management utilities with improved validation and realism.

    - Dynamic ATR calculation for volatility-aware stops
    - Automated position sizing to risk a fixed fraction of capital
    - Minimum stop loss bounds and maximum position size limits
    - Comprehensive validation and logging
    """

    def __init__(self,
                 risk_per_trade: float = 0.02,
                 atr_period: int = 14,
                 atr_multiplier: float = 2.0,
                 min_stop_pips: float = 5.0,
                 max_leverage: float = 10.0,
                 max_position_size: float = 100.0,
                 slippage_buffer: float = 0.5,
                 spread_pips: float = 1.0,
                 account_currency: str = "USD",
                 symbol_config: dict = None):
        self.risk_per_trade = risk_per_trade
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.min_stop_pips = min_stop_pips
        self.max_leverage = max_leverage
        self.max_position_size = max_position_size
        self.slippage_buffer = slippage_buffer
        self.spread_pips = spread_pips  # NEW: Spread in pips
        self.account_currency = account_currency.upper()  # NEW: Account base currency
        
        # Symbol configuration for pip values and decimal places
        self.symbol_config = symbol_config or self._get_default_symbol_config()
        
        # Setup logging
        self.logger = logging.getLogger(__name__)

    def _get_default_symbol_config(self) -> dict:
        """
        Get default symbol configuration with pip decimals and custom pip values.
        
        Returns:
            Dictionary with symbol configurations
        """
        return {
            # Major pairs (4 decimal places, 1 pip = 0.0001)
            'EURUSD': {'pip_decimals': 4, 'custom_pip_value': None},
            'GBPUSD': {'pip_decimals': 4, 'custom_pip_value': None},
            'AUDUSD': {'pip_decimals': 4, 'custom_pip_value': None},
            'NZDUSD': {'pip_decimals': 4, 'custom_pip_value': None},
            'USDCAD': {'pip_decimals': 4, 'custom_pip_value': None},
            'USDCHF': {'pip_decimals': 4, 'custom_pip_value': None},
            
            # JPY pairs (2 decimal places, 1 pip = 0.01)
            'USDJPY': {'pip_decimals': 2, 'custom_pip_value': None},
            'EURJPY': {'pip_decimals': 2, 'custom_pip_value': None},
            'GBPJPY': {'pip_decimals': 2, 'custom_pip_value': None},
            'AUDJPY': {'pip_decimals': 2, 'custom_pip_value': None},
            'NZDJPY': {'pip_decimals': 2, 'custom_pip_value': None},
            'CADJPY': {'pip_decimals': 2, 'custom_pip_value': None},
            'CHFJPY': {'pip_decimals': 2, 'custom_pip_value': None},
            
            # Gold (2 decimal places, but pip value can vary by broker)
            'XAUUSD': {'pip_decimals': 2, 'custom_pip_value': 0.01},
            'GOLD': {'pip_decimals': 2, 'custom_pip_value': 0.01},
            
            # Silver (3 decimal places)
            'XAGUSD': {'pip_decimals': 3, 'custom_pip_value': None},
            'SILVER': {'pip_decimals': 3, 'custom_pip_value': None},
            
            # Crypto (varies by exchange, using common values)
            'BTCUSD': {'pip_decimals': 2, 'custom_pip_value': 1.0},  # 1 USD per pip
            'ETHUSD': {'pip_decimals': 2, 'custom_pip_value': 0.1},  # 0.1 USD per pip
            'LTCUSD': {'pip_decimals': 2, 'custom_pip_value': 0.1},
            'ADAUSD': {'pip_decimals': 4, 'custom_pip_value': 0.0001},
            
            # Indices (varies by broker)
            'SPX500': {'pip_decimals': 1, 'custom_pip_value': 0.1},
            'NAS100': {'pip_decimals': 1, 'custom_pip_value': 0.1},
            'US30': {'pip_decimals': 1, 'custom_pip_value': 1.0},
            
            # Default fallback
            'DEFAULT': {'pip_decimals': 4, 'custom_pip_value': None}
        }

    def add_symbol_config(self, symbol: str, pip_decimals: int, custom_pip_value: float = None):
        """
        Add or update symbol configuration.
        
        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            pip_decimals: Number of decimal places for pip calculation
            custom_pip_value: Custom pip value (overrides calculated value)
        """
        symbol = symbol.upper()
        self.symbol_config[symbol] = {
            'pip_decimals': pip_decimals,
            'custom_pip_value': custom_pip_value
        }
        self.logger.info(f"Added symbol config: {symbol} - {pip_decimals} decimals, pip_value={custom_pip_value}")

    def get_symbol_config(self, symbol: str) -> dict:
        """
        Get symbol configuration with fallback to default.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Symbol configuration dictionary
        """
        symbol = symbol.upper()
        if symbol in self.symbol_config:
            return self.symbol_config[symbol]
        else:
            self.logger.warning(f"Symbol {symbol} not found in config, using default")
            return self.symbol_config['DEFAULT']

    # --- ATR ---
    def calculate_atr(self, data: pd.DataFrame, period: int | None = None) -> pd.Series:
        """
        Return ATR series for given OHLCV DataFrame with validation.
        
        Args:
            data: OHLCV DataFrame
            period: ATR period (defaults to self.atr_period)
            
        Returns:
            ATR series with validation warnings
        """
        # Debug ATR calculation
        print(f"ATR input data shape: {data.shape}")
        print(f"Data columns: {data.columns.tolist()}")
        print(f"First few rows:\n{data.head()}")
        
        if data is None or data.empty:
            self.logger.warning("Empty or None data provided for ATR calculation")
            return pd.Series(dtype=float)

        period_to_use = period if period is not None else self.atr_period
        
        # Validate required columns
        required_cols = ['High', 'Low', 'Close']
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            self.logger.error(f"Missing required columns for ATR: {missing_cols}")
            return pd.Series(dtype=float)

        # Use base utility function for ATR calculation
        atr = _base_calculate_atr(data, period=period_to_use)
        
        # Validate ATR values (only warn if there are unexpected NaN values after the warmup period)
        invalid_atr_count = atr.isna().sum()
        expected_nan_count = min(period_to_use - 1, len(atr))  # First (period-1) values should be NaN
        unexpected_nan_count = invalid_atr_count - expected_nan_count
        
        if unexpected_nan_count > 0:
            self.logger.warning(f"ATR calculation produced {unexpected_nan_count} unexpected invalid values")
        
        return atr

    # --- Stops / Targets ---
    def compute_stop_and_target_from_atr(self,
                                         market_price: float,
                                         direction: str,
                                         atr_value: float,
                                         reward_risk_ratio: float,
                                         symbol: str = "EURUSD") -> Optional[Tuple[float, float]]:
        """
        Compute stop-loss and take-profit using ATR based on market price (without spread).
        This calculates the theoretical stops before applying spread and slippage.

        Args:
            market_price: Market close price (without spread)
            direction: "BUY" or "SELL"
            atr_value: ATR value for the period
            reward_risk_ratio: Risk-reward ratio (e.g., 2.0 for 1:2)
            symbol: Trading symbol for pip calculation

        Returns:
            Tuple of (stop_loss, take_profit) or None if invalid
        """
        # Validate inputs
        if pd.isna(atr_value) or atr_value <= 0:
            self.logger.warning(f"Invalid ATR value: {atr_value}. Cannot compute stops.")
            return None
            
        if market_price <= 0:
            self.logger.error(f"Invalid market price: {market_price}")
            return None
            
        if reward_risk_ratio <= 0:
            self.logger.error(f"Invalid reward-risk ratio: {reward_risk_ratio}")
            return None

        # Calculate pip value for minimum stop validation
        pip_value = self._get_pip_value(symbol, market_price)
        min_stop_distance = self.min_stop_pips * pip_value

        # Calculate ATR-based risk distance
        risk_distance = atr_value * self.atr_multiplier
        
        # Apply minimum stop bound
        if risk_distance < min_stop_distance:
            self.logger.warning(f"ATR-based stop ({risk_distance:.5f}) below minimum ({min_stop_distance:.5f}). Using minimum.")
            risk_distance = min_stop_distance

        # Calculate stops and targets based on market price (no spread/slippage yet)
        if direction.upper() == "BUY":
            stop_loss = market_price - risk_distance
            take_profit = market_price + risk_distance * reward_risk_ratio
        elif direction.upper() == "SELL":
            stop_loss = market_price + risk_distance
            take_profit = market_price - risk_distance * reward_risk_ratio
        else:
            self.logger.error(f"Invalid direction: {direction}. Must be 'BUY' or 'SELL'")
            return None

        # Validate stops are reasonable
        if stop_loss <= 0 or take_profit <= 0:
            self.logger.error(f"Invalid stop levels: SL={stop_loss}, TP={take_profit}")
            return None

        # Log the setup for debugging
        self.logger.info(f"Risk setup (market price): Market={market_price:.5f}, SL={stop_loss:.5f}, TP={take_profit:.5f}, "
                        f"Risk={risk_distance:.5f}, RR={reward_risk_ratio:.1f}")

        return stop_loss, take_profit

    def apply_spread_and_slippage(self,
                                 market_price: float,
                                 stop_loss: float,
                                 take_profit: float,
                                 direction: str,
                                 symbol: str = "EURUSD") -> Tuple[float, float, float]:
        """
        Apply spread to entry price and slippage to stop loss for realistic trade execution.
        
        Args:
            market_price: Market close price (without spread)
            stop_loss: Stop loss based on market price
            take_profit: Take profit based on market price
            direction: "BUY" or "SELL"
            symbol: Trading symbol for pip calculation
            
        Returns:
            Tuple of (adjusted_entry_price, adjusted_stop_loss, adjusted_take_profit)
        """
        # Calculate pip value
        pip_value = self._get_pip_value(symbol, market_price)
        
        # Calculate spread in price units
        spread_price = self.spread_pips * pip_value
        
        # Calculate slippage in price units
        slippage_price = self.slippage_buffer * pip_value
        
        if direction.upper() == "BUY":
            # BUY: Entry at ASK price (market_price + spread/2)
            adjusted_entry_price = market_price + (spread_price / 2)
            # Stop loss gets slippage buffer (worse for us)
            adjusted_stop_loss = stop_loss - slippage_price
            # Take profit stays the same (no slippage on TP)
            adjusted_take_profit = take_profit
            
        elif direction.upper() == "SELL":
            # SELL: Entry at BID price (market_price - spread/2)
            adjusted_entry_price = market_price - (spread_price / 2)
            # Stop loss gets slippage buffer (worse for us)
            adjusted_stop_loss = stop_loss + slippage_price
            # Take profit stays the same (no slippage on TP)
            adjusted_take_profit = take_profit
            
        else:
            self.logger.error(f"Invalid direction: {direction}. Must be 'BUY' or 'SELL'")
            return market_price, stop_loss, take_profit
        
        # Log the adjustments
        self.logger.info(f"Trade execution adjustments: Market={market_price:.5f} -> Entry={adjusted_entry_price:.5f}, "
                        f"SL={stop_loss:.5f} -> {adjusted_stop_loss:.5f}, TP={take_profit:.5f} -> {adjusted_take_profit:.5f}, "
                        f"Spread={spread_price:.5f}, Slippage={slippage_price:.5f}")
        
        return adjusted_entry_price, adjusted_stop_loss, adjusted_take_profit

    def compute_realistic_trade_setup(self,
                                     market_price: float,
                                     direction: str,
                                     atr_value: float,
                                     reward_risk_ratio: float,
                                     symbol: str = "EURUSD") -> Optional[Tuple[float, float, float]]:
        """
        Compute complete trade setup with realistic spread and slippage adjustments.
        
        Args:
            market_price: Market close price (without spread)
            direction: "BUY" or "SELL"
            atr_value: ATR value for the period
            reward_risk_ratio: Risk-reward ratio (e.g., 2.0 for 1:2)
            symbol: Trading symbol for pip calculation
            
        Returns:
            Tuple of (entry_price, stop_loss, take_profit) with spread and slippage applied
        """
        # First, calculate stops based on market price
        stop_result = self.compute_stop_and_target_from_atr(
            market_price=market_price,
            direction=direction,
            atr_value=atr_value,
            reward_risk_ratio=reward_risk_ratio,
            symbol=symbol
        )
        
        if stop_result is None:
            return None
        
        stop_loss, take_profit = stop_result
        
        # Then apply spread and slippage adjustments
        entry_price, adjusted_stop_loss, adjusted_take_profit = self.apply_spread_and_slippage(
            market_price=market_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            direction=direction,
            symbol=symbol
        )
        
        return entry_price, adjusted_stop_loss, adjusted_take_profit

    # --- Position sizing ---
    def calculate_position_size(self,
                                entry_price: float,
                                stop_loss: float,
                                risk_amount: float,
                                account_balance: float,
                                symbol: str = "EURUSD") -> float:
        """
        Calculate position size with enhanced validation and limits.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_amount: Amount to risk
            account_balance: Account balance
            symbol: Trading symbol
            
        Returns:
            Position size with validation and limits applied
        """
        # Validate inputs
        if entry_price <= 0 or stop_loss <= 0:
            self.logger.error(f"Invalid prices: Entry={entry_price}, SL={stop_loss}")
            return 0.0
            
        if risk_amount <= 0:
            self.logger.error(f"Invalid risk amount: {risk_amount}")
            return 0.0
            
        if account_balance <= 0:
            self.logger.error(f"Invalid account balance: {account_balance}")
            return 0.0

        # Calculate base position size
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            self.logger.warning("Zero risk per unit - cannot calculate position size")
            return 0.0
            
        base_position_size = risk_amount / risk_per_unit
        
        # Apply maximum position size limit
        if base_position_size > self.max_position_size:
            self.logger.warning(f"Position size ({base_position_size:.2f}) exceeds maximum ({self.max_position_size}). Capping.")
            base_position_size = self.max_position_size
        
        # Apply leverage limit with proper currency conversion
        conversion_rate = self._get_currency_conversion_rate(symbol, entry_price)
        max_position_by_leverage = account_balance * self.max_leverage / (entry_price * conversion_rate)
        if base_position_size > max_position_by_leverage:
            self.logger.warning(f"Position size ({base_position_size:.2f}) exceeds leverage limit ({max_position_by_leverage:.2f}). Capping.")
            base_position_size = max_position_by_leverage
        
        # Log position sizing details with proper leverage calculation
        position_value_in_account_currency = base_position_size * entry_price * conversion_rate
        actual_leverage = position_value_in_account_currency / account_balance
        self.logger.info(f"Position sizing: Risk={risk_amount:.2f}, Risk/Unit={risk_per_unit:.5f}, "
                        f"Size={base_position_size:.2f}, Leverage={actual_leverage:.2f}x, "
                        f"Conversion Rate={conversion_rate:.6f}")
        
        return base_position_size

    def risk_amount_for_balance(self, account_balance: float) -> float:
        """Calculate risk amount based on account balance and risk per trade."""
        if account_balance <= 0:
            self.logger.error(f"Invalid account balance: {account_balance}")
            return 0.0
        return account_balance * self.risk_per_trade

    # --- Validation and debugging ---
    def validate_risk_setup(self,
                           entry_price: float,
                           stop_loss: float,
                           take_profit: float,
                           position_size: float,
                           account_balance: float,
                           symbol: str = "EURUSD") -> dict:
        """
        Comprehensive validation of risk setup with detailed logging.
        
        Returns:
            Dictionary with validation results and metrics
        """
        validation = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'metrics': {}
        }
        
        # Basic validation
        if entry_price <= 0:
            validation['errors'].append(f"Invalid entry price: {entry_price}")
            validation['valid'] = False
            
        if stop_loss <= 0:
            validation['errors'].append(f"Invalid stop loss: {stop_loss}")
            validation['valid'] = False
            
        if take_profit <= 0:
            validation['errors'].append(f"Invalid take profit: {take_profit}")
            validation['valid'] = False
            
        if position_size <= 0:
            validation['errors'].append(f"Invalid position size: {position_size}")
            validation['valid'] = False
        
        if not validation['valid']:
            return validation
        
        # Calculate metrics
        risk_distance = abs(entry_price - stop_loss)
        reward_distance = abs(take_profit - entry_price)
        reward_risk_ratio = reward_distance / risk_distance if risk_distance > 0 else 0
        
        pip_value = self._get_pip_value(symbol, entry_price)
        risk_pips = risk_distance / pip_value
        reward_pips = reward_distance / pip_value
        
        position_value = position_size * entry_price
        leverage = position_value / account_balance
        risk_amount = position_size * risk_distance
        
        validation['metrics'] = {
            'risk_distance': risk_distance,
            'reward_distance': reward_distance,
            'reward_risk_ratio': reward_risk_ratio,
            'risk_pips': risk_pips,
            'reward_pips': reward_pips,
            'position_value': position_value,
            'leverage': leverage,
            'risk_amount': risk_amount,
            'risk_percentage': (risk_amount / account_balance) * 100
        }
        
        # Validation checks
        if reward_risk_ratio < 1.0:
            validation['warnings'].append(f"Poor risk-reward ratio: {reward_risk_ratio:.2f}")
            
        if leverage > self.max_leverage:
            validation['errors'].append(f"Excessive leverage: {leverage:.2f}x (max: {self.max_leverage}x)")
            validation['valid'] = False
            
        if risk_pips < self.min_stop_pips:
            validation['warnings'].append(f"Small stop loss: {risk_pips:.1f} pips (min: {self.min_stop_pips})")
            
        if (risk_amount / account_balance) > self.risk_per_trade * 1.1:  # 10% tolerance
            validation['warnings'].append(f"Risk exceeds target: {(risk_amount / account_balance) * 100:.1f}% (target: {self.risk_per_trade * 100:.1f}%)")
        
        # Log validation results
        if validation['warnings']:
            self.logger.warning(f"Risk setup warnings: {validation['warnings']}")
        if validation['errors']:
            self.logger.error(f"Risk setup errors: {validation['errors']}")
        else:
            self.logger.info(f"Risk setup validated: RR={reward_risk_ratio:.2f}, Risk={risk_amount:.2f}, Leverage={leverage:.2f}x")
        
        return validation

    # --- Helper methods ---
    def _get_pip_value(self, symbol: str, price: float = None) -> float:
        """
        Calculate pip value for different symbols using flexible configuration.
        
        Args:
            symbol: Trading symbol
            price: Current price (used for JPY pairs and some calculations)
            
        Returns:
            Pip value for the symbol
        """
        symbol = symbol.upper()
        config = self.get_symbol_config(symbol)
        
        # Use custom pip value if specified
        if config['custom_pip_value'] is not None:
            return config['custom_pip_value']
        
        # Calculate pip value based on decimal places
        pip_decimals = config['pip_decimals']
        pip_value = 10 ** (-pip_decimals)
        
        # Special handling for JPY pairs (pip value depends on price)
        if symbol.endswith('JPY') and price is not None and price > 0:
            # For JPY pairs, pip value = 0.01 * (1 / price)
            # This gives the pip value in the quote currency
            pip_value = 0.01 / price
        
        return pip_value

    def _get_currency_conversion_rate(self, symbol: str, entry_price: float) -> float:
        """
        Calculate currency conversion rate from symbol's base currency to account currency.
        
        Args:
            symbol: Trading symbol (e.g., 'EURUSD', 'USDJPY', 'XAUUSD')
            entry_price: Current entry price
            
        Returns:
            Conversion rate to convert position value to account currency
        """
        symbol = symbol.upper()
        
        # Extract base and quote currencies from symbol
        if len(symbol) == 6:  # Standard forex pair (e.g., EURUSD)
            base_currency = symbol[:3]
            quote_currency = symbol[3:]
        elif symbol in ['XAUUSD', 'XAGUSD', 'GOLD', 'SILVER']:  # Precious metals
            base_currency = symbol[:3] if symbol.startswith('XAU') or symbol.startswith('XAG') else symbol
            quote_currency = 'USD'
        elif symbol.endswith('USD'):  # Crypto or other USD-denominated
            base_currency = symbol[:-3]
            quote_currency = 'USD'
        else:
            # Default fallback - assume USD-denominated
            self.logger.warning(f"Unknown symbol format: {symbol}, assuming USD-denominated")
            return 1.0
        
        # If quote currency matches account currency, conversion rate is 1.0
        if quote_currency == self.account_currency:
            return 1.0
        
        # If base currency matches account currency, conversion rate is 1/price
        if base_currency == self.account_currency:
            return 1.0 / entry_price if entry_price > 0 else 1.0
        
        # For cross-currency pairs, we need additional conversion logic
        # This is a simplified approach - in practice, you'd need real-time rates
        if self.account_currency == 'USD':
            # Common USD conversion rates (simplified)
            if base_currency == 'EUR' and quote_currency == 'USD':
                return 1.0  # EURUSD: 1 EUR = entry_price USD
            elif base_currency == 'USD' and quote_currency == 'JPY':
                return 1.0 / entry_price  # USDJPY: 1 USD = entry_price JPY
            elif base_currency == 'GBP' and quote_currency == 'USD':
                return 1.0  # GBPUSD: 1 GBP = entry_price USD
            elif base_currency == 'AUD' and quote_currency == 'USD':
                return 1.0  # AUDUSD: 1 AUD = entry_price USD
            elif base_currency == 'XAU' and quote_currency == 'USD':
                return 1.0  # XAUUSD: 1 oz gold = entry_price USD
            elif base_currency == 'BTC' and quote_currency == 'USD':
                return 1.0  # BTCUSD: 1 BTC = entry_price USD
            else:
                # Default: assume 1:1 conversion (may need adjustment)
                self.logger.warning(f"Unknown currency pair: {base_currency}{quote_currency}, using 1:1 conversion")
                return 1.0
        else:
            # For non-USD accounts, you'd need more complex conversion logic
            self.logger.warning(f"Non-USD account currency ({self.account_currency}) not fully supported, using 1:1 conversion")
            return 1.0


