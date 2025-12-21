"""
Unit Tests for Trading Bot

Tests for trade_strategy.py, trader.py, and trader_with_dashboard.py
Uses mocking to avoid actual API calls to Robinhood.
"""
import pytest
import datetime as dt
from unittest.mock import Mock, patch, MagicMock
import pandas as pd


# ============================================================================
# Mock config module
# ============================================================================
@pytest.fixture
def mock_config():
    """Create a mock config module with test values."""
    config = Mock()
    config.username = "test_user"
    config.password = "test_pass"
    config.STOCKS = ["AAPL", "GOOGL", "MSFT"]
    config.SMA_WINDOW = 5
    config.SMA_UPDATE_INTERVAL = 1
    config.TRADING_BUFFER = 0.02
    config.CHECK_INTERVAL = 60
    config.MAX_CASH_PER_STOCK = 0.25
    config.MIN_SHARES_TO_BUY = 1
    config.MARKET_OPEN_HOUR = 9
    config.MARKET_OPEN_MINUTE = 30
    config.MARKET_CLOSE_HOUR = 16
    config.MARKET_CLOSE_MINUTE = 0
    config.SAVE_GRAPHS = False
    config.VERBOSE_LOGGING = True
    return config


# ============================================================================
# Tests for trade_strategy.py
# ============================================================================
class TestTradingStrategy:
    """Tests for the TradingStrategy class."""

    @pytest.fixture
    def strategy(self, mock_config):
        """Create a TradingStrategy instance with mocked dependencies."""
        with patch.dict('sys.modules', {'config': mock_config}):
            with patch('trade_strategy.config', mock_config):
                from trade_strategy import TradingStrategy
                return TradingStrategy(["AAPL", "GOOGL"])

    def test_init(self, strategy):
        """Test strategy initialization."""
        assert strategy.stocks == ["AAPL", "GOOGL"]
        assert strategy.run_time == 0
        assert strategy.sma_values == {"AAPL": 0, "GOOGL": 0}
        assert strategy.price_sma_ratios == {"AAPL": 0, "GOOGL": 0}

    def test_calculate_price_sma_ratio_normal(self, strategy):
        """Test price/SMA ratio calculation with normal values."""
        ratio = strategy.calculate_price_sma_ratio(105.0, 100.0)
        assert ratio == 1.05

    def test_calculate_price_sma_ratio_below_sma(self, strategy):
        """Test price/SMA ratio when price is below SMA."""
        ratio = strategy.calculate_price_sma_ratio(95.0, 100.0)
        assert ratio == 0.95

    def test_calculate_price_sma_ratio_zero_sma(self, strategy):
        """Test price/SMA ratio when SMA is zero (edge case)."""
        ratio = strategy.calculate_price_sma_ratio(100.0, 0)
        assert ratio == 1.0

    def test_calculate_sma(self, strategy, mock_config):
        """Test SMA calculation."""
        # Create sample price data
        dates = pd.date_range(start='2024-01-01', periods=10, freq='5min')
        prices = [100.0, 101.0, 102.0, 101.5, 100.5, 99.5, 100.0, 101.0, 102.0, 103.0]
        df_prices = pd.DataFrame({'AAPL': prices}, index=dates)
        
        with patch('trade_strategy.config', mock_config):
            sma = strategy.calculate_sma('AAPL', df_prices, window=5)
        
        # Expected SMA of last 5 values: (99.5 + 100.0 + 101.0 + 102.0 + 103.0) / 5 = 101.1
        assert sma == 101.1

    def test_increment_runtime(self, strategy):
        """Test runtime counter increment."""
        assert strategy.run_time == 0
        strategy.increment_runtime()
        assert strategy.run_time == 1
        strategy.increment_runtime()
        assert strategy.run_time == 2

    def test_get_status(self, strategy):
        """Test getting strategy status."""
        strategy.sma_values['AAPL'] = 150.0
        strategy.price_sma_ratios['AAPL'] = 1.02
        strategy.run_time = 5
        
        status = strategy.get_status('AAPL')
        
        assert status['sma'] == 150.0
        assert status['price_sma_ratio'] == 1.02
        assert status['runtime_minutes'] == 5

    def test_get_status_unknown_stock(self, strategy):
        """Test getting status for a stock not being tracked."""
        status = strategy.get_status('UNKNOWN')
        
        assert status['sma'] == 0
        assert status['price_sma_ratio'] == 0

    @patch('trade_strategy.rh')
    def test_get_historical_prices(self, mock_rh, strategy):
        """Test fetching historical prices."""
        mock_rh.stocks.get_stock_historicals.return_value = [
            {'begins_at': '2024-01-01T09:30:00Z', 'close_price': '150.00'},
            {'begins_at': '2024-01-01T09:35:00Z', 'close_price': '151.00'},
            {'begins_at': '2024-01-01T09:40:00Z', 'close_price': '152.00'},
        ]
        
        df = strategy.get_historical_prices('AAPL', span='day')
        
        assert len(df) == 3
        assert 'AAPL' in df.columns
        mock_rh.stocks.get_stock_historicals.assert_called_once()

    @patch('trade_strategy.rh')
    def test_get_historical_prices_empty(self, mock_rh, strategy):
        """Test handling of empty historical data."""
        mock_rh.stocks.get_stock_historicals.return_value = []
        
        df = strategy.get_historical_prices('AAPL', span='day')
        
        assert df.empty

    @patch('trade_strategy.rh')
    def test_get_trade_signal_buy(self, mock_rh, strategy, mock_config):
        """Test BUY signal generation when price is below SMA."""
        # Set up SMA value
        strategy.sma_values['AAPL'] = 100.0
        strategy.run_time = 1  # Skip SMA recalculation
        
        with patch('trade_strategy.config', mock_config):
            # Price at 97 is 3% below SMA (buffer is 2%)
            signal = strategy.get_trade_signal('AAPL', 97.0)
        
        assert signal == 'BUY'

    @patch('trade_strategy.rh')
    def test_get_trade_signal_sell(self, mock_rh, strategy, mock_config):
        """Test SELL signal generation when price is above SMA."""
        strategy.sma_values['AAPL'] = 100.0
        strategy.run_time = 1
        
        with patch('trade_strategy.config', mock_config):
            # Price at 103 is 3% above SMA (buffer is 2%)
            signal = strategy.get_trade_signal('AAPL', 103.0)
        
        assert signal == 'SELL'

    @patch('trade_strategy.rh')
    def test_get_trade_signal_hold(self, mock_rh, strategy, mock_config):
        """Test HOLD signal when price is near SMA."""
        strategy.sma_values['AAPL'] = 100.0
        strategy.run_time = 1
        
        with patch('trade_strategy.config', mock_config):
            # Price at 100.5 is only 0.5% above SMA (within 2% buffer)
            signal = strategy.get_trade_signal('AAPL', 100.5)
        
        assert signal == 'HOLD'


