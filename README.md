# Robinhood Trading Bot

A simple automated trading bot for Robinhood that uses moving average strategies.

## ⚠️ IMPORTANT DISCLAIMER

**THE STOCK MARKET IS INHERENTLY RISKY. USE AT YOUR OWN RISK.**

This bot is for educational purposes. What works for one person may not work for another. Always:
- Start with paper trading or very small amounts
- Understand the strategy before using it
- Monitor your bot regularly
- Be prepared for losses

## Features

- Simple Moving Average (SMA) based trading strategy
- Automated buy/sell decisions during market hours
- Real-time price tracking and visualization
- Configurable trading parameters

## Setup

### 1. Install Dependencies

```bash
pip install robin-stocks pandas matplotlib
```

### 2. Configure Your Credentials

Create a `.env` file in the project directory:

```bash
ROBINHOOD_USERNAME=your_email@example.com
ROBINHOOD_PASSWORD=your_password
```

**Security Note:** Never commit your `.env` file to version control. It's already in `.gitignore`.

### 3. Configure Trading Settings

Edit `config.py` to customize:
- Stock symbols to trade
- Trading buffer (default 0.2%)
- Maximum investment per stock

## Usage

### Running the Bot

```bash
python trader.py
```

The bot will:
1. Log into your Robinhood account
2. Monitor the stocks you configured
3. Make buy/sell decisions based on the SMA strategy
4. Display live graphs of prices and trading actions
5. Run during market hours (9:30 AM - 4:00 PM EST)

### Understanding the Strategy

The bot uses a Simple Moving Average (SMA) strategy:

1. **Calculate SMA**: Averages the last 12 price points (1 hour of 5-minute intervals)
2. **Compare Price to SMA**:
   - If price is **below** SMA by more than 0.2% → **BUY** signal
   - if price is **above** SMA by more than 0.2% → **SELL** signal
   - Otherwise → **HOLD**

3. **Buffer**: The 0.2% buffer prevents excessive trading on minor price fluctuations

### Modifying the Strategy

To change the trading strategy, edit `trade_strategy.py`:

```python
# Change the buffer (currently 0.2%)
self.buffer = 0.002  # 0.002 = 0.2%

# Change the SMA window (currently 12 periods = 1 hour)
def get_sma(self, stock, df_prices, window=12):
```

**Common adjustments:**
- **More aggressive**: Lower buffer (e.g., 0.001 = 0.1%)
- **Less aggressive**: Higher buffer (e.g., 0.005 = 0.5%)
- **Longer trend**: Increase window (e.g., 24 = 2 hours)
- **Shorter trend**: Decrease window (e.g., 6 = 30 minutes)

## File Structure

```
├── trader.py           # Main trading bot (runs the strategy)
├── trade_strategy.py   # Trading strategy logic (SMA calculations)
├── config.py          # Configuration (stocks to trade, settings)
├── .env               # Credentials (YOU create this - not in repo)
├── .gitignore         # Prevents committing sensitive files
└── README.md          # This file
```

## Safety Features

- **Commented Out Trading**: By default, actual buy/sell orders are commented out
- **Dry Run Mode**: Uncomment the order lines in `trader.py` only when ready
- **Market Hours Only**: Bot only trades during regular market hours
- **Position Limits**: Won't buy if you already hold shares
- **Cash Management**: Divides cash across multiple stocks (max 10% per stock)

## Enabling Live Trading

⚠️ **CAUTION**: This will execute real trades with real money!

In `trader.py`, uncomment these lines:

```python
def sell(stock, holdings, price):
    sell_price = round((price - 0.10), 2)
    # UNCOMMENT THE NEXT 4 LINES TO ENABLE LIVE SELLING:
    # sell_order = rh.orders.order_sell_limit(
    #     symbol=stock,
    #     quantity=holdings,
    #     limitPrice=sell_price,
    #     timeInForce='gfd'
    # )

def buy(stock, allowable_holdings, price):
    buy_price = round((price + 0.10), 2)
    # UNCOMMENT THE NEXT 4 LINES TO ENABLE LIVE BUYING:
    # buy_order = rh.orders.order_buy_limit(
    #     symbol=stock,
    #     quantity=allowable_holdings,
    #     limitPrice=buy_price,
    #     timeInForce='gfd'
    # )
```

## Monitoring

The bot creates a graph saved as `YYYY-MM-DD.png` showing:
- **Solid lines**: Stocks you're holding or considering buying
- **Faded lines**: Stocks you've sold or aren't trading
- **Green vertical lines**: Buy signals
- **Red vertical lines**: Sell signals

## Troubleshooting

### "The Market is closed"
- Bot only runs 9:30 AM - 4:00 PM EST on weekdays
- This is normal outside trading hours

### Login Issues
- Check your `.env` file credentials
- You may need 2FA (the bot will prompt you)
- Ensure your Robinhood account is in good standing

### "404 Error" or API Issues
- Robinhood's API can be unstable
- Try again in a few minutes
- Check Robinhood's service status

## License

This project is provided as-is for educational purposes. Use at your own risk.

## Contributing

This is a simple educational bot. Feel free to fork and modify for your own use.

---

**Remember**: Never invest more than you can afford to lose. Automated trading carries significant risks.