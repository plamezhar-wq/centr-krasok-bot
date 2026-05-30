import os
import logging
import anthropic
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction
from company_info import COMPANY_KNOWLEDGE

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

dialog_histories = {}

SYSTEM_PROMPT = f"""Ты — Айгерим, живой консультант магазина «Центр Красок #1» (Казахстан, centr-krasok.kz).
Ты не робот, не AI, не бот — ты человек-консультант с характером и душой.

СТИЛЬ ОБЩЕНИЯ:
• Первое сообщение — всегда приветствуй: "Добрый день!", "Здравствуйте!", "Привет!" — подбирай под тон клиента.
• Отвечай живо и тепло: "Отличный выбор!", "Хороший вопрос!", "Да, с удовольствием помогу!"
• После КАЖДОГО ответа задавай ОДИН уточняющий вопрос чтобы продолжить диалог:
  - "Это для квартиры или частного дома?"
  - "Вы уже определились с цветом или подберём вместе?"
  - "Для какой поверхности — стены, потолок, дерево, металл?"
  - "Вы сами будете красить или работает мастер?"
  - "Какой примерно метраж помещения?"
• Отвечай коротко и по делу, без огромных списков.

СТРОГИЕ ПРАВИЛА:
1. Отвечай ТОЛЬКО на основе базы знаний ниже. Не придумывай факты и цены.
2. На телефон переводи ТОЛЬКО если клиент сам просит контакты или вопрос про наличие на складе.
3. Если информации нет в базе — скажи "уточню у коллег" и дай телефон +7 (777) 292-84-01.
4. Отвечай на том языке на котором пишет клиент (русский, казахский).
5. Никогда не говори что ты AI или бот.

БАЗА ЗНАНИЙ:
{COMPANY_KNOWLEDGE}
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name or ""
    dialog_histories[chat_id] = []

    welcome_text = (
        f"Здравствуйте{', ' + user_name if user_name else ''}! 👋\n\n"
        "Я — консультант магазина *«Центр Красок #1»*.\n\n"
        "Помогу подобрать краску, лак или отделочный материал — "
        "у нас 20+ брендов и 45 000 оттенков 🎨\n\n"
        "Расскажите, что планируете красить или обновлять!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if not user_text or not user_text.strip():
        return

    if chat_id not in dialog_histories:
        dialog_histories[chat_id] = []

    dialog_histories[chat_id].append({"role": "user", "content": user_text})
    dialog_histories[chat_id] = dialog_histories[chat_id][-10:]

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=dialog_histories[chat_id]
        )
        ai_reply = response.content[0].text.strip()
        dialog_histories[chat_id].append({"role": "assistant", "content": ai_reply})
        await update.message.reply_text(ai_reply)

    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        await update.message.reply_text(
            "Добрый день! Уточню этот вопрос у коллег 😊\n"
            "Позвоните нам: +7 (777) 292-84-01 — ответим сразу!"
        )


def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не задан!")
        return

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен!")
    application.run_polling()


if __name__ == '__main__':
    main()
