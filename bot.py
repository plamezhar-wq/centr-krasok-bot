import os
import logging
import anthropic
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction
from company_info import COMPANY_KNOWLEDGE

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN_HERE")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY_HERE")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Хранилище истории диалогов (в памяти)
# Для продакшена лучше использовать Redis или БД
user_conversations: dict[int, list] = {}
MAX_HISTORY = 10  # последних сообщений в контексте

SYSTEM_PROMPT = f"""Ты — AI-ассистент интернет-магазина «Центр Красок #1» (centr-krasok.kz).
Твоя задача — отвечать на вопросы покупателей о компании, её товарах и услугах.

ПРАВИЛА:
1. Отвечай ТОЛЬКО на основе информации ниже. Не придумывай факты.
2. Если вопрос не связан с компанией или информация отсутствует — вежливо скажи, что не знаешь, и предложи позвонить по номеру +7 778 061 5000.
3. Отвечай на том же языке, на котором написал пользователь (русский, казахский, английский).
4. Будь дружелюбным, кратким и конкретным. Не пиши длинные простыни текста.
5. Не обсуждай конкурентов, политику, религию и другие посторонние темы.
6. Если спрашивают о цене конкретного товара — дай примерную цену если есть, иначе направь на сайт.

ИНФОРМАЦИЯ О КОМПАНИИ:
{COMPANY_KNOWLEDGE}
"""


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    if not user_text:
        return

    # Показываем "печатает..."
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    # Инициализируем историю для нового пользователя
    if user_id not in user_conversations:
        user_conversations[user_id] = []

    # Добавляем сообщение пользователя в историю
    user_conversations[user_id].append({
        "role": "user",
        "content": user_text
    })

    # Обрезаем историю до MAX_HISTORY сообщений
    if len(user_conversations[user_id]) > MAX_HISTORY * 2:
        user_conversations[user_id] = user_conversations[user_id][-MAX_HISTORY * 2:]

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=user_conversations[user_id]
        )

        assistant_reply = response.content[0].text

        # Добавляем ответ ассистента в историю
        user_conversations[user_id].append({
            "role": "assistant",
            "content": assistant_reply
        })

        await update.message.reply_text(assistant_reply)

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        await update.message.reply_text(
            "Извините, произошла техническая ошибка. Пожалуйста, попробуйте позже "
            "или позвоните нам: +7 778 061 5000"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await update.message.reply_text(
            "Что-то пошло не так. Попробуйте ещё раз или свяжитесь с нами: +7 778 061 5000"
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_conversations[user_id] = []  # Сброс истории

    await update.message.reply_text(
        "👋 Привет! Я — AI-ассистент магазина *Центр Красок #1*.\n\n"
        "Спрашивайте меня о наших товарах, брендах, ценах, доставке или услугах — "
        "отвечу на любой вопрос!\n\n"
        "🌐 centr-krasok.kz | 📞 +7 778 061 5000",
        parse_mode="Markdown"
    )


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    from telegram.ext import CommandHandler
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
