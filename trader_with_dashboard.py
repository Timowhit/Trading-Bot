"""
Main Trading Bot (with Dashboard Integration)

This version updates the Flask dashboard with real-time data.
Run dashboard.py separately to view the web interface.
"""
import datetime as dt
import time
import pandas as pd

import robin_stocks.robinhood as rh
import config
import trade_strategy

# Import dashboard state updater (optional - works without dashboard too)
try:
    from dashboard import update_bot_state, add_trade_log, bot_state
    DASHBOARD_ENABLED = True
except ImportError:
    DASHBOARD_ENABLED = False
    print("Dashboard not available - running standalone")


def login(days=7):
    """Log into Robinhood account."""
    print("Logging into Robinhood...")
    time_logged_in = 60 * 60 * 24 * days
    
    rh.authentication.login(
        username=config.username,
        password=config.password,
        expiresIn=time_logged_in,
        store_session=True
    )
    print("✓ Login successful!")


def logout():
    """Log out of Robinhood account."""
    print("Logging out...")
    rh.authentication.logout()
    print("✓ Logged out successfully!")


def is_market_open():
    """Check if the market is currently open."""
    time_now = dt.datetime.now().time()
    
    market_open = dt.time(config.MARKET_OPEN_HOUR, config.MARKET_OPEN_MINUTE, 0)
    market_close = dt.time(config.MARKET_CLOSE_HOUR, config.MARKET_CLOSE_MINUTE, 0)
    
    is_open = market_open < time_now < market_close
    
    if not is_open:
        print(f"Market is closed (opens at {market_open}, closes at {market_close})")
    
    return is_open


def get_account_cash():
    """Get current cash and equity in account."""
    profile = rh.account.build_user_profile()
    cash = float(profile['cash'])
    equity = float(profile['equity'])
    return cash, equity


def get_holdings_and_prices(stocks):
    """Get current holdings and average buy prices for stocks."""
    holdings = {stock: 0 for stock in stocks}
    bought_price = {stock: 0 for stock in stocks}
    
    rh_holdings = rh.account.build_holdings()
    
    for stock in stocks:
        try:
            holdings[stock] = int(float(rh_holdings[stock]['quantity']))
            bought_price[stock] = float(rh_holdings[stock]['average_buy_price'])
        except (KeyError, TypeError):
            holdings[stock] = 0
            bought_price[stock] = 0
    
    return holdings, bought_price


def execute_sell(stock, quantity, price):
    """Execute a sell order."""
    sell_price = round(price - 0.10, 2)
    
    print(f"🔴 SELL SIGNAL: {stock} - {quantity} shares @ ${sell_price}")
    
    if DASHBOARD_ENABLED:
        add_trade_log(stock, 'SELL', quantity, sell_price)
    
    # UNCOMMENT THESE LINES TO ENABLE LIVE TRADING
    # WARNING: This will execute real trades!
    #sell_order = rh.orders.order_sell_limit(
    #    symbol=stock,
    #    quantity=quantity,
    #    limitPrice=sell_price,
    #    timeInForce='gfd'
    #)
    #print(f"✓ Sell order placed: {sell_order}")


def execute_buy(stock, quantity, price):
    """Execute a buy order."""
    buy_price = round(price + 0.10, 2)
    
    print(f"🟢 BUY SIGNAL: {stock} - {quantity} shares @ ${buy_price}")
    
    if DASHBOARD_ENABLED:
        add_trade_log(stock, 'BUY', quantity, buy_price)
    
    # UNCOMMENT THESE LINES TO ENABLE LIVE TRADING
    # WARNING: This will execute real trades!
    #buy_order = rh.orders.order_buy_limit(
    #    symbol=stock,
    #    quantity=quantity,
    #    limitPrice=buy_price,
    #    timeInForce='gfd'
    #)
    #print(f"✓ Buy order placed: {buy_order}")


def create_graph(df_prices, df_trades):
    """Create and save trading graph."""
    if not config.SAVE_GRAPHS:
        return
    
    try:
        from robin_stocks.robinhood import grapher
        normalized_prices = grapher.normalize(df_prices)
        grapher.active_graph(normalized_prices, df_trades, pause=1)
    except Exception as e:
        print(f"Warning: Could not create graph: {e}")


