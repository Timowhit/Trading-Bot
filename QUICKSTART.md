# Quick Start Guide

Get your trading bot running in 5 minutes!

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Set Up Credentials

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Robinhood credentials:

   ```
   ROBINHOOD_USERNAME=your_email@example.com
   ROBINHOOD_PASSWORD=your_password
   ```

## Step 3: Configure Your Stocks

Edit `config.py` and customize the `STOCKS` list:

```python
STOCKS = [
    "SPY",   # S&P 500 ETF
    "QQQ",   # Nasdaq-100 ETF
    "AAPL",  # Apple
]
```

## Step 4: Run in Dry-Run Mode (Safe!)

```bash
python trader.py
```

The bot will:

- ✓ Show you what it would buy/sell
- ✓ Create graphs of trading activity
- ✗ NOT execute real trades (safe for testing)

## Step 5: Enable Live Trading (Optional)

⚠️ **CAUTION**: Only do this when you're ready!

1. Open `trader.py`
2. Find the `execute_buy()` and `execute_sell()` functions
3. Uncomment the order placement code
4. Save and run again

## Understanding the Output

When running, you'll see:

```
--- Iteration 1 at 10:30:45 ---
Holdings: {'SPY': 0, 'QQQ': 5, 'AAPL': 0}

SPY: $450.25
  Signal: BUY
  SMA: $455.30, Ratio: 0.9889
🟢 BUY SIGNAL: SPY - 10 shares @ $450.35

QQQ: $385.60
  Signal: HOLD
  Holding 5 shares (bought @ $380.20)
  SMA: $384.15, Ratio: 1.0038
```

### What This Means

- **Signal**: What the strategy recommends (BUY/SELL/HOLD)
- **SMA**: The moving average price
- **Ratio**: Current price ÷ SMA
  - < 1.0 = Price below average (potential buy)
  - > 1.0 = Price above average (potential sell)

## Monitoring

- Graph saved as `YYYY-MM-DD.png`
- Green lines = Buy signals
- Red lines = Sell signals
- Solid lines = Actively trading
- Faded lines = Not trading

## Stopping the Bot

Press `Ctrl+C` to stop the bot safely.

## Troubleshooting

### "Missing credentials!"

→ Create a `.env` file with your Robinhood login

### "Market is closed"

→ Normal! Bot only runs 9:30 AM - 4:00 PM ET on weekdays

### "Could not create graph"

→ Graph module issue, but trading still works

## Tips for Success

1. **Start small**: Test with stocks you understand
2. **Monitor closely**: Check the bot regularly during market hours
3. **Adjust buffer**: If too many trades, increase `TRADING_BUFFER` in config
4. **Paper trade first**: Run in dry-run mode for several days before going live

## Need Help?

- Review the full README.md for detailed explanations
- Check your bot's output for error messages
- Ensure your Robinhood account is in good standing

---

**Remember**: This is a simple bot for educational purposes. Always monitor your automated trading!
