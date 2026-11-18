#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot & Mini App Server — «Яндекс.АвтоЭксперт» (Тестовый полигон)
Разработано без сторонних зависимостей (чистая стандартная библиотека Python 3).

Запуск:
    python3 bot.py --token "ВАШ_ТОКЕН"
"""

import sys
import os
import json
import math
import time
import uuid
import socket
import argparse
import threading
import urllib.request
import urllib.parse
from http.server import SimpleHTTPRequestHandler, HTTPServer

PORT = 8080
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_FILE = os.path.join(WORKSPACE_DIR, "autoexpert_demo.html")

class TMAHTTPHandler(SimpleHTTPRequestHandler):
    """Раздача статики WebApp с корректными заголовками и CORS"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WORKSPACE_DIR, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass

def run_http_server(port=PORT):
    # Проверяем, не занят ли порт
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        is_busy = s.connect_ex(('127.0.0.1', port)) == 0

    if is_busy:
        print(f"[HTTP] Порт {port} уже обслуживается локальным сервером.")
        return

    try:
        server_address = ('0.0.0.0', port)
        httpd = HTTPServer(server_address, TMAHTTPHandler)
        print(f"[HTTP] Сервер Mini App запущен: http://localhost:{port}/")
        httpd.serve_forever()
    except Exception as e:
        print(f"[HTTP] Статус сервера: {e}")

# ================= Telegram Bot API (urllib) =================