# ============================================================================
# Tests for trader_with_dashboard.py
# ============================================================================
class TestTrader:
    """Tests for the trader module functions."""

    @pytest.fixture
    def mock_rh(self):
        """Create a mock robin_stocks.robinhood module."""
        with patch('trader_with_dashboard.rh') as mock:
            yield mock

    @pytest.fixture
    def trader_module(self, mock_config):
        """Import trader module with mocked config."""
        with patch.dict('sys.modules', {'config': mock_config}):
            with patch('trader_with_dashboard.config', mock_config):
                import trader_with_dashboard as trader
                return trader

    def test_login(self, mock_rh, trader_module):
        """Test Robinhood login."""
        trader_module.login(days=7)
        
        mock_rh.authentication.login.assert_called_once()
        call_kwargs = mock_rh.authentication.login.call_args[1]
        assert call_kwargs['expiresIn'] == 60 * 60 * 24 * 7
        assert call_kwargs['store_session'] is True

    def test_logout(self, mock_rh, trader_module):
        """Test Robinhood logout."""
        trader_module.logout()
        
        mock_rh.authentication.logout.assert_called_once()

    def test_is_market_open_during_hours(self, trader_module, mock_config):
        """Test market open check during trading hours."""
        with patch('trader_with_dashboard.config', mock_config):
            # Mock time to be during market hours (10:30 AM)
            with patch('trader_with_dashboard.dt') as mock_dt:
                mock_dt.datetime.now.return_value.time.return_value = dt.time(10, 30, 0)
                mock_dt.time = dt.time
                
                assert trader_module.is_market_open() is True

    def test_is_market_open_after_hours(self, trader_module, mock_config):
        """Test market open check after trading hours."""
        with patch('trader_with_dashboard.config', mock_config):
            with patch('trader_with_dashboard.dt') as mock_dt:
                mock_dt.datetime.now.return_value.time.return_value = dt.time(17, 0, 0)
                mock_dt.time = dt.time
                
                assert trader_module.is_market_open() is False

    def test_is_market_open_before_hours(self, trader_module, mock_config):
        """Test market open check before trading hours."""
        with patch('trader_with_dashboard.config', mock_config):
            with patch('trader_with_dashboard.dt') as mock_dt:
                mock_dt.datetime.now.return_value.time.return_value = dt.time(8, 0, 0)
                mock_dt.time = dt.time
                
                assert trader_module.is_market_open() is False

    def test_get_account_cash(self, mock_rh, trader_module):
        """Test fetching account cash and equity."""
        mock_rh.account.build_user_profile.return_value = {
            'cash': '10000.50',
            'equity': '25000.75'
        }
        
        cash, equity = trader_module.get_account_cash()
        
        assert cash == 10000.50
        assert equity == 25000.75

    def test_get_holdings_and_prices(self, mock_rh, trader_module):
        """Test fetching current holdings."""
        mock_rh.account.build_holdings.return_value = {
            'AAPL': {'quantity': '10', 'average_buy_price': '150.00'},
            'GOOGL': {'quantity': '5', 'average_buy_price': '2800.00'}
        }
        
        holdings, prices = trader_module.get_holdings_and_prices(['AAPL', 'GOOGL', 'MSFT'])
        
        assert holdings['AAPL'] == 10
        assert holdings['GOOGL'] == 5
        assert holdings['MSFT'] == 0  # Not in holdings
        assert prices['AAPL'] == 150.00
        assert prices['GOOGL'] == 2800.00
        assert prices['MSFT'] == 0

    def test_get_holdings_empty(self, mock_rh, trader_module):
        """Test fetching holdings when account is empty."""
        mock_rh.account.build_holdings.return_value = {}
        
        holdings, prices = trader_module.get_holdings_and_prices(['AAPL'])
        
        assert holdings['AAPL'] == 0
        assert prices['AAPL'] == 0

    def test_execute_sell(self, mock_rh, trader_module, capsys):
        """Test sell order execution (dry run mode)."""
        trader_module.execute_sell('AAPL', 10, 155.00)
        
        captured = capsys.readouterr()
        assert 'SELL SIGNAL' in captured.out
        assert 'AAPL' in captured.out
        assert '10' in captured.out
        # Orders are commented out, so no actual order should be placed
        mock_rh.orders.order_sell_limit.assert_not_called()

    def test_execute_buy(self, mock_rh, trader_module, capsys):
        """Test buy order execution (dry run mode)."""
        trader_module.execute_buy('AAPL', 5, 150.00)
        
        captured = capsys.readouterr()
        assert 'BUY SIGNAL' in captured.out
        assert 'AAPL' in captured.out
        assert '5' in captured.out
        # Orders are commented out, so no actual order should be placed
        mock_rh.orders.order_buy_limit.assert_not_called()

    def test_save_dataframe(self, trader_module):
        """Test dataframe saving function."""
        df_trades = pd.DataFrame(columns=['AAPL'])
        df_prices = pd.DataFrame(columns=['AAPL'])
        
        result_trades, result_prices = trader_module.save_dataframe(
            df_trades, df_prices, '10:00:00'
        )
        
        # Function currently just returns the dataframes
        assert result_trades is df_trades
        assert result_prices is df_prices


