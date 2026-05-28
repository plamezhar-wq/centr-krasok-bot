import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from company_info import COMPANY_KNOWLEDGE

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Gemini API
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
else:
    logger.error("GEMINI_API_KEY не задан в переменных окружения!")

# Хранилище контекста диалогов {chat_id: [messages]}
dialog_histories = {}

SYSTEM_PROMPT = f"""
Ты — официальный AI-ассистент компании "Центр Красок" (Казахстан, сайт centr-krasok.kz).
Твоя задача — отвечать на вопросы клиентов вежливо, грамотно и СТРОГО на основе предоставленной информации о компании.

ИНФОРМАЦИЯ О КОМПАНИИ:
{COMPANY_KNOWLEDGE}

ПРАВИЛА ОТВЕТОВ:
1. Отвечай на том языке, на котором обратился клиент (русский или казахский).
2. Используй только факты из текста выше. Если информации о каком-то товаре, цене или услуге нет в базе данных, НЕ придумывай её. В таком случае вежливо ответь, что не владеешь этой информацией, и предложи связаться по телефону: +7 778 061 5000.
3. Твои ответы должны быть четкими, структурированными и дружелюбными.
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

    # Добавляем сообщение пользователя
    dialog_histories[chat_id].append({"role": "user", "parts": user_text})
    dialog_histories[chat_id] = dialog_histories[chat_id][-10:]

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT
        )
        
        # Создаем сессию чата с историей
        chat = model.start_chat(history=dialog_histories[chat_id][:-1])
        response = chat.send_message(user_text)
        ai_reply = response.text

        # Сохраняем ответ модели
        dialog_histories[chat_id].append({"role": "model", "parts": ai_reply})
        
        await update.message.reply_text(ai_reply)

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        fallback_text = "Извините, произошла техническая ошибка. Пожалуйста, попробуйте позже или позвоните нам: +7 778 061 5000"
        await update.message.reply_text(fallback_text)

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не задан!")
        return

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started!")
    application.run_polling()

if __name__ == '__main__':
    main()
