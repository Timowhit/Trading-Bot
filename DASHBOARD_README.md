# Trading Bot Dashboard

A web dashboard to monitor your trading bot from any device.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the dashboard

```bash
python dashboard.py
```

### 3. Open in browser

- **Local**: <http://localhost:5000>
- **From phone** (same WiFi): http://YOUR_COMPUTER_IP:5000

To find your computer's IP:

- **Mac**: `ipconfig getifaddr en0`
- **Windows**: `ipconfig` (look for IPv4)
- **Linux**: `hostname -I`

## Running Both Together

**Option A**: Two terminals

```bash
# Terminal 1 - Dashboard
python dashboard.py

# Terminal 2 - Trading bot
python trader_with_dashboard.py
```

**Option B**: Background the dashboard

```bash
python dashboard.py &
python trader_with_dashboard.py
```

## Cloud Deployment (Run 24/7)

### PythonAnywhere (easiest)

1. Create account at pythonanywhere.com
2. Upload files via Files tab
3. Create a Web App (Flask)
4. Set up a scheduled task for `trader_with_dashboard.py`

### Railway / Render

1. Push code to GitHub
2. Connect repo to Railway/Render
3. Set environment variables (ROBINHOOD_USERNAME, ROBINHOOD_PASSWORD)
4. Deploy

### DigitalOcean / AWS

```bash
# On server
git clone your-repo
cd trading-bot
pip install -r requirements.txt
cp .env.example .env
nano .env  # Add credentials

# Run with screen (persists after disconnect)
screen -S bot
python trader_with_dashboard.py
# Ctrl+A, D to detach

screen -S dashboard  
python dashboard.py
# Ctrl+A, D to detach
```

## Features

- 📊 Real-time portfolio value
- 💰 Cash balance
- 📈 Stock prices, SMA, and signals
- 📜 Trade history log
- 📱 Mobile-friendly design
- 🔄 Auto-refresh every 30 seconds

## Files

```python
dashboard.py           # Flask web server
templates/dashboard.html  # Web interface
trader_with_dashboard.py  # Bot with dashboard integration
```
