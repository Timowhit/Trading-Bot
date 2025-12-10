"""
Trading Bot Dashboard with Options and Settings
"""
import os
import threading
import datetime as dt
import json
from flask import Flask, render_template, jsonify, request
import robin_stocks.robinhood as rh
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

bot_state = {
    'running': False,
    'last_update': None,
    'holdings': {},
    'holdings_info': {},
    'options': [],
    'prices': {},
    'signals': {},
    'sma_values': {},
    'ratios': {},
    'cash': 0,
    'equity': 0,
    'trade_log': [],
    'configured_stocks': []
}

state_lock = threading.Lock()
SETTINGS_FILE = 'bot_settings.json'

def load_settings():
    default_settings = {
        'stocks': [],
        'trading_buffer': 0.002,
        'sma_window': 12,
        'max_cash_per_stock': 0.15,
        'min_shares_to_buy': 3,
        'check_interval': 30,
        'auto_refresh': True,
        'refresh_interval': 30
    }
    
    try:
        with open(SETTINGS_FILE, 'r') as f:
            saved = json.load(f)
            default_settings.update(saved)
    except FileNotFoundError:
        try:
            import config
            default_settings['stocks'] = config.STOCKS.copy()
            default_settings['trading_buffer'] = config.TRADING_BUFFER
            default_settings['sma_window'] = config.SMA_WINDOW
            default_settings['max_cash_per_stock'] = config.MAX_CASH_PER_STOCK
            default_settings['min_shares_to_buy'] = config.MIN_SHARES_TO_BUY
            default_settings['check_interval'] = config.CHECK_INTERVAL
        except:
            pass
    
    return default_settings

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def get_configured_stocks():
    settings = load_settings()
    if settings['stocks']:
        return settings['stocks']
    try:
        import config
        return config.STOCKS
    except:
        return []


def update_bot_state(holdings=None, prices=None, signals=None, 
                     sma_values=None, ratios=None, cash=None, equity=None, options=None):
    with state_lock:
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
        bot_state['last_update'] = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def add_trade_log(stock, action, shares, price):
    with state_lock:
        bot_state['trade_log'].insert(0, {
            'time': dt.datetime.now().strftime('%H:%M:%S'),
            'stock': stock,
            'action': action,
            'shares': shares,
            'price': price
        })
        bot_state['trade_log'] = bot_state['trade_log'][:50]


@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/settings')
def settings_page():
    return render_template('settings.html')


@app.route('/api/status')
def get_status():
    with state_lock:
        return jsonify(bot_state)


@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'GET':
        return jsonify(load_settings())
    else:
        settings = request.json
        save_settings(settings)
        return jsonify({'success': True})


@app.route('/api/refresh')
def refresh_data():
    try:
        username = os.getenv('ROBINHOOD_USERNAME')
        password = os.getenv('ROBINHOOD_PASSWORD')
        
        if not username or not password:
            return jsonify({'error': 'Missing credentials'}), 400
        
        rh.authentication.login(username, password, store_session=True)
        
        profile = rh.account.build_user_profile()
        cash = float(profile.get('cash', 0))
        equity = float(profile.get('equity', 0))
        
        configured_stocks = get_configured_stocks()
        
        rh_holdings = rh.account.build_holdings()
        
        all_stocks = set(configured_stocks)
        for stock in rh_holdings.keys():
            all_stocks.add(stock)
        all_stocks = list(all_stocks)
        
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
                    'configured': stock in configured_stocks
                }
            except (KeyError, TypeError):
                holdings[stock] = 0
                holdings_info[stock] = {
                    'quantity': 0,
                    'avg_price': 0,
                    'equity': 0,
                    'percent_change': 0,
                    'configured': stock in configured_stocks
                }
        
        prices_list = rh.stocks.get_latest_price(all_stocks)
        prices = {stock: float(prices_list[i]) if prices_list[i] else 0 for i, stock in enumerate(all_stocks)}
        
        # Get OPTIONS
        options_data = []
        try:
            options_positions = rh.options.get_open_option_positions()
            
            for opt in options_positions:
                try:
                    qty = float(opt.get('quantity', 0))
                    if qty <= 0:
                        continue
                    
                    chain_symbol = opt.get('chain_symbol', 'N/A')
                    option_id = opt.get('option_id', '')
                    
                    option_data = {}
                    market_data = {}
                    
                    if option_id:
                        try:
                            option_data = rh.options.get_option_instrument_data_by_id(option_id) or {}
                        except Exception as e:
                            print(f"Error getting option instrument: {e}")
                        
                        try:
                            md = rh.options.get_option_market_data_by_id(option_id)
                            # market_data comes back as a LIST, not a dict!
                            if md and isinstance(md, list) and len(md) > 0:
                                market_data = md[0]
                            elif md and isinstance(md, dict):
                                market_data = md
                        except Exception as e:
                            print(f"Error getting market data: {e}")
                    
                    # average_price is in cents
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
                    
                    # Get expiration
                    expiration = opt.get('expiration_date') or option_data.get('expiration_date', 'N/A')
                    
                    # Get option type (call/put)
                    option_type = (option_data.get('type', '') or 'N/A').upper()
                    
                    # Get strike price
                    strike = float(option_data.get('strike_price', 0) or 0)
                    
                    options_data.append({
                        'symbol': chain_symbol,
                        'type': option_type,
                        'strike': strike,
                        'expiration': expiration,
                        'quantity': int(qty),
                        'avg_price': avg_price,
                        'current_price': current_price,
                        'equity': qty * current_price * 100,
                        'percent_change': pct_change
                    })
                    
                except Exception as e:
                    print(f"Error processing option: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error fetching options: {e}")
        
        update_bot_state(
            holdings=holdings,
            prices=prices,
            cash=cash,
            equity=equity,
            options=options_data
        )
        
        with state_lock:
            bot_state['holdings_info'] = holdings_info
            bot_state['configured_stocks'] = configured_stocks
        
        return jsonify({'success': True, 'message': f'Found {len(options_data)} options'})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/debug/options')
def debug_options():
    try:
        username = os.getenv('ROBINHOOD_USERNAME')
        password = os.getenv('ROBINHOOD_PASSWORD')
        rh.authentication.login(username, password, store_session=True)
        
        options_positions = rh.options.get_open_option_positions()
        
        instrument_data = None
        market_data = None
        if options_positions and len(options_positions) > 0:
            option_id = options_positions[0].get('option_id')
            if option_id:
                try:
                    instrument_data = rh.options.get_option_instrument_data_by_id(option_id)
                except Exception as e:
                    instrument_data = {'error': str(e)}
                try:
                    market_data = rh.options.get_option_market_data_by_id(option_id)
                except Exception as e:
                    market_data = {'error': str(e)}
        
        return jsonify({
            'count': len(options_positions),
            'positions': options_positions,
            'first_instrument_data': instrument_data,
            'first_market_data': market_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)