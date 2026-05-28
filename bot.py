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
2. Используй ТОЛЬКО факты из предоставленного текста. Если информации в базе нет, НЕ придумывай её. Вежливо ответь, что не владеешь информацией, и предложи связаться по телефону: +7 778 061 5000.
"""

def fallback_local_search(user_text):
    """Резервный автономный ИИ-поиск по ключевым словам на случай сбоя API"""
    text = user_text.lower().strip()
    lines = [line.strip() for line in COMPANY_KNOWLEDGE.split('\n') if line.strip()]
    blocks = []
    
    if "привет" in text or "здравствуй" in text or "салем" in text:
        return "Здравствуйте! Чем я могу помочь вам сегодня? Напишите, какой товар или услуга вас интересует."
    
    if "компани" in text or "о нас" in text or "кто вы" in text:
        blocks.extend([l for l in lines if "центр красок" in l.lower() or "магазин" in l.lower()])
    if "доставк" in text or "довезти" in text or "курьер" in text:
        blocks.extend([l for l in lines if "доставк" in l.lower() or "бесплатн" in l.lower()])
    if "адрес" in text or "где" in text or "находит" in text or "филиал" in text:
        blocks.extend([l for l in lines if "адрес" in l.lower() or "ул." in l.lower() or "алматы" in l.lower() or "астана" in l.lower()])
    if "телефон" in text or "номер" in text or "связаться" in text or "контакт" in text:
        blocks.extend([l for l in lines if "телефон" in l.lower() or "+7" in l.lower()])
    if "бренд" in text or "товар" in text or "краск" in text or "ассортимент" in text:
        blocks.extend([l for l in lines if "бренд" in l.lower() or "краск" in l.lower() or "продукт" in l.lower()])

    if not blocks:
        words = [w for w in text.split() if len(w) > 3]
        for line in lines:
            if any(w in line.lower() for w in words) and line not in blocks:
                blocks.append(line)

    if blocks:
        return "\n\n".join(list(dict.fromkeys(blocks)))
    
    return "К сожалению, я не нашёл точного ответа в базе данных. Пожалуйста, свяжитесь с нами по телефону: +7 778 061 5000"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    dialog_histories[chat_id] = []
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

    dialog_histories[chat_id].append({"role": "user", "content": user_text})
    dialog_histories[chat_id] = dialog_histories[chat_id][-6:]

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    api_key = os.getenv("OPENROUTER_API_KEY")

    # 1. Пробуем сделать официальный запрос к AI API
    if api_key:
        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + dialog_histories[chat_id]
            async with httpx.AsyncClient(timeout=10.0) as client:
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
                        "temperature": 0.1
                    }
                )
                
                if response.status_code == 200:
                    ai_reply = response.json()['choices'][0]['message']['content'].strip()
                    dialog_histories[chat_id].append({"role": "assistant", "content": ai_reply})
                    await update.message.reply_text(ai_reply, parse_mode="Markdown")
                    return
                else:
                    logger.warning(f"API Error {response.status_code}, переключаюсь на локальный поиск.")
        except Exception as e:
            logger.error(f"Ошибка сети API: {e}, переключаюсь на локальный поиск.")

    # 2. Если API сбоит — незаметно спасаем положение локальным поиском
    local_reply = fallback_local_search(user_text)
    dialog_histories[chat_id].append({"role": "assistant", "content": local_reply})
    await update.message.reply_text(local_reply, parse_mode="Markdown")

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не задан!")
        return

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот успешно запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
