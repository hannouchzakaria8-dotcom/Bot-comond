import os
import asyncio
import asyncpg
import json
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ===== التكوين =====
TOKEN = "8680331502:AAFGdzSKemmYtMtsZplXbGEQcTqijxuOv8I"
DATABASE_URL = "postgresql://postgres:ZikoBoss200@db.zxkvqyaidsszmufykwmr.supabase.co:5432/postgres?sslmode=require"
# ⚠️ تأكد من استخدام Session Pooler (منفذ 5432) وليس Direct connection.
# ===================

app = Flask(__name__)
bot = Bot(TOKEN)
application = None
pool = None

# ---------- دوال قاعدة البيانات ----------
async def get_pool():
    return await asyncpg.create_pool(DATABASE_URL)

async def create_task(pool, task_type, user_id, chat_id, parameters):
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO tasks (type, user_id, chat_id, parameters, status) "
            "VALUES ($1, $2, $3, $4, 'pending') RETURNING id",
            task_type, user_id, chat_id, json.dumps(parameters)
        )

async def wait_for_result(pool, task_id, timeout=60):
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT status, result FROM tasks WHERE id = $1", task_id)
            if row['status'] in ('done', 'error'):
                return row['result']
        await asyncio.sleep(2)
    return "⏰ انتهى وقت الانتظار."

# ---------- معالجات الأوامر ----------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 بوت Free Fire القائد\nأرسل:\n/info UID\n/outfit UID\n/check UID")

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استخدم: /info UID")
        return
    uid = context.args[0]
    params = {"uid": uid}
    task_id = await create_task(pool, "info", update.effective_user.id, update.effective_chat.id, params)
    await update.message.reply_text(f"⏳ جاري جلب معلومات {uid}...")
    result = await wait_for_result(pool, task_id)
    await update.message.reply_text(result)

async def cmd_outfit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استخدم: /outfit UID (region اختياري)")
        return
    uid = context.args[0]
    region = context.args[1] if len(context.args) > 1 else "me"
    params = {"uid": uid, "region": region}
    task_id = await create_task(pool, "outfit", update.effective_user.id, update.effective_chat.id, params)
    await update.message.reply_text(f"⏳ جاري جلب الأوتفيت...")
    result = await wait_for_result(pool, task_id)
    await update.message.reply_text(result)

async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استخدم: /check UID")
        return
    uid = context.args[0]
    params = {"uid": uid}
    task_id = await create_task(pool, "check", update.effective_user.id, update.effective_chat.id, params)
    await update.message.reply_text(f"⏳ جاري فحص حظر {uid}...")
    result = await wait_for_result(pool, task_id)
    await update.message.reply_text(result)

# ---------- إعداد webhook ----------
async def setup_webhook():
    global application, pool
    pool = await get_pool()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("info", cmd_info))
    application.add_handler(CommandHandler("outfit", cmd_outfit))
    application.add_handler(CommandHandler("check", cmd_check))
    await application.initialize()
    await application.start()
    # احصل على اسم المضيف من متغير البيئة RENDER_EXTERNAL_URL (إذا كان موجودًا)
    base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://bot-comond-1.onrender.com")
    webhook_url = f"{base_url}/webhook"
    await application.bot.set_webhook(webhook_url)
    print(f"✅ Webhook set to {webhook_url}")

# ---------- نقطة دخول Flask ----------
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.create_task(application.process_update(update))
    return "OK"

@app.route('/')
def index():
    return "✅ Commander Bot is running"

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_webhook())
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
