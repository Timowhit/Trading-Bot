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
    - Automatic .env setup if missing credentials

================================================================================
EXTERNAL FILES AND DEPENDENCIES
================================================================================

REQUIRED EXTERNAL FILES:
------------------------
1. .env (auto-generated via setup page if missing)
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

from flask import Flask, render_template_string, jsonify, request, redirect  # Web framework
import robin_stocks.robinhood as rh   # Robinhood API wrapper
from dotenv import load_dotenv        # Loads .env file into environment variables

# Load environment variables from .env file
# This reads ROBINHOOD_USERNAME and ROBINHOOD_PASSWORD from .env
load_dotenv()

# Initialize Flask web application
# Flask handles all the web routes and serves the dashboard
app = Flask(__name__)

# Path to the .env file (same directory as this script)
ENV_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')


# ============================================================================
# CREDENTIALS MANAGEMENT - Functions for checking and saving .env credentials
# ============================================================================

def check_credentials_exist():
    """
    Check if .env file exists and contains required credentials.
    
    Returns:
        bool: True if credentials are configured, False otherwise
    """
    if not os.path.exists(ENV_FILE_PATH):
        return False
    
    # Reload environment variables to get fresh values
    load_dotenv(override=True)
    
    username = os.getenv('ROBINHOOD_USERNAME')
    password = os.getenv('ROBINHOOD_PASSWORD')
    
    return bool(username and password)


def save_credentials(username, password):
    """
    Save Robinhood credentials to .env file.
    
    Args:
        username: Robinhood username/email
        password: Robinhood password
    """
    with open(ENV_FILE_PATH, 'w') as f:
        f.write(f"ROBINHOOD_USERNAME={username}\n")
        f.write(f"ROBINHOOD_PASSWORD={password}\n")
    
    # Reload environment variables
    load_dotenv(override=True)


# ============================================================================
# SETUP PAGE HTML - Shown when .env file is missing
# ============================================================================

SETUP_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Setup - Trading Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .setup-container {
            max-width: 500px;
            width: 100%;
        }
        .card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 40px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        h1 {
            font-size: 2rem;
            text-align: center;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            text-align: center;
            color: #888;
            margin-bottom: 30px;
            font-size: 0.95rem;
        }
        .warning-box {
            background: rgba(255, 152, 0, 0.1);
            border: 1px solid rgba(255, 152, 0, 0.3);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 25px;
        }
        .warning-box h3 {
            color: #ffb74d;
            font-size: 0.9rem;
            margin-bottom: 8px;
        }
        .warning-box p {
            color: #888;
            font-size: 0.85rem;
            line-height: 1.5;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #888;
            font-size: 0.9rem;
        }
        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 14px 16px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            background: rgba(0, 0, 0, 0.3);
            color: #fff;
            font-size: 1rem;
            transition: border-color 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #00d4ff;
        }
        input::placeholder {
            color: #555;
        }
        .btn {
            width: 100%;
            padding: 14px 25px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 10px;
        }
        .btn-primary {
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            color: #000;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.3);
        }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .error-msg {
            background: rgba(255, 82, 82, 0.1);
            border: 1px solid rgba(255, 82, 82, 0.3);
            color: #ff5252;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
            font-size: 0.9rem;
        }
        .success-msg {
            background: rgba(0, 200, 83, 0.1);
            border: 1px solid rgba(0, 200, 83, 0.3);
            color: #00c853;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
            font-size: 0.9rem;
        }
        .footer-note {
            text-align: center;
            margin-top: 20px;
            font-size: 0.8rem;
            color: #555;
        }
        .show-password {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 8px;
            font-size: 0.85rem;
            color: #666;
            cursor: pointer;
        }
        .show-password input[type="checkbox"] {
            width: auto;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="setup-container">
        <div class="card">
            <h1>🤖 Trading Bot Setup</h1>
            <p class="subtitle">Enter your Robinhood credentials to get started</p>
            
            <div class="warning-box">
                <h3>🔒 Security Notice</h3>
                <p>Your credentials will be stored locally in a .env file on your computer. 
                   They are never sent to any external servers. This bot runs entirely on your machine.</p>
            </div>
            
            <div id="errorMsg" class="error-msg"></div>
            <div id="successMsg" class="success-msg"></div>
            
            <form id="setupForm" onsubmit="saveCredentials(event)">
                <div class="form-group">
                    <label for="username">Robinhood Email/Username</label>
                    <input type="text" id="username" name="username" 
                           placeholder="your@email.com" required autocomplete="username">
                </div>
                
                <div class="form-group">
                    <label for="password">Robinhood Password</label>
                    <input type="password" id="password" name="password" 
                           placeholder="••••••••••••" required autocomplete="current-password">
                    <label class="show-password">
                        <input type="checkbox" onclick="togglePassword()"> Show password
                    </label>
                </div>
                
                <button type="submit" id="submitBtn" class="btn btn-primary">
                    🚀 Save & Continue to Dashboard
                </button>
            </form>
            
            <p class="footer-note">
                Credentials are stored in: .env (same folder as this script)
            </p>
        </div>
    </div>
    
    <script>
        function togglePassword() {
            const pwd = document.getElementById('password');
            pwd.type = pwd.type === 'password' ? 'text' : 'password';
        }
        
        async function saveCredentials(event) {
            event.preventDefault();
            
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value;
            const submitBtn = document.getElementById('submitBtn');
            const errorMsg = document.getElementById('errorMsg');
            const successMsg = document.getElementById('successMsg');
            
            // Hide previous messages
            errorMsg.style.display = 'none';
            successMsg.style.display = 'none';
            
            // Validate
            if (!username || !password) {
                errorMsg.textContent = 'Please enter both username and password.';
                errorMsg.style.display = 'block';
                return;
            }
            
            // Disable button while saving
            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ Saving...';
            
            try {
                const response = await fetch('/api/setup/credentials', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    successMsg.textContent = '✓ Credentials saved! Redirecting to dashboard...';
                    successMsg.style.display = 'block';
                    
                    // Redirect to dashboard after short delay
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 1500);
                } else {
                    errorMsg.textContent = result.message || 'Failed to save credentials.';
                    errorMsg.style.display = 'block';
                    submitBtn.disabled = false;
                    submitBtn.textContent = '🚀 Save & Continue to Dashboard';
                }
            } catch (e) {
                console.error('Error saving credentials:', e);
                errorMsg.textContent = 'Error saving credentials. Please try again.';
                errorMsg.style.display = 'block';
                submitBtn.disabled = false;
                submitBtn.textContent = '🚀 Save & Continue to Dashboard';
            }
        }
    </script>
