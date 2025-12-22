# 🤖 Robinhood Trading Bot Dashboard

A Python-based trading bot with a real-time web dashboard for monitoring and managing your Robinhood portfolio.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Flask](https://img.shields.io/badge/Flask-2.0%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Features

- **Real-time Dashboard** - Monitor your portfolio, holdings, and options positions
- **Smart Strategy Selection** - Automatically detects market conditions and recommends optimal strategies
- **6 Market Presets** - Pre-configured strategies for bullish, bearish, volatile, stagnant, recovery, and correction markets
- **SMA Trading Strategy** - Simple Moving Average based buy/sell signals
- **Options Support** - View all your options positions with P/L tracking
- **Web-based Controls** - Start/stop the bot from your browser
- **Configurable Settings** - Customize stocks, trading parameters, and timing
- **Auto-setup** - Guided credential setup if `.env` file is missing
- **Trade Logging** - Track all trading activity in real-time

## 🚀 Quickstart

### Prerequisites

- Python 3.8 or higher
- A Robinhood account
- pip (Python package manager)

### Step 1: Clone or Download

```bash
# Clone the repository (or download the files)
git clone <your-repo-url>
cd robinhood-trading-bot
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

Or install packages individually:

```bash
pip install flask robin-stocks python-dotenv pandas
```

### Step 3: Run the Dashboard

```bash
python Trading_Bot_Dashboard.py
```

**That's it!** The dashboard will open automatically in your browser.

### Step 4: Enter Credentials (First Run Only)

On first run, you'll see a setup page. Enter your Robinhood credentials:

1. Enter your Robinhood email/username
2. Enter your Robinhood password
3. Click "Save & Continue to Dashboard"

Your credentials are stored locally in a `.env` file and never sent anywhere.

> **Note:** You may need to complete 2FA verification on first login.

### Step 5: Select Your Strategy

After credentials are set, you'll see the **Strategy Selection** screen:

1. The bot analyzes current market conditions (SPY performance, volatility)
2. It recommends an optimal strategy based on market state
3. Choose the recommended strategy, your saved settings, or any preset
4. If no selection is made within **30 seconds**, the recommended strategy is auto-applied

## 📊 Market Condition Presets

The bot includes 6 pre-configured strategies optimized for different market conditions:

| Preset | Condition | ETFs | Strategy |
| ------ | --------- | ---- | -------- |
| 🚀 **Bullish Growth** | Rising markets | QQQ, VGT, SMH, XLK, SOXX | Aggressive growth, larger positions |
| 🛡️ **Bearish Defense** | Declining markets | SH, GLD, TLT, XLU, VPU | Defensive/inverse ETFs, smaller positions |
| ⚡ **High Volatility** | Turbulent markets | SPLV, USMV, VYM, SCHD, XLP | Low-vol ETFs, tight position sizing |
| 📊 **Sideways Income** | Flat markets | VYM, SCHD, HDV, DVY, JEPI | Dividend focus, income generation |
| 📈 **Market Recovery** | Recovering markets | VTI, SPY, IWM, XLF, VB | Broad market + small caps |
| 🎯 **Correction Mode** | Pullback markets | VOO, QQQ, VTI, SCHG, VUG | Quality ETFs for dip-buying |

### How Market Detection Works

The bot analyzes:

- **SPY daily change** - Today's market movement
- **SPY weekly change** - 5-day trend direction
- **Volatility level** - Based on VIXY behavior
- **Confidence score** - How certain the detection is

## 📁 Project Structure

```python
robinhood-trading-bot/
├── Trading_Bot_Dashboard.py   # Main application (all-in-one)
├── requirements.txt           # Python dependencies
├── .env                       # Credentials (auto-created)
├── bot_settings.json          # User settings (auto-created)
└── README.md                  # This file
```

## 🖥️ Using the Dashboard

### Dashboard URL

```txt
http://127.0.0.1:5000
```

### Available Pages

| Page | URL | Description |
| ---- | --- | ----------- |
| Dashboard | `/` | Main portfolio view with controls |
| Strategy Select | `/select-strategy` | Choose trading strategy |
| Settings | `/settings` | Configure stocks and parameters |
| Setup | `/setup` | Credential configuration |

### Dashboard Controls

- **▶ Start** - Start the trading bot
- **■ Stop** - Stop the trading bot
- **↻ Refresh** - Manually refresh portfolio data
- **⚙ Settings** - Configure trading parameters

## ⚙️ Configuration

### Via Strategy Selection (Recommended)

On startup, select from market-optimized presets or your saved strategy.

### Via Web Interface

1. Click **Settings** in the dashboard
2. Modify any settings
3. Click **Save Settings**

### Via Settings File

Edit `bot_settings.json` directly:

```json
{
  "stocks": ["QQQ", "SPY", "NVDA", "AAPL", "MSFT"],
  "trading_buffer": 0.02,
  "sma_window": 12,
  "max_cash_per_stock": 0.25,
  "min_shares_to_buy": 1,
  "check_interval": 30,
  "preset_applied": "bullish"
}
```

### Configuration Options

| Setting | Default | Description |
| ------- | ------- | ----------- |
| `stocks` | Varies by preset | Stock/ETF symbols to monitor |
| `trading_buffer` | 0.015 - 0.035 | Price deviation from SMA to trigger trades |
| `sma_window` | 8 - 15 | Number of data points for SMA calculation |
| `max_cash_per_stock` | 0.12 - 0.30 | Max portfolio % per single trade |
| `min_shares_to_buy` | 1 | Minimum shares to execute a buy |
| `check_interval` | 20 - 60 | Seconds between price checks |

## 📈 Trading Strategy

The bot uses a **Simple Moving Average (SMA)** strategy:

1. **Tracks** price history for each configured stock
2. **Calculates** the SMA over the configured window
3. **Generates signals** based on price deviation:
   - **BUY** when price drops below SMA by more than the buffer
   - **SELL** when price rises above SMA by more than the buffer
   - **HOLD** when price is near the SMA

### Signal Example

With `trading_buffer = 0.02` (2%):

- If SMA = $100 and price drops to $97 → **BUY** signal
- If SMA = $100 and price rises to $103 → **SELL** signal
- If SMA = $100 and price is $99-$101 → **HOLD** signal

## ⚠️ Important Notes

### Paper Trading Mode (Default)

**The bot runs in paper trading mode by default.** Trades are logged but not executed.

To enable live trading, uncomment the trade execution code in `Trading_Bot_Dashboard.py`:

```python
# Find these sections and uncomment:
# rh.orders.order_buy_limit(...)
# rh.orders.order_sell_limit(...)
```

### Market Hours

The bot only operates during market hours (9:30 AM - 4:00 PM ET). Outside these hours, it waits automatically.

### Security

- Credentials are stored locally in `.env`
- Never commit `.env` to version control
- The `.gitignore` file excludes sensitive files

## 🛠️ Troubleshooting

### "Missing credentials" error

1. Delete the `.env` file
2. Restart the application
3. Re-enter your credentials on the setup page

### 2FA Issues

If you use 2FA on Robinhood:

1. The first login may prompt for a code in the terminal
2. Enter the code from your authenticator app
3. Session is cached for future logins

### Port Already in Use

If port 5000 is busy, modify the last line in `Trading_Bot_Dashboard.py`:

```python
app.run(host='0.0.0.0', port=5001, debug=False)  # Change 5000 to 5001
```

### Dashboard Won't Load

1. Check if the terminal shows any errors
2. Ensure all dependencies are installed: `pip install -r requirements.txt`
3. Try accessing `http://127.0.0.1:5000` directly in your browser

### Skip Strategy Selection

To go directly to dashboard without strategy selection:

```txt
http://127.0.0.1:5000/?skip_strategy=1
```

## 🔧 Windows Quick Launch

Double-click `run_dashboard.bat` to start the bot, or create one:

```batch
@echo off
cd /d "%~dp0"
python Trading_Bot_Dashboard.py
```

## 📋 API Endpoints

| Endpoint | Method | Description |
| -------- | ------ | ----------- |
| `/api/status` | GET | Current bot state and portfolio data |
| `/api/settings` | GET/POST | Read or update settings |
| `/api/market-condition` | GET | Detect current market condition |
| `/api/apply-strategy` | POST | Apply a strategy preset |
| `/api/presets` | GET | Get all available presets |
| `/api/bot/start` | POST | Start the trading bot |
| `/api/bot/stop` | POST | Stop the trading bot |
| `/api/refresh` | GET | Refresh data from Robinhood |
| `/api/setup/credentials` | POST | Save Robinhood credentials |
| `/api/shutdown` | POST | Shutdown the server |

## ⚖️ Disclaimer

**This software is for educational purposes only.**

- Trading stocks involves risk of loss
- Past performance does not guarantee future results
- The authors are not responsible for any financial losses
- Always do your own research before trading
- Test thoroughly with paper trading before using real money

## 📄 License

MIT License - Feel free to modify and distribute.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.
