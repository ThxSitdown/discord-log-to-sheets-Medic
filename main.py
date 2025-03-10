import discord
import os
import gspread
import json
import re
import logging
import threading
import requests
import time
import datetime
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask
from discord.ext import commands
from dotenv import load_dotenv  # ✅ โหลด environment variables

# โหลด Environment Variables
load_dotenv()

# ตั้งค่า Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ตั้งค่า Discord Bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ตั้งค่า Flask App
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running."

@app.route('/health')
def health_check():
    return {"status": "ok", "bot_status": bot.is_ready()}

def run_flask():
    try:
        logging.info("🌍 Starting Flask on port 5000...")
        app.run(host="0.0.0.0", port=5000, threaded=True)
    except Exception as e:
        logging.error(f"❌ Flask app error: {e}")

@bot.event
async def on_ready():
    logging.info(f"🤖 {bot.user} is online and ready!")
    await bot.change_presence(activity=discord.Game(name="Minecraft"))

    if sheet:
        try:
            test_value = sheet.acell("A1").value
            logging.info(f"✅ Google Sheets เชื่อมต่อสำเร็จ! (Test Read: A1 = {test_value})")
        except Exception as e:
            logging.error(f"❌ ไม่สามารถเชื่อมต่อ Google Sheets: {e}")

# ✅ รับข้อมูลเฉพาะจากห้องที่มี ID 
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", 1341317473164726272))

# ฟังก์ชันแปลงเวลา
def format_datetime(raw_time):
    pattern = r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})"
    match = re.search(pattern, raw_time)
    
    if match:
        day, month, year, hour, minute, second = match.groups()
        formatted_time = f"{int(day):02d}/{int(month):02d}/{year} {int(hour):02d}:{int(minute):02d}:{int(second):02d}"
        logging.info(f"🕒 แปลงเวลา {raw_time} ➝ {formatted_time}")
        return formatted_time
    else:
        logging.warning(f"⚠️ รูปแบบเวลาไม่ถูกต้อง: {raw_time}")
        return raw_time

# ✅ ฟังก์ชันหาบรรทัดสุดท้ายของ Google Sheets
def get_last_row():
    if sheet:
        values = sheet.col_values(1)
        return len(values) + 1
    return None

@bot.event
async def on_message(message):
    if message.channel.id != TARGET_CHANNEL_ID:
        return

    if message.author.bot and message.author.name == "Captain Hook":
        try:
            content = message.content.strip()
            name, steam_id, check_in_time, check_out_time = None, None, None, None

            # ✅ ดึงข้อมูลจาก Embed
            if message.embeds:
                for embed in message.embeds:
                    for field in embed.fields:
                        if "ชื่อ" in field.name:
                            name = field.value.strip("`").strip()
                        elif "ไอดี" in field.name:
                            steam_id = field.value.strip().replace("steam:", "")
                        elif "เข้างาน" in field.name:
                            check_in_time = format_datetime(field.value.strip())
                        elif "ออกงาน" in field.name:
                            check_out_time = format_datetime(field.value.strip())

            # ✅ ใช้ Regex หากดึงจาก Embed ไม่ได้
            if not all([name, steam_id, check_in_time, check_out_time]):
                pattern = r"ชื่อ\s*(.+?)\s*ไอดี\s*steam:(\S+)\s*เวลาเข้างาน\s*(?:\S+\s-\s)?([\d/]+\s[\d:]+)\s*เวลาออกงาน\s*(?:\S+\s-\s)?([\d/]+\s[\d:]+)"
                match = re.search(pattern, content, re.DOTALL | re.MULTILINE | re.IGNORECASE)

                if match:
                    name = match.group(1).strip("`").strip()
                    steam_id = match.group(2).strip()
                    check_in_time = format_datetime(match.group(3).strip())
                    check_out_time = format_datetime(match.group(4).strip())

            if all([name, steam_id, check_in_time, check_out_time]):
                logging.info(f"📌 บันทึกข้อมูล: {name}, {steam_id}, {check_in_time}, {check_out_time}")

                if sheet:
                    try:
                        last_row = get_last_row()
                        if last_row:
                            sheet.update(f"A{last_row}:D{last_row}", [[name, steam_id, check_in_time, check_out_time]])
                            logging.info("✅ ข้อมูลถูกบันทึกลง Google Sheets สำเร็จ")
                    except Exception as e:
                        logging.error(f"❌ Google Sheets error: {e}")
            else:
                logging.warning("⚠️ ข้อมูลไม่ครบถ้วน ไม่สามารถบันทึกได้!")
        except Exception as e:
            logging.error(f"❌ Error processing message: {e}")

    await bot.process_commands(message)

# ✅ ตั้งค่า Google Sheets
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
sheet = None

if GOOGLE_CREDENTIALS:
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(GOOGLE_CREDENTIALS), SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open("MedicDuty").worksheet("Log")
        logging.info("✅ Google Sheets setup completed.")
    except Exception as e:
        logging.error(f"❌ Google Sheets error: {e}")
else:
    logging.warning("⚠️ GOOGLE_CREDENTIALS not found.")

# ✅ ฟังก์ชันรัน Discord Bot
def run_discord_bot():
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if not DISCORD_BOT_TOKEN:
        logging.error("❌ DISCORD_BOT_TOKEN not found.")
        return
    
    try:
        logging.info("🚀 Starting Discord Bot...")
        bot.run(DISCORD_BOT_TOKEN)
    except discord.errors.LoginFailure:
        logging.error("❌ Invalid Discord Bot Token!")
    except Exception as e:
        logging.error(f"❌ Discord bot error: {e}")

# ✅ Keep-Alive
KEEP_ALIVE_URL = "https://discord-log-to-sheets-medic.onrender.com/health"

def keep_alive():
    while True:
        try:
            response = requests.get(KEEP_ALIVE_URL, timeout=5)
            if response.status_code == 200:
                logging.info("✅ Keep-alive successful.")
            else:
                logging.warning(f"⚠️ Keep-alive failed (Status: {response.status_code})")
        except Exception as e:
            logging.error(f"❌ Keep-alive error: {e}")
        time.sleep(45)

# ✅ Main
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    run_discord_bot()
