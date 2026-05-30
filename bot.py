import os
import logging
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from company_info import COMPANY_KNOWLEDGE

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

dialog_histories = {}

SYSTEM_PROMPT = f"""Ты — Айгерим, консультант магазина «Центр Красок #1» (Казахстан, centr-krasok.kz).
Ты живой, тёплый человек-консультант с характером — не робот и не справочник.

ТВОЙ СТИЛЬ ОБЩЕНИЯ:
- Всегда приветствуй клиента тепло: "Добрый день!", "Здравствуйте!", "Привет!" — в зависимости от тона клиента.
- Отвечай живо и по-человечески. Используй фразы типа: "Отличный выбор!", "Хороший вопрос!", "Да, конечно!", "С удовольствием помогу!"
- После ответа ВСЕГДА задавай один уточняющий вопрос — чтобы помочь клиенту лучше. Примеры:
  * "Скажите, это для квартиры или для дома?"
  * "Вы уже знаете какой цвет хотите, или подберём вместе?"
  * "Для какой поверхности выбираете — стены, потолок, дерево?"
  * "Вы сами будете красить или нанимаете мастера?"
  * "Какой у вас примерно метраж помещения?"
- Не пиши длинные списки без нужды — говори как живой человек.
- Иногда можно добавить лёгкую эмоцию: "Это один из наших самых популярных брендов 😊"

ПРАВИЛА (СТРОГО):
1. Отвечай ТОЛЬКО на основе информации о компании ниже. Не придумывай факты о товарах и ценах.
2. Если информации нет — скажи: "Уточню у коллег! Позвоните нам: +7 778 061 5000 — ответим сразу."
3. Отвечай на том языке, на котором написал клиент (русский, казахский).
4. Посторонние темы (политика, личное, конкуренты) — мягко уводи: "Я специализируюсь на красках и отделке 😊 Могу помочь с выбором материалов!"
5. Никогда не говори что ты AI или бот — ты Айгерим, консультант.

ИНФОРМАЦИЯ О КОМПАНИИ:
{COMPANY_KNOWLEDGE}
"""

def fallback_local_search(user_text):
    text = user_text.lower().strip()
    
    if any(word in text for word in ["занимается", "компания", "кто вы", "что вы"]):
        return ("Добрый день! 😊 «Центр Красок #1» — это специализированный магазин премиальных красок и отделочных материалов в Казахстане. "
                "Работаем в Алматы и Астане, доставляем по всей стране.\n\n"
                "Скажите, вы планируете ремонт или ищете что-то конкретное?")
        
    if any(word in text for word in ["бренд", "бренды", "производитель"]):
        return ("У нас представлено более 20 ведущих мировых брендов:\n"
                "🌍 Мировые лидеры: Dulux, Marshall, Dufa\n"
                "✨ Премиум: Little Greene, Oikos, Swiss Lake, Hygge\n"
                "🔧 Профессиональные: Teknos, Sikkens, Pinotex, Hammerite, Tikkurila\n"
                "🖌 Инструменты: Anza, Storch, Wagner\n\n"
                "Для каких задач подбираете краску?")

    if any(word in text for word in ["услуги", "колеровка", "доставка"]):
        return ("С удовольствием расскажу! Наши услуги:\n"
                "🎨 Колеровка — более 45 000 оттенков\n"
                "💬 Бесплатная консультация по подбору материалов\n"
                "🚚 Доставка до двери или самовывоз\n"
                "⭐ Специальные условия для дизайнеров и строителей\n\n"
                "Что из этого вас интересует?")

    if any(word in text for word in ["контакт", "телефон", "адрес", "офис", "где"]):
        return ("Конечно! Наши контакты:\n"
                "📞 +7 778 061 5000\n"
                "📧 info@centr-krasok.kz\n"
                "🕐 Режим работы: Пн–Вс, 10:00–20:00\n"
                "📍 Алматы: ул. Кабдолова, д. 1/8\n\n"
                "Вы планируете приехать к нам или удобнее доставка?")

    return ("Добрый день! Уточню этот вопрос у коллег 😊\n"
            "Позвоните нам: +7 778 061 5000 — ответим сразу!\n\n"
            "Могу помочь ещё с чем-нибудь?")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name or "друг"
    dialog_histories[chat_id] = []
    
    welcome_text = (
        f"Здравствуйте, {user_name}! 👋\n\n"
        "Я — Айгерим, консультант магазина *«Центр Красок #1»*.\n\n"
        "Помогу подобрать краску, лак или отделочный материал под вашу задачу — "
        "у нас более 20 брендов и 45 000 оттенков 🎨\n\n"
        "С чего начнём? Расскажите, что планируете красить или обновлять!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in dialog_histories:
        dialog_histories[chat_id] = []

    dialog_histories[chat_id].append({"role": "user", "content": user_text})
    dialog_histories[chat_id] = dialog_histories[chat_id][-10:]

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    api_key = os.getenv("OPENROUTER_API_KEY")

    if api_key:
        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + dialog_histories[chat_id]
            async with httpx.AsyncClient(timeout=15.0) as client:
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
                        "temperature": 0.4
                    }
                )
                
                if response.status_code == 200:
                    ai_reply = response.json()['choices'][0]['message']['content'].strip()
                    dialog_histories[chat_id].append({"role": "assistant", "content": ai_reply})
                    await update.message.reply_text(ai_reply, parse_mode="Markdown")
                    return
                else:
                    logger.warning(f"API Error {response.status_code}")
        except Exception as e:
            logger.error(f"Ошибка API: {e}")

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
    
    logger.info("Бот запущен!")
    application.run_polling()


if __name__ == '__main__':
    main()
