"""
bot.py — CPBL Discord Bot 主程式
啟動方式: python bot.py
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


class CPBLBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"Loaded: {cog}")
            except Exception as e:
                log.error(f"Failed {cog}: {e}")
        await self.tree.sync()

    async def on_ready(self):
        log.info(f"Online: {self.user} ({self.user.id})")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="中職賽事"))


def run_web():
    from web.app import create_app
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("WEB_PORT", 5000)), debug=False, use_reloader=False)


async def main():
    init_db()
    threading.Thread(target=run_web, daemon=True).start()
    log.info(f"Web admin: http://0.0.0.0:{os.getenv('WEB_PORT', 5000)}")
    bot = CPBLBot()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN 未設定")
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
