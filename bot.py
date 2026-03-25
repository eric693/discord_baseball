"""
bot.py — CPBL Discord Bot 主程式（Render 合一部署版）

Bot + Flask 後台跑在同一個 Render Web Service。
Flask 在獨立 thread 監聽 $PORT（Render 要求），
Discord Bot 在主 asyncio loop 運行。
"""
import asyncio, threading, logging, os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from database import init_db

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("cpbl")

COGS = [
    "cogs.welcome", "cogs.points", "cogs.shop", "cogs.betting",
    "cogs.tickets", "cogs.moderation", "cogs.election",
    "cogs.draft", "cogs.feed", "cogs.tags", "cogs.vip",
    "cogs.help",
]


def build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.members         = True   # Developer Portal 需開啟 Server Members Intent
    intents.message_content = True   # Developer Portal 需開啟 Message Content Intent
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
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="中職賽事"
            )
        )


def run_web():
    """
    在獨立 thread 啟動 Flask。
    Render Web Service 會注入 $PORT 環境變數，必須監聽這個 port，
    否則 Render 會認為服務沒有啟動而反覆重啟。
    """
    from web.app import create_app
    flask_app = create_app()
    port = int(os.getenv("PORT", os.getenv("WEB_PORT", 5000)))

    if os.getenv("RENDER"):
        # Render 環境：用 gunicorn（穩定，支援併發請求）
        import gunicorn.app.base

        class StandaloneApp(gunicorn.app.base.BaseApplication):
            def __init__(self, app, options=None):
                self.application = app
                self.options = options or {}
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        StandaloneApp(flask_app, {
            "bind":    f"0.0.0.0:{port}",
            "workers": 2,
            "timeout": 120,
            "loglevel": "info",
        }).run()
    else:
        # 本機開發：直接用 Flask dev server
        flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


async def main():
    init_db()

    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    log.info(f"Web admin started on port {os.getenv('PORT', os.getenv('WEB_PORT', 5000))}")

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN 未設定，請確認環境變數或 .env 檔案")

    bot = CPBLBot()
    try:
        async with bot:
            await bot.start(token)
    except discord.errors.PrivilegedIntentsRequired:
        log.error(
            "\n\n"
            "  錯誤：需要開啟 Privileged Intents，請依下列步驟操作：\n"
            "  1. 前往 https://discord.com/developers/applications\n"
            "  2. 選擇你的 Application → 左側選單「Bot」\n"
            "  3. 開啟「SERVER MEMBERS INTENT」\n"
            "  4. 開啟「MESSAGE CONTENT INTENT」\n"
            "  5. 點擊「Save Changes」後重新啟動\n\n"
        )
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())