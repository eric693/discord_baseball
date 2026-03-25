"""
bot.py — CPBL Discord Bot 主程式
啟動方式: python bot.py

必要條件（啟動前請先完成）：
  1. pip install -r requirements.txt
  2. 複製 .env.example 為 .env 並填入 DISCORD_TOKEN 等設定
  3. Discord Developer Portal → 你的 App → Bot →
       開啟 "Server Members Intent" 與 "Message Content Intent"
"""
import asyncio, threading, logging, os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from database import init_db

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("cpbl")

COGS = [
    "cogs.welcome", "cogs.points", "cogs.shop", "cogs.betting",
    "cogs.tickets", "cogs.moderation", "cogs.election",
    "cogs.draft", "cogs.feed", "cogs.tags", "cogs.vip",
]


def build_intents() -> discord.Intents:
    """
    只開啟本 Bot 實際需要的 Intent，避免不必要的 Privileged Intent 問題。

    需要在 Developer Portal 手動開啟的 Privileged Intents：
      - Server Members Intent  (偵測成員加入/離開)
      - Message Content Intent (讀取訊息內容以觸發關鍵字/驗票)

    Presence Intent 本 Bot 不需要，保持關閉。
    """
    intents = discord.Intents.default()
    # ── Privileged（需在 Developer Portal 手動開啟）──
    intents.members          = True   # on_member_join、get_member
    intents.message_content  = True   # 讀取訊息內容（關鍵字、售票亭格式驗證）
    # ── 非 Privileged，default() 已包含 ──
    # intents.guilds           已開啟
    # intents.guild_messages   已開啟
    # intents.reactions        已開啟
    return intents


class CPBLBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=build_intents(),
            help_command=None,
        )

    async def setup_hook(self):
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"Loaded: {cog}")
            except Exception as e:
                log.error(f"Failed {cog}: {e}")
        await self.tree.sync()
        log.info("Slash commands synced")

    async def on_ready(self):
        log.info(f"Online: {self.user} ({self.user.id})")
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="中職賽事")
        )


def run_web():
    from web.app import create_app
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("WEB_PORT", 5000)),
        debug=False,
        use_reloader=False,
    )


async def main():
    init_db()
    threading.Thread(target=run_web, daemon=True).start()
    log.info(f"Web admin: http://0.0.0.0:{os.getenv('WEB_PORT', 5000)}")

    bot = CPBLBot()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN 未設定，請確認 .env 檔案")

    try:
        async with bot:
            await bot.start(token)
    except discord.errors.PrivilegedIntentsRequired:
        log.error(
            "\n\n"
            "  錯誤：Bot 需要開啟 Privileged Intents，請依下列步驟操作：\n"
            "  1. 前往 https://discord.com/developers/applications\n"
            "  2. 選擇你的 Application → 左側選單「Bot」\n"
            "  3. 往下捲動到「Privileged Gateway Intents」區塊\n"
            "  4. 開啟「SERVER MEMBERS INTENT」\n"
            "  5. 開啟「MESSAGE CONTENT INTENT」\n"
            "  6. 點擊「Save Changes」後重新啟動 bot.py\n\n"
        )
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