# ============================================================================
# Tests for trader_with_dashboard.py
# ============================================================================
class TestTraderWithDashboard:
    """Tests for the trader module functions."""

    @pytest.fixture
    def mock_rh(self):
        """Create a mock robin_stocks.robinhood module."""
        with patch('trader_with_dashboard.rh') as mock:
            yield mock

    @pytest.fixture
    def mock_dashboard(self):
        """Create mock dashboard functions."""
        mock_update = Mock()
        mock_add_log = Mock()
        mock_state = {'running': False}
        return mock_update, mock_add_log, mock_state

    @pytest.fixture
    def dashboard_trader_module(self, mock_config, mock_dashboard):
        """Import trader_with_dashboard module with mocked dependencies."""
        mock_update, mock_add_log, mock_state = mock_dashboard
        
        with patch.dict('sys.modules', {'config': mock_config}):
            with patch('trader_with_dashboard.config', mock_config):
                with patch('trader_with_dashboard.DASHBOARD_ENABLED', True):
                    with patch('trader_with_dashboard.update_bot_state', mock_update):
                        with patch('trader_with_dashboard.add_trade_log', mock_add_log):
                            with patch('trader_with_dashboard.bot_state', mock_state):
                                import trader_with_dashboard as trader
                                trader.update_bot_state = mock_update
                                trader.add_trade_log = mock_add_log
                                trader.bot_state = mock_state
                                trader.DASHBOARD_ENABLED = True
                                return trader

    def test_login(self, mock_rh, dashboard_trader_module):
        """Test Robinhood login with dashboard version."""
        dashboard_trader_module.login(days=5)
        
        mock_rh.authentication.login.assert_called_once()
        call_kwargs = mock_rh.authentication.login.call_args[1]
        assert call_kwargs['expiresIn'] == 60 * 60 * 24 * 5

    def test_logout(self, mock_rh, dashboard_trader_module):
        """Test Robinhood logout with dashboard version."""
        dashboard_trader_module.logout()
        
        mock_rh.authentication.logout.assert_called_once()

    def test_execute_sell_with_dashboard(self, mock_rh, dashboard_trader_module, capsys):
        """Test sell execution updates dashboard."""
        dashboard_trader_module.execute_sell('AAPL', 10, 155.00)
        
        captured = capsys.readouterr()
        assert 'SELL SIGNAL' in captured.out
        
        # Verify dashboard was updated
        dashboard_trader_module.add_trade_log.assert_called_once_with(
            'AAPL', 'SELL', 10, 154.90  # Price minus $0.10
        )

    def test_execute_buy_with_dashboard(self, mock_rh, dashboard_trader_module, capsys):
        """Test buy execution updates dashboard."""
        dashboard_trader_module.execute_buy('GOOGL', 3, 2800.00)
        
        captured = capsys.readouterr()
        assert 'BUY SIGNAL' in captured.out
        
        # Verify dashboard was updated
        dashboard_trader_module.add_trade_log.assert_called_once_with(
            'GOOGL', 'BUY', 3, 2800.10  # Price plus $0.10
        )

    def test_get_account_cash(self, mock_rh, dashboard_trader_module):
        """Test fetching account info."""
        mock_rh.account.build_user_profile.return_value = {
            'cash': '5000.00',
            'equity': '15000.00'
        }
        
        cash, equity = dashboard_trader_module.get_account_cash()
        
        assert cash == 5000.00
        assert equity == 15000.00

    def test_get_holdings_and_prices(self, mock_rh, dashboard_trader_module):
        """Test fetching holdings with dashboard version."""
        mock_rh.account.build_holdings.return_value = {
            'MSFT': {'quantity': '20', 'average_buy_price': '380.50'}
        }
        
        holdings, prices = dashboard_trader_module.get_holdings_and_prices(['MSFT', 'AAPL'])
        
        assert holdings['MSFT'] == 20
        assert holdings['AAPL'] == 0
        assert prices['MSFT'] == 380.50