def main():
    """Main trading bot loop."""
    print("=" * 60)
    print("ROBINHOOD TRADING BOT")
    print("=" * 60)
    print("\n⚠️  WARNING: Trading is currently DISABLED (dry run mode)")
    print("To enable live trading, uncomment the order lines in this file.")
    if DASHBOARD_ENABLED:
        print("📊 Dashboard integration: ENABLED")
    print("=" * 60)
    
    login(days=7)
    
    stocks = config.STOCKS
    print(f"\nMonitoring stocks: {', '.join(stocks)}")
    
    cash, equity = get_account_cash()
    print(f"Account equity: ${equity:,.2f}")
    print(f"Available cash: ${cash:,.2f}")
    
    strategy = trade_strategy.TradingStrategy(stocks)
    
    trade_dict = {stock: 'WAIT' for stock in stocks}
    price_dict = {stock: 0.0 for stock in stocks}
    df_trades = pd.DataFrame(columns=stocks)
    df_prices = pd.DataFrame(columns=stocks)
    
    # Update dashboard with initial state
    if DASHBOARD_ENABLED:
        bot_state['running'] = True
        update_bot_state(cash=cash, equity=equity)
    
    print("\n" + "=" * 60)
    print("Starting trading loop...")
    print("=" * 60 + "\n")
    
    iteration = 0
    try:
        while is_market_open():
            iteration += 1
            print(f"\n--- Iteration {iteration} at {dt.datetime.now().strftime('%H:%M:%S')} ---")
            
            prices = rh.stocks.get_latest_price(stocks)
            holdings, bought_prices = get_holdings_and_prices(stocks)
            cash, equity = get_account_cash()
            
            print(f"Holdings: {holdings}")
            
            signals_dict = {}
            sma_dict = {}
            ratios_dict = {}
            
            for i, stock in enumerate(stocks):
                try:
                    price = float(prices[i])
                    print(f"\n{stock}: ${price:.2f}")
                    
                    signal = strategy.get_trade_signal(stock, price)
                    print(f"  Signal: {signal}")
                    
                    signals_dict[stock] = signal
                    status = strategy.get_status(stock)
                    sma_dict[stock] = status['sma']
                    ratios_dict[stock] = status['price_sma_ratio']
                    
                    if signal == 'BUY':
                        max_investment = cash * config.MAX_CASH_PER_STOCK
                        shares_to_buy = int(max_investment / price)
                        
                        if shares_to_buy >= config.MIN_SHARES_TO_BUY and holdings[stock] == 0:
                            execute_buy(stock, shares_to_buy, price)
                            trade_dict[stock] = 'BUY'
                        else:
                            trade_dict[stock] = 'WAIT'
                            if shares_to_buy < config.MIN_SHARES_TO_BUY:
                                print(f"  Skipping: Can only afford {shares_to_buy} shares")
                    
                    elif signal == 'SELL':
                        if holdings[stock] > 0:
                            execute_sell(stock, holdings[stock], price)
                            trade_dict[stock] = 'SELL'
                        else:
                            trade_dict[stock] = 'WAIT'
                    
                    else:
                        if holdings[stock] > 0:
                            trade_dict[stock] = 'HOLD'
                            print(f"  Holding {holdings[stock]} shares (bought @ ${bought_prices[stock]:.2f})")
                        else:
                            trade_dict[stock] = 'WAIT'
                    
                    price_dict[stock] = price
                    
                    if config.VERBOSE_LOGGING:
                        print(f"  SMA: ${status['sma']:.2f}, Ratio: {status['price_sma_ratio']:.4f}")
                
                except Exception as e:
                    print(f"Error processing {stock}: {e}")
                    continue
            
            # Update dashboard
            if DASHBOARD_ENABLED:
                update_bot_state(
                    holdings=holdings,
                    prices=price_dict,
                    signals=signals_dict,
                    sma_values=sma_dict,
                    ratios=ratios_dict,
                    cash=cash,
                    equity=equity
                )
            
            timestamp = dt.datetime.now().strftime('%H:%M:%S')
            df_trades.loc[timestamp] = trade_dict
            df_prices.loc[timestamp] = price_dict
            
            create_graph(df_prices, df_trades)
            strategy.increment_runtime()
            
            print(f"\nWaiting {config.CHECK_INTERVAL} seconds...")
            time.sleep(config.CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n\nBot stopped by user.")
    
    except Exception as e:
        print(f"\n\nError in main loop: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if DASHBOARD_ENABLED:
            bot_state['running'] = False
        logout()
        print("\nBot session ended.")


if __name__ == "__main__":
    main()
