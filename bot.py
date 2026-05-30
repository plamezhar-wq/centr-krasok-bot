import os
import logging
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from company_info import COMPANY_KNOWLEDGE

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

dialog_histories = {}

SYSTEM_PROMPT = f"""Ты — Айгерим, живой консультант магазина «Центр Красок #1» (Казахстан, centr-krasok.kz).
Ты не робот, не AI, не бот — ты человек-консультант с характером и душой.

═══════════════════════════════
СТИЛЬ ОБЩЕНИЯ
═══════════════════════════════
• Первое сообщение от клиента — всегда приветствуй: "Добрый день!", "Здравствуйте!", "Привет!" — подбирай под тон клиента.
• Отвечай живо и тепло: "Отличный выбор!", "Хороший вопрос!", "Да, с удовольствием помогу!"
• После КАЖДОГО ответа задавай ОДИН уточняющий вопрос — чтобы помочь клиенту лучше:
  - "Это для квартиры или частного дома?"
  - "Вы уже определились с цветом или подберём вместе?"
  - "Для какой поверхности — стены, потолок, дерево, металл?"
  - "Вы сами будете красить или работает мастер?"
  - "Какой примерно метраж помещения?"
  - "Это для нового ремонта или обновляете покрытие?"
• Не пиши огромные списки без нужды — говори как живой человек, коротко и по делу.
• Эмодзи использовать уместно, не перебарщивать.

═══════════════════════════════
СТРОГИЕ ПРАВИЛА
═══════════════════════════════
1. ТОЛЬКО факты из базы знаний ниже. Не придумывай цены, бренды, характеристики.
2. НА ТЕЛЕФОН ПЕРЕВОДИ ТОЛЬКО если: клиент сам просит контакты, ИЛИ вопрос очень специфический (точная цена конкретного товара, наличие на складе, индивидуальный заказ).
3. НЕ говори "не знаю" и не отправляй на телефон при простых вопросах — лучше ответь то, что знаешь.
4. Язык — тот же, на котором пишет клиент (русский, казахский).
5. Посторонние темы (политика, личное) — мягко: "Я по части красок и отделки 😊 Чем могу помочь?"
6. НИКОГДА не говори что ты AI или бот.

═══════════════════════════════
БАЗА ЗНАНИЙ О КОМПАНИИ
═══════════════════════════════
{COMPANY_KNOWLEDGE}
"""

