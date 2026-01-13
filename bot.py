#!/usr/bin/env python3
"""
Telegram Group Manager Bot
Version 2.0 - Now with file blocking

Features:
1. Welcome new members
2. Block links from non-VIP users
3. Block files (photos, documents, videos, stickers) from non-VIP users
4. VIP verification system (/vip command)
5. Auto-delete /vip command after 5 minutes

IMPORTANT: Replace YOUR_BOT_TOKEN_HERE with your actual bot token from @BotFather
"""

import os
import json
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.constants import ChatMemberStatus, ParseMode

# ==================== CONFIGURATION ====================
# ⚠️ SECURITY WARNING: Replace this with your own bot token!
BOT_TOKEN = "8293356561:AAFHZRKobH6sa-z_mCnu98p3WuGPXVHJPNs"  # REPLACE WITH YOUR ACTUAL TOKEN

# File to store VIP users (persists between bot restarts)
VIP_FILE = 'vip_users.json'

# Toggle file blocking (True = ON, False = OFF)
BLOCK_FILES = True

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== VIP USER MANAGEMENT ====================
class VIPManager:
    """Handles loading and saving VIP users"""
    
    def __init__(self, vip_file):
        self.vip_file = vip_file
        self.vip_users = self._load_vips()
    
    def _load_vips(self):
        """Load VIP users from JSON file"""
        try:
            if os.path.exists(self.vip_file):
                with open(self.vip_file, 'r') as f:
                    data = json.load(f)
                    return [str(user_id) for user_id in data]
        except Exception as e:
            logger.error(f"Error loading VIP users: {e}")
        return []
    
    def save_vips(self):
        """Save VIP users to JSON file"""
        try:
            with open(self.vip_file, 'w') as f:
                json.dump(self.vip_users, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving VIP users: {e}")
    
    def add_vip(self, user_id):
        """Add a user to VIP list"""
        user_str = str(user_id)
        if user_str not in self.vip_users:
            self.vip_users.append(user_str)
            self.save_vips()
            logger.info(f"Added VIP: {user_id}")
            return True
        return False
    
    def is_vip(self, user_id):
        """Check if user is VIP"""
        return str(user_id) in self.vip_users
    
    def list_vips(self):
        """Get list of all VIPs"""
        return self.vip_users.copy()

# Initialize VIP manager
vip_manager = VIPManager(VIP_FILE)

# ==================== BOT COMMAND HANDLERS ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_text = (
        "🤖 *Group Manager Bot*\n\n"
        "I help manage your Telegram group with these features:\n"
        "• ✅ Welcome new members\n"
        "• 🔗 Block links from non-VIP users\n"
        "• 📎 Block files from non-VIP users\n"
        "• 👑 VIP verification system\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/vip @username - Verify user as VIP (Admin only)\n"
        "/vips - List all VIP users\n"
        "/help - Show help information"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    file_blocking_status = "ENABLED" if BLOCK_FILES else "DISABLED"
    
    help_text = (
        "📖 *Bot Help Guide*\n\n"
        "*Admin Commands:*\n"
        "• `/vip @username` - Grant VIP status to a user\n"
        "• The /vip command auto-deletes after 5 minutes\n\n"
        "*VIP Privileges:*\n"
        "• VIP users can post links AND files\n"
        "• Regular members cannot post links or files\n\n"
        "*File Blocking:*\n"
        f"• File blocking is currently *{file_blocking_status}*\n"
        "• Blocks: photos, documents, videos, stickers\n\n"
        "*Bot Requirements:*\n"
        "1. Bot must be group administrator\n"
        "2. Group privacy must be DISABLED in @BotFather\n"
        "3. Bot needs 'Delete Messages' permission\n\n"
        "Use `/vips` to see current VIP users."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def vips_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /vips command - List all VIP users"""
    vip_list = vip_manager.list_vips()
    
    if not vip_list:
        await update.message.reply_text("📭 No VIP users yet.")
        return
    
    # Try to get usernames for better display
    vip_details = []
    for user_id in vip_list[:20]:  # Limit to first 20 for readability
        try:
            user = await context.bot.get_chat(int(user_id))
            display = f"• {user.mention_html()}"
        except:
            display = f"• User ID: {user_id}"
        vip_details.append(display)
    
    vip_text = "👑 *VIP Users:*\n\n" + "\n".join(vip_details)
    
    if len(vip_list) > 20:
        vip_text += f"\n\n... and {len(vip_list) - 20} more VIPs"
    
    await update.message.reply_html(vip_text)

async def verify_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /vip command - Verify a user as VIP (Admin only)"""
    user = update.effective_user
    chat = update.effective_chat
    message = update.message
    
    # Check if command sender is admin
    try:
        chat_member = await chat.get_member(user.id)
        is_admin = chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        
        if not is_admin:
            reply = await message.reply_text("❌ Only group administrators can use this command.")
            # Delete warning after 10 seconds
            await context.bot.delete_message(
                chat_id=chat.id,
                message_id=reply.message_id,
                message_thread_id=None
            )
            return
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return
    
    # Check if user was mentioned
    mentioned_user = None
    
    # Method 1: Check if replying to a message
    if message.reply_to_message:
        mentioned_user = message.reply_to_message.from_user
    
    # Method 2: Check for mentioned user in command
    elif message.entities:
        for entity in message.entities:
            if entity.type == "text_mention" and entity.user:
                mentioned_user = entity.user
                break
    
    if not mentioned_user:
        reply = await message.reply_text(
            "Usage: Reply to a user's message with `/vip` OR type `/vip @username`",
            parse_mode=ParseMode.MARKDOWN
        )
        # Delete usage reminder after 15 seconds
        await context.bot.delete_message(
            chat_id=chat.id,
            message_id=reply.message_id,
            message_thread_id=None
        )
        return
    
    # Add user to VIP list
    added = vip_manager.add_vip(mentioned_user.id)
    
    if added:
        confirmation_msg = await message.reply_html(
            f"✅ {mentioned_user.mention_html()} has been verified as a VIP member!\n\n"
            f"They can now post links and files in this group."
        )
        status = "added as new VIP"
    else:
        confirmation_msg = await message.reply_html(
            f"ℹ️ {mentioned_user.mention_html()} is already a VIP member."
        )
        status = "already VIP"
    
    logger.info(f"VIP command used by {user.username}: {mentioned_user.username} {status}")
    
    # Schedule deletion of both the command and confirmation after 5 minutes (300 seconds)
    messages_to_delete = [message.message_id, confirmation_msg.message_id]
    
    context.job_queue.run_once(
        delete_messages,
        300,  # 5 minutes = 300 seconds
        data={'chat_id': chat.id, 'message_ids': messages_to_delete},
        name=f"delete_vip_cmd_{message.message_id}"
    )

async def delete_messages(context: ContextTypes.DEFAULT_TYPE):
    """Delete scheduled messages"""
    job_data = context.job.data
    chat_id = job_data['chat_id']
    message_ids = job_data['message_ids']
    
    for msg_id in message_ids:
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=msg_id,
                message_thread_id=None
            )
        except Exception as e:
            # Message might already be deleted
            logger.debug(f"Could not delete message {msg_id}: {e}")

# ==================== MESSAGE HANDLERS ====================
async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new members to the group"""
    for new_member in update.message.new_chat_members:
        # Skip if the new member is the bot itself
        if new_member.id == context.bot.id:
            continue
            
        welcome_message = (
            f"🎉 Welcome to the group, {new_member.mention_html()}!\n\n"
            f"We're excited to have you here. Please:\n"
            f"• Read the group rules\n"
            f"• Introduce yourself\n"
            f"• Enjoy your stay!"
        )
        
        await update.message.reply_html(welcome_message)
        logger.info(f"Welcomed new member: {new_member.username} (ID: {new_member.id})")

async def block_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Block links AND files from non-VIP, non-admin users"""
    # Skip processing commands
    if update.message.text and update.message.text.startswith('/'):
        return
        
    user = update.effective_user
    chat = update.effective_chat
    message = update.message
    
    # Check if message contains links
    has_links = False
    if message.entities:
        for entity in message.entities:
            if entity.type in ["url", "text_link"]:
                has_links = True
                break
    
    # Check if message contains files (if file blocking is enabled)
    has_file = False
    file_type = None
    
    if BLOCK_FILES:
        if message.photo:
            has_file = True
            file_type = "photo"
        elif message.document:
            has_file = True
            file_type = "document"
        elif message.video:
            has_file = True
            file_type = "video"
        elif message.voice:
            has_file = True
            file_type = "voice"
        elif message.sticker:
            has_file = True
            file_type = "sticker"
    
    # If message has neither links nor files, do nothing
    if not (has_links or has_file):
        return
    
    try:
        # Check user status
        chat_member = await chat.get_member(user.id)
        is_admin = chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        is_vip = vip_manager.is_vip(user.id)
        
        # Allow content from admins and VIPs
        if is_admin or is_vip:
            content_type = "link" if has_links else file_type
            logger.debug(f"{content_type} allowed from {user.username} (Admin: {is_admin}, VIP: {is_vip})")
            return
        
        # Delete message from regular users
        await message.delete()
        
        # Determine what was deleted for logging and warning
        if has_links:
            content_description = "links"
        elif has_file:
            content_description = f"{file_type}s"
        else:
            content_description = "content"
        
        # Send warning (will be deleted shortly)
        warning_msg = await chat.send_message(
            f"⚠️ {user.mention_html()}, only VIP members and admins can post {content_description}.\n"
            f"Contact an admin for VIP status.",
            parse_mode=ParseMode.HTML
        )
        
        # Delete warning after 30 seconds
        await context.bot.delete_message(
            chat_id=chat.id,
            message_id=warning_msg.message_id,
            message_thread_id=None
        )
        
        log_content = "link" if has_links else file_type
        logger.info(f"Deleted {log_content} from user {user.username} (ID: {user.id})")
        
    except Exception as e:
        logger.error(f"Error blocking content: {e}")

# ==================== ERROR HANDLING ====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the bot"""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
    
    # Try to notify user about error
    try:
        if update and update.effective_chat:
            await update.effective_chat.send_message(
                "❌ An error occurred. Please try again later."
            )
    except:
        pass

# ==================== MAIN FUNCTION ====================
def main():
    """Start the bot"""
    
    # Security check for token
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("=" * 60)
        print("⚠️  SECURITY WARNING")
        print("=" * 60)
        print("You MUST replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token!")
        print("Get your token from @BotFather on Telegram.")
        print("=" * 60)
        return
    
    print("🤖 Starting Telegram Bot...")
    print(f"📂 VIP data will be saved to: {VIP_FILE}")
    print(f"📝 Logs will be saved to: bot.log")
    print(f"📎 File blocking is: {'ENABLED' if BLOCK_FILES else 'DISABLED'}")
    print("\n✅ Features Enabled:")
    print("   • Welcome new members")
    print("   • Block links from non-VIPs")
    if BLOCK_FILES:
        print("   • Block files (photos, docs, videos, stickers) from non-VIPs")
    print("   • VIP verification (/vip @username)")
    print("   • Auto-delete /vip command after 5 minutes")
    print("   • VIP list (/vips)")
    print("\n⚙️ Bot Requirements:")
    print("   1. Add bot as group administrator")
    print("   2. Disable 'Group Privacy' in @BotFather")
    print("   3. Grant 'Delete Messages' permission")
    print("\nPress Ctrl+C to stop the bot")
    print("=" * 60)
    
    # Create application
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("vip", verify_vip))
    application.add_handler(CommandHandler("vips", vips_command))
    
    # Add message handlers
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        welcome_new_members
    ))
    
    # FIXED LINE: Using filters.ATTACHMENT instead of individual document/sticker filters
    application.add_handler(MessageHandler(
        filters.TEXT | filters.ATTACHMENT | filters.VOICE,
        block_messages
    ))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

# ==================== START THE BOT ====================
if __name__ == '__main__':
    main()
