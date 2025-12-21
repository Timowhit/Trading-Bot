"""
Robinhood Trading Bot with Web Dashboard
=========================================
A combined trading bot with a real-time web dashboard.
The dashboard opens automatically in your browser when you run this file.

Features:
    - Real-time portfolio monitoring
    - Options positions display
    - Start/Stop bot from web interface
    - Configurable settings
    - Trade logging

================================================================================
EXTERNAL FILES AND DEPENDENCIES
================================================================================

REQUIRED EXTERNAL FILES:
------------------------
1. .env (must be created by user)
   - Location: Same directory as this script
   - Purpose: Stores Robinhood login credentials securely
   - Required contents:
       ROBINHOOD_USERNAME=your_username
       ROBINHOOD_PASSWORD=your_password

2. bot_settings.json (auto-generated)
   - Location: Same directory as this script
   - Purpose: Stores user-configured settings (stocks, trading parameters)
   - Created automatically when you save settings from the web interface
   - Can be manually edited if needed

BUILT-IN CONFIGURATION (no external file needed):
-------------------------------------------------
3. Config class (built into this file)
   - Located in the DEFAULT CONFIGURATION section below
   - Contains default stocks, trading parameters, market hours, etc.
   - Edit the Config class directly to change defaults
   - Or use the web Settings page to override without editing code
   
   Default stocks: QQQ, SPY, VOO, V, HOOD
   Default trading buffer: 2% (0.02)
   Default SMA window: 12 periods
   Default max cash per stock: 25%
   Default check interval: 30 seconds

REQUIRED PYTHON PACKAGES (install via pip):
-------------------------------------------
- flask          : Web framework for the dashboard
- robin-stocks   : Robinhood API wrapper
- python-dotenv  : Loads credentials from .env file
- pandas         : Data manipulation (used by robin-stocks)

Install all with:
    pip install flask robin-stocks python-dotenv pandas

================================================================================
"""

# ============================================================================
# IMPORTS
# ============================================================================

import os                      # For accessing environment variables and file paths
import threading               # For running bot and browser opener in background threads
import datetime as dt          # For timestamps and market hours checking
import json                    # For saving/loading settings to JSON file
import time                    # For sleep delays between checks
import webbrowser              # For auto-opening dashboard in browser

from flask import Flask, render_template_string, jsonify, request  # Web framework
import robin_stocks.robinhood as rh   # Robinhood API wrapper
from dotenv import load_dotenv        # Loads .env file into environment variables

# Load environment variables from .env file
# This reads ROBINHOOD_USERNAME and ROBINHOOD_PASSWORD from .env
load_dotenv()

# Initialize Flask web application
# Flask handles all the web routes and serves the dashboard
app = Flask(__name__)


# ============================================================================
# DEFAULT CONFIGURATION - Built-in settings (replaces external config.py)
# ============================================================================
# These defaults are used if no bot_settings.json exists
# Users can override these via the Settings page in the web interface

class Config:
    """
    Default configuration for the trading bot.
    
    All settings can be overridden via the web interface's Settings page,
    which saves to bot_settings.json.
    """
    
    # ========================================================================
    # STOCKS TO TRADE
    # ========================================================================
    # Add or remove stock tickers you want to trade
    # These are just examples - customize via Settings page or edit here
    STOCKS = [
        "QQQ",   # Invesco QQQ Trust (Nasdaq-100 ETF)
        "SPY",   # SPDR S&P 500 ETF Trust
        "VOO",   # Vanguard S&P 500 ETF
        "V",     # Visa Inc.
        "HOOD",  # Robinhood Markets Inc.
    ]
    
    # ========================================================================
    # TRADING PARAMETERS
    # ========================================================================
    
    # Buffer for buy/sell decisions (0.02 = 2%)
    # Lower = more sensitive (more trades)
    # Higher = less sensitive (fewer trades)
    # Example: 0.02 means buy when price is 2% below SMA, sell when 2% above
    TRADING_BUFFER = 0.02
    
    # SMA window size (number of price points to average)
    # Default: 12 periods
    # With 30-second intervals: 12 * 30s = 6 minutes of price history
    # With 5-minute intervals: 12 * 5min = 1 hour of price history
    SMA_WINDOW = 12
    
    # Maximum percentage of cash to invest in a single stock
    # 0.25 = 25% of available cash per stock
    # Lower = more diversified, Higher = more concentrated
    MAX_CASH_PER_STOCK = 0.25
    
    # Minimum shares to buy (prevents buying too few shares)
    # Skip buy signal if we can't afford at least this many shares
    MIN_SHARES_TO_BUY = 1
    
    # ========================================================================
    # MARKET HOURS (Eastern Time)
    # ========================================================================
    # Regular market hours: 9:30 AM - 4:00 PM ET
    # Bot will only trade during these hours
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 30
    MARKET_CLOSE_HOUR = 15      # 3 PM (bot stops before 4 PM close)
    MARKET_CLOSE_MINUTE = 59    # 3:59 PM
    
    # How often to check prices (in seconds)
    # 30 seconds is a good balance between responsiveness and API limits
    # Lower = more responsive but more API calls
    # Higher = fewer API calls but slower reaction
    CHECK_INTERVAL = 30
    
    # ========================================================================
    # DISPLAY SETTINGS
    # ========================================================================
    
    # Save trading graphs (True/False)
    # If True, creates price/trade visualizations
    SAVE_GRAPHS = True
    
    # Show detailed logging in console (True/False)
    # If True, prints extra debug information
    VERBOSE_LOGGING = True


# Create a global config instance for easy access
config = Config()


# ============================================================================
# BOT STATE - Global dictionary storing all current bot/portfolio information
# ============================================================================

# This dictionary is shared between the web dashboard and the trading bot
# It gets updated in real-time and the dashboard reads from it
bot_state = {
    'running': False,          # Whether the trading bot is currently active
    'last_update': None,       # Timestamp of last data refresh
    'holdings': {},            # Simple dict of {stock: quantity}
    'holdings_info': {},       # Detailed holdings info (avg price, equity, P/L, etc.)
    'options': [],             # List of options positions
    'prices': {},              # Current prices for each stock {stock: price}
    'signals': {},             # Trading signals for each stock {stock: 'BUY'/'SELL'/'HOLD'/'WAIT'}
    'sma_values': {},          # Simple Moving Average values {stock: sma}
    'ratios': {},              # Price-to-SMA ratios {stock: ratio}
    'cash': 0,                 # Available cash in account
    'equity': 0,               # Total portfolio equity
    'trade_log': [],           # List of recent trades (for display in dashboard)
    'configured_stocks': []    # List of stocks user has configured to monitor
}

# Thread lock to prevent race conditions when multiple threads access bot_state
# This ensures data integrity when the bot thread and web thread access the same data
state_lock = threading.Lock()

# File where user settings are saved (stocks to watch, trading parameters, etc.)
SETTINGS_FILE = 'bot_settings.json'