# Умный fallback — отвечает по теме, не гонит на телефон
def fallback_local_search(user_text: str) -> str:
    text = user_text.lower().strip()

    greetings = ["привет", "здравствуй", "добрый", "салем", "сәлем", "hi", "hello", "хай"]
    if any(w in text for w in greetings):
        return ("Добрый день! 😊 Я консультант магазина «Центр Красок #1».\n\n"
                "Помогу подобрать краску, лак или отделочный материал. "
                "У нас более 20 брендов и 45 000 оттенков на любой вкус!\n\n"
                "Что планируете красить или обновлять?")

    about = ["занимается", "что вы", "кто вы", "о компании", "расскажи о", "что за магазин", "чем торгует"]
    if any(w in text for w in about):
        return ("«Центр Красок #1» — это специализированный магазин премиальных красок и отделочных материалов в Казахстане 🎨\n\n"
                "Мы официальные дистрибьюторы мировых брендов: Dulux, Marshall, Little Greene, Oikos, Pinotex и ещё 15+ брендов. "
                "Работаем в Алматы и Астане, доставляем по всей стране.\n\n"
                "Вы ищете что-то конкретное или нужна помощь с выбором?")

    brands = ["бренд", "марк", "производитель", "dulux", "marshall", "pinotex", "tikkurila", "oikos"]
    if any(w in text for w in brands):
        return ("У нас представлено 20+ ведущих мировых брендов:\n\n"
                "🌍 Популярные: Dulux, Marshall, Dufa\n"
                "✨ Премиум: Little Greene, Oikos, Swiss Lake, Hygge\n"
                "🔧 Профессиональные: Sikkens, Teknos, Pinotex, Hammerite, Tikkurila\n"
                "🖌 Инструменты: Anza, Storch, Wagner\n\n"
                "Для каких задач подбираете материал?")

    services = ["услуг", "колеровк", "колер", "оттенок", "цвет", "подобрать цвет"]
    if any(w in text for w in services):
        return ("С удовольствием расскажу об услугах! 😊\n\n"
                "🎨 Колеровка — более 45 000 оттенков на профессиональном оборудовании\n"
                "💬 Бесплатная консультация по подбору материалов\n"
                "🚚 Доставка до двери или самовывоз из шоу-рума\n"
                "⭐ Специальные условия для дизайнеров и строителей\n\n"
                "Вы уже знаете какой цвет хотите, или будем подбирать вместе?")

    delivery = ["доставк", "привез", "доставит", "город", "регион", "астан", "алмат"]
    if any(w in text for w in delivery):
        return ("Доставляем по всему Казахстану! 🚚\n\n"
                "Работаем в 23 городах: Алматы, Астана, Шымкент, Караганды, Актобе, Атырау и других.\n"
                "Также можно забрать самовывозом из наших шоу-румов в Алматы и Астане.\n\n"
                "Из какого вы города?")

    price = ["цен", "сколько стоит", "стоимость", "почём", "бюджет", "дешев", "дорог"]
    if any(w in text for w in price):
        return ("Цены у нас очень разные — зависит от бренда и объёма 😊\n\n"
                "Например, сейчас на акции:\n"
                "🔹 Luxium Prof Bindo 3 (9л) — 37 088 тг (скидка 20%)\n"
                "🔹 Marshall AKRIKOR фасадная (9л) — 43 243 тг (скидка 17%)\n"
                "🔹 Luxium Окна и Двери (0,75л) — 10 640 тг (скидка 20%)\n\n"
                "Для какого помещения ищете краску?")

    assortment = ["ассортимент", "каталог", "что есть", "что продаёт", "товар", "продукц"]
    if any(w in text for w in assortment):
        return ("У нас большой ассортимент! 😊 Основные категории:\n\n"
                "🏠 Интерьерные краски (стены, потолки, детские, ванные)\n"
                "🏗 Фасадные краски\n"
                "🪵 Краски по дереву (мебель, полы, окна)\n"
                "⚙️ Краски по металлу\n"
                "✨ Декоративные покрытия и штукатурки\n"
                "🔧 Грунтовки, лаки, шпатлёвки\n"
                "🖌 Малярные инструменты и краскопульты\n\n"
                "Что именно вас интересует?")

    contacts = ["контакт", "телефон", "номер", "позвонить", "адрес", "где находит", "офис", "шоурум"]
    if any(w in text for w in contacts):
        return ("Наши контакты:\n\n"
                "📞 +7 (777) 292-84-01\n"
                "📧 info@centr-krasok.kz\n"
                "🌐 centr-krasok.kz\n"
                "🕐 Пн–Вс, 10:00–20:00\n"
                "📍 Алматы: ул. Кабдолова, д. 1/8\n\n"
                "Вы планируете приехать к нам или удобнее оформить доставку?")

    # Общий умный ответ — не гонит на телефон
    return ("Хороший вопрос! 😊 Уточните, пожалуйста:\n\n"
            "Вы ищете конкретный товар или нужна помощь с подбором материала для ремонта?")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name or ""
    dialog_histories[chat_id] = []

    greeting = f"Здравствуйте{', ' + user_name if user_name else ''}! 👋\n\n"
    welcome_text = (
        greeting +
        "Я — консультант магазина *«Центр Красок #1»*.\n\n"
        "Помогу подобрать краску, лак или отделочный материал под вашу задачу — "
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
    # Храним последние 10 сообщений (5 пар)
    dialog_histories[chat_id] = dialog_histories[chat_id][-10:]

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    api_key = os.getenv("OPENROUTER_API_KEY")

    if api_key:
        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + dialog_histories[chat_id]
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://railway.app",
                        "X-Title": "Centr Krasok Bot"
                    },
                    json={
                        "model": "meta-llama/llama-3.3-70b-instruct:free",
                        "messages": messages,
                        "temperature": 0.4,
                        "max_tokens": 600
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    ai_reply = data['choices'][0]['message']['content'].strip()
                    dialog_histories[chat_id].append({"role": "assistant", "content": ai_reply})
                    await update.message.reply_text(ai_reply, parse_mode="Markdown")
                    return
                else:
                    logger.warning(f"OpenRouter API вернул {response.status_code}: {response.text[:200]}")
        except Exception as e:
            logger.error(f"Ошибка OpenRouter API: {e}")

    # Умный fallback — не гонит на телефон без причины
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
