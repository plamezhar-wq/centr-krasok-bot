import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from company_info import COMPANY_KNOWLEDGE

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 Привет! Я — официальный AI-ассистент магазина «Центр Красок #1».\n\n"
        "Спрашивайте меня о наших товарах, брендах, ценах, доставке или услугах — отвечу на любой вопрос!"
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.lower().strip()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Превращаем текст базы данных в список строк для удобного поиска
    lines = [line.strip() for line in COMPANY_KNOWLEDGE.split('\n') if line.strip()]
    
    response_blocks = []

    # Логика умного поиска по ключевым словам в базе данных
    if "привет" in user_text or "здравствуй" in user_text or "салем" in user_text:
        response_blocks.append("Здравствуйте! Чем я могу помочь вам сегодня? Напишите, какой товар или услуга вас интересует.")
    
    elif "компани" in user_text or "о нас" in user_text or "кто вы" in user_text:
        # Ищем блок общей информации
        for line in lines:
            if "центр красок" in line.lower() or "официальный" in line.lower() or "магазин" in line.lower():
                response_blocks.append(line)
                
    elif "доставк" in user_text or "довезти" in user_text or "курьер" in user_text:
        for line in lines:
            if "доставк" in line.lower() or "город" in line.lower() or "бесплатн" in line.lower():
                response_blocks.append(line)
                
    elif "адрес" in user_text or "где" in user_text or "находит" in user_text or "филиал" in user_text or "город" in line.lower():
        for line in lines:
            if "адрес" in line.lower() or "ул." in line.lower() or "алматы" in line.lower() or "астана" in line.lower() or "филиал" in line.lower():
                response_blocks.append(line)

    elif "телефон" in user_text or "номер" in user_text or "связаться" in user_text or "контакт" in user_text:
        for line in lines:
            if "телефон" in line.lower() or "контакт" in line.lower() or "+7" in line.lower():
                response_blocks.append(line)

    elif "бренд" in user_text or "товар" in user_text or "краск" in user_text or "ассортимент" in user_text or "что есть" in user_text:
        for line in lines:
            if "бренд" in line.lower() or "краск" in line.lower() or "продукт" in line.lower() or "декор" in line.lower():
                response_blocks.append(line)

    # Если точечные ключевые слова не сработали, ищем любые совпадения по словам пользователя
    if not response_blocks:
        user_words = [w for w in user_text.split() if len(w) > 3]
        for line in lines:
            if any(word in line.lower() for word in user_words):
                if line not in response_blocks:
                    response_blocks.append(line)

    # Собираем ответ
    if response_blocks:
        # Убираем дубликаты и соединяем в красивый текст
        final_reply = "\n\n".join(list(dict.fromkeys(response_blocks)))
        # Ограничим длину, если вышло слишком много текста
        if len(final_reply) > 4000:
            final_reply = final_reply[:3900] + "..."
    else:
        final_reply = (
            "К сожалению, я не нашёл точного ответа на этот вопрос в нашей базе данных.\n\n"
            "Пожалуйста, свяжитесь с нашим отделом продаж по телефону: **+7 778 061 5000**, и наш менеджер с радостью вам поможет!"
        )

    await update.message.reply_text(final_reply, parse_mode="Markdown")

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не задан!")
        return

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот успешно запущен в автономном режиме!")
    application.run_polling()

if __name__ == '__main__':
    main()