# Thread reference for the trading bot (so we can check if it's running)
bot_thread = None

# Event flag to signal the bot to stop gracefully
# When set, the bot will finish its current iteration and exit
stop_bot_event = threading.Event()


# ============================================================================
# SETTINGS MANAGEMENT - Functions for loading and saving user configuration
# ============================================================================

def load_settings():
    """
    Load bot settings from file or use defaults.
    
    Settings priority:
    1. bot_settings.json (if exists) - User's saved settings from web interface
    2. Built-in Config class defaults - Hard-coded in this file
    
    Returns:
        dict: Settings dictionary with all configuration values
    """
    # Default settings from the built-in Config class
    default_settings = {
        'stocks': Config.STOCKS.copy(),                    # List of stock symbols to monitor
        'trading_buffer': Config.TRADING_BUFFER,           # Deviation from SMA to trigger trade
        'sma_window': Config.SMA_WINDOW,                   # Number of data points for SMA
        'max_cash_per_stock': Config.MAX_CASH_PER_STOCK,   # Max % of cash per single trade
        'min_shares_to_buy': Config.MIN_SHARES_TO_BUY,     # Min shares to make a buy worthwhile
        'check_interval': Config.CHECK_INTERVAL,           # Seconds between price checks
        'auto_refresh': True,                              # Auto-refresh dashboard
        'refresh_interval': 30,                            # Dashboard refresh interval (seconds)
        'market_open_hour': Config.MARKET_OPEN_HOUR,       # Market opens at 9:30 AM
        'market_open_minute': Config.MARKET_OPEN_MINUTE,
        'market_close_hour': Config.MARKET_CLOSE_HOUR,     # Market closes at 4:00 PM
        'market_close_minute': Config.MARKET_CLOSE_MINUTE,
        'save_graphs': Config.SAVE_GRAPHS,                 # Save trading graphs
        'verbose_logging': Config.VERBOSE_LOGGING          # Show detailed logging
    }
    
    # Try to load saved settings from JSON file (overrides defaults)
    try:
        with open(SETTINGS_FILE, 'r') as f:
            saved = json.load(f)
            # Merge saved settings with defaults (saved values override defaults)
            default_settings.update(saved)
    except FileNotFoundError:
        # No saved settings file - use the built-in defaults
        # Settings will be saved when user clicks "Save" on Settings page
        pass
    
    return default_settings


def save_settings(settings):
    """
    Save settings to JSON file.
    
    This is called when user clicks "Save" on the settings page.
    Settings persist across restarts.
    
    Args:
        settings (dict): Settings dictionary to save
    """
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)  # indent=2 makes file human-readable


def get_configured_stocks():
    """
    Get the list of stocks the user wants to monitor.
    
    Returns:
        list: List of stock symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])
    """
    settings = load_settings()
    if settings['stocks']:
        return settings['stocks']
    # Fallback to built-in Config defaults if no stocks configured
    return Config.STOCKS.copy()


# ============================================================================
# STATE MANAGEMENT - Functions for updating the global bot_state
# ============================================================================

def update_bot_state(holdings=None, prices=None, signals=None, 
                     sma_values=None, ratios=None, cash=None, equity=None, options=None):
    """
    Update the global bot_state with new data.
    
    Uses a thread lock to prevent race conditions when both the trading bot
    and web dashboard try to access the state simultaneously.
    
    All parameters are optional - only provided values are updated.
    
    Args:
        holdings: Dict of {stock: quantity}
        prices: Dict of {stock: current_price}
        signals: Dict of {stock: 'BUY'/'SELL'/'HOLD'/'WAIT'}
        sma_values: Dict of {stock: sma_value}
        ratios: Dict of {stock: price_to_sma_ratio}
        cash: Available cash amount
        equity: Total portfolio value
        options: List of options positions
    """
    with state_lock:  # Acquire lock before modifying shared state
        if holdings is not None:
            bot_state['holdings'] = holdings
        if prices is not None:
            bot_state['prices'] = prices
        if signals is not None:
            bot_state['signals'] = signals
        if sma_values is not None:
            bot_state['sma_values'] = sma_values
        if ratios is not None:
            bot_state['ratios'] = ratios
        if cash is not None:
            bot_state['cash'] = cash
        if equity is not None:
            bot_state['equity'] = equity
        if options is not None:
            bot_state['options'] = options
        # Always update the timestamp when state changes
        bot_state['last_update'] = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def add_trade_log(stock, action, shares, price):
    """
    Add a trade entry to the trade log.
    
    The trade log is displayed in the dashboard to show recent trading activity.
    Keeps only the 50 most recent trades to prevent memory bloat.
    
    Args:
        stock: Stock symbol (e.g., 'AAPL')
        action: 'BUY' or 'SELL'
        shares: Number of shares traded
        price: Price per share
    """
    with state_lock:
        # Insert new trade at the beginning of the list (most recent first)
        bot_state['trade_log'].insert(0, {
            'time': dt.datetime.now().strftime('%H:%M:%S'),
            'stock': stock,
            'action': action,
            'shares': shares,
            'price': price
        })
        # Keep only the 50 most recent trades
        bot_state['trade_log'] = bot_state['trade_log'][:50]


# ============================================================================
# TRADING STRATEGY - Simple Moving Average (SMA) based strategy
# ============================================================================

