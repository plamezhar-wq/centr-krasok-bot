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
    text = user_text.lower().strip()
    
    # Прямой поиск по всей базе знаний без сложных условий
    if any(word in text for word in ["занимается", "компания", "кто вы"]):
        return [sec for sec in COMPANY_KNOWLEDGE.split('#') if "компании" in sec.lower()][0]
    
    if any(word in text for word in ["услуги", "колеровка", "доставка"]):
        return [sec for sec in COMPANY_KNOWLEDGE.split('#') if "услуги" in sec.lower()][0]
        
    if any(word in text for word in ["бренд", "сотрудничает"]):
        return [sec for sec in COMPANY_KNOWLEDGE.split('#') if "бренды" in sec.lower()][0]

    return "К сожалению, я не нашел точного ответа в базе. Пожалуйста, позвоните нам: +7 778 061 5000"
    
    # Ищем, к какому разделу относится запрос
       
    if found_section:
        # Убираем заголовок раздела из ответа для красоты
        return "\n".join(found_section.split('\n')[1:]).strip()
    
    return "К сожалению, я не нашел точного ответа в базе. Пожалуйста, позвоните нам: +7 778 061 5000"

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