class TelegramBot:
    def __init__(self, token, webapp_url=None):
        self.token = token
        self.webapp_url = webapp_url or f"http://localhost:{PORT}/index.html"
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.last_update_id = 0

    def make_request(self, method, payload=None):
        url = f"{self.api_url}/{method}"
        headers = {"Content-Type": "application/json"}
        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"ok": False, "description": str(e)}

    def send_message(self, chat_id, text, reply_markup=None):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.make_request("sendMessage", payload)

    def answer_callback_query(self, callback_query_id, text=None):
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        return self.make_request("answerCallbackQuery", payload)

    def send_document(self, chat_id, filepath, caption=""):
        if not os.path.exists(filepath):
            return {"ok": False, "description": "File not found"}
        boundary = uuid.uuid4().hex
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        lines = [
            f"--{boundary}".encode(),
            b'Content-Disposition: form-data; name="chat_id"',
            b'',
            str(chat_id).encode(),
            f"--{boundary}".encode(),
            b'Content-Disposition: form-data; name="caption"',
            b'',
            caption.encode("utf-8"),
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="document"; filename="{filename}"'.encode(),
            b'Content-Type: text/html',
            b'',
            file_bytes,
            f"--{boundary}--".encode(),
            b''
        ]
        body = b"\r\n".join(lines)
        req = urllib.request.Request(
            f"{self.api_url}/sendDocument",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"ok": False, "description": str(e)}

    def set_menu_button(self, url):
        payload = {
            "menu_button": {
                "type": "web_app",
                "text": "АвтоЭксперт",
                "web_app": {"url": url}
            }
        }
        return self.make_request("setChatMenuButton", payload)

    def get_main_keyboard(self):
        is_https = self.webapp_url.startswith("https://")
        kb = [
            [
                {
                    "text": "🚀 Открыть полигон «Яндекс.АвтоЭксперт»",
                    "web_app": {"url": self.webapp_url}
                } if is_https else {
                    "text": "📱 Скачать автономный полигон (.html)",
                    "callback_data": "cmd_demo"
                }
            ],
            [
                {"text": "⚖️ Методика ЭКЦ МВД (ст. 264 УК)", "callback_data": "cmd_mvd"},
                {"text": "🛡️ Трасология СОДФУ (ОСАГО)", "callback_data": "cmd_sodfu"}
            ],
            [
                {"text": "⚡ Экспресс-расчет скорости", "callback_data": "cmd_calc_help"},
                {"text": "📲 Загрузить WebApp-файл", "callback_data": "cmd_demo"}
            ]
        ]
        return {"inline_keyboard": kb}

    def handle_callback(self, query):
        qid = query.get("id")
        data = query.get("data", "")
        chat_id = query.get("message", {}).get("chat", {}).get("id")

        self.answer_callback_query(qid)

        if data == "cmd_mvd":
            self.send_message(chat_id, self.get_mvd_text())
        elif data == "cmd_sodfu":
            self.send_message(chat_id, self.get_sodfu_text())
        elif data == "cmd_calc_help":
            self.send_message(
                chat_id,
                "💡 *Формат команды экспресс-расчета:*\n"
                "`/calc <длина_юза_м> [покрытие]`\n\n"
                "*Примеры:*\n"
                "• `/calc 25` (по умолчанию сухой асфальт)\n"
                "• `/calc 25 мокрый` (kc = 0.4)\n"
                "• `/calc 20 снег` (kc = 0.2)\n"
                "• `/calc 15 лед` (kc = 0.1)\n\n"
                "Также доступен расчет техвозможности предотвращения наезда:\n"
                "`/mvd <скорость_кмч> <дистанция_пешехода_м>` (например `/mvd 65 35`)"
            )
        elif data == "cmd_demo":
            self.send_message(chat_id, "⏳ Отправляю автономный полигон со встроенными стилями и скриптами...")
            self.send_document(
                chat_id,
                DEMO_FILE,
                caption="📱 Автономный интерактивный полигон «Яндекс.АвтоЭксперт». Открывается в один клик на смартфоне и ПК без интернета!"
            )

    def get_mvd_text(self):
        return (
            "⚖️ *МЕТОДИКА ЭКЦ МВД (2010 г.) — ст. 264 УК РФ*\n\n"
            "Ключевой вопрос следствия и суда: _«Располагал ли водитель технической возможностью предотвратить наезд?»_\n\n"
            "1. *Остановочный путь S₀:* автомобиль начинает тормозить не мгновенно!\n"
            "`S₀ = (t₁ + t₂ + 0.5·t₃) · (Va / 3.6) + Va² / (26 · ja)`\n"
            "• `t₁` = время реакции водителя (0.6–1.4 с)\n"
            "• `t₂` = время срабатывания привода (0.1–0.4 с)\n"
            "• `t₃` = нарастание замедления (0.2–0.5 с)\n"
            "• `ja` = установившееся замедление (6.8–7.5 м/с² на сухом)\n\n"
            "2. *Удаление пешехода Sa:* расстояние от ТС до пешехода в момент возникновения опасности.\n"
            "• Если `S₀ ≤ Sa` — водитель *располагал* технической возможностью (усматривается вина по п. 10.1 ПДД).\n"
            "• Если `S₀ > Sa` — водитель *НЕ располагал* возможностью (невиновен, отсутствует состав преступления по ст. 264 УК РФ).\n\n"
            "💡 *Команда для мгновенного расчета:* `/mvd <скорость> <дистанция>`"
        )

    def get_sodfu_text(self):
        return (
            "🛡️ *МЕТОДИКА АНО «СОДФУ» (Звягин, 2021) — СПОРЫ СО СТРАХОВЫМИ*\n\n"
            "Страховые компании часто отказывают в выплатах по ОСАГО/КАСКО под предлогом: "
            "_«Повреждения не соответствуют обстоятельствам ДТП, бамперы не совпадают по высоте»_.\n\n"
            "🔍 *Главный козырь защиты — динамический клевок кузова:*\n"
            "• При экстренном торможении передняя ось проседает на *30–70 мм*, а задняя поднимается на *20–45 мм*.\n"
            "• Эксперты страховщиков сопоставляют стоящие автомобили в статике на ровном асфальте, занижая зону контакта!\n"
            "• Трасологический анализ по Звягину доказывает: высотная разница полностью вызвана дифферентом при замедлении, повреждения законны."
        )

    def handle_command(self, chat_id, text, web_app_data=None):
        if web_app_data:
            try:
                data = json.loads(web_app_data)
                resp = (
                    "📋 *ЭКСПЕРТНОЕ ЗАКЛЮЧЕНИЕ (ПОЛИГОН АВТОЭКСПЕРТ)*\n\n"
                    f"🔹 *Событие:* {data.get('type', 'ДТП')}\n"
                    f"🔹 *Транспорт:* {data.get('vehicle', 'Автомобиль')} (kt = {data.get('kt', 1.0)})\n"
                    f"🔹 *Покрытие:* {data.get('road', 'Сухой асфальт')} (kc = {data.get('kc', 0.7)})\n"
                    f"🔹 *Длина юза:* {data.get('distance', 0)} м\n"
                    f"🔹 *Расчетная скорость V₀:* *{data.get('speed', 0)} км/ч*\n"
                    f"🔹 *Установленный лимит:* {data.get('limit', 60)} км/ч\n\n"
                    f"⚖️ *Квалификация:* {data.get('verdict', 'Анализ завершен')}\n"
                    f"📌 *Формула Минюста:* `V = √(S · kc · 254 / kt)`\n\n"
                    "_Данные зафиксированы для формирования судебного ходатайства._"
                )
                self.send_message(chat_id, resp)
            except Exception as ex:
                self.send_message(chat_id, f"⚠️ Ошибка обработки данных экспертизы: {ex}")
            return

        cmd = text.split()[0].lower() if text else ""
        args = text.split()[1:] if text else []

        if cmd in ["/start", "/menu", "/help"]:
            welcome = (
                "👋 *Добро пожаловать в тестовый полигон «Яндекс.АвтоЭксперт»!*\n\n"
                "Этот бот и Mini App созданы для проверки формул автотехнической экспертизы, "
                "судебной практики по ст. 264 УК РФ и споров со страховыми компаниями.\n\n"
                "📌 *Быстрые команды:*\n"
                "• `/calc <метры> [покрытие]` — расчет скорости по юзу\n"
                "• `/mvd <скорость> <удаление>` — анализ техвозможности (ст. 264 УК РФ)\n"
                "• `/sodfu` — разбор уловок страховых по трасологии\n"
                "• `/app` — получить автономный полигон файлом"
            )
            self.send_message(chat_id, welcome, reply_markup=self.get_main_keyboard())

        elif cmd == "/app" or cmd == "/demo":
            self.send_message(chat_id, "⏳ Отправляю автономный файл полигона...")
            self.send_document(
                chat_id,
                DEMO_FILE,
                caption="📱 Автономный интерактивный полигон «Яндекс.АвтоЭксперт». Открывается в один клик на смартфоне и ПК без интернета!"
            )

        elif cmd == "/seturl":
            if not args:
                self.send_message(chat_id, "💡 Укажите адрес: `/seturl https://ваш-домен/index.html`")
                return
            new_url = args[0]
            if not new_url.startswith("https://"):
                self.send_message(chat_id, "⚠️ Telegram требует обязательный HTTPS протокол (`https://...`).")
                return
            self.webapp_url = new_url
            res = self.set_menu_button(new_url)
            if res.get("ok"):
                self.send_message(
                    chat_id,
                    f"🎉 *Мини-приложение подключено!*\\n\\n"
                    f"🔗 URL: `{new_url}`\\n"
                    f"Кнопка **«АвтоЭксперт»** теперь активна в нижнем меню Telegram! Нажмите её, чтобы открыть приложение прямо внутри мессенджера.",
                    reply_markup=self.get_main_keyboard()
                )
            else:
                self.send_message(chat_id, f"⚠️ Ошибка установки кнопки: {res.get('description')}")

        elif cmd == "/calc":
            if not args:
                self.send_message(chat_id, "💡 Формат команды: `/calc <длина_торможения_м> [тип_покрытия]`\nПример: `/calc 25 мокрый`")
                return
            try:
                s = float(args[0].replace(",", "."))
                kc = 0.7
                road = "Сухой асфальт"
                if len(args) > 1:
                    r = args[1].lower()
                    if "мокр" in r:
                        kc = 0.4
                        road = "Мокрый асфальт"
                    elif "снег" in r:
                        kc = 0.2
                        road = "Укатанный снег"
                    elif "лед" in r or "гололед" in r:
                        kc = 0.1
                        road = "Обледенение"
                v = math.sqrt(s * kc * 254 / 1.0)
                v_round = round(v, 1)
                limit = 60
                delta = round(v_round - limit, 1)
                verdict = f"⚠️ *Превышение на {delta} км/ч* (п. 10.1, 10.2 ПДД)" if delta > 0 else "✅ *Скорость в пределах нормы* (до 60 км/ч)"
                msg = (
                    f"🏎️ *Экспресс-расчет скорости по следу торможения:*\n\n"
                    f"• Длина юза: *{s} м*\n"
                    f"• Покрытие: *{road}* (kc = {kc})\n"
                    f"• Тип ТС: *Легковой* (kt = 1.0)\n\n"
                    f"📊 *Начальная скорость: {v_round} км/ч*\n"
                    f"{verdict}\n\n"
                    f"`Формула: V = √({s} · {kc} · 254 / 1.0) = {v_round} км/ч`"
                )
                self.send_message(chat_id, msg)
            except ValueError:
                self.send_message(chat_id, "⚠️ Ошибка: укажите число метров (например, `/calc 28.5`).")

        elif cmd == "/mvd":
            if len(args) >= 2:
                try:
                    va = float(args[0].replace(",", "."))
                    sa = float(args[1].replace(",", "."))
                    t1 = 0.8 # день
                    t2 = 0.1
                    t3 = 0.3
                    ja = 6.87 # на сухом
                    va_ms = va / 3.6
                    s_reac = (t1 + t2 + 0.5 * t3) * va_ms
                    s_brake = (va * va) / (26 * ja)
                    s0 = round(s_reac + s_brake, 1)
                    if s0 <= sa:
                        verdict = f"⚠️ *ВОДИТЕЛЬ РАСПОЛАГАЛ ВОЗМОЖНОСТЬЮ* (S₀ = {s0} м ≤ Sa = {sa} м).\nЭкстренное торможение предотвращало наезд. Усматривается п. 10.1 ПДД РФ."
                    else:
                        verdict = f"✅ *ВОДИТЕЛЬ НЕ РАСПОЛАГАЛ ВОЗМОЖНОСТЬЮ* (S₀ = {s0} м > Sa = {sa} м).\nНаезд технически непредотвратим! Отсутствует состав ст. 264 УК РФ."
                    resp = (
                        f"⚖️ *Экспертиза ЭКЦ МВД (ст. 264 УК РФ):*\n\n"
                        f"• Скорость движения Va: *{va} км/ч*\n"
                        f"• Дистанция обнаружения Sa: *{sa} м*\n"
                        f"• Расчетный остановочный путь S₀: *{s0} м*\n\n"
                        f"{verdict}\n\n"
                        f"`S₀ = ({t1}+{t2}+0.5·{t3})·{round(va_ms,1)} + {round(va**2)}/(26·{ja}) = {s0} м`"
                    )
                    self.send_message(chat_id, resp)
                    return
                except ValueError:
                    pass
            self.send_message(chat_id, self.get_mvd_text())

        elif cmd == "/sodfu":
            self.send_message(chat_id, self.get_sodfu_text())

    def poll(self):
        masked_token = f"{self.token[:6]}...{self.token[-4:]}"
        print(f"[BOT] Запущен Telegram Bot Polling (токен: {masked_token})")
        while True:
            try:
                res = self.make_request("getUpdates", {"offset": self.last_update_id + 1, "timeout": 20})
                if res.get("ok"):
                    for update in res.get("result", []):
                        self.last_update_id = update["update_id"]
                        if "callback_query" in update:
                            self.handle_callback(update["callback_query"])
                        elif "message" in update:
                            msg = update["message"]
                            chat_id = msg.get("chat", {}).get("id")
                            text = msg.get("text", "")
                            web_app_data = msg.get("web_app_data", {}).get("data")
                            if chat_id:
                                self.handle_command(chat_id, text, web_app_data)
                time.sleep(0.3)
            except Exception as e:
                time.sleep(2)

def main():
    parser = argparse.ArgumentParser(description="АвтоЭксперт — Telegram Bot & Mini App Server")
    parser.add_argument("--token", type=str, default=os.environ.get("TG_BOT_TOKEN", ""), help="Telegram Bot Token")
    parser.add_argument("--url", type=str, default="", help="Внешний HTTPS URL для Telegram WebApp")
    parser.add_argument("--port", type=int, default=PORT, help=f"Порт локального HTTP-сервера (по умолчанию {PORT})")
    args = parser.parse_args()

    http_thread = threading.Thread(target=run_http_server, args=(args.port,), daemon=True)
    http_thread.start()

    if not args.token:
        print("Токен не указан. Запустите: python3 bot.py --token <ТОКЕН>")
        return

    url = args.url if args.url else f"http://localhost:{args.port}/index.html"
    bot = TelegramBot(token=args.token, webapp_url=url)
    bot.poll()

if __name__ == "__main__":
    main()