class TradingStrategy:
    """
    Simple SMA-based trading strategy.
    
    This strategy:
    1. Tracks price history for each stock
    2. Calculates a Simple Moving Average (SMA)
    3. Generates signals based on price deviation from SMA:
       - BUY when price drops below SMA by more than the buffer
       - SELL when price rises above SMA by more than the buffer
       - HOLD otherwise
    
    The idea is to buy when stocks dip below their average (potentially undervalued)
    and sell when they rise above their average (potentially overvalued).
    """
    
    def __init__(self, stocks, sma_window=12, trading_buffer=0.002):
        """
        Initialize the trading strategy.
        
        Args:
            stocks: List of stock symbols to track
            sma_window: Number of data points for SMA (default 12)
            trading_buffer: Percentage deviation to trigger trades (default 0.2%)
        """
        self.stocks = stocks
        self.sma_window = sma_window           # How many prices to average
        self.trading_buffer = trading_buffer   # How far from SMA to trigger trade
        # Dictionary to store price history for each stock
        self.price_history = {stock: [] for stock in stocks}
        self.runtime = 0  # Tracks how many iterations the bot has run
    
    def get_trade_signal(self, stock, current_price):
        """
        Get trading signal for a stock based on current price.
        
        This is the core trading logic:
        1. Add current price to history
        2. Calculate SMA if we have enough data
        3. Compare current price to SMA
        4. Return appropriate signal
        
        Args:
            stock: Stock symbol
            current_price: Current price of the stock
            
        Returns:
            str: 'BUY', 'SELL', 'HOLD', or 'WAIT'
        """
        # Add new price to history
        self.price_history[stock].append(current_price)
        
        # Trim history to prevent memory growth (keep 2x window size)
        if len(self.price_history[stock]) > self.sma_window * 2:
            self.price_history[stock] = self.price_history[stock][-self.sma_window * 2:]
        
        # Need enough data points before we can calculate a meaningful SMA
        if len(self.price_history[stock]) < self.sma_window:
            return 'WAIT'  # Not enough data yet
        
        # Calculate Simple Moving Average (average of last N prices)
        prices = self.price_history[stock][-self.sma_window:]
        sma = sum(prices) / len(prices)
        
        # Calculate how far current price is from SMA (as a ratio)
        # ratio > 1 means price is above SMA
        # ratio < 1 means price is below SMA
        ratio = current_price / sma if sma > 0 else 1.0
        
        # Generate signal based on ratio vs buffer
        if ratio < (1 - self.trading_buffer):
            # Price is below SMA by more than buffer - potential buying opportunity
            return 'BUY'
        elif ratio > (1 + self.trading_buffer):
            # Price is above SMA by more than buffer - potential selling opportunity
            return 'SELL'
        else:
            # Price is near SMA - hold current position
            return 'HOLD'
    
    def get_status(self, stock):
        """
        Get current status/metrics for a stock.
        
        Used by the dashboard to display SMA and ratio values.
        
        Args:
            stock: Stock symbol
            
        Returns:
            dict: Contains 'sma', 'price_sma_ratio', and 'prices_collected'
        """
        prices = self.price_history[stock]
        
        if len(prices) >= self.sma_window:
            # Calculate SMA from the most recent window of prices
            sma = sum(prices[-self.sma_window:]) / self.sma_window
            current = prices[-1] if prices else 0
            ratio = current / sma if sma > 0 else 1.0
        else:
            # Not enough data - use average of what we have
            sma = sum(prices) / len(prices) if prices else 0
            current = prices[-1] if prices else 0
            ratio = 1.0  # Neutral ratio until we have enough data
        
        return {
            'sma': sma,
            'price_sma_ratio': ratio,
            'prices_collected': len(prices)
        }
    
    def increment_runtime(self):
        """Increment the runtime counter (called after each iteration)."""
        self.runtime += 1


# ============================================================================
# TRADING BOT LOOP - Main bot logic that runs in a background thread
# ============================================================================

