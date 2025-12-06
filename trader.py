"""
Main Trading Bot

This is the main script that runs the automated trading bot.
It handles login, market hours checking, and executes the trading strategy.
"""
import datetime as dt
import time
import pandas as pd

import robin_stocks.robinhood as rh
import config
import trade_strategy


def login(days=7):
    """
    Log into Robinhood account.
    
    Args:
        days (int): Number of days to stay logged in
    """
    print("Logging into Robinhood...")
    time_logged_in = 60 * 60 * 24 * days
    
    rh.authentication.login(
        username=config.username,
        password=config.password,
        expiresIn=time_logged_in,
        scope='internal',
        by_sms=True,
        store_session=True
    )
    print("✓ Login successful!")


def logout():
    """Log out of Robinhood account."""
    print("Logging out...")
    rh.authentication.logout()
    print("✓ Logged out successfully!")


def is_market_open():
    """
    Check if the market is currently open.
    
    Returns:
        bool: True if market is open, False otherwise
    """
    time_now = dt.datetime.now().time()
    
    market_open = dt.time(
        config.MARKET_OPEN_HOUR,
        config.MARKET_OPEN_MINUTE,
        0
    )
    market_close = dt.time(
        config.MARKET_CLOSE_HOUR,
        config.MARKET_CLOSE_MINUTE,
        0
    )
    
    is_open = market_open < time_now < market_close
    
    if not is_open:
        print(f"Market is closed (opens at {market_open}, closes at {market_close})")
    
    return is_open


def get_account_cash():
    """
    Get current cash and equity in account.
    
    Returns:
        tuple: (cash, equity) as floats
    """
    profile = rh.account.build_user_profile()
    
    cash = float(profile['cash'])
    equity = float(profile['equity'])
    
    return cash, equity


def get_holdings_and_prices(stocks):
    """
    Get current holdings and average buy prices for stocks.
    
    Args:
        stocks (list): List of stock ticker symbols
    
    Returns:
        tuple: (holdings_dict, bought_price_dict)
    """
    holdings = {stock: 0 for stock in stocks}
    bought_price = {stock: 0 for stock in stocks}
    
    rh_holdings = rh.account.build_holdings()
    
    for stock in stocks:
        try:
            holdings[stock] = int(float(rh_holdings[stock]['quantity']))
            bought_price[stock] = float(rh_holdings[stock]['average_buy_price'])
        except (KeyError, TypeError):
            # Stock not in holdings
            holdings[stock] = 0
            bought_price[stock] = 0
    
    return holdings, bought_price


def execute_sell(stock, quantity, price):
    """
    Execute a sell order.
    
    Args:
        stock (str): Stock ticker symbol
        quantity (int): Number of shares to sell
        price (float): Current price
    """
    sell_price = round(price - 0.10, 2)
    
    print(f"🔴 SELL SIGNAL: {stock} - {quantity} shares @ ${sell_price}")
    
    # UNCOMMENT THESE LINES TO ENABLE LIVE TRADING
    # WARNING: This will execute real trades!
    # sell_order = rh.orders.order_sell_limit(
    #     symbol=stock,
    #     quantity=quantity,
    #     limitPrice=sell_price,
    #     timeInForce='gfd'
    # )
    # print(f"✓ Sell order placed: {sell_order}")


def execute_buy(stock, quantity, price):
    """
    Execute a buy order.
    
    Args:
        stock (str): Stock ticker symbol
        quantity (int): Number of shares to buy
        price (float): Current price
    """
    buy_price = round(price + 0.10, 2)
    
    print(f"🟢 BUY SIGNAL: {stock} - {quantity} shares @ ${buy_price}")
    
    # UNCOMMENT THESE LINES TO ENABLE LIVE TRADING
    # WARNING: This will execute real trades!
    # buy_order = rh.orders.order_buy_limit(
    #     symbol=stock,
    #     quantity=quantity,
    #     limitPrice=buy_price,
    #     timeInForce='gfd'
    # )
    # print(f"✓ Buy order placed: {buy_order}")


def save_dataframe(df_trades, df_prices, timestamp):
    """
    Update dataframes with current data.
    
    Args:
        df_trades (DataFrame): Trading signals dataframe
        df_prices (DataFrame): Prices dataframe
        timestamp (str): Current timestamp
    
    Returns:
        tuple: Updated (df_trades, df_prices)
    """
    # This would be implemented with actual data
    # For now, just return the dataframes
    return df_trades, df_prices


def create_graph(df_prices, df_trades):
    """
    Create and save trading graph.
    
    Args:
        df_prices (DataFrame): Historical prices
        df_trades (DataFrame): Trading signals
    """
    if not config.SAVE_GRAPHS:
        return
    
    try:
        from robin_stocks.robinhood import grapher
        
        # Normalize prices
        normalized_prices = grapher.normalize(df_prices)
        
        # Create graph
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
    print("=" * 60)
    
    # Login
    login(days=7)
    
    # Get configuration
    stocks = config.STOCKS
    print(f"\nMonitoring stocks: {', '.join(stocks)}")
    
    # Get initial account info
    cash, equity = get_account_cash()
    print(f"Account equity: ${equity:,.2f}")
    print(f"Available cash: ${cash:,.2f}")
    
    # Initialize strategy
    strategy = trade_strategy.TradingStrategy(stocks)
    
    # Initialize dataframes for tracking
    trade_dict = {stock: 'WAIT' for stock in stocks}
    price_dict = {stock: 0.0 for stock in stocks}
    df_trades = pd.DataFrame(columns=stocks)
    df_prices = pd.DataFrame(columns=stocks)
    
    print("\n" + "=" * 60)
    print("Starting trading loop...")
    print("=" * 60 + "\n")
    
    # Main trading loop
    iteration = 0
    try:
        while is_market_open():
            iteration += 1
            print(f"\n--- Iteration {iteration} at {dt.datetime.now().strftime('%H:%M:%S')} ---")
            
            # Get current prices
            prices = rh.stocks.get_latest_price(stocks)
            holdings, bought_prices = get_holdings_and_prices(stocks)
            
            print(f"Holdings: {holdings}")
            
            # Process each stock
            for i, stock in enumerate(stocks):
                try:
                    price = float(prices[i])
                    print(f"\n{stock}: ${price:.2f}")
                    
                    # Get trading signal from strategy
                    signal = strategy.get_trade_signal(stock, price)
                    print(f"  Signal: {signal}")
                    
                    # Execute trades based on signal
                    if signal == 'BUY':
                        # Calculate how many shares we can buy
                        max_investment = cash * config.MAX_CASH_PER_STOCK
                        shares_to_buy = int(max_investment / price)
                        
                        # Only buy if we can afford minimum shares and don't already hold
                        if shares_to_buy >= config.MIN_SHARES_TO_BUY and holdings[stock] == 0:
                            execute_buy(stock, shares_to_buy, price)
                            trade_dict[stock] = 'BUY'
                        else:
                            trade_dict[stock] = 'WAIT'
                            if shares_to_buy < config.MIN_SHARES_TO_BUY:
                                print(f"  Skipping: Can only afford {shares_to_buy} shares (min: {config.MIN_SHARES_TO_BUY})")
                    
                    elif signal == 'SELL':
                        # Only sell if we have shares
                        if holdings[stock] > 0:
                            execute_sell(stock, holdings[stock], price)
                            trade_dict[stock] = 'SELL'
                        else:
                            trade_dict[stock] = 'WAIT'
                    
                    else:  # HOLD
                        if holdings[stock] > 0:
                            trade_dict[stock] = 'HOLD'
                            print(f"  Holding {holdings[stock]} shares (bought @ ${bought_prices[stock]:.2f})")
                        else:
                            trade_dict[stock] = 'WAIT'
                    
                    # Update price tracking
                    price_dict[stock] = price
                    
                    # Show strategy status if verbose
                    if config.VERBOSE_LOGGING:
                        status = strategy.get_status(stock)
                        print(f"  SMA: ${status['sma']:.2f}, Ratio: {status['price_sma_ratio']:.4f}")
                
                except Exception as e:
                    print(f"Error processing {stock}: {e}")
                    continue
            
            # Update dataframes and create graph
            timestamp = dt.datetime.now().strftime('%H:%M:%S')
            df_trades.loc[timestamp] = trade_dict
            df_prices.loc[timestamp] = price_dict
            
            create_graph(df_prices, df_trades)
            
            # Increment strategy runtime
            strategy.increment_runtime()
            
            # Wait before next check
            print(f"\nWaiting {config.CHECK_INTERVAL} seconds before next check...")
            time.sleep(config.CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n\nBot stopped by user.")
    
    except Exception as e:
        print(f"\n\nError in main loop: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Logout
        logout()
        print("\nBot session ended.")


if __name__ == "__main__":
    main()