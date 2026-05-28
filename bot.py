import os
import logging
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from company_info import COMPANY_KNOWLEDGE

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

dialog_histories = {}

SYSTEM_PROMPT = f"""Ты — официальный AI-ассистент компании "Центр Красок" (Казахстан, сайт centr-krasok.kz).
Отвечай вежливо, грамотно и СТРОГО на основе предоставленной информации о компании.

ИНФОРМАЦИЯ О КОМПАНИИ:
{COMPANY_KNOWLEDGE}

ПРАВИЛА ОТВЕТОВ:
1. Отвечай на том языке, на котором обратился клиент (русский или казахский).
2. Используй только факты из текста выше. Если информации нет в базе данных, НЕ придумывай её. Вежливо ответь, что не владеешь этой информацией, и предложи связаться по телефону: +7 778 061 5000.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    dialog_histories[chat_id] = []
    welcome_text = (
        "👋 Привет! Я — AI-ассистент магазина «Центр Красок #1».\n\n"
        "Спрашивайте меня о наших товарах, брендах, ценах, доставке или услугах — отвечу на любой вопрос!"
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in dialog_histories:
        dialog_histories[chat_id] = []

    dialog_histories[chat_id].append({"role": "user", "content": user_text})
    dialog_histories[chat_id] = dialog_histories[chat_id][-10:]

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    api_key = os.getenv("OPENROUTER_API_KEY")

    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + dialog_histories[chat_id]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://railway.app", 
                    "X-Title": "Centr Krasok Bot"
                },
                "model": "google/gemini-2.5-flash:free",
                }
            )
            
            if response.status_code == 200:
                ai_reply = response.json()['choices'][0]['message']['content'].strip()
                dialog_histories[chat_id].append({"role": "assistant", "content": ai_reply})
                await update.message.reply_text(ai_reply)
            else:
                logger.error(f"OpenRouter Error: {response.text}")
                raise Exception("API Error")

    except Exception as e:
        logger.error(f"Error: {e}")
        fallback_text = "Извините, произошла техническая ошибка. Пожалуйста, попробуйте позже или позвоните нам: +7 778 061 5000"
        await update.message.reply_text(fallback_text)

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()