def run_trading_bot():
    """
    Main trading bot loop - runs in a background thread.
    
    This function:
    1. Logs into Robinhood
    2. Loads settings
    3. Enters main loop:
       a. Check if market is open
       b. Get current prices and holdings
       c. Calculate trading signals
       d. Execute trades (if enabled)
       e. Update dashboard state
       f. Wait for next check interval
    4. Continues until stop_bot_event is set
    """
    print("=" * 60)
    print("TRADING BOT STARTED")
    print("=" * 60)
    
    try:
        # ----------------------------------------------------------------
        # STEP 1: Login to Robinhood
        # ----------------------------------------------------------------
        username = os.getenv('ROBINHOOD_USERNAME')  # From .env file
        password = os.getenv('ROBINHOOD_PASSWORD')  # From .env file
        
        if not username or not password:
            print("ERROR: Missing credentials in .env file")
            print("Required: ROBINHOOD_USERNAME and ROBINHOOD_PASSWORD")
            with state_lock:
                bot_state['running'] = False
            return
        
        # Login with session storage (won't need 2FA every time)
        rh.authentication.login(username, password, store_session=True)
        print("✓ Login successful!")
        
        # ----------------------------------------------------------------
        # STEP 2: Load settings
        # ----------------------------------------------------------------
        settings = load_settings()
        
        # Get stocks to monitor (use Config defaults if none configured)
        stocks = settings['stocks'] if settings['stocks'] else Config.STOCKS.copy()
        
        # Trading parameters
        trading_buffer = settings.get('trading_buffer', 0.002)
        sma_window = settings.get('sma_window', 12)
        max_cash_per_stock = settings.get('max_cash_per_stock', 0.15)
        min_shares_to_buy = settings.get('min_shares_to_buy', 3)
        check_interval = settings.get('check_interval', 30)
        
        # Market hours
        market_open_hour = settings.get('market_open_hour', 9)
        market_open_minute = settings.get('market_open_minute', 30)
        market_close_hour = settings.get('market_close_hour', 16)
        market_close_minute = settings.get('market_close_minute', 0)
        
        print(f"Monitoring stocks: {', '.join(stocks)}")
        print(f"Trading buffer: {trading_buffer}")
        print(f"SMA window: {sma_window}")
        
        # ----------------------------------------------------------------
        # STEP 3: Initialize trading strategy
        # ----------------------------------------------------------------
        strategy = TradingStrategy(stocks, sma_window, trading_buffer)
        
        iteration = 0  # Counter for logging
        
        # ----------------------------------------------------------------
        # STEP 4: Main trading loop
        # ----------------------------------------------------------------
        while not stop_bot_event.is_set():  # Continue until stop signal
            
            # Check if market is currently open
            time_now = dt.datetime.now().time()
            market_open = dt.time(market_open_hour, market_open_minute, 0)
            market_close = dt.time(market_close_hour, market_close_minute, 0)
            
            if not (market_open < time_now < market_close):
                # Market is closed - wait and check again
                print(f"Market closed. Waiting... (opens {market_open}, closes {market_close})")
                # Check for stop signal every 10 seconds while waiting
                for _ in range(6):  # 6 x 10 seconds = 1 minute
                    if stop_bot_event.is_set():
                        break
                    time.sleep(10)
                continue  # Go back to start of loop
            
            iteration += 1
            print(f"\n--- Iteration {iteration} at {dt.datetime.now().strftime('%H:%M:%S')} ---")
            
            try:
                # --------------------------------------------------------
                # Get account information from Robinhood
                # --------------------------------------------------------
                profile = rh.account.build_user_profile()
                cash = float(profile.get('cash', 0))      # Available cash
                equity = float(profile.get('equity', 0))  # Total portfolio value
                
                # Get current prices for all monitored stocks
                prices_list = rh.stocks.get_latest_price(stocks)
                
                # Get current holdings (what stocks we own)
                rh_holdings = rh.account.build_holdings()
                holdings = {}       # {stock: quantity}
                bought_prices = {}  # {stock: average_buy_price}
                
                for stock in stocks:
                    try:
                        # Try to get holding info for this stock
                        holdings[stock] = int(float(rh_holdings[stock]['quantity']))
                        bought_prices[stock] = float(rh_holdings[stock]['average_buy_price'])
                    except (KeyError, TypeError):
                        # We don't own this stock
                        holdings[stock] = 0
                        bought_prices[stock] = 0
                
                print(f"Cash: ${cash:,.2f} | Equity: ${equity:,.2f}")
                print(f"Holdings: {holdings}")
                
                # --------------------------------------------------------
                # Process each stock
                # --------------------------------------------------------
                signals_dict = {}   # Store signals for dashboard
                sma_dict = {}       # Store SMA values for dashboard
                ratios_dict = {}    # Store ratios for dashboard
                price_dict = {}     # Store prices for dashboard
                
                for i, stock in enumerate(stocks):
                    try:
                        # Get current price (convert from string to float)
                        price = float(prices_list[i]) if prices_list[i] else 0
                        price_dict[stock] = price
                        print(f"\n{stock}: ${price:.2f}")
                        
                        # Get trading signal from strategy
                        signal = strategy.get_trade_signal(stock, price)
                        print(f"  Signal: {signal}")
                        
                        # Store for dashboard
                        signals_dict[stock] = signal
                        status = strategy.get_status(stock)
                        sma_dict[stock] = status['sma']
                        ratios_dict[stock] = status['price_sma_ratio']
                        
                        # ------------------------------------------------
                        # Execute trades based on signal
                        # ------------------------------------------------
                        if signal == 'BUY':
                            # Calculate how many shares we can afford
                            max_investment = cash * max_cash_per_stock  # e.g., 15% of cash
                            shares_to_buy = int(max_investment / price) if price > 0 else 0
                            
                            # Only buy if we can afford minimum shares AND don't already own any
                            if shares_to_buy >= min_shares_to_buy and holdings[stock] == 0:
                                # Add $0.10 to price for limit order (ensures execution)
                                buy_price = round(price + 0.10, 2)
                                print(f"🟢 BUY: {stock} - {shares_to_buy} shares @ ${buy_price}")
                                
                                # Log the trade for dashboard display
                                add_trade_log(stock, 'BUY', shares_to_buy, buy_price)
                                
                                # ============================================
                                # UNCOMMENT BELOW FOR LIVE TRADING:
                                # WARNING: This will execute real trades!
                                # ============================================
                                # rh.orders.order_buy_limit(
                                #     symbol=stock,
                                #     quantity=shares_to_buy,
                                #     limitPrice=buy_price,
                                #     timeInForce='gfd'  # Good for day
                                # )
                        
                        elif signal == 'SELL':
                            # Only sell if we actually own shares
                            if holdings[stock] > 0:
                                # Subtract $0.10 from price for limit order
                                sell_price = round(price - 0.10, 2)
                                print(f"🔴 SELL: {stock} - {holdings[stock]} shares @ ${sell_price}")
                                
                                # Log the trade for dashboard display
                                add_trade_log(stock, 'SELL', holdings[stock], sell_price)
                                
                                # ============================================
                                # UNCOMMENT BELOW FOR LIVE TRADING:
                                # WARNING: This will execute real trades!
                                # ============================================
                                # rh.orders.order_sell_limit(
                                #     symbol=stock,
                                #     quantity=holdings[stock],
                                #     limitPrice=sell_price,
                                #     timeInForce='gfd'  # Good for day
                                # )
                        
                        else:  # HOLD or WAIT
                            if holdings[stock] > 0:
                                print(f"  Holding {holdings[stock]} shares")
                        
                        # Print additional info
                        print(f"  SMA: ${status['sma']:.2f}, Ratio: {status['price_sma_ratio']:.4f}")
                    
                    except Exception as e:
                        print(f"Error processing {stock}: {e}")
                        continue  # Skip to next stock
                
                # --------------------------------------------------------
                # Update dashboard with latest data
                # --------------------------------------------------------
                update_bot_state(
                    holdings=holdings,
                    prices=price_dict,
                    signals=signals_dict,
                    sma_values=sma_dict,
                    ratios=ratios_dict,
                    cash=cash,
                    equity=equity
                )
                
                strategy.increment_runtime()
            
            except Exception as e:
                print(f"Error in iteration: {e}")
                import traceback
                traceback.print_exc()
            
            # --------------------------------------------------------
            # Wait for next check interval
            # --------------------------------------------------------
            print(f"\nWaiting {check_interval} seconds...")
            # Check for stop signal every second during wait
            for _ in range(check_interval):
                if stop_bot_event.is_set():
                    break
                time.sleep(1)
    
    except Exception as e:
        print(f"Bot error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # ----------------------------------------------------------------
        # Cleanup when bot stops (either normally or due to error)
        # ----------------------------------------------------------------
        print("\n" + "=" * 60)
        print("TRADING BOT STOPPED")
        print("=" * 60)
        with state_lock:
            bot_state['running'] = False


# ============================================================================
# HTML TEMPLATES - Embedded HTML/CSS/JavaScript for the web dashboard
# ============================================================================

# Main dashboard page HTML
# This is a complete single-page app with:
# - Portfolio summary cards (equity, cash, positions)
# - Holdings table with signals and SMA data
# - Options positions table
# - Trade log
# - Start/Stop/Refresh controls
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Bot Dashboard</title>
    <style>
        /* ============================================================
           CSS STYLES - Dark theme with gradient background
           ============================================================ */
        
        /* Reset default margins/padding */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        /* Body - dark gradient background */
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        
        /* Main container - centers content */
        .container { max-width: 1400px; margin: 0 auto; }
        
        /* Header - flexbox layout for title and controls */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        /* Title with gradient text effect */
        h1 {
            font-size: 2rem;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        /* Status badge (RUNNING/STOPPED) */
        .status-badge {
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9rem;
        }
        .status-running { background: #00c853; color: #000; }
        .status-stopped { background: #ff5252; color: #fff; }
        
        /* Control buttons container */
        .controls { display: flex; gap: 10px; flex-wrap: wrap; }
        
        /* Button base styles */
        .btn {
            padding: 10px 25px;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        /* Button variants */
        .btn-start { background: #00c853; color: #000; }
        .btn-start:hover { background: #00e676; transform: translateY(-2px); }
        .btn-stop { background: #ff5252; color: #fff; }
        .btn-stop:hover { background: #ff1744; transform: translateY(-2px); }
        .btn-refresh { background: #2196f3; color: #fff; }
        .btn-refresh:hover { background: #42a5f5; transform: translateY(-2px); }
        .btn-settings { background: #9c27b0; color: #fff; }
        .btn-settings:hover { background: #ab47bc; transform: translateY(-2px); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        
        /* Grid layout for cards */
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }
        
        /* Card component - glass morphism effect */
        .card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .card h2 {
            font-size: 1.1rem;
            color: #888;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        /* Big numbers for summary cards */
        .big-number {
            font-size: 2.5rem;
            font-weight: 700;
            color: #00d4ff;
        }
        .sub-text { color: #666; font-size: 0.9rem; margin-top: 5px; }
        
        /* Full width card */
        .full-width { grid-column: 1 / -1; }
        
        /* Table styles */
        table { width: 100%; border-collapse: collapse; }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        th { color: #888; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }
        tr:hover { background: rgba(255, 255, 255, 0.05); }
        
        /* Signal colors */
        .signal-buy { color: #00c853; font-weight: 600; }
        .signal-sell { color: #ff5252; font-weight: 600; }
        .signal-hold { color: #ffd600; font-weight: 600; }
        .signal-wait { color: #888; }
        
        /* Positive/negative colors for P/L */
        .positive { color: #00c853; }
        .negative { color: #ff5252; }
        
        /* Trade log styles */
        .trade-log { max-height: 300px; overflow-y: auto; }
        .log-entry {
            padding: 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .log-buy { border-left: 3px solid #00c853; }
        .log-sell { border-left: 3px solid #ff5252; }
        
        /* Last update timestamp */
        .last-update { color: #666; font-size: 0.85rem; margin-top: 20px; text-align: center; }
        
        /* Loading animation */
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .loading { animation: pulse 1.5s infinite; }
        
        /* Empty state message */
        .empty-state { text-align: center; padding: 40px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header with title and controls -->
        <header>
            <h1>🤖 Trading Bot Dashboard</h1>
            <div class="controls">
                <!-- Status badge shows RUNNING or STOPPED -->
                <span id="statusBadge" class="status-badge status-stopped">STOPPED</span>
                <!-- Control buttons -->
                <button id="startBtn" class="btn btn-start" onclick="startBot()">▶ Start</button>
                <button id="stopBtn" class="btn btn-stop" onclick="stopBot()" disabled>■ Stop</button>
                <button class="btn btn-refresh" onclick="refreshData()">↻ Refresh</button>
                <a href="/settings" class="btn btn-settings">⚙ Settings</a>
            </div>
        </header>
        
        <!-- Summary cards row -->
        <div class="grid">
            <div class="card">
                <h2>💰 Portfolio Value</h2>
                <div class="big-number" id="equity">$0.00</div>
                <div class="sub-text">Total Equity</div>
            </div>
            <div class="card">
                <h2>💵 Available Cash</h2>
                <div class="big-number" id="cash">$0.00</div>
                <div class="sub-text">Ready to Trade</div>
            </div>
            <div class="card">
                <h2>📊 Positions</h2>
                <div class="big-number" id="positionCount">0</div>
                <div class="sub-text">Active Holdings</div>
            </div>
        </div>
        
        <!-- Holdings table -->
        <div class="grid">
            <div class="card full-width">
                <h2>📈 Stock Holdings</h2>
                <div id="holdingsTable">
                    <div class="empty-state">Click "Refresh" to load data</div>
                </div>
            </div>
        </div>
        
        <!-- Options table -->
        <div class="grid">
            <div class="card full-width">
                <h2>📋 Options Positions</h2>
                <div id="optionsTable">
                    <div class="empty-state">No options positions</div>
                </div>
            </div>
        </div>
        
        <!-- Trade log -->
        <div class="grid">
            <div class="card">
                <h2>📜 Trade Log</h2>
                <div id="tradeLog" class="trade-log">
                    <div class="empty-state">No trades yet</div>
                </div>
            </div>
        </div>
        
        <!-- Last update timestamp -->
        <div class="last-update">Last updated: <span id="lastUpdate">Never</span></div>
    </div>
    
    <script>
        /* ============================================================
           JAVASCRIPT - Dashboard functionality
           ============================================================ */
        
        // Auto-refresh settings
        let autoRefresh = true;
        let refreshInterval = 30000;  // 30 seconds
        
        /**
         * Format a number as currency (e.g., $1,234.56)
         */
        function formatMoney(value) {
            return '$' + parseFloat(value || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        }
        
        /**
         * Format a number as percentage with sign (e.g., +5.23%)
         */
        function formatPercent(value) {
            const num = parseFloat(value || 0);
            const sign = num >= 0 ? '+' : '';
            return sign + num.toFixed(2) + '%';
        }
        
        /**
         * Get CSS class for a trading signal
         */
        function getSignalClass(signal) {
            if (!signal) return 'signal-wait';
            switch(signal.toUpperCase()) {
                case 'BUY': return 'signal-buy';
                case 'SELL': return 'signal-sell';
                case 'HOLD': return 'signal-hold';
                default: return 'signal-wait';
            }
        }
        
        /**
         * Fetch current bot status from server
         */
        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                updateDashboard(data);
            } catch (e) {
                console.error('Error fetching status:', e);
            }
        }
        
        /**
         * Update all dashboard elements with new data
         */
        function updateDashboard(data) {
            // Update status badge and button states
            const badge = document.getElementById('statusBadge');
            const startBtn = document.getElementById('startBtn');
            const stopBtn = document.getElementById('stopBtn');
            
            if (data.running) {
                badge.textContent = 'RUNNING';
                badge.className = 'status-badge status-running';
                startBtn.disabled = true;
                stopBtn.disabled = false;
            } else {
                badge.textContent = 'STOPPED';
                badge.className = 'status-badge status-stopped';
                startBtn.disabled = false;
                stopBtn.disabled = true;
            }
            
            // Update summary cards
            document.getElementById('equity').textContent = formatMoney(data.equity);
            document.getElementById('cash').textContent = formatMoney(data.cash);
            
            // Count active positions (stocks + options)
            let posCount = 0;
            if (data.holdings_info) {
                posCount = Object.values(data.holdings_info).filter(h => h.quantity > 0).length;
            }
            posCount += (data.options || []).length;
            document.getElementById('positionCount').textContent = posCount;
            
            // Update tables
            updateHoldingsTable(data);
            updateOptionsTable(data.options || []);
            updateTradeLog(data.trade_log || []);
            
            // Update timestamp
            document.getElementById('lastUpdate').textContent = data.last_update || 'Never';
        }
        
        /**
         * Render the holdings table
         */
        function updateHoldingsTable(data) {
            const container = document.getElementById('holdingsTable');
            const holdings = data.holdings_info || {};
            
            // Show stocks that either have holdings or are configured to monitor
            const stocks = Object.keys(holdings).filter(s => holdings[s].quantity > 0 || holdings[s].configured);
            
            if (stocks.length === 0) {
                container.innerHTML = '<div class="empty-state">No holdings</div>';
                return;
            }
            
            // Build table HTML
            let html = `<table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Shares</th>
                        <th>Avg Price</th>
                        <th>Current</th>
                        <th>Equity</th>
                        <th>P/L %</th>
                        <th>Signal</th>
                        <th>SMA</th>
                        <th>Ratio</th>
                    </tr>
                </thead>
                <tbody>`;
            
            stocks.forEach(stock => {
                const info = holdings[stock] || {};
                const price = data.prices ? data.prices[stock] : 0;
                const signal = data.signals ? data.signals[stock] : '';
                const sma = data.sma_values ? data.sma_values[stock] : 0;
                const ratio = data.ratios ? data.ratios[stock] : 1;
                const pctClass = info.percent_change >= 0 ? 'positive' : 'negative';
                
                html += `<tr>
                    <td><strong>${stock}</strong></td>
                    <td>${info.quantity || 0}</td>
                    <td>${formatMoney(info.avg_price)}</td>
                    <td>${formatMoney(price)}</td>
                    <td>${formatMoney(info.equity)}</td>
                    <td class="${pctClass}">${formatPercent(info.percent_change)}</td>
                    <td class="${getSignalClass(signal)}">${signal || '-'}</td>
                    <td>${sma ? formatMoney(sma) : '-'}</td>
                    <td>${ratio ? ratio.toFixed(4) : '-'}</td>
                </tr>`;
            });
            
            html += '</tbody></table>';
            container.innerHTML = html;
        }
        
        /**
         * Render the options table
         */
        function updateOptionsTable(options) {
            const container = document.getElementById('optionsTable');
            
            if (!options || options.length === 0) {
                container.innerHTML = '<div class="empty-state">No options positions</div>';
                return;
            }
            
            let html = `<table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Type</th>
                        <th>Strike</th>
                        <th>Expiration</th>
                        <th>Qty</th>
                        <th>Avg Price</th>
                        <th>Current</th>
                        <th>Value</th>
                        <th>P/L %</th>
                    </tr>
                </thead>
                <tbody>`;
            
            options.forEach(opt => {
                const pctClass = opt.percent_change >= 0 ? 'positive' : 'negative';
                const typeClass = opt.type === 'CALL' ? 'signal-buy' : 'signal-sell';
                
                html += `<tr>
                    <td><strong>${opt.symbol}</strong></td>
                    <td class="${typeClass}">${opt.type}</td>
                    <td>${formatMoney(opt.strike)}</td>
                    <td>${opt.expiration}</td>
                    <td>${opt.quantity}</td>
                    <td>${formatMoney(opt.avg_price)}</td>
                    <td>${formatMoney(opt.current_price)}</td>
                    <td>${formatMoney(opt.equity)}</td>
                    <td class="${pctClass}">${formatPercent(opt.percent_change)}</td>
                </tr>`;
            });
            
            html += '</tbody></table>';
            container.innerHTML = html;
        }
        
        /**
         * Render the trade log
         */
        function updateTradeLog(logs) {
            const container = document.getElementById('tradeLog');
            
            if (!logs || logs.length === 0) {
                container.innerHTML = '<div class="empty-state">No trades yet</div>';
                return;
            }
            
            let html = '';
            logs.forEach(log => {
                const logClass = log.action === 'BUY' ? 'log-buy' : 'log-sell';
                html += `<div class="log-entry ${logClass}">
                    <span><strong>${log.stock}</strong> ${log.action} ${log.shares} @ ${formatMoney(log.price)}</span>
                    <span style="color: #666">${log.time}</span>
                </div>`;
            });
            
            container.innerHTML = html;
        }
        
        /**
         * Start the trading bot
         */
        async function startBot() {
            try {
                const response = await fetch('/api/bot/start', { method: 'POST' });
                const data = await response.json();
                if (data.success) {
                    fetchStatus();  // Refresh dashboard
                } else {
                    alert(data.message || 'Failed to start bot');
                }
            } catch (e) {
                console.error('Error starting bot:', e);
                alert('Error starting bot');
            }
        }
        
        /**
         * Stop the trading bot
         */
        async function stopBot() {
            try {
                const response = await fetch('/api/bot/stop', { method: 'POST' });
                const data = await response.json();
                if (data.success) {
                    setTimeout(fetchStatus, 1000);  // Refresh after 1 second
                } else {
                    alert(data.message || 'Failed to stop bot');
                }
            } catch (e) {
                console.error('Error stopping bot:', e);
                alert('Error stopping bot');
            }
        }
        
        /**
         * Manually refresh data from Robinhood
         */
        async function refreshData() {
            const btn = document.querySelector('.btn-refresh');
            btn.textContent = '↻ Loading...';
            btn.disabled = true;
            
            try {
                await fetch('/api/refresh');  // Fetch fresh data from Robinhood
                await fetchStatus();           // Update dashboard
            } catch (e) {
                console.error('Error refreshing:', e);
            } finally {
                btn.textContent = '↻ Refresh';
                btn.disabled = false;
            }
        }
        
        // Initial load when page opens - refresh data from Robinhood
        refreshData();
        
        // Auto-refresh every 30 seconds
        setInterval(() => {
            if (autoRefresh) fetchStatus();
        }, refreshInterval);
        
        // Track if we're navigating within the app (not closing)
        let isNavigating = false;
        
        // Mark internal links as navigation (not closing)
        document.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => { isNavigating = true; });
        });
        
        // Shutdown server when page is closed (but not when navigating)
        window.addEventListener('beforeunload', function() {
            if (!isNavigating) {
                // Use sendBeacon for reliable delivery during page unload
                navigator.sendBeacon('/api/shutdown', '');
            }
        });
    </script>
</body>
</html>
'''

# Settings page HTML
# Allows user to configure:
# - Which stocks to monitor
# - Trading parameters (buffer, SMA window, etc.)
# - Timing settings (check interval)
SETTINGS_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Settings</title>
    <style>
        /* Same base styles as dashboard */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 800px; margin: 0 auto; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
        }
        h1 {
            font-size: 2rem;
            background: linear-gradient(90deg, #9c27b0, #e91e63);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .btn {
            padding: 10px 25px;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.3s ease;
        }
        .btn-back { background: #455a64; color: #fff; }
        .btn-back:hover { background: #607d8b; }
        .btn-save { background: #00c853; color: #000; }
        .btn-save:hover { background: #00e676; }
        
        /* Card styles for form sections */
        .card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .card h2 {
            font-size: 1.2rem;
            color: #00d4ff;
            margin-bottom: 20px;
        }
        
        /* Form styles */
        .form-group { margin-bottom: 20px; }
        label {
            display: block;
            margin-bottom: 8px;
            color: #888;
            font-size: 0.9rem;
        }
        input[type="text"], input[type="number"] {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            background: rgba(0, 0, 0, 0.3);
            color: #fff;
            font-size: 1rem;
        }
        input:focus {
            outline: none;
            border-color: #00d4ff;
        }
        .help-text {
            font-size: 0.8rem;
            color: #666;
            margin-top: 5px;
        }
        
        /* Success message */
        .success-msg {
            background: #00c853;
            color: #000;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>⚙ Bot Settings</h1>
            <button type="button" class="btn btn-save" onclick="saveSettings()">💾 Save Settings</button>
            <a href="/" class="btn btn-back">← Back to Dashboard</a>
        </header>
        
        <!-- Success message (hidden by default) -->
        <div id="successMsg" class="success-msg">Settings saved successfully!</div>
        
        <form id="settingsForm">
            <!-- Stocks configuration -->
            <div class="card">
                <h2>📊 Stocks to Monitor</h2>
                <div class="form-group">
                    <label>Stock Symbols (comma separated)</label>
                    <input type="text" id="stocks" placeholder="AAPL, MSFT, GOOGL">
                    <div class="help-text">Enter stock symbols separated by commas</div>
                </div>
            </div>
            
            <!-- Trading parameters -->
            <div class="card">
                <h2>📈 Trading Parameters</h2>
                <div class="form-group">
                    <label>Trading Buffer</label>
                    <input type="number" id="tradingBuffer" step="0.001" min="0" max="0.1" value="0.002">
                    <div class="help-text">Price deviation from SMA to trigger trades (0.002 = 0.2%)</div>
                </div>
                <div class="form-group">
                    <label>SMA Window</label>
                    <input type="number" id="smaWindow" min="3" max="100" value="12">
                    <div class="help-text">Number of data points for SMA calculation</div>
                </div>
                <div class="form-group">
                    <label>Max Cash Per Stock (%)</label>
                    <input type="number" id="maxCash" step="0.01" min="0.01" max="1" value="0.15">
                    <div class="help-text">Maximum portfolio percentage per trade (0.15 = 15%)</div>
                </div>
                <div class="form-group">
                    <label>Minimum Shares to Buy</label>
                    <input type="number" id="minShares" min="1" max="100" value="3">
                    <div class="help-text">Skip buy if can't afford this many shares</div>
                </div>
            </div>
            
            <!-- Timing settings -->
            <div class="card">
                <h2>⏱ Timing</h2>
                <div class="form-group">
                    <label>Check Interval (seconds)</label>
                    <input type="number" id="checkInterval" min="10" max="300" value="30">
                    <div class="help-text">Time between price checks</div>
                </div>
            </div>
        </form>
    </div>
    
    <script>
        /**
         * Load current settings from server and populate form
         */
        async function loadSettings() {
            try {
                const response = await fetch('/api/settings');
                const settings = await response.json();
                
                // Populate form fields with current values
                document.getElementById('stocks').value = (settings.stocks || []).join(', ');
                document.getElementById('tradingBuffer').value = settings.trading_buffer || 0.002;
                document.getElementById('smaWindow').value = settings.sma_window || 12;
                document.getElementById('maxCash').value = settings.max_cash_per_stock || 0.15;
                document.getElementById('minShares').value = settings.min_shares_to_buy || 3;
                document.getElementById('checkInterval').value = settings.check_interval || 30;
            } catch (e) {
                console.error('Error loading settings:', e);
            }
        }
        
        // Handle form submission
        async function saveSettings() {
            // Parse stocks input (comma-separated, uppercase, trimmed)
            const stocksRaw = document.getElementById('stocks').value;
            const stocks = stocksRaw.split(',').map(s => s.trim().toUpperCase()).filter(s => s);
            
            // Build settings object from form values
            const settings = {
                stocks: stocks,
                trading_buffer: parseFloat(document.getElementById('tradingBuffer').value),
                sma_window: parseInt(document.getElementById('smaWindow').value),
                max_cash_per_stock: parseFloat(document.getElementById('maxCash').value),
                min_shares_to_buy: parseInt(document.getElementById('minShares').value),
                check_interval: parseInt(document.getElementById('checkInterval').value)
            };
            
            // Send to server
            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                
                const result = await response.json();
                if (result.success) {
                    // Mark as navigating before redirect
                    isNavigating = true;
                    // Redirect to dashboard after saving
                    window.location.href = '/';
                }
            } catch (e) {
                console.error('Error saving settings:', e);
                alert('Error saving settings');
            }
        }
        
        // Load settings when page loads
        loadSettings();
        
        // Track if we're navigating within the app (not closing)
        let isNavigating = false;
        
        // Mark internal links as navigation (not closing)
        document.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => { isNavigating = true; });
        });
        
        // Shutdown server when page is closed (but not when navigating)
        window.addEventListener('beforeunload', function() {
            if (!isNavigating) {
                navigator.sendBeacon('/api/shutdown', '');
            }
        });
    </script>
</body>
</html>
'''


# ============================================================================
# FLASK ROUTES - URL endpoints that the web browser can access
# ============================================================================

@app.route('/')
def dashboard():
    """
    Main dashboard page.
    
    URL: http://127.0.0.1:5000/
    Returns the dashboard HTML which shows portfolio status,
    holdings, options, and trade controls.
    """
    return render_template_string(DASHBOARD_HTML)


@app.route('/settings')
def settings_page():
    """
    Settings configuration page.
    
    URL: http://127.0.0.1:5000/settings
    Returns the settings HTML which allows users to configure
    stocks to monitor and trading parameters.
    """
    return render_template_string(SETTINGS_HTML)


@app.route('/api/status')
def get_status():
    """
    API endpoint to get current bot status.
    
    URL: http://127.0.0.1:5000/api/status
    Returns JSON with all current bot state data.
    Called by dashboard JavaScript to update the display.
    """
    with state_lock:
        return jsonify(bot_state)


@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """
    API endpoint to get or save settings.
    
    URL: http://127.0.0.1:5000/api/settings
    GET: Returns current settings as JSON
    POST: Saves new settings from JSON body
    """
    if request.method == 'GET':
        return jsonify(load_settings())
    else:
        settings = request.json
        save_settings(settings)
        return jsonify({'success': True})


@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """
    API endpoint to start the trading bot.
    
    URL: http://127.0.0.1:5000/api/bot/start (POST only)
    Starts the bot in a background thread if not already running.
    """
    global bot_thread, stop_bot_event
    
    # Check if already running
    with state_lock:
        if bot_state['running']:
            return jsonify({'success': False, 'message': 'Bot is already running'})
    
    # Clear any previous stop signal
    stop_bot_event.clear()
    
    # Mark as running
    with state_lock:
        bot_state['running'] = True
    
    # Start bot in background thread (daemon=True means it dies when main program exits)
    bot_thread = threading.Thread(target=run_trading_bot, daemon=True)
    bot_thread.start()
    
    return jsonify({'success': True, 'message': 'Bot started'})


@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """
    API endpoint to stop the trading bot.
    
    URL: http://127.0.0.1:5000/api/bot/stop (POST only)
    Signals the bot to stop gracefully after current iteration.
    """
    global stop_bot_event
    
    # Check if actually running
    with state_lock:
        if not bot_state['running']:
            return jsonify({'success': False, 'message': 'Bot is not running'})
    
    # Set the stop event - bot will check this and exit
    stop_bot_event.set()
    
    return jsonify({'success': True, 'message': 'Stop signal sent'})


@app.route('/api/shutdown', methods=['POST'])
def shutdown_server():
    """
    API endpoint to shut down the entire Flask server.
    
    URL: http://127.0.0.1:5000/api/shutdown (POST only)
    Called when browser tab is closed to terminate the program.
    """
    # Stop the trading bot first if running
    global stop_bot_event
    stop_bot_event.set()
    
    # Schedule the shutdown
    def shutdown():
        time.sleep(0.5)  # Brief delay to allow response to be sent
        os._exit(0)  # Force exit the entire program
    
    shutdown_thread = threading.Thread(target=shutdown, daemon=True)
    shutdown_thread.start()
    
    return jsonify({'success': True, 'message': 'Server shutting down'})


@app.route('/api/refresh')
def refresh_data():
    """
    API endpoint to manually refresh account data from Robinhood.
    
    URL: http://127.0.0.1:5000/api/refresh
    Fetches current portfolio, holdings, options from Robinhood
    and updates the bot_state. Useful when bot is not running
    but you want to see current positions.
    """
    try:
        # Get credentials from environment
        username = os.getenv('ROBINHOOD_USERNAME')
        password = os.getenv('ROBINHOOD_PASSWORD')
        
        if not username or not password:
            return jsonify({'error': 'Missing credentials in .env file'}), 400
        
        # Login to Robinhood
        rh.authentication.login(username, password, store_session=True)
        
        # Get account profile (cash, equity)
        profile = rh.account.build_user_profile()
        cash = float(profile.get('cash', 0))
        equity = float(profile.get('equity', 0))
        
        # Get configured stocks
        configured_stocks = get_configured_stocks()
        
        # Get current holdings from Robinhood
        rh_holdings = rh.account.build_holdings()
        
        # Combine configured stocks with any stocks we actually hold
        all_stocks = set(configured_stocks)
        for stock in rh_holdings.keys():
            all_stocks.add(stock)
        all_stocks = list(all_stocks)
        
        # Build holdings info for each stock
        holdings = {}
        holdings_info = {}
        for stock in all_stocks:
            try:
                holdings[stock] = int(float(rh_holdings[stock]['quantity']))
                holdings_info[stock] = {
                    'quantity': holdings[stock],
                    'avg_price': float(rh_holdings[stock]['average_buy_price']),
                    'equity': float(rh_holdings[stock]['equity']),
                    'percent_change': float(rh_holdings[stock]['percent_change']),
                    'configured': stock in configured_stocks  # Is this stock in our watch list?
                }
            except (KeyError, TypeError):
                # We don't hold this stock (but it might be in our watch list)
                holdings[stock] = 0
                holdings_info[stock] = {
                    'quantity': 0,
                    'avg_price': 0,
                    'equity': 0,
                    'percent_change': 0,
                    'configured': stock in configured_stocks
                }
        
        # Get current prices for all stocks
        prices_list = rh.stocks.get_latest_price(all_stocks)
        prices = {stock: float(prices_list[i]) if prices_list[i] else 0 
                  for i, stock in enumerate(all_stocks)}
        
        # ----------------------------------------------------------------
        # Get options positions (more complex than stocks)
        # ----------------------------------------------------------------
        options_data = []
        try:
            # Get all open options positions
            options_positions = rh.options.get_open_option_positions()
            
            for opt in options_positions:
                try:
                    qty = float(opt.get('quantity', 0))
                    if qty <= 0:
                        continue  # Skip closed positions
                    
                    chain_symbol = opt.get('chain_symbol', 'N/A')  # Underlying stock
                    option_id = opt.get('option_id', '')
                    
                    option_data = {}
                    market_data = {}
                    
                    # Get detailed option info using option_id
                    if option_id:
                        try:
                            option_data = rh.options.get_option_instrument_data_by_id(option_id) or {}
                        except Exception as e:
                            print(f"Error getting option instrument: {e}")
                        
                        try:
                            md = rh.options.get_option_market_data_by_id(option_id)
                            if md and isinstance(md, list) and len(md) > 0:
                                market_data = md[0]
                            elif md and isinstance(md, dict):
                                market_data = md
                        except Exception as e:
                            print(f"Error getting market data: {e}")
                    
                    # Calculate prices (Robinhood stores average_price in cents)
                    avg_price = float(opt.get('average_price', 0)) / 100
                    
                    # Get current price from market data
                    current_price = 0
                    if market_data:
                        current_price = float(
                            market_data.get('adjusted_mark_price') or 
                            market_data.get('mark_price') or 
                            market_data.get('last_trade_price') or 0
                        )
                    
                    # Calculate P/L percentage
                    pct_change = 0
                    if avg_price > 0 and current_price > 0:
                        pct_change = ((current_price - avg_price) / avg_price) * 100
                    
                    # Get option details
                    expiration = opt.get('expiration_date') or option_data.get('expiration_date', 'N/A')
                    option_type = (option_data.get('type', '') or 'N/A').upper()  # CALL or PUT
                    strike = float(option_data.get('strike_price', 0) or 0)
                    
                    options_data.append({
                        'symbol': chain_symbol,
                        'type': option_type,
                        'strike': strike,
                        'expiration': expiration,
                        'quantity': int(qty),
                        'avg_price': avg_price,
                        'current_price': current_price,
                        'equity': qty * current_price * 100,  # Options are 100 shares each
                        'percent_change': pct_change
                    })
                    
                except Exception as e:
                    print(f"Error processing option: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error fetching options: {e}")
        
        # Update global state with all the new data
        update_bot_state(
            holdings=holdings,
            prices=prices,
            cash=cash,
            equity=equity,
            options=options_data
        )
        
        # Also update the detailed holdings info
        with state_lock:
            bot_state['holdings_info'] = holdings_info
            bot_state['configured_stocks'] = configured_stocks
        
        return jsonify({'success': True, 'message': f'Found {len(options_data)} options'})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# MAIN ENTRY POINT - What runs when you execute this file
# ============================================================================

def open_browser():
    """
    Open the dashboard in the default web browser.
    
    Runs in a background thread with a short delay to give
    the Flask server time to start.
    """
    time.sleep(1.5)  # Wait for server to start
    webbrowser.open('http://127.0.0.1:5000')


if __name__ == '__main__':
    # This block runs when you execute: python trading_bot_dashboard.py
    
    # Print startup banner
    print("=" * 60)
    print("ROBINHOOD TRADING BOT WITH DASHBOARD")
    print("=" * 60)
    print()
    print("Starting web server...")
    print("Dashboard will open in your browser automatically.")
    print()
    print("Dashboard URL: http://127.0.0.1:5000")
    print("Settings URL:  http://127.0.0.1:5000/settings")
    print()
    print("Press Ctrl+C to stop the server.")
    print("Closing the browser tab will also stop the server.")
    print("=" * 60)
    
    # Start browser opener in background thread
    # daemon=True means this thread won't prevent the program from exiting
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # Run Flask web server
    # host='0.0.0.0' allows access from other devices on network
    # port=5000 is the default Flask port
    # debug=False because we're running our own threads
    app.run(host='0.0.0.0', port=5000, debug=False)