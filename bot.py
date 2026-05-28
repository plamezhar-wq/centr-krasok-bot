import os
import logging
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from company_info import COMPANY_KNOWLEDGE

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилище контекста диалогов (Память бота для UX)
dialog_histories = {}

SYSTEM_PROMPT = f"""Ты — официальный AI-ассистент компании "Центр Красок" (Казахстан, сайт centr-krasok.kz).
Отвечай вежливо, грамотно и СТРОГО на основе предоставленной информации о компании.

ИНФОРМАЦИЯ О КОМПАНИИ:
{COMPANY_KNOWLEDGE}

ПРАВИЛА ОТВЕТОВ (ЗАЩИТА ОТ ГАЛЛЮЦИНАЦИЙ):
1. Отвечай на том языке, на котором обратился клиент (русский или казахский).
2. Используй ТОЛЬКО факты из предоставленного текста. Если информации о вакансиях, ценах или конкретном товаре нет в тексте, НЕ придумывай её от себя! Вежливо ответь, что не владеешь этой информацией, и предложи связаться с отделом продаж по телефону: +7 778 061 5000.
3. Ответы должны быть четкими, короткими и дружелюбными.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    dialog_histories[chat_id] = [] # Очистка контекста при перезапуске
    
    welcome_text = (
        "👋 Привет! Я — официальный AI-ассистент магазина «Центр Красок #1».\n\n"
        "Спрашивайте меня о наших товарах, брендах, ценах, доставке или услугах — отвечу на любой вопрос!"
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in dialog_histories:
        dialog_histories[chat_id] = []

    # Сохраняем историю для поддержки контекста диалога
    dialog_histories[chat_id].append({"role": "user", "parts": [{"text": user_text}]})
    dialog_histories[chat_id] = dialog_histories[chat_id][-8:] # Храним последние 4 реплики туда-обратно

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        await update.message.reply_text("Ошибка конфигурации: Не задан GEMINI_API_KEY в Railway.")
        return

    # Формируем запрос для Google Gemini API согласно официальной документации
    contents = dialog_histories[chat_id].copy()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": contents,
                    "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                    "generationConfig": {
                        "temperature": 0.2, # Низкая температура снижает галлюцинации
                        "maxOutputTokens": 800
                    }
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_reply = result['candidates'][0]['content']['parts'][0]['text'].strip()
                
                # Записываем ответ ИИ в историю
                dialog_histories[chat_id].append({"role": "model", "parts": [{"text": ai_reply}]})
                await update.message.reply_text(ai_reply, parse_mode="Markdown")
            else:
                logger.error(f"Gemini API Error: {response.text}")
                await update.message.reply_text("Извините, произошла техническая ошибка. Пожалуйста, попробуйте позже или позвоните нам: +7 778 061 5000")
                
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("Извините, сервис временно недоступен. Наш телефон: +7 778 061 5000")

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не задан!")
        return

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот на базе реального ИИ успешно запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