# ============================================================================
# Integration-style tests
# ============================================================================
class TestIntegration:
    """Integration tests that test components working together."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config for integration tests."""
        config = Mock()
        config.STOCKS = ["AAPL"]
        config.SMA_WINDOW = 3
        config.SMA_UPDATE_INTERVAL = 1
        config.TRADING_BUFFER = 0.02
        config.MAX_CASH_PER_STOCK = 0.5
        config.MIN_SHARES_TO_BUY = 1
        config.VERBOSE_LOGGING = False
        return config

    def test_strategy_signal_flow(self, mock_config):
        """Test the complete flow from price data to trade signal."""
        with patch.dict('sys.modules', {'config': mock_config}):
            with patch('trade_strategy.config', mock_config):
                with patch('trade_strategy.rh') as mock_rh:
                    from trade_strategy import TradingStrategy
                    
                    # Set up historical data
                    mock_rh.stocks.get_stock_historicals.return_value = [
                        {'begins_at': '2024-01-01T09:30:00Z', 'close_price': '100.00'},
                        {'begins_at': '2024-01-01T09:35:00Z', 'close_price': '100.00'},
                        {'begins_at': '2024-01-01T09:40:00Z', 'close_price': '100.00'},
                    ]
                    
                    strategy = TradingStrategy(["AAPL"])
                    
                    # First call calculates SMA (run_time is 0, which is divisible by 1)
                    signal = strategy.get_trade_signal('AAPL', 100.0)
                    assert signal == 'HOLD'  # Price equals SMA
                    
                    # Verify SMA was calculated
                    assert strategy.sma_values['AAPL'] == 100.0

    def test_buy_sell_price_adjustment(self):
        """Test that buy/sell prices are adjusted by $0.10."""
        with patch('trader_with_dashboard.rh'):
            import trader_with_dashboard as trader
            
            # Test that sell uses price - 0.10
            with patch('builtins.print') as mock_print:
                trader.execute_sell('AAPL', 10, 150.00)
                call_args = str(mock_print.call_args_list)
                assert '149.9' in call_args  # 150.00 - 0.10
            
            # Test that buy uses price + 0.10
            with patch('builtins.print') as mock_print:
                trader.execute_buy('AAPL', 10, 150.00)
                call_args = str(mock_print.call_args_list)
                assert '150.1' in call_args  # 150.00 + 0.10


