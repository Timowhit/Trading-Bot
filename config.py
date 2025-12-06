"""
Configuration file for the trading bot.
Credentials are loaded from environment variables for security.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# ROBINHOOD CREDENTIALS (loaded from .env file)
# ============================================================================
# Create a .env file with:
# ROBINHOOD_USERNAME=your_email@example.com
# ROBINHOOD_PASSWORD=your_password

username = os.getenv('ROBINHOOD_USERNAME')
password = os.getenv('ROBINHOOD_PASSWORD')

if not username or not password:
    raise ValueError(
        "Missing credentials! Create a .env file with:\n"
        "ROBINHOOD_USERNAME=your_email@example.com\n"
        "ROBINHOOD_PASSWORD=your_password"
    )


# ============================================================================
# STOCKS TO TRADE
# ============================================================================
# Add or remove stock tickers you want to trade
# These are just examples - customize to your preferences
STOCKS = [
    "QQQ",   # Invesco QQQ Trust (Nasdaq-100 ETF)
    "SPY",   # SPDR S&P 500 ETF Trust
    "VOO",   # Vanguard S&P 500 ETF
    "TSLA",  # Tesla, Inc.
    "QUBT",  # Quantum Computing Inc.
]


# ============================================================================
# TRADING PARAMETERS
# ============================================================================

# Buffer for buy/sell decisions (0.002 = 0.2%)
# Lower = more sensitive (more trades)
# Higher = less sensitive (fewer trades)
TRADING_BUFFER = 0.002

# SMA window size (number of periods to average)
# Default: 12 periods = 1 hour (with 5-minute intervals)
SMA_WINDOW = 12

# Maximum percentage of cash to invest in a single stock
# 0.1 = 10% of available cash per stock
MAX_CASH_PER_STOCK = 0.1

# Minimum shares to buy (prevents buying too few shares)
MIN_SHARES_TO_BUY = 5


# ============================================================================
# MARKET HOURS (Eastern Time)
# ============================================================================
# Regular market hours: 9:30 AM - 4:00 PM ET
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 59

# How often to check prices (in seconds)
# 30 seconds is a good balance between responsiveness and API limits
CHECK_INTERVAL = 30

# Update SMA every N minutes
# Default: 5 minutes
SMA_UPDATE_INTERVAL = 5


# ============================================================================
# DISPLAY SETTINGS
# ============================================================================

# Save graphs (True/False)
SAVE_GRAPHS = True

# Show detailed logging (True/False)
VERBOSE_LOGGING = True