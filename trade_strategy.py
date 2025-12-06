"""
Simple Moving Average (SMA) Trading Strategy

This strategy buys when price drops below the SMA and sells when it rises above.
The buffer prevents excessive trading on minor fluctuations.
"""
import pandas as pd
import robin_stocks.robinhood as rh
import config


class TradingStrategy:
    """
    Implements a Simple Moving Average (SMA) trading strategy.
    
    The strategy:
    1. Calculates the SMA over a rolling window
    2. Compares current price to SMA
    3. Generates BUY when price < SMA - buffer
    4. Generates SELL when price > SMA + buffer
    5. Otherwise, HOLD
    """
    
    def __init__(self, stocks):
        """
        Initialize the trading strategy.
        
        Args:
            stocks (list): List of stock ticker symbols to trade
        """
        self.stocks = stocks
        self.run_time = 0  # Track how long the bot has been running (in minutes)
        
        # Store current SMA values for each stock
        self.sma_values = {stock: 0 for stock in stocks}
        
        # Store current price/SMA ratios
        self.price_sma_ratios = {stock: 0 for stock in stocks}
    
    def get_historical_prices(self, stock, span='day'):
        """
        Fetch historical price data for a stock.
        
        Args:
            stock (str): Stock ticker symbol
            span (str): Time span ('day', 'week', 'month', '3month', 'year', '5year')
        
        Returns:
            DataFrame: Historical prices with timestamps
        """
        # Map span to appropriate interval
        span_interval = {
            'day': '5minute',
            'week': '10minute',
            'month': 'hour',
            '3month': 'hour',
            'year': 'day',
            '5year': 'week'
        }
        interval = span_interval[span]
        
        # Fetch historical data from Robinhood
        historical_data = rh.stocks.get_stock_historicals(
            stock,
            interval=interval,
            span=span,
            bounds='extended'
        )
        
        if not historical_data:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(historical_data)
        
        # Extract and format the data we need
        dates_times = pd.to_datetime(df.loc[:, 'begins_at'])
        close_prices = df.loc[:, 'close_price'].astype('float')
        
        # Combine into a single DataFrame
        df_price = pd.concat([close_prices, dates_times], axis=1)
        df_price = df_price.rename(columns={'close_price': stock})
        df_price = df_price.set_index('begins_at')
        
        return df_price
    
    def calculate_sma(self, stock, df_prices, window=None):
        """
        Calculate Simple Moving Average.
        
        Args:
            stock (str): Stock ticker symbol
            df_prices (DataFrame): Historical prices
            window (int): Number of periods to average (default from config)
        
        Returns:
            float: The SMA value
        """
        if window is None:
            window = config.SMA_WINDOW
        
        # Calculate rolling mean
        sma = df_prices.rolling(window=window, min_periods=window).mean()
        
        # Return the most recent SMA value
        return round(float(sma[stock].iloc[-1]), 4)
    
    def calculate_price_sma_ratio(self, price, sma):
        """
        Calculate the ratio of current price to SMA.
        
        A ratio < 1.0 means price is below SMA (potential buy)
        A ratio > 1.0 means price is above SMA (potential sell)
        
        Args:
            price (float): Current stock price
            sma (float): Simple Moving Average
        
        Returns:
            float: Price/SMA ratio
        """
        if sma == 0:
            return 1.0
        return round(price / sma, 4)
    
    def get_trade_signal(self, stock, price):
        """
        Generate a trading signal (BUY, SELL, or HOLD) for a stock.
        
        Args:
            stock (str): Stock ticker symbol
            price (float): Current stock price
        
        Returns:
            str: Trade signal ('BUY', 'SELL', or 'HOLD')
        """
        # Update SMA every N minutes (configurable)
        if self.run_time % config.SMA_UPDATE_INTERVAL == 0:
            df_historical = self.get_historical_prices(stock, span='day')
            
            if len(df_historical) < config.SMA_WINDOW:
                # Not enough data yet
                return 'HOLD'
            
            # Calculate new SMA using the most recent data
            self.sma_values[stock] = self.calculate_sma(
                stock,
                df_historical[-config.SMA_WINDOW:]
            )
        
        # Calculate price to SMA ratio
        self.price_sma_ratios[stock] = self.calculate_price_sma_ratio(
            price,
            self.sma_values[stock]
        )
        
        ratio = self.price_sma_ratios[stock]
        
        # Generate trading signal based on ratio and buffer
        # BUY when price is significantly below SMA
        if ratio < (1.0 - config.TRADING_BUFFER):
            return 'BUY'
        
        # SELL when price is significantly above SMA
        elif ratio > (1.0 + config.TRADING_BUFFER):
            return 'SELL'
        
        # Otherwise HOLD (price is near SMA)
        else:
            return 'HOLD'
    
    def increment_runtime(self):
        """Increment the runtime counter (call this every minute)."""
        self.run_time += 1
    
    def get_status(self, stock):
        """
        Get current strategy status for a stock.
        
        Args:
            stock (str): Stock ticker symbol
        
        Returns:
            dict: Status information (SMA, ratio, etc.)
        """
        return {
            'sma': self.sma_values.get(stock, 0),
            'price_sma_ratio': self.price_sma_ratios.get(stock, 0),
            'runtime_minutes': self.run_time
        }