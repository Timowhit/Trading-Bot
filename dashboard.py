"""
Trading Bot Dashboard with Start/Stop Control
"""
import os
import threading
import datetime as dt
import json
import time
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

# Bot control
bot_thread = None
stop_bot_event = threading.Event()


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


# ============================================================================
# BOT TRADING LOOP (runs in background thread)
# ============================================================================

def run_trading_bot():
    """Main trading bot loop - runs in a background thread."""
    import config
    import trade_strategy
    import pandas as pd
    
    print("=" * 60)
    print("TRADING BOT STARTED")
    print("=" * 60)
    
    try:
        # Login
        username = os.getenv('ROBINHOOD_USERNAME')
        password = os.getenv('ROBINHOOD_PASSWORD')
        
        if not username or not password:
            print("ERROR: Missing credentials")
            with state_lock:
                bot_state['running'] = False
            return
        
        rh.authentication.login(username, password, store_session=True)
        print("✓ Login successful!")
        
        # Get settings
        settings = load_settings()
        stocks = settings['stocks'] if settings['stocks'] else config.STOCKS
        trading_buffer = settings.get('trading_buffer', config.TRADING_BUFFER)
        max_cash_per_stock = settings.get('max_cash_per_stock', config.MAX_CASH_PER_STOCK)
        min_shares_to_buy = settings.get('min_shares_to_buy', config.MIN_SHARES_TO_BUY)
        check_interval = settings.get('check_interval', config.CHECK_INTERVAL)
        
        print(f"Monitoring stocks: {', '.join(stocks)}")
        
        # Override config with settings
        config.TRADING_BUFFER = trading_buffer
        config.MAX_CASH_PER_STOCK = max_cash_per_stock
        config.MIN_SHARES_TO_BUY = min_shares_to_buy
        
        # Initialize strategy
        strategy = trade_strategy.TradingStrategy(stocks)
        
        iteration = 0
        
        # Main loop - check stop_bot_event to know when to stop
        while not stop_bot_event.is_set():
            # Check market hours
            time_now = dt.datetime.now().time()
            market_open = dt.time(config.MARKET_OPEN_HOUR, config.MARKET_OPEN_MINUTE, 0)
            market_close = dt.time(config.MARKET_CLOSE_HOUR, config.MARKET_CLOSE_MINUTE, 0)
            
            if not (market_open < time_now < market_close):
                print(f"Market closed. Waiting... (opens {market_open}, closes {market_close})")
                # Wait but check for stop signal every 10 seconds
                for _ in range(6):  # Check every 10 seconds for 1 minute
                    if stop_bot_event.is_set():
                        break
                    time.sleep(10)
                continue
            
            iteration += 1
            print(f"\n--- Iteration {iteration} at {dt.datetime.now().strftime('%H:%M:%S')} ---")
            
            try:
                # Get account info
                profile = rh.account.build_user_profile()
                cash = float(profile.get('cash', 0))
                equity = float(profile.get('equity', 0))
                
                # Get current prices
                prices_list = rh.stocks.get_latest_price(stocks)
                
                # Get holdings
                rh_holdings = rh.account.build_holdings()
                holdings = {}
                bought_prices = {}
                
                for stock in stocks:
                    try:
                        holdings[stock] = int(float(rh_holdings[stock]['quantity']))
                        bought_prices[stock] = float(rh_holdings[stock]['average_buy_price'])
                    except (KeyError, TypeError):
                        holdings[stock] = 0
                        bought_prices[stock] = 0
                
                print(f"Holdings: {holdings}")
                
                signals_dict = {}
                sma_dict = {}
                ratios_dict = {}
                price_dict = {}
                
                for i, stock in enumerate(stocks):
                    try:
                        price = float(prices_list[i]) if prices_list[i] else 0
                        price_dict[stock] = price
                        print(f"\n{stock}: ${price:.2f}")
                        
                        # Get trading signal
                        signal = strategy.get_trade_signal(stock, price)
                        print(f"  Signal: {signal}")
                        
                        signals_dict[stock] = signal
                        status = strategy.get_status(stock)
                        sma_dict[stock] = status['sma']
                        ratios_dict[stock] = status['price_sma_ratio']
                        
                        # Execute trades
                        if signal == 'BUY':
                            max_investment = cash * max_cash_per_stock
                            shares_to_buy = int(max_investment / price) if price > 0 else 0
                            
                            if shares_to_buy >= min_shares_to_buy and holdings[stock] == 0:
                                buy_price = round(price + 0.10, 2)
                                print(f"🟢 BUY: {stock} - {shares_to_buy} shares @ ${buy_price}")
                                
                                add_trade_log(stock, 'BUY', shares_to_buy, buy_price)
                                
                                # UNCOMMENT FOR LIVE TRADING:
                                # rh.orders.order_buy_limit(
                                #     symbol=stock,
                                #     quantity=shares_to_buy,
                                #     limitPrice=buy_price,
                                #     timeInForce='gfd'
                                # )
                        
                        elif signal == 'SELL':
                            if holdings[stock] > 0:
                                sell_price = round(price - 0.10, 2)
                                print(f"🔴 SELL: {stock} - {holdings[stock]} shares @ ${sell_price}")
                                
                                add_trade_log(stock, 'SELL', holdings[stock], sell_price)
                                
                                # UNCOMMENT FOR LIVE TRADING:
                                # rh.orders.order_sell_limit(
                                #     symbol=stock,
                                #     quantity=holdings[stock],
                                #     limitPrice=sell_price,
                                #     timeInForce='gfd'
                                # )
                        
                        else:
                            if holdings[stock] > 0:
                                print(f"  Holding {holdings[stock]} shares")
                        
                        print(f"  SMA: ${status['sma']:.2f}, Ratio: {status['price_sma_ratio']:.4f}")
                    
                    except Exception as e:
                        print(f"Error processing {stock}: {e}")
                        continue
                
                # Update dashboard state
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
            
            # Wait for next check, but check stop signal every second
            print(f"\nWaiting {check_interval} seconds...")
            for _ in range(check_interval):
                if stop_bot_event.is_set():
                    break
                time.sleep(1)
    
    except Exception as e:
        print(f"Bot error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n" + "=" * 60)
        print("TRADING BOT STOPPED")
        print("=" * 60)
        with state_lock:
            bot_state['running'] = False