</body>
</html>
'''


# ============================================================================
# MARKET CONDITION PRESETS - Strategies for different market conditions
# ============================================================================

MARKET_PRESETS = {
    'bullish': {
        'name': 'Bullish Growth',
        'description': 'Aggressive growth strategy for rising markets',
        'icon': '🚀',
        'color': '#00c853',
        'stocks': ['QQQ', 'VGT', 'SMH', 'XLK', 'SOXX'],
        'trading_buffer': 0.025,      # 2.5% - Less sensitive, ride the trend
        'sma_window': 15,             # Longer window for trend following
        'max_cash_per_stock': 0.30,   # Larger positions in bull market
        'min_shares_to_buy': 1,
        'check_interval': 45,         # Less frequent checks
        'rationale': 'Focus on high-growth tech ETFs with larger positions to maximize gains in uptrending markets.'
    },
    'bearish': {
        'name': 'Bearish Defense',
        'description': 'Defensive strategy for declining markets',
        'icon': '🛡️',
        'color': '#ff5252',
        'stocks': ['SH', 'GLD', 'TLT', 'XLU', 'VPU'],
        'trading_buffer': 0.015,      # 1.5% - More responsive to catch reversals
        'sma_window': 8,              # Shorter window for quicker signals
        'max_cash_per_stock': 0.15,   # Smaller positions, preserve capital
        'min_shares_to_buy': 1,
        'check_interval': 20,         # More frequent monitoring
        'rationale': 'Inverse and defensive ETFs (gold, bonds, utilities) with smaller positions to preserve capital.'
    },
    'volatile': {
        'name': 'High Volatility',
        'description': 'Cautious strategy for turbulent markets',
        'icon': '⚡',
        'color': '#ff9800',
        'stocks': ['SPLV', 'USMV', 'VYM', 'SCHD', 'XLP'],
        'trading_buffer': 0.035,      # 3.5% - Avoid whipsaws
        'sma_window': 10,
        'max_cash_per_stock': 0.12,   # Very small positions
        'min_shares_to_buy': 1,
        'check_interval': 25,
        'rationale': 'Low-volatility and dividend ETFs with tight position sizing to reduce risk in choppy markets.'
    },
    'stagnant': {
        'name': 'Sideways Income',
        'description': 'Income-focused strategy for flat markets',
        'icon': '📊',
        'color': '#9c27b0',
        'stocks': ['VYM', 'SCHD', 'HDV', 'DVY', 'JEPI'],
        'trading_buffer': 0.02,       # 2% - Standard buffer
        'sma_window': 12,
        'max_cash_per_stock': 0.25,
        'min_shares_to_buy': 1,
        'check_interval': 60,         # Less frequent in sideways market
        'rationale': 'High-dividend ETFs for income generation when capital appreciation is limited.'
    },
    'recovery': {
        'name': 'Market Recovery',
        'description': 'Balanced strategy for recovering markets',
        'icon': '📈',
        'color': '#2196f3',
        'stocks': ['VTI', 'SPY', 'IWM', 'XLF', 'VB'],
        'trading_buffer': 0.02,
        'sma_window': 12,
        'max_cash_per_stock': 0.22,
        'min_shares_to_buy': 1,
        'check_interval': 30,
        'rationale': 'Broad market and small-cap ETFs to capture recovery gains across all sectors.'
    },
    'correction': {
        'name': 'Correction Mode',
        'description': 'Opportunistic buying during pullbacks',
        'icon': '🎯',
        'color': '#00bcd4',
        'stocks': ['VOO', 'QQQ', 'VTI', 'SCHG', 'VUG'],
        'trading_buffer': 0.018,      # Slightly more sensitive for dip buying
        'sma_window': 10,
        'max_cash_per_stock': 0.20,
        'min_shares_to_buy': 1,
        'check_interval': 25,
        'rationale': 'Quality broad-market ETFs positioned for dip-buying opportunities during market corrections.'
    }
}

# Global variable to store the detected/selected market condition
current_market_condition = {
    'condition': 'stagnant',
    'confidence': 0,
    'spy_change': 0,
    'vix_level': 0,
    'detected_at': None
}


def detect_market_condition():
    """
    Detect current market condition based on SPY performance and VIX levels.
    
    Returns:
        dict: Market condition info including type, confidence, and metrics
    """
    global current_market_condition
    
    try:
        # Get credentials
        username = os.getenv('ROBINHOOD_USERNAME')
        password = os.getenv('ROBINHOOD_PASSWORD')
        
        if not username or not password:
            return {
                'condition': 'stagnant',
                'confidence': 50,
                'spy_change': 0,
                'vix_level': 20,
                'error': 'No credentials'
            }
        
        # Login to Robinhood
        rh.authentication.login(username, password, store_session=True)
        
        # Get SPY data for market direction
        spy_quote = rh.stocks.get_stock_quote_by_symbol('SPY')
        spy_price = float(spy_quote.get('last_trade_price', 0))
        spy_prev_close = float(spy_quote.get('previous_close', spy_price))
        spy_change_pct = ((spy_price - spy_prev_close) / spy_prev_close * 100) if spy_prev_close > 0 else 0
        
        # Get historical data for trend analysis (5-day performance)
        spy_historical = rh.stocks.get_stock_historicals('SPY', interval='day', span='week')
        if spy_historical and len(spy_historical) >= 5:
            week_ago_price = float(spy_historical[0].get('close_price', spy_price))
            weekly_change = ((spy_price - week_ago_price) / week_ago_price * 100) if week_ago_price > 0 else 0
        else:
            weekly_change = spy_change_pct
        
        # Try to get VIX (volatility index) - use VIXY as proxy if direct VIX unavailable
        vix_level = 20  # Default moderate volatility
        try:
            vixy_quote = rh.stocks.get_stock_quote_by_symbol('VIXY')
            if vixy_quote:
                # VIXY price roughly correlates with VIX behavior
                vixy_price = float(vixy_quote.get('last_trade_price', 0))
                vixy_prev = float(vixy_quote.get('previous_close', vixy_price))
                vixy_change = ((vixy_price - vixy_prev) / vixy_prev * 100) if vixy_prev > 0 else 0
                
                # Estimate VIX level based on VIXY behavior
                if vixy_change > 10:
                    vix_level = 35  # High volatility spike
                elif vixy_change > 5:
                    vix_level = 28
                elif vixy_change < -5:
                    vix_level = 15  # Low volatility
                else:
                    vix_level = 20
        except:
            pass
        
        # Determine market condition based on metrics
        condition = 'stagnant'
        confidence = 50
        
        # High volatility check (VIX > 25 or big daily swings)
        if vix_level > 28 or abs(spy_change_pct) > 2.5:
            condition = 'volatile'
            confidence = min(90, 60 + vix_level)
        
        # Bullish: Strong positive momentum
        elif weekly_change > 2 and spy_change_pct > 0:
            condition = 'bullish'
            confidence = min(90, 50 + weekly_change * 10)
        
        # Bearish: Strong negative momentum
        elif weekly_change < -2 and spy_change_pct < 0:
            condition = 'bearish'
            confidence = min(90, 50 + abs(weekly_change) * 10)
        
        # Correction: Market down 5-10% but showing signs of stabilization
        elif weekly_change < -3 and spy_change_pct > 0:
            condition = 'correction'
            confidence = 65
        
        # Recovery: Coming off lows with positive momentum
        elif weekly_change > 0 and weekly_change < 2 and spy_change_pct > 0.5:
            condition = 'recovery'
            confidence = 60
        
        # Stagnant: Low movement
        elif abs(weekly_change) < 1 and abs(spy_change_pct) < 0.5:
            condition = 'stagnant'
            confidence = 70
        
        # Default to stagnant if unclear
        else:
            condition = 'stagnant'
            confidence = 50
        
        result = {
            'condition': condition,
            'confidence': confidence,
            'spy_change': round(spy_change_pct, 2),
            'weekly_change': round(weekly_change, 2),
            'vix_level': vix_level,
            'spy_price': round(spy_price, 2),
            'detected_at': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        current_market_condition = result
        return result
        
    except Exception as e:
        print(f"Error detecting market condition: {e}")
        return {
            'condition': 'stagnant',
            'confidence': 50,
            'spy_change': 0,
            'vix_level': 20,
            'error': str(e)
        }


def apply_preset(preset_name):
    """
    Apply a market preset to the current settings.
    
    Args:
        preset_name: Key from MARKET_PRESETS dict
        
    Returns:
        dict: The applied settings
    """
    if preset_name not in MARKET_PRESETS:
        preset_name = 'stagnant'
    
    preset = MARKET_PRESETS[preset_name]
    
    settings = {
        'stocks': preset['stocks'].copy(),
        'trading_buffer': preset['trading_buffer'],
        'sma_window': preset['sma_window'],
        'max_cash_per_stock': preset['max_cash_per_stock'],
        'min_shares_to_buy': preset['min_shares_to_buy'],
        'check_interval': preset['check_interval'],
        'preset_applied': preset_name,
        'preset_applied_at': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    save_settings(settings)
    return settings


# Strategy selection page HTML - shown on startup
STRATEGY_SELECT_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Select Strategy - Trading Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        
        header {
            text-align: center;
            margin-bottom: 30px;
        }
        h1 {
            font-size: 2.2rem;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .subtitle { color: #888; font-size: 1.1rem; }
        
        /* Countdown timer */
        .countdown-container {
            text-align: center;
            margin: 20px 0;
            padding: 15px;
            background: rgba(255, 152, 0, 0.1);
            border: 1px solid rgba(255, 152, 0, 0.3);
            border-radius: 12px;
        }
        .countdown-text { color: #ffb74d; font-size: 0.95rem; }
        .countdown-timer {
            font-size: 2.5rem;
            font-weight: 700;
            color: #ff9800;
            margin: 10px 0;
        }
        .countdown-action { color: #888; font-size: 0.9rem; }
        
        /* Market condition banner */
        .market-banner {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 25px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .market-condition {
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 10px;
        }
        .market-metrics {
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            margin-top: 15px;
        }
        .metric {
            text-align: center;
        }
        .metric-value {
            font-size: 1.5rem;
            font-weight: 600;
        }
        .metric-label { color: #888; font-size: 0.85rem; }
        .positive { color: #00c853; }
        .negative { color: #ff5252; }
        
        /* Strategy cards grid */
        .strategy-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .strategy-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 25px;
            border: 2px solid transparent;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
        }
        .strategy-card:hover {
            transform: translateY(-5px);
            border-color: rgba(255, 255, 255, 0.2);
        }
        .strategy-card.recommended {
            border-color: #00d4ff;
            box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
        }
        .strategy-card.selected {
            border-color: #00ff88;
            box-shadow: 0 0 20px rgba(0, 255, 136, 0.3);
        }
        
        .recommended-badge {
            position: absolute;
            top: -10px;
            right: 20px;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            color: #000;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        
        .strategy-header {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
        }
        .strategy-icon { font-size: 2.5rem; }
        .strategy-title { font-size: 1.3rem; font-weight: 600; }
        .strategy-desc { color: #888; font-size: 0.9rem; margin-bottom: 15px; }
        
        .strategy-details {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .detail-row {
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        .detail-row:last-child { border-bottom: none; }
        .detail-label { color: #888; }
        .detail-value { color: #00d4ff; font-weight: 500; }
        
        .etf-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        .etf-tag {
            background: rgba(0, 212, 255, 0.2);
            color: #00d4ff;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85rem;
            font-weight: 500;
        }
        
        .rationale {
            font-size: 0.85rem;
            color: #aaa;
            font-style: italic;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* Saved strategy card */
        .saved-strategy-card {
            background: rgba(156, 39, 176, 0.1);
            border-color: rgba(156, 39, 176, 0.3);
        }
        .saved-strategy-card:hover {
            border-color: #9c27b0;
        }
        
        /* Action buttons */
        .actions {
            display: flex;
            justify-content: center;
            gap: 15px;
            flex-wrap: wrap;
        }
        .btn {
            padding: 15px 40px;
            border: none;
            border-radius: 10px;
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .btn-primary {
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            color: #000;
        }
        .btn-primary:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(0, 212, 255, 0.3);
        }
        .btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        /* Skip link */
        .skip-link {
            text-align: center;
            margin-top: 20px;
        }
        .skip-link a {
            color: #666;
            text-decoration: none;
            font-size: 0.9rem;
        }
        .skip-link a:hover {
            color: #888;
            text-decoration: underline;
        }
        
        /* Loading state */
        .loading {
            text-align: center;
            padding: 60px;
        }
        .spinner {
            width: 50px;
            height: 50px;
            border: 4px solid rgba(255, 255, 255, 0.1);
            border-top-color: #00d4ff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 Trading Bot Strategy Selection</h1>
            <p class="subtitle">Choose your trading strategy based on current market conditions</p>
        </header>
        
        <!-- Countdown timer -->
        <div class="countdown-container" id="countdownContainer">
            <div class="countdown-text">Auto-selecting recommended strategy in:</div>
            <div class="countdown-timer" id="countdownTimer">30</div>
            <div class="countdown-action">Recommended: <strong id="recommendedName">Loading...</strong></div>
        </div>
        
        <!-- Market condition banner -->
        <div class="market-banner" id="marketBanner">
            <div class="loading" id="loadingIndicator">
                <div class="spinner"></div>
                <div>Analyzing market conditions...</div>
            </div>
            <div id="marketInfo" style="display: none;">
                <div class="market-condition" id="marketCondition">Loading...</div>
                <div class="market-metrics">
                    <div class="metric">
                        <div class="metric-value" id="spyChange">-</div>
                        <div class="metric-label">SPY Today</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value" id="weeklyChange">-</div>
                        <div class="metric-label">SPY Weekly</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value" id="vixLevel">-</div>
                        <div class="metric-label">Volatility</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value" id="confidence">-</div>
                        <div class="metric-label">Confidence</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Strategy cards -->
        <div class="strategy-grid" id="strategyGrid">
            <!-- Cards will be populated by JavaScript -->
        </div>
        
        <!-- Action buttons -->
        <div class="actions">
            <button class="btn btn-primary" id="applyBtn" onclick="applySelectedStrategy()" disabled>
                🚀 Apply Selected Strategy
            </button>
        </div>
        
        <div class="skip-link">
            <a href="/" onclick="skipSelection()">Skip and go to dashboard →</a>
        </div>
    </div>
    
    <script>
        let countdown = 30;
        let countdownInterval;
        let selectedStrategy = null;
        let recommendedStrategy = 'stagnant';
        let marketData = null;
        let savedSettings = null;
        
        const presets = {
            bullish: {
                name: 'Bullish Growth',
                description: 'Aggressive growth strategy for rising markets',
                icon: '🚀',
                color: '#00c853',
                stocks: ['QQQ', 'VGT', 'SMH', 'XLK', 'SOXX'],
                trading_buffer: 0.025,
                sma_window: 15,
                max_cash_per_stock: 0.30,
                check_interval: 45,
                rationale: 'Focus on high-growth tech ETFs with larger positions to maximize gains in uptrending markets.'
            },
            bearish: {
                name: 'Bearish Defense',
                description: 'Defensive strategy for declining markets',
                icon: '🛡️',
                color: '#ff5252',
                stocks: ['SH', 'GLD', 'TLT', 'XLU', 'VPU'],
                trading_buffer: 0.015,
                sma_window: 8,
                max_cash_per_stock: 0.15,
                check_interval: 20,
                rationale: 'Inverse and defensive ETFs (gold, bonds, utilities) with smaller positions to preserve capital.'
            },
            volatile: {
                name: 'High Volatility',
                description: 'Cautious strategy for turbulent markets',
                icon: '⚡',
                color: '#ff9800',
                stocks: ['SPLV', 'USMV', 'VYM', 'SCHD', 'XLP'],
                trading_buffer: 0.035,
                sma_window: 10,
                max_cash_per_stock: 0.12,
                check_interval: 25,
                rationale: 'Low-volatility and dividend ETFs with tight position sizing to reduce risk in choppy markets.'
            },
            stagnant: {
                name: 'Sideways Income',
                description: 'Income-focused strategy for flat markets',
                icon: '📊',
                color: '#9c27b0',
                stocks: ['VYM', 'SCHD', 'HDV', 'DVY', 'JEPI'],
                trading_buffer: 0.02,
                sma_window: 12,
                max_cash_per_stock: 0.25,
                check_interval: 60,
                rationale: 'High-dividend ETFs for income generation when capital appreciation is limited.'
            },
            recovery: {
                name: 'Market Recovery',
                description: 'Balanced strategy for recovering markets',
                icon: '📈',
                color: '#2196f3',
                stocks: ['VTI', 'SPY', 'IWM', 'XLF', 'VB'],
                trading_buffer: 0.02,
                sma_window: 12,
                max_cash_per_stock: 0.22,
                check_interval: 30,
                rationale: 'Broad market and small-cap ETFs to capture recovery gains across all sectors.'
            },
            correction: {
                name: 'Correction Mode',
                description: 'Opportunistic buying during pullbacks',
                icon: '🎯',
                color: '#00bcd4',
                stocks: ['VOO', 'QQQ', 'VTI', 'SCHG', 'VUG'],
                trading_buffer: 0.018,
                sma_window: 10,
                max_cash_per_stock: 0.20,
                check_interval: 25,
                rationale: 'Quality broad-market ETFs positioned for dip-buying opportunities during market corrections.'
            }
        };
        
        // Start countdown timer
        function startCountdown() {
            countdownInterval = setInterval(() => {
                countdown--;
                document.getElementById('countdownTimer').textContent = countdown;
                
                if (countdown <= 0) {
                    clearInterval(countdownInterval);
                    autoSelectRecommended();
                }
            }, 1000);
        }
        
        // Stop countdown
        function stopCountdown() {
            clearInterval(countdownInterval);
            document.getElementById('countdownContainer').style.display = 'none';
        }
        
        // Auto-select recommended strategy
        function autoSelectRecommended() {
            selectedStrategy = recommendedStrategy;
            applySelectedStrategy();
        }
        
        // Fetch market condition from server
        async function fetchMarketCondition() {
            try {
                const response = await fetch('/api/market-condition');
                marketData = await response.json();
                
                recommendedStrategy = marketData.condition || 'stagnant';
                
                // Update UI
                document.getElementById('loadingIndicator').style.display = 'none';
                document.getElementById('marketInfo').style.display = 'block';
                
                const preset = presets[recommendedStrategy];
                document.getElementById('marketCondition').innerHTML = 
                    `${preset.icon} ${preset.name} Market Detected`;
                document.getElementById('marketCondition').style.color = preset.color;
                
                const spyChange = marketData.spy_change || 0;
                const spyEl = document.getElementById('spyChange');
                spyEl.textContent = (spyChange >= 0 ? '+' : '') + spyChange.toFixed(2) + '%';
                spyEl.className = 'metric-value ' + (spyChange >= 0 ? 'positive' : 'negative');
                
                const weeklyChange = marketData.weekly_change || 0;
                const weeklyEl = document.getElementById('weeklyChange');
                weeklyEl.textContent = (weeklyChange >= 0 ? '+' : '') + weeklyChange.toFixed(2) + '%';
                weeklyEl.className = 'metric-value ' + (weeklyChange >= 0 ? 'positive' : 'negative');
                
                document.getElementById('vixLevel').textContent = 
                    marketData.vix_level > 25 ? 'High' : marketData.vix_level < 15 ? 'Low' : 'Normal';
                document.getElementById('confidence').textContent = marketData.confidence + '%';
                
                document.getElementById('recommendedName').textContent = preset.name;
                
                // Render strategy cards
                renderStrategyCards();
                
                // Start countdown
                startCountdown();
                
            } catch (e) {
                console.error('Error fetching market condition:', e);
                document.getElementById('loadingIndicator').innerHTML = 
                    '<div style="color: #ff9800;">Could not analyze market. Using default strategies.</div>';
                recommendedStrategy = 'stagnant';
                renderStrategyCards();
                startCountdown();
            }
        }
        
        // Fetch saved settings
        async function fetchSavedSettings() {
            try {
                const response = await fetch('/api/settings');
                savedSettings = await response.json();
            } catch (e) {
                console.error('Error fetching settings:', e);
            }
        }
        
        // Render strategy cards
        function renderStrategyCards() {
            const grid = document.getElementById('strategyGrid');
            let html = '';
            
            // Add saved strategy card first if exists
            if (savedSettings && savedSettings.stocks && savedSettings.stocks.length > 0) {
                const isRecommended = false;
                html += `
                    <div class="strategy-card saved-strategy-card" onclick="selectStrategy('saved')" id="card-saved">
                        <div class="strategy-header">
                            <div class="strategy-icon">💾</div>
                            <div class="strategy-title">Your Saved Strategy</div>
                        </div>
                        <div class="strategy-desc">Continue with your previously configured settings</div>
                        <div class="strategy-details">
                            <div class="detail-row">
                                <span class="detail-label">Buffer</span>
                                <span class="detail-value">${(savedSettings.trading_buffer * 100).toFixed(1)}%</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">SMA Window</span>
                                <span class="detail-value">${savedSettings.sma_window} periods</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Max Position</span>
                                <span class="detail-value">${(savedSettings.max_cash_per_stock * 100).toFixed(0)}%</span>
                            </div>
                        </div>
                        <div class="etf-list">
                            ${savedSettings.stocks.map(s => `<span class="etf-tag">${s}</span>`).join('')}
                        </div>
                    </div>
                `;
            }
            
            // Add preset cards
            for (const [key, preset] of Object.entries(presets)) {
                const isRecommended = key === recommendedStrategy;
                html += `
                    <div class="strategy-card ${isRecommended ? 'recommended' : ''}" 
                         onclick="selectStrategy('${key}')" id="card-${key}">
                        ${isRecommended ? '<div class="recommended-badge">✨ RECOMMENDED</div>' : ''}
                        <div class="strategy-header">
                            <div class="strategy-icon">${preset.icon}</div>
                            <div class="strategy-title" style="color: ${preset.color}">${preset.name}</div>
                        </div>
                        <div class="strategy-desc">${preset.description}</div>
                        <div class="strategy-details">
                            <div class="detail-row">
                                <span class="detail-label">Trading Buffer</span>
                                <span class="detail-value">${(preset.trading_buffer * 100).toFixed(1)}%</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">SMA Window</span>
                                <span class="detail-value">${preset.sma_window} periods</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Max Position</span>
                                <span class="detail-value">${(preset.max_cash_per_stock * 100).toFixed(0)}%</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Check Interval</span>
                                <span class="detail-value">${preset.check_interval}s</span>
                            </div>
                        </div>
                        <div class="etf-list">
                            ${preset.stocks.map(s => `<span class="etf-tag">${s}</span>`).join('')}
                        </div>
                        <div class="rationale">${preset.rationale}</div>
                    </div>
                `;
            }
            
            grid.innerHTML = html;
        }
        
        // Select a strategy
        function selectStrategy(key) {
            stopCountdown();
            
            // Remove selected class from all cards
            document.querySelectorAll('.strategy-card').forEach(card => {
                card.classList.remove('selected');
            });
            
            // Add selected class to clicked card
            document.getElementById('card-' + key).classList.add('selected');
            
            selectedStrategy = key;
            document.getElementById('applyBtn').disabled = false;
        }
        
        // Apply selected strategy
        async function applySelectedStrategy() {
            if (!selectedStrategy) {
                selectedStrategy = recommendedStrategy;
            }
            
            const btn = document.getElementById('applyBtn');
            btn.disabled = true;
            btn.textContent = '⏳ Applying...';
            
            try {
                const response = await fetch('/api/apply-strategy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ strategy: selectedStrategy })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    window.location.href = '/';
                } else {
                    alert('Error applying strategy: ' + result.message);
                    btn.disabled = false;
                    btn.textContent = '🚀 Apply Selected Strategy';
                }
            } catch (e) {
                console.error('Error:', e);
                alert('Error applying strategy');
                btn.disabled = false;
                btn.textContent = '🚀 Apply Selected Strategy';
            }
        }
        
        // Skip selection and go to dashboard
        function skipSelection() {
            stopCountdown();
            window.location.href = '/?skip_strategy=1';
        }
        
        // Initialize
        async function init() {
            await fetchSavedSettings();
            await fetchMarketCondition();
        }
        
        init();
    </script>
</body>
</html>
'''


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
    'configured_stocks': [],   # List of stocks user has configured to monitor
    'strategy_shown_this_session': False,  # Track if strategy selection was shown
    'active_preset': None      # Currently active market preset
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
# - Preset selection and management
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
        .container { max-width: 900px; margin: 0 auto; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 10px;
        }
        h1 {
            font-size: 2rem;
            background: linear-gradient(90deg, #9c27b0, #e91e63);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header-buttons {
            display: flex;
            gap: 10px;
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
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }
        .btn-back { background: #455a64; color: #fff; }
        .btn-back:hover { background: #607d8b; }
        .btn-save { background: #00c853; color: #000; }
        .btn-save:hover { background: #00e676; }
        .btn-small {
            padding: 6px 12px;
            font-size: 0.85rem;
        }
        .btn-danger { background: #ff5252; color: #fff; }
        .btn-danger:hover { background: #ff1744; }
        .btn-secondary { background: rgba(255,255,255,0.1); color: #fff; border: 1px solid rgba(255,255,255,0.2); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .btn-primary { background: #2196f3; color: #fff; }
        .btn-primary:hover { background: #42a5f5; }
        
        /* Preset bar */
        .preset-bar {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .preset-bar h2 {
            font-size: 1rem;
            color: #00d4ff;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .preset-section {
            margin-bottom: 15px;
        }
        .preset-section-title {
            font-size: 0.8rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        .preset-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .preset-chip {
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s ease;
            border: 2px solid transparent;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .preset-chip:hover {
            transform: translateY(-2px);
        }
        .preset-chip.active {
            border-color: #00ff88;
            box-shadow: 0 0 10px rgba(0, 255, 136, 0.3);
        }
        .preset-chip .delete-btn {
            background: rgba(255,255,255,0.2);
            border: none;
            color: #fff;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0.7;
        }
        .preset-chip .delete-btn:hover {
            background: #ff5252;
            opacity: 1;
        }
        
        /* Preset colors */
        .preset-bullish { background: rgba(0, 200, 83, 0.2); color: #00c853; }
        .preset-bearish { background: rgba(255, 82, 82, 0.2); color: #ff5252; }
        .preset-volatile { background: rgba(255, 152, 0, 0.2); color: #ff9800; }
        .preset-stagnant { background: rgba(156, 39, 176, 0.2); color: #9c27b0; }
        .preset-recovery { background: rgba(33, 150, 243, 0.2); color: #2196f3; }
        .preset-correction { background: rgba(0, 188, 212, 0.2); color: #00bcd4; }
        .preset-custom { background: rgba(255, 255, 255, 0.1); color: #e0e0e0; }
        
        /* New preset form */
        .new-preset-form {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        .new-preset-form input {
            flex: 1;
            padding: 10px 15px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            background: rgba(0, 0, 0, 0.3);
            color: #fff;
            font-size: 0.9rem;
        }
        .new-preset-form input:focus {
            outline: none;
            border-color: #00d4ff;
        }
        
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
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .card-description {
            color: #888;
            font-size: 0.9rem;
            margin-bottom: 20px;
            line-height: 1.5;
        }
        
        /* Form styles */
        .form-group { margin-bottom: 25px; }
        .form-group:last-child { margin-bottom: 0; }
        label {
            display: block;
            margin-bottom: 8px;
            color: #e0e0e0;
            font-size: 0.95rem;
            font-weight: 500;
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
        
        /* Enhanced help text */
        .help-text {
            font-size: 0.85rem;
            color: #888;
            margin-top: 8px;
            line-height: 1.5;
        }
        .help-details {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 12px 15px;
            margin-top: 10px;
            border-left: 3px solid #00d4ff;
        }
        .help-details strong {
            color: #00d4ff;
        }
        .help-example {
            background: rgba(0, 212, 255, 0.1);
            padding: 8px 12px;
            border-radius: 4px;
            margin-top: 8px;
            font-family: monospace;
            font-size: 0.85rem;
            color: #00d4ff;
        }
        .help-warning {
            background: rgba(255, 152, 0, 0.1);
            border-left-color: #ff9800;
            color: #ffb74d;
        }
        .help-tip {
            background: rgba(0, 200, 83, 0.1);
            border-left-color: #00c853;
        }
        
        /* Collapsible details */
        .details-toggle {
            color: #00d4ff;
            cursor: pointer;
            font-size: 0.85rem;
            display: inline-flex;
            align-items: center;
            gap: 5px;
            margin-top: 5px;
        }
        .details-toggle:hover {
            text-decoration: underline;
        }
        .details-content {
            display: none;
            margin-top: 10px;
        }
        .details-content.show {
            display: block;
        }
        
        /* Range indicator */
        .range-indicator {
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: #666;
            margin-top: 5px;
        }
        
        /* Input with suffix */
        .input-with-suffix {
            position: relative;
        }
        .input-with-suffix input {
            padding-right: 50px;
        }
        .input-suffix {
            position: absolute;
            right: 15px;
            top: 50%;
            transform: translateY(-50%);
            color: #666;
            font-size: 0.9rem;
        }
        
        /* Success/Error messages */
        .message {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }
        .message.success {
            background: rgba(0, 200, 83, 0.1);
            border: 1px solid rgba(0, 200, 83, 0.3);
            color: #00c853;
        }
        .message.error {
            background: rgba(255, 82, 82, 0.1);
            border: 1px solid rgba(255, 82, 82, 0.3);
            color: #ff5252;
        }
        
        /* Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        .modal-overlay.show {
            display: flex;
        }
        .modal {
            background: #1a1a2e;
            border-radius: 16px;
            padding: 30px;
            max-width: 400px;
            width: 90%;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .modal h3 {
            margin-bottom: 15px;
            color: #ff5252;
        }
        .modal p {
            margin-bottom: 20px;
            color: #888;
        }
        .modal-buttons {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>⚙ Bot Settings</h1>
            <div class="header-buttons">
                <button type="button" class="btn btn-save" onclick="saveSettings()">💾 Save Settings</button>
                <a href="/" class="btn btn-back">← Dashboard</a>
            </div>
        </header>
        
        <!-- Messages -->
        <div id="successMsg" class="message success"></div>
        <div id="errorMsg" class="message error"></div>
        
        <!-- Preset Selection Bar -->
        <div class="preset-bar">
            <h2>📋 Strategy Presets</h2>
            
            <!-- Built-in Presets -->
            <div class="preset-section">
                <div class="preset-section-title">Market Condition Presets</div>
                <div class="preset-grid" id="builtinPresets">
                    <div class="preset-chip preset-bullish" onclick="loadPreset('bullish')" id="preset-bullish">
                        🚀 Bullish Growth
                    </div>
                    <div class="preset-chip preset-bearish" onclick="loadPreset('bearish')" id="preset-bearish">
                        🛡️ Bearish Defense
                    </div>
                    <div class="preset-chip preset-volatile" onclick="loadPreset('volatile')" id="preset-volatile">
                        ⚡ High Volatility
                    </div>
                    <div class="preset-chip preset-stagnant" onclick="loadPreset('stagnant')" id="preset-stagnant">
                        📊 Sideways Income
                    </div>
                    <div class="preset-chip preset-recovery" onclick="loadPreset('recovery')" id="preset-recovery">
                        📈 Market Recovery
                    </div>
                    <div class="preset-chip preset-correction" onclick="loadPreset('correction')" id="preset-correction">
                        🎯 Correction Mode
                    </div>
                </div>
            </div>
            
            <!-- Custom Presets -->
            <div class="preset-section">
                <div class="preset-section-title">Your Custom Presets</div>
                <div class="preset-grid" id="customPresets">
                    <!-- Custom presets will be loaded here -->
                    <span style="color: #666; font-size: 0.9rem;">No custom presets yet</span>
                </div>
            </div>
            
            <!-- Create New Preset -->
            <div class="new-preset-form">
                <input type="text" id="newPresetName" placeholder="Enter preset name..." maxlength="30">
                <button class="btn btn-primary btn-small" onclick="saveAsPreset()">
                    ➕ Save Current as Preset
                </button>
            </div>
        </div>
        
        <form id="settingsForm">
            <!-- Stocks configuration -->
            <div class="card">
                <h2>📊 Stocks & ETFs to Monitor</h2>
                <p class="card-description">
                    Define which securities the bot will track and trade. The bot monitors these symbols 
                    for buy/sell opportunities based on the SMA strategy.
                </p>
                <div class="form-group">
                    <label>Stock/ETF Symbols</label>
                    <input type="text" id="stocks" placeholder="QQQ, SPY, AAPL, MSFT, NVDA">
                    <div class="help-text">
                        Enter stock or ETF ticker symbols separated by commas.
                        <span class="details-toggle" onclick="toggleDetails('stocks-details')">
                            ℹ️ Learn more
                        </span>
                    </div>
                    <div id="stocks-details" class="details-content">
                        <div class="help-details">
                            <strong>What are good choices?</strong><br>
                            • <strong>ETFs</strong> (SPY, QQQ, VTI) - Lower risk, diversified exposure<br>
                            • <strong>Large-cap stocks</strong> (AAPL, MSFT) - More stable, liquid<br>
                            • <strong>Sector ETFs</strong> (XLK, XLF) - Target specific industries<br><br>
                            
                            <strong>Tips:</strong><br>
                            • Start with 3-5 symbols to keep it manageable<br>
                            • Avoid penny stocks or low-volume securities<br>
                            • Mix ETFs and stocks for diversification
                        </div>
                        <div class="help-example">
                            Example: QQQ, SPY, AAPL, MSFT, NVDA
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Trading Parameters -->
            <div class="card">
                <h2>📈 Trading Parameters</h2>
                <p class="card-description">
                    These parameters control when and how the bot makes trading decisions. 
                    Adjust these based on your risk tolerance and market conditions.
                </p>
                
                <div class="form-group">
                    <label>Trading Buffer (Price Deviation Threshold)</label>
                    <div class="input-with-suffix">
                        <input type="number" id="tradingBuffer" step="0.001" min="0.005" max="0.1" value="0.02">
                        <span class="input-suffix">ratio</span>
                    </div>
                    <div class="range-indicator">
                        <span>0.005 (0.5%) - More trades</span>
                        <span>0.1 (10%) - Fewer trades</span>
                    </div>
                    <div class="help-text">
                        How far the price must deviate from the SMA before triggering a trade signal.
                        <span class="details-toggle" onclick="toggleDetails('buffer-details')">
                            ℹ️ Detailed explanation
                        </span>
                    </div>
                    <div id="buffer-details" class="details-content">
                        <div class="help-details">
                            <strong>How it works:</strong><br>
                            The bot calculates a Simple Moving Average (SMA) of recent prices. 
                            When the current price deviates from this average by more than the buffer, 
                            it triggers a signal.<br><br>
                            
                            <strong>BUY Signal:</strong> When price &lt; SMA × (1 - buffer)<br>
                            <strong>SELL Signal:</strong> When price &gt; SMA × (1 + buffer)<br><br>
                            
                            <strong>Choosing a value:</strong><br>
                            • <strong>0.01 (1%)</strong> - Very sensitive, many trades, higher fees, good for volatile stocks<br>
                            • <strong>0.02 (2%)</strong> - Balanced, recommended starting point<br>
                            • <strong>0.03-0.05 (3-5%)</strong> - Conservative, fewer but larger moves<br>
                            • <strong>0.05+ (5%+)</strong> - Very conservative, only major swings
                        </div>
                        <div class="help-example">
                            If SMA = $100 and buffer = 0.02:<br>
                            • BUY when price drops below $98<br>
                            • SELL when price rises above $102
                        </div>
                        <div class="help-details help-warning">
                            <strong>⚠️ Warning:</strong> Lower buffers mean more trades, which increases 
                            transaction costs and potential for "whipsaws" (rapid buy/sell cycles).
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>SMA Window (Moving Average Period)</label>
                    <div class="input-with-suffix">
                        <input type="number" id="smaWindow" min="3" max="100" value="12">
                        <span class="input-suffix">periods</span>
                    </div>
                    <div class="range-indicator">
                        <span>3 - Very responsive</span>
                        <span>100 - Very smooth</span>
                    </div>
                    <div class="help-text">
                        Number of price data points used to calculate the moving average.
                        <span class="details-toggle" onclick="toggleDetails('sma-details')">
                            ℹ️ Detailed explanation
                        </span>
                    </div>
                    <div id="sma-details" class="details-content">
                        <div class="help-details">
                            <strong>What is SMA?</strong><br>
                            Simple Moving Average is the average of the last N prices. 
                            It smooths out price fluctuations to identify trends.<br><br>
                            
                            <strong>Time calculation:</strong><br>
                            Actual time period = SMA Window × Check Interval<br><br>
                            
                            <strong>Examples with 30-second check interval:</strong><br>
                            • Window of 12 = 6 minutes of price history<br>
                            • Window of 20 = 10 minutes of price history<br>
                            • Window of 60 = 30 minutes of price history<br><br>
                            
                            <strong>Choosing a value:</strong><br>
                            • <strong>5-10</strong> - Very responsive, catches quick moves, more noise<br>
                            • <strong>12-20</strong> - Balanced, good for day trading<br>
                            • <strong>20-50</strong> - Smoother, better for swing trading<br>
                            • <strong>50+</strong> - Very smooth, longer-term trends only
                        </div>
                        <div class="help-details help-tip">
                            <strong>💡 Tip:</strong> The bot needs to collect this many data points 
                            before it can calculate the SMA and generate signals. With a window of 12 
                            and 30-second intervals, this takes about 6 minutes after starting.
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Maximum Cash Per Stock</label>
                    <div class="input-with-suffix">
                        <input type="number" id="maxCash" step="0.01" min="0.05" max="1" value="0.25">
                        <span class="input-suffix">ratio</span>
                    </div>
                    <div class="range-indicator">
                        <span>0.05 (5%) - Very diversified</span>
                        <span>1.0 (100%) - All-in</span>
                    </div>
                    <div class="help-text">
                        Maximum percentage of available cash to invest in a single stock per trade.
                        <span class="details-toggle" onclick="toggleDetails('maxcash-details')">
                            ℹ️ Detailed explanation
                        </span>
                    </div>
                    <div id="maxcash-details" class="details-content">
                        <div class="help-details">
                            <strong>Position sizing explained:</strong><br>
                            When a BUY signal triggers, the bot calculates: 
                            Available Cash × Max Cash Per Stock = Maximum investment<br><br>
                            
                            <strong>Example:</strong><br>
                            If you have $10,000 cash and max is 0.25 (25%), 
                            the bot will invest up to $2,500 in any single stock.<br><br>
                            
                            <strong>Risk management:</strong><br>
                            • <strong>0.10-0.15 (10-15%)</strong> - Conservative, well-diversified<br>
                            • <strong>0.20-0.25 (20-25%)</strong> - Moderate, balanced approach<br>
                            • <strong>0.30-0.40 (30-40%)</strong> - Aggressive, concentrated bets<br>
                            • <strong>0.50+ (50%+)</strong> - Very aggressive, high risk
                        </div>
                        <div class="help-details help-warning">
                            <strong>⚠️ Risk Warning:</strong> Higher values mean more concentrated 
                            positions. A 50% drop in one stock could significantly impact your portfolio. 
                            Most professionals recommend 5-10% per position.
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Minimum Shares to Buy</label>
                    <div class="input-with-suffix">
                        <input type="number" id="minShares" min="1" max="100" value="1">
                        <span class="input-suffix">shares</span>
                    </div>
                    <div class="help-text">
                        Minimum number of shares required to execute a buy order.
                        <span class="details-toggle" onclick="toggleDetails('minshares-details')">
                            ℹ️ Detailed explanation
                        </span>
                    </div>
                    <div id="minshares-details" class="details-content">
                        <div class="help-details">
                            <strong>Why set a minimum?</strong><br>
                            Buying just 1 share of a $500 stock when you have $600 cash 
                            might not be worth the transaction. This setting prevents 
                            trades that are too small to be meaningful.<br><br>
                            
                            <strong>Recommendations:</strong><br>
                            • <strong>1 share</strong> - Allow all trades (good for expensive stocks like AMZN, GOOGL)<br>
                            • <strong>3-5 shares</strong> - Skip very small positions<br>
                            • <strong>10+ shares</strong> - Only meaningful positions (for cheap stocks)
                        </div>
                        <div class="help-details help-tip">
                            <strong>💡 Tip:</strong> For expensive stocks (>$200), keep this at 1. 
                            For cheaper stocks (<$50), you might want 5-10 minimum.
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Timing Settings -->
            <div class="card">
                <h2>⏱ Timing & Frequency</h2>
                <p class="card-description">
                    Control how often the bot checks prices and looks for trading opportunities.
                </p>
                
                <div class="form-group">
                    <label>Check Interval</label>
                    <div class="input-with-suffix">
                        <input type="number" id="checkInterval" min="10" max="300" value="30">
                        <span class="input-suffix">seconds</span>
                    </div>
                    <div class="range-indicator">
                        <span>10s - Very frequent</span>
                        <span>300s (5min) - Infrequent</span>
                    </div>
                    <div class="help-text">
                        How often the bot checks prices and evaluates trading signals.
                        <span class="details-toggle" onclick="toggleDetails('interval-details')">
                            ℹ️ Detailed explanation
                        </span>
                    </div>
                    <div id="interval-details" class="details-content">
                        <div class="help-details">
                            <strong>What happens each interval:</strong><br>
                            1. Fetches current prices for all monitored stocks<br>
                            2. Updates the SMA calculation<br>
                            3. Evaluates buy/sell signals<br>
                            4. Executes trades if conditions are met<br><br>
                            
                            <strong>Choosing an interval:</strong><br>
                            • <strong>10-20 seconds</strong> - Day trading, volatile markets, quick reactions<br>
                            • <strong>30 seconds</strong> - Balanced, recommended default<br>
                            • <strong>60 seconds</strong> - Less active trading, calmer markets<br>
                            • <strong>120-300 seconds</strong> - Swing trading, less monitoring
                        </div>
                        <div class="help-details help-warning">
                            <strong>⚠️ API Limits:</strong> Very low intervals (< 15 seconds) may 
                            hit Robinhood's rate limits and cause errors. 30 seconds is a safe choice.
                        </div>
                        <div class="help-details">
                            <strong>Impact on SMA:</strong><br>
                            Remember that your effective SMA time period depends on both the 
                            SMA Window and Check Interval:<br><br>
                            <code>Effective Period = SMA Window × Check Interval</code><br><br>
                            Example: Window of 12 × 30 seconds = 6 minutes of price history
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Market Hours (collapsible) -->
            <div class="card">
                <h2>🕐 Market Hours (Advanced)</h2>
                <p class="card-description">
                    The bot only trades during market hours. These are pre-configured for US markets (Eastern Time).
                    <span class="details-toggle" onclick="toggleDetails('market-hours-details')">
                        ⚙️ Show settings
                    </span>
                </p>
                <div id="market-hours-details" class="details-content">
                    <div class="form-group">
                        <label>Market Open Time</label>
                        <div style="display: flex; gap: 10px;">
                            <input type="number" id="marketOpenHour" min="0" max="23" value="9" style="width: 80px;">
                            <span style="color: #888; line-height: 42px;">:</span>
                            <input type="number" id="marketOpenMinute" min="0" max="59" value="30" style="width: 80px;">
                            <span style="color: #888; line-height: 42px;">ET</span>
                        </div>
                        <div class="help-text">Standard US market open: 9:30 AM ET</div>
                    </div>
                    <div class="form-group">
                        <label>Market Close Time</label>
                        <div style="display: flex; gap: 10px;">
                            <input type="number" id="marketCloseHour" min="0" max="23" value="15" style="width: 80px;">
                            <span style="color: #888; line-height: 42px;">:</span>
                            <input type="number" id="marketCloseMinute" min="0" max="59" value="59" style="width: 80px;">
                            <span style="color: #888; line-height: 42px;">ET</span>
                        </div>
                        <div class="help-text">
                            Bot stops before 4:00 PM to avoid end-of-day volatility. 
                            Set to 15:59 (3:59 PM) by default.
                        </div>
                    </div>
                </div>
            </div>
        </form>
    </div>
    
    <!-- Delete Confirmation Modal -->
    <div class="modal-overlay" id="deleteModal">
        <div class="modal">
            <h3>🗑️ Delete Preset</h3>
            <p>Are you sure you want to delete "<span id="deletePresetName"></span>"? This cannot be undone.</p>
            <div class="modal-buttons">
                <button class="btn btn-secondary" onclick="closeDeleteModal()">Cancel</button>
                <button class="btn btn-danger" onclick="confirmDelete()">Delete</button>
            </div>
        </div>
    </div>
    
    <script>
        // Built-in presets (same as server-side MARKET_PRESETS)
        const builtinPresets = {
            bullish: {
                name: 'Bullish Growth',
                stocks: ['QQQ', 'VGT', 'SMH', 'XLK', 'SOXX'],
                trading_buffer: 0.025,
                sma_window: 15,
                max_cash_per_stock: 0.30,
                min_shares_to_buy: 1,
                check_interval: 45
            },
            bearish: {
                name: 'Bearish Defense',
                stocks: ['SH', 'GLD', 'TLT', 'XLU', 'VPU'],
                trading_buffer: 0.015,
                sma_window: 8,
                max_cash_per_stock: 0.15,
                min_shares_to_buy: 1,
                check_interval: 20
            },
            volatile: {
                name: 'High Volatility',
                stocks: ['SPLV', 'USMV', 'VYM', 'SCHD', 'XLP'],
                trading_buffer: 0.035,
                sma_window: 10,
                max_cash_per_stock: 0.12,
                min_shares_to_buy: 1,
                check_interval: 25
            },
            stagnant: {
                name: 'Sideways Income',
                stocks: ['VYM', 'SCHD', 'HDV', 'DVY', 'JEPI'],
                trading_buffer: 0.02,
                sma_window: 12,
                max_cash_per_stock: 0.25,
                min_shares_to_buy: 1,
                check_interval: 60
            },
            recovery: {
                name: 'Market Recovery',
                stocks: ['VTI', 'SPY', 'IWM', 'XLF', 'VB'],
                trading_buffer: 0.02,
                sma_window: 12,
                max_cash_per_stock: 0.22,
                min_shares_to_buy: 1,
                check_interval: 30
            },
            correction: {
                name: 'Correction Mode',
                stocks: ['VOO', 'QQQ', 'VTI', 'SCHG', 'VUG'],
                trading_buffer: 0.018,
                sma_window: 10,
                max_cash_per_stock: 0.20,
                min_shares_to_buy: 1,
                check_interval: 25
            }
        };
        
        let customPresets = {};
        let currentSettings = {};
        let presetToDelete = null;
        
        // Toggle details visibility
        function toggleDetails(id) {
            const el = document.getElementById(id);
            el.classList.toggle('show');
        }
        
        // Show message
        function showMessage(type, text) {
            const el = document.getElementById(type + 'Msg');
            el.textContent = text;
            el.style.display = 'block';
            setTimeout(() => { el.style.display = 'none'; }, 5000);
        }
        
        // Load settings from server
        async function loadSettings() {
            try {
                const response = await fetch('/api/settings');
                currentSettings = await response.json();
                
                // Load custom presets
                customPresets = currentSettings.custom_presets || {};
                
                // Populate form
                populateForm(currentSettings);
                renderCustomPresets();
                
                // Highlight active preset if any
                if (currentSettings.preset_applied) {
                    highlightPreset(currentSettings.preset_applied);
                }
            } catch (e) {
                console.error('Error loading settings:', e);
                showMessage('error', 'Failed to load settings');
            }
        }
        
        // Populate form with settings
        function populateForm(settings) {
            document.getElementById('stocks').value = (settings.stocks || []).join(', ');
            document.getElementById('tradingBuffer').value = settings.trading_buffer || 0.02;
            document.getElementById('smaWindow').value = settings.sma_window || 12;
            document.getElementById('maxCash').value = settings.max_cash_per_stock || 0.25;
            document.getElementById('minShares').value = settings.min_shares_to_buy || 1;
            document.getElementById('checkInterval').value = settings.check_interval || 30;
            document.getElementById('marketOpenHour').value = settings.market_open_hour || 9;
            document.getElementById('marketOpenMinute').value = settings.market_open_minute || 30;
            document.getElementById('marketCloseHour').value = settings.market_close_hour || 15;
            document.getElementById('marketCloseMinute').value = settings.market_close_minute || 59;
        }
        
        // Get current form values
        function getFormValues() {
            const stocksRaw = document.getElementById('stocks').value;
            return {
                stocks: stocksRaw.split(',').map(s => s.trim().toUpperCase()).filter(s => s),
                trading_buffer: parseFloat(document.getElementById('tradingBuffer').value),
                sma_window: parseInt(document.getElementById('smaWindow').value),
                max_cash_per_stock: parseFloat(document.getElementById('maxCash').value),
                min_shares_to_buy: parseInt(document.getElementById('minShares').value),
                check_interval: parseInt(document.getElementById('checkInterval').value),
                market_open_hour: parseInt(document.getElementById('marketOpenHour').value),
                market_open_minute: parseInt(document.getElementById('marketOpenMinute').value),
                market_close_hour: parseInt(document.getElementById('marketCloseHour').value),
                market_close_minute: parseInt(document.getElementById('marketCloseMinute').value),
                custom_presets: customPresets
            };
        }
        
        // Save settings
        async function saveSettings() {
            const settings = getFormValues();
            
            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                
                const result = await response.json();
                if (result.success) {
                    showMessage('success', '✓ Settings saved successfully!');
                } else {
                    showMessage('error', 'Failed to save settings');
                }
            } catch (e) {
                console.error('Error saving settings:', e);
                showMessage('error', 'Error saving settings');
            }
        }
        
        // Load a preset
        function loadPreset(presetKey) {
            let preset;
            
            if (builtinPresets[presetKey]) {
                preset = builtinPresets[presetKey];
            } else if (customPresets[presetKey]) {
                preset = customPresets[presetKey];
            } else {
                return;
            }
            
            // Update form
            document.getElementById('stocks').value = preset.stocks.join(', ');
            document.getElementById('tradingBuffer').value = preset.trading_buffer;
            document.getElementById('smaWindow').value = preset.sma_window;
            document.getElementById('maxCash').value = preset.max_cash_per_stock;
            document.getElementById('minShares').value = preset.min_shares_to_buy;
            document.getElementById('checkInterval').value = preset.check_interval;
            
            // Highlight active preset
            highlightPreset(presetKey);
            
            showMessage('success', `✓ Loaded "${preset.name}" preset`);
        }
        
        // Highlight active preset
        function highlightPreset(presetKey) {
            // Remove active class from all presets
            document.querySelectorAll('.preset-chip').forEach(chip => {
                chip.classList.remove('active');
            });
            
            // Add active class to selected preset
            const chip = document.getElementById('preset-' + presetKey);
            if (chip) {
                chip.classList.add('active');
            }
        }
        
        // Render custom presets
        function renderCustomPresets() {
            const container = document.getElementById('customPresets');
            const keys = Object.keys(customPresets);
            
            if (keys.length === 0) {
                container.innerHTML = '<span style="color: #666; font-size: 0.9rem;">No custom presets yet</span>';
                return;
            }
            
            container.innerHTML = keys.map(key => {
                const preset = customPresets[key];
                return `
                    <div class="preset-chip preset-custom" id="preset-${key}" onclick="loadPreset('${key}')">
                        📌 ${preset.name}
                        <button class="delete-btn" onclick="event.stopPropagation(); deletePreset('${key}')" title="Delete">×</button>
                    </div>
                `;
            }).join('');
        }
        
        // Save current settings as preset
        async function saveAsPreset() {
            const nameInput = document.getElementById('newPresetName');
            const name = nameInput.value.trim();
            
            if (!name) {
                showMessage('error', 'Please enter a preset name');
                nameInput.focus();
                return;
            }
            
            // Generate a key from the name
            const key = 'custom_' + name.toLowerCase().replace(/[^a-z0-9]/g, '_');
            
            // Check if name already exists
            if (customPresets[key]) {
                if (!confirm(`Preset "${name}" already exists. Overwrite?`)) {
                    return;
                }
            }
            
            // Get current form values
            const values = getFormValues();
            
            // Create preset
            customPresets[key] = {
                name: name,
                stocks: values.stocks,
                trading_buffer: values.trading_buffer,
                sma_window: values.sma_window,
                max_cash_per_stock: values.max_cash_per_stock,
                min_shares_to_buy: values.min_shares_to_buy,
                check_interval: values.check_interval
            };
            
            // Save to server
            const settings = getFormValues();
            settings.custom_presets = customPresets;
            
            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                
                const result = await response.json();
                if (result.success) {
                    nameInput.value = '';
                    renderCustomPresets();
                    highlightPreset(key);
                    showMessage('success', `✓ Preset "${name}" saved!`);
                }
            } catch (e) {
                console.error('Error saving preset:', e);
                showMessage('error', 'Error saving preset');
            }
        }
        
        // Delete preset
        function deletePreset(key) {
            presetToDelete = key;
            document.getElementById('deletePresetName').textContent = customPresets[key].name;
            document.getElementById('deleteModal').classList.add('show');
        }
        
        // Close delete modal
        function closeDeleteModal() {
            document.getElementById('deleteModal').classList.remove('show');
            presetToDelete = null;
        }
        
        // Confirm delete
        async function confirmDelete() {
            if (!presetToDelete) return;
            
            delete customPresets[presetToDelete];
            
            // Save to server
            const settings = getFormValues();
            settings.custom_presets = customPresets;
            
            try {
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                
                renderCustomPresets();
                closeDeleteModal();
                showMessage('success', '✓ Preset deleted');
            } catch (e) {
                console.error('Error deleting preset:', e);
                showMessage('error', 'Error deleting preset');
            }
        }
        
        // Track navigation
        let isNavigating = false;
        document.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => { isNavigating = true; });
        });
        
        window.addEventListener('beforeunload', function() {
            if (!isNavigating) {
                navigator.sendBeacon('/api/shutdown', '');
            }
        });
        
        // Initialize
        loadSettings();
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
    
    If credentials are not configured, redirects to the setup page.
    On first visit (session), redirects to strategy selection.
    Otherwise returns the dashboard HTML which shows portfolio status,
    holdings, options, and trade controls.
    """
    # Check if credentials exist, redirect to setup if not
    if not check_credentials_exist():
        return redirect('/setup')
    
    # Check if user wants to skip strategy selection
    skip_strategy = request.args.get('skip_strategy', '0')
    
    # Check if this is a fresh session that should show strategy selection
    # Use a simple flag in bot_state to track if strategy was already selected this session
    with state_lock:
        strategy_shown = bot_state.get('strategy_shown_this_session', False)
    
    if not strategy_shown and skip_strategy != '1':
        # Mark that we're showing strategy selection
        with state_lock:
            bot_state['strategy_shown_this_session'] = True
        return redirect('/select-strategy')
    
    return render_template_string(DASHBOARD_HTML)


@app.route('/setup')
def setup_page():
    """
    Setup page for entering Robinhood credentials.
    
    URL: http://127.0.0.1:5000/setup
    Shown when .env file is missing or incomplete.
    """
    return render_template_string(SETUP_HTML)


@app.route('/api/setup/credentials', methods=['POST'])
def save_credentials_api():
    """
    API endpoint to save Robinhood credentials.
    
    URL: http://127.0.0.1:5000/api/setup/credentials (POST only)
    Receives username and password from the setup form and saves to .env file.
    """
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password are required'})
        
        # Save credentials to .env file
        save_credentials(username, password)
        
        return jsonify({'success': True, 'message': 'Credentials saved successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/check-credentials')
def check_credentials_api():
    """
    API endpoint to check if credentials are configured.
    
    URL: http://127.0.0.1:5000/api/check-credentials
    Returns JSON indicating whether .env file exists with valid credentials.
    """
    return jsonify({'configured': check_credentials_exist()})


@app.route('/select-strategy')
def strategy_select_page():
    """
    Strategy selection page shown on startup.
    
    URL: http://127.0.0.1:5000/select-strategy
    Allows user to choose between saved strategy or market-based presets.
    """
    # Check if credentials exist, redirect to setup if not
    if not check_credentials_exist():
        return redirect('/setup')
    
    return render_template_string(STRATEGY_SELECT_HTML)


@app.route('/api/market-condition')
def get_market_condition():
    """
    API endpoint to detect and return current market condition.
    
    URL: http://127.0.0.1:5000/api/market-condition
    Analyzes SPY performance and volatility to determine market state.
    """
    condition = detect_market_condition()
    return jsonify(condition)


@app.route('/api/apply-strategy', methods=['POST'])
def apply_strategy_api():
    """
    API endpoint to apply a trading strategy preset.
    
    URL: http://127.0.0.1:5000/api/apply-strategy (POST only)
    Accepts strategy name and applies the corresponding preset settings.
    """
    try:
        data = request.json
        strategy = data.get('strategy', 'stagnant')
        
        if strategy == 'saved':
            # Keep existing settings, just mark that user chose saved
            settings = load_settings()
            settings['strategy_source'] = 'saved'
            settings['strategy_applied_at'] = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_settings(settings)
            return jsonify({'success': True, 'message': 'Saved strategy applied'})
        
        elif strategy in MARKET_PRESETS:
            settings = apply_preset(strategy)
            return jsonify({'success': True, 'message': f'{strategy} preset applied', 'settings': settings})
        
        else:
            return jsonify({'success': False, 'message': 'Unknown strategy'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/presets')
def get_presets():
    """
    API endpoint to get all available market presets.
    
    URL: http://127.0.0.1:5000/api/presets
    Returns all preset configurations for display in UI.
    """
    return jsonify(MARKET_PRESETS)


@app.route('/settings')
def settings_page():
    """
    Settings configuration page.
    
    URL: http://127.0.0.1:5000/settings
    Returns the settings HTML which allows users to configure
    stocks to monitor and trading parameters.
    """
    # Check if credentials exist, redirect to setup if not
    if not check_credentials_exist():
        return redirect('/setup')
    
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
    print("URLs:")
    print("  Dashboard:         http://127.0.0.1:5000")
    print("  Settings:          http://127.0.0.1:5000/settings")
    print("  Strategy Select:   http://127.0.0.1:5000/select-strategy")
    print("  Setup:             http://127.0.0.1:5000/setup")
    print()
    
    # Check if credentials exist and inform user
    if not check_credentials_exist():
        print("⚠  No .env file found - you will be prompted to enter credentials")
    else:
        print("✓  Credentials found in .env file")
        print("📊 You will be prompted to select a trading strategy")
        print("   (auto-selects recommended strategy after 30 seconds)")
    
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