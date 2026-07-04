# Main Telegram bot for Croma Stock Tracker

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    CHECK_INTERVAL_MINUTES,
    RATE_LIMIT_SECONDS,
    LOG_LEVEL,
    LOG_FILE,
)
import database as db
from croma_checker import check_stock_scrapedo

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL),
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def check_rate_limit(user_id: int) -> bool:
    """Check if user has exceeded rate limit. Returns True if allowed."""
    last_command = db.get_user_last_command(user_id)
    
    if last_command is None:
        return True
    
    time_since_last = datetime.now() - last_command
    return time_since_last.total_seconds() >= RATE_LIMIT_SECONDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name
    
    # Add/update user in database
    db.add_user(user_id, username)
    db.update_user_last_command(user_id)
    
    welcome_message = f"""
👋 Welcome {user.first_name}!

I'm the Croma Stock Tracker Bot. I'll notify you when your desired products come back in stock on Croma.

📦 *Commands:*
/track <SKU> <pincode> - Start tracking a product
/untrack <SKU> - Stop tracking a product
/list - Show all tracked products
/help - Get help

*Example:*
`/track 123456 400001`

Simply add products you want to track, and I'll alert you the moment they're available!
    """
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /track command."""
    user_id = update.effective_user.id
    
    # Rate limiting
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            f"⚠️ Please wait {RATE_LIMIT_SECONDS} seconds between commands."
        )
        return
    
    db.update_user_last_command(user_id)
    
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Invalid format!\n\nUsage: `/track <SKU> <pincode>`\n\nExample: `/track 123456 400001`",
            parse_mode='Markdown'
        )
        return
    
    sku = args[0].strip().upper()
    pincode = args[1].strip()
    
    # Validate SKU (alphanumeric)
    if not sku.isalnum():
        await update.message.reply_text("❌ SKU must be alphanumeric.")
        return
    
    # Validate pincode (6 digits for India)
    if not pincode.isdigit() or len(pincode) != 6:
        await update.message.reply_text("❌ Pincode must be 6 digits.")
        return
    
    # Add to tracking
    success, message = db.add_tracked_product(user_id, sku, pincode)
    
    if success:
        # Do an initial stock check
        await update.message.reply_text(f"⏳ Checking initial stock status for {sku}...")
        
        is_in_stock, product_name, error = await check_stock_scrapedo(sku, pincode)
        
        if product_name:
            db.update_product_stock(
                db.get_user_tracked_products(user_id)[-1]['id'],
                is_in_stock,
                product_name
            )
            
            if is_in_stock:
                await update.message.reply_text(
                    f"🎉 Good news! *{product_name}* (SKU: {sku}) is already IN STOCK for pincode {pincode}!",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"✅ Tracking started for *{product_name}*\nSKU: `{sku}` | Pincode: `{pincode}`\n\nYou'll be notified when it comes in stock!",
                    parse_mode='Markdown'
                )
        else:
            await update.message.reply_text(
                f"{message}\n\nNote: Could not fetch product details. Will continue monitoring.",
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(message)


async def untrack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /untrack command."""
    user_id = update.effective_user.id
    
    # Rate limiting
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            f"⚠️ Please wait {RATE_LIMIT_SECONDS} seconds between commands."
        )
        return
    
    db.update_user_last_command(user_id)
    
    args = context.args
    
    if len(args) < 1:
        await update.message.reply_text(
            "❌ Invalid format!\n\nUsage: `/untrack <SKU>`\n\nExample: `/untrack 123456`",
            parse_mode='Markdown'
        )
        return
    
    sku = args[0].strip().upper()
    success, message = db.remove_tracked_product(user_id, sku)
    
    await update.message.reply_text(message)


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list command."""
    user_id = update.effective_user.id
    
    # Rate limiting
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            f"⚠️ Please wait {RATE_LIMIT_SECONDS} seconds between commands."
        )
        return
    
    db.update_user_last_command(user_id)
    
    products = db.get_user_tracked_products(user_id)
    
    if not products:
        await update.message.reply_text(
            "📭 You're not tracking any products yet.\n\nUse `/track <SKU> <pincode>` to start tracking!"
        )
        return
    
    message = "📦 *Your Tracked Products:*\n\n"
    
    for i, product in enumerate(products, 1):
        status = "✅ IN STOCK" if product['is_in_stock'] else "⏳ Out of Stock"
        name = product['product_name'] or "Unknown Product"
        
        message += f"{i}. *{name}*\n"
        message += f"   SKU: `{product['sku']}` | Pincode: `{product['pincode']}`\n"
        message += f"   Status: {status}\n\n"
    
    message += f"Total: {len(products)} product(s)"
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    user_id = update.effective_user.id
    
    # Rate limiting
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            f"⚠️ Please wait {RATE_LIMIT_SECONDS} seconds between commands."
        )
        return
    
    db.update_user_last_command(user_id)
    
    help_message = """
🤖 *Croma Stock Tracker Bot - Help*

*Available Commands:*
/start - Welcome message and introduction
/track <SKU> <pincode> - Add a product to track
/untrack <SKU> - Stop tracking a product
/list - Show all your tracked products
/help - Display this help message

*How It Works:*
1. Find the SKU of a product on Croma website
2. Use /track command with SKU and your pincode
3. The bot checks stock every 5 minutes
4. You get instant notification when product is available!

*Finding SKU:*
- Go to croma.com
- Open any product page
- The SKU is usually in the URL or product details
- Example: For URL croma.com/product-xyz-123456, SKU might be 123456

*Tips:*
- You can track up to 10 products
- Track products at different pincodes for better chances
- Notifications are instant when stock changes

*Need Help?*
Make sure your API keys are properly configured in .env file.
    """
    
    await update.message.reply_text(help_message, parse_mode='Markdown')


async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unknown commands."""
    await update.message.reply_text(
        "❓ Unknown command. Use /help to see available commands."
    )


async def background_stock_checker(application: Application) -> None:
    """Background job to check stock for all tracked products."""
    logger.info("Starting background stock check...")
    
    products = db.get_all_tracked_products()
    
    if not products:
        logger.info("No products to check.")
        return
    
    logger.info(f"Checking stock for {len(products)} product(s)...")
    
    for product in products:
        try:
            is_in_stock, product_name, error = await check_stock_scrapedo(
                product['sku'], 
                product['pincode']
            )
            
            # Update database
            db.update_product_stock(product['id'], is_in_stock, product_name)
            
            # Check if stock status changed from out of stock to in stock
            if is_in_stock and not product['is_in_stock']:
                # Send notification to user
                user = db.get_user_by_id(product['user_id'])
                if user:
                    await send_stock_alert(
                        application.bot,
                        product['user_id'],
                        product['sku'],
                        product_name or "Product",
                        product['pincode']
                    )
            
            logger.info(
                f"Checked SKU {product['sku']} for pincode {product['pincode']}: "
                f"{'IN STOCK' if is_in_stock else 'Out of Stock'}"
            )
            
        except Exception as e:
            logger.error(f"Error checking product {product['sku']}: {str(e)}")
    
    logger.info("Background stock check completed.")


async def send_stock_alert(bot: Bot, user_id: int, sku: str, product_name: str, pincode: str) -> None:
    """Send stock availability alert to user."""
    alert_message = f"""
🎉 *STOCK ALERT!* 🎉

*{product_name}* is now IN STOCK!

📦 SKU: `{sku}`
📍 Pincode: `{pincode}`

Hurry! Popular items sell out quickly.
Order now on Croma! 🛒
    """
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=alert_message,
            parse_mode='Markdown'
        )
        logger.info(f"Sent stock alert to user {user_id} for SKU {sku}")
    except Exception as e:
        logger.error(f"Failed to send alert to user {user_id}: {str(e)}")


async def post_init(application: Application) -> None:
    """Initialize database after application starts."""
    db.init_db()
    logger.info("Database initialized.")


def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found. Please set it in .env file.")
        print("Error: TELEGRAM_BOT_TOKEN not found. Please set it in .env file.")
        return
    
    # Create application
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("track", track_command))
    application.add_handler(CommandHandler("untrack", untrack_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Handle unknown commands
    application.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))
    
    # Run background job
    async def run_background_job(context: ContextTypes.DEFAULT_TYPE) -> None:
        await background_stock_checker(context.application)
    
    job_queue = application.job_queue
    job_queue.run_repeating(
        run_background_job,
        interval=CHECK_INTERVAL_MINUTES * 60,
        first=10,  # Start after 10 seconds
        name="stock_checker"
    )
    
    logger.info(f"Bot started. Stock check interval: {CHECK_INTERVAL_MINUTES} minutes.")
    print(f"Bot is running! Press Ctrl+C to stop.")
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