# ============================================================================
# ROUTES
# ============================================================================

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


@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the trading bot in a background thread."""
    global bot_thread, stop_bot_event
    
    with state_lock:
        if bot_state['running']:
            return jsonify({'success': False, 'message': 'Bot is already running'})
    
    # Clear the stop event and start the bot
    stop_bot_event.clear()
    
    with state_lock:
        bot_state['running'] = True
    
    bot_thread = threading.Thread(target=run_trading_bot, daemon=True)
    bot_thread.start()
    
    return jsonify({'success': True, 'message': 'Bot started'})


@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot."""
    global stop_bot_event
    
    with state_lock:
        if not bot_state['running']:
            return jsonify({'success': False, 'message': 'Bot is not running'})
    
    # Signal the bot to stop
    stop_bot_event.set()
    
    return jsonify({'success': True, 'message': 'Stop signal sent'})


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
                            if md and isinstance(md, list) and len(md) > 0:
                                market_data = md[0]
                            elif md and isinstance(md, dict):
                                market_data = md
                        except Exception as e:
                            print(f"Error getting market data: {e}")
                    
                    avg_price = float(opt.get('average_price', 0)) / 100
                    
                    current_price = 0
                    if market_data:
                        current_price = float(
                            market_data.get('adjusted_mark_price') or 
                            market_data.get('mark_price') or 
                            market_data.get('last_trade_price') or 0
                        )
                    
                    pct_change = 0
                    if avg_price > 0 and current_price > 0:
                        pct_change = ((current_price - avg_price) / avg_price) * 100
                    
                    expiration = opt.get('expiration_date') or option_data.get('expiration_date', 'N/A')
                    option_type = (option_data.get('type', '') or 'N/A').upper()
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