import os
import logging
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from company_info import COMPANY_KNOWLEDGE

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилище контекста диалогов (Память бота)
dialog_histories = {}

SYSTEM_PROMPT = f"""Ты — официальный AI-ассистент компании "Центр Красок" (Казахстан, сайт centr-krasok.kz).
Отвечай вежливо, грамотно и СТРОГО на основе предоставленной информации о компании.

ИНФОРМАЦИЯ О КОМПАНИИ:
{COMPANY_KNOWLEDGE}

ПРАВИЛА ОТВЕТОВ (ЗАЩИТА ОТ ГАЛЛЮЦИНАЦИЙ):
1. Отвечай на том языке, на котором обратился клиент (русский или казахский).
2. Используй ТОЛЬКО факты из предоставленного текста. Если информации о ценах, вакансиях или конкретных услугах нет в базе, НЕ придумывай её от себя! Вежливо ответь, что не владеешь этой информацией, и предложи связаться с отделом продаж по телефону: +7 778 061 5000.
3. Ответы должны быть четкими, емкими и дружелюбными.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    dialog_histories[chat_id] = [] # Очистка истории при старте
    
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

    # Добавляем сообщение пользователя в историю
    dialog_histories[chat_id].append({"role": "user", "content": user_text})
    # Храним последние 6 реплик для удержания контекста диалога
    dialog_histories[chat_id] = dialog_histories[chat_id][-6:]

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        await update.message.reply_text("Ошибка конфигурации: Проверьте OPENROUTER_API_KEY в Railway.")
        return

    try:
        # Собираем системный промпт и историю диалога
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + dialog_histories[chat_id]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://railway.app", 
                    "X-Title": "Centr Krasok Bot"
                },
                json={
                    "model": "google/gemini-2.5-flash:free",
                    "messages": messages,
                    "temperature": 0.1 # Минимальная температура для исключения галлюцинаций
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_reply = result['choices'][0]['message']['content'].strip()
                
                # Запоминаем ответ бота
                dialog_histories[chat_id].append({"role": "assistant", "content": ai_reply})
                await update.message.reply_text(ai_reply, parse_mode="Markdown")
            else:
                logger.error(f"OpenRouter Error Status {response.status_code}: {response.text}")
                await update.message.reply_text("Извините, произошла техническая ошибка запроса к AI. Наш телефон: +7 778 061 5000")

    except Exception as e:
        logger.error(f"Ошибка в handle_message: {e}")
        await update.message.reply_text("Извините, сервис временно недоступен. Пожалуйста, позвоните нам: +7 778 061 5000")

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не задан!")
        return

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот на базе Gemini успешно запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
