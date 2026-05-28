import os
import logging
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from company_info import COMPANY_KNOWLEDGE

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилище контекста диалогов
dialog_histories = {}

SYSTEM_PROMPT = f"""Ты — официальный AI-ассистент компании "Центр Красок" (Казахстан, сайт centr-krasok.kz).
Отвечай вежливо, грамотно и СТРОГО на основе предоставленной информации о компании.

ИНФОРМАЦИЯ О КОМПАНИИ:
{COMPANY_KNOWLEDGE}

ПРАВИЛА ОТВЕТОВ:
1. Отвечай на том языке, на котором обратился клиент (русский или казахский).
2. Используй только факты из текста выше. Если информации нет в базе данных, НЕ придумывай её. Вежливо ответь, что не владеешь этой информацией, и предложи связаться по телефону: +7 778 061 5000.
3. Ответы должны быть четкими и дружелюбными.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    dialog_histories[chat_id] = []  # Очищаем историю
    
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

    try:
        # Формируем историю для отправки в DuckDuckGo AI API (используем модель Llama 3)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + dialog_histories[chat_id]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Шаг 1: Получаем обязательный статус-токен от DuckDuckGo
            v_resp = await client.get("https://duckduckgo.com/duckchat/v1/status", headers={"x-vqd-accept": "1"})
            vqd_token = v_resp.headers.get("x-vqd-4")
            
            if not vqd_token:
                raise Exception("Не удалось получить токен авторизации DuckDuckGo")
            
            # Шаг 2: Отправляем запрос к бесплатной нейросети
            headers = {
                "x-vqd-4": vqd_token,
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            }
            
            payload = {
                "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                "messages": messages
            }
            
            response = await client.post("https://duckduckgo.com/duckchat/v1/chat", headers=headers, json=payload)
            
            if response.status_code == 200:
                # Парсим потоковый текстовый ответ
                lines = response.text.split("\n")
                ai_reply = ""
                for line in lines:
                    if line.startswith("data: "):
                        data_content = line[6:]
                        if data_content == "[DONE]":
                            break
                        import json
                        try:
                            chunk = json.loads(data_content)
                            if "message" in chunk:
                                ai_reply += chunk["message"]
                        except:
                            continue
                
                ai_reply = ai_reply.strip()
                if not ai_reply:
                    raise Exception("Пустой ответ от модели")
                
                # Сохраняем в контекст
                dialog_histories[chat_id].append({"role": "assistant", "content": ai_reply})
                await update.message.reply_text(ai_reply)
            else:
                logger.error(f"DuckDuckGo API Error: {response.text}")
                raise Exception("Ошибка сервера нейросети")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
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
    
    logger.info("Бот успешно запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
