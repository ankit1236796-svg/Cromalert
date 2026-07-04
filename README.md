# Croma Stock Tracker Telegram Bot

A dedicated Telegram bot that tracks Croma product availability by SKU and pincode, sending instant alerts when products come back in stock.

## Features

- 🛍️ **Track Multiple Products**: Monitor up to 10 products per user
- 📍 **Pincode-Specific**: Check availability for your specific location
- ⚡ **Instant Alerts**: Get notified immediately when stock is available
- 🔒 **Stealth Mode**: Uses Scrape.do Premium API with stealth mode to bypass Akamai protection
- 👥 **Multi-User Support**: Each user can track their own products
- ⏰ **Automatic Checking**: Background job checks stock every 5 minutes
- 🚫 **Rate Limiting**: Prevents abuse with per-user rate limiting
- 💾 **SQLite Storage**: Persistent storage for user data and tracking lists

## Tech Stack

- **Python 3.9+**
- **python-telegram-bot v20+** (async)
- **httpx** (async HTTP client)
- **python-dotenv** (environment variables)
- **SQLite** (database)
- **Scrape.do API** (web scraping with stealth mode)

## Prerequisites

1. **Telegram Bot Token**: Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. **Scrape.do API Key**: Sign up at [scrape.do](https://scrape.do) and get your API key
3. **VPS/Server**: A Linux server to run the bot 24/7

## Installation

### 1. Clone or Download the Project

```bash
cd /path/to/your/project
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
TELEGRAM_BOT_TOKEN=your_actual_telegram_bot_token
SCRAPE_DO_API_KEY=your_actual_scrapedo_api_key
```

### 5. Run the Bot

```bash
python bot.py
```

## Bot Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Welcome message and introduction | `/start` |
| `/track` | Add a product to track | `/track 123456 400001` |
| `/untrack` | Stop tracking a product | `/untrack 123456` |
| `/list` | Show all tracked products | `/list` |
| `/help` | Display help message | `/help` |

## Usage Examples

### Start Tracking a Product

```
/track 123456 400001
```

This will:
1. Validate the SKU and pincode
2. Perform an initial stock check
3. Add the product to your tracking list
4. Notify you if it's already in stock

### Stop Tracking

```
/untrack 123456
```

### View Tracked Products

```
/list
```

Output example:
```
📦 Your Tracked Products:

1. Apple iPhone 15 Pro (256GB)
   SKU: `123456` | Pincode: `400001`
   Status: ⏳ Out of Stock

2. Sony WH-1000XM5 Headphones
   SKU: `789012` | Pincode: `400001`
   Status: ✅ IN STOCK

Total: 2 product(s)
```

## Deployment on VPS

### Using systemd (Recommended)

1. Create a systemd service file:

```bash
sudo nano /etc/systemd/system/croma-bot.service
```

2. Add the following content:

```ini
[Unit]
Description=Croma Stock Tracker Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/your/project
Environment="PATH=/path/to/your/project/venv/bin"
ExecStart=/path/to/your/project/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable croma-bot
sudo systemctl start croma-bot
sudo systemctl status croma-bot
```

### Using Docker (Alternative)

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

Build and run:

```bash
docker build -t croma-stock-bot .
docker run -d --name croma-bot \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e SCRAPE_DO_API_KEY=your_api_key \
  croma-stock-bot
```

## Configuration Options

Edit `config.py` to customize:

```python
CHECK_INTERVAL_MINUTES = 5      # How often to check stock
MAX_TRACKED_PRODUCTS_PER_USER = 10  # Max products per user
RATE_LIMIT_SECONDS = 60         # Minimum time between commands
LOG_LEVEL = "INFO"              # Logging level
```

## Database Schema

The bot uses SQLite with three tables:

1. **users**: User information and rate limiting
2. **tracked_products**: Products being tracked by users
3. **stock_history**: Historical stock status changes

## Finding Product SKUs

To find a product's SKU on Croma:

1. Go to [croma.com](https://www.croma.com)
2. Search for or navigate to the product
3. The SKU is usually found in:
   - The product URL (e.g., `croma.com/product-name-123456`)
   - Product details section
   - Page source code

## Troubleshooting

### Bot doesn't respond
- Check if the bot is running: `systemctl status croma-bot`
- Verify Telegram bot token is correct
- Check logs: `journalctl -u croma-bot -f`

### No stock alerts received
- Ensure `/list` shows the product is being tracked
- Check Scrape.do API key is valid
- Review logs for API errors

### Scrape.do API errors
- Verify API key in `.env` file
- Check your Scrape.do account credits/balance
- Ensure stealth mode is enabled in the request

## Rate Limits & Best Practices

- **User Rate Limit**: 60 seconds between commands
- **Max Products**: 10 products per user
- **Check Interval**: Every 5 minutes
- **API Considerations**: Scrape.do has usage limits based on your plan

## Security Notes

- Never commit `.env` file to version control
- Keep your API keys secret
- The bot validates all user inputs
- Rate limiting prevents abuse

## License

MIT License - Feel free to modify and use as needed.

## Support

For issues or questions:
1. Check the logs first (`bot.log` file)
2. Verify your API keys are correct
3. Ensure all dependencies are installed
4. Check Scrape.do account status

---

**Note**: This bot is for personal use. Respect Croma's terms of service and don't abuse the scraping functionality.