# ============================================================================
# Edge case tests
# ============================================================================
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_stocks_list(self, mock_config):
        """Test strategy initialization with empty stocks list."""
        with patch.dict('sys.modules', {'config': mock_config}):
            with patch('trade_strategy.config', mock_config):
                from trade_strategy import TradingStrategy
                
                strategy = TradingStrategy([])
                assert strategy.stocks == []
                assert strategy.sma_values == {}

    def test_very_small_price(self, mock_config):
        """Test ratio calculation with very small prices."""
        with patch.dict('sys.modules', {'config': mock_config}):
            with patch('trade_strategy.config', mock_config):
                from trade_strategy import TradingStrategy
                
                strategy = TradingStrategy(["PENNY"])
                ratio = strategy.calculate_price_sma_ratio(0.01, 0.02)
                assert ratio == 0.5

    def test_holdings_with_fractional_shares(self):
        """Test handling of fractional shares (rounds down to int)."""
        with patch('trader_with_dashboard.rh') as mock_rh:
            mock_rh.account.build_holdings.return_value = {
                'AAPL': {'quantity': '10.5', 'average_buy_price': '150.00'}
            }
            
            import trader_with_dashboard as trader
            holdings, _ = trader.get_holdings_and_prices(['AAPL'])
            
            assert holdings['AAPL'] == 10  # Should be integer

    def test_negative_ratio_handling(self, mock_config):
        """Test that negative prices don't break ratio calculation."""
        with patch.dict('sys.modules', {'config': mock_config}):
            with patch('trade_strategy.config', mock_config):
                from trade_strategy import TradingStrategy
                
                strategy = TradingStrategy(["TEST"])
                # This shouldn't happen in real trading, but test robustness
                ratio = strategy.calculate_price_sma_ratio(-10.0, 100.0)
                assert ratio == -0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
