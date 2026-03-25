"""
cogs/feed.py — 自動推播：YouTube 新影片 + PTT 棒球板情報/炸裂文
"""
import discord, os, hashlib, aiohttp, feedparser
from discord.ext import commands, tasks
from discord import app_commands
from database import db

PTT_TAGS   = ["[情報]", "[炸裂]", "[新聞]", "[討論]", "[閒聊]"]
PTT_RSS    = os.getenv("PTT_RSS_URL", "https://www.ptt.cc/rss/Baseball")
YT_KEY     = os.getenv("YOUTUBE_API_KEY", "")
YT_CHANNELS = [c.strip() for c in os.getenv("YT_CHANNEL_IDS", "").split(",") if c.strip()]


def _cached(source, ext_id) -> bool:
    with db() as c:
        return bool(c.execute("SELECT id FROM feed_cache WHERE source=? AND ext_id=?", (source, ext_id)).fetchone())


def _mark(source, ext_id):
    with db() as c:
        c.execute("INSERT OR IGNORE INTO feed_cache(source,ext_id) VALUES(?,?)", (source, ext_id))


class Feed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_ptt.start()
        if YT_KEY and YT_CHANNELS:
            self.check_youtube.start()

    def cog_unload(self):
        self.check_ptt.cancel()
        if YT_KEY and YT_CHANNELS:
            self.check_youtube.cancel()

    def _news_channel(self):
        ch_id = os.getenv("NEWS_CHANNEL_ID"); gid = os.getenv("GUILD_ID")
        if not ch_id or not gid: return None
        guild = self.bot.get_guild(int(gid))
        return guild.get_channel(int(ch_id)) if guild else None

    @tasks.loop(minutes=5)
    async def check_ptt(self):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(PTT_RSS, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status != 200: return
                    text = await r.text()
            feed = feedparser.parse(text)
            ch = self._news_channel()
            if not ch: return
            for entry in reversed(feed.entries[:15]):
                title = entry.get("title", "")
                link  = entry.get("link", "")
                if not any(tag in title for tag in PTT_TAGS): continue
                ext_id = hashlib.md5(link.encode()).hexdigest()
                if _cached("ptt", ext_id): continue
                _mark("ptt", ext_id)
                embed = discord.Embed(title=title[:256], url=link, color=0x00C851)
                embed.set_author(name="PTT 棒球板")
                summary = entry.get("summary", "")[:400]
                if summary: embed.description = summary
                embed.set_footer(text=entry.get("published", "")[:30])
                await ch.send(embed=embed)
        except Exception as e:
            print(f"[Feed] PTT error: {e}")

    @tasks.loop(minutes=5)
    async def check_youtube(self):
        ch = self._news_channel()
        if not ch: return
        try:
            async with aiohttp.ClientSession() as s:
                for yt_ch in YT_CHANNELS:
                    url = (f"https://www.googleapis.com/youtube/v3/search"
                           f"?key={YT_KEY}&channelId={yt_ch}&part=snippet&order=date&maxResults=3&type=video")
                    async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                        if r.status != 200: continue
                        data = await r.json()
                    for item in reversed(data.get("items", [])):
                        vid = item["id"].get("videoId", "")
                        if not vid: continue
                        if _cached("youtube", vid): continue
                        _mark("youtube", vid)
                        snip = item["snippet"]
                        embed = discord.Embed(
                            title=snip["title"][:256],
                            url=f"https://www.youtube.com/watch?v={vid}",
                            description=snip.get("description", "")[:300],
                            color=0xFF0000
                        )
                        thumb = snip.get("thumbnails", {}).get("high", {}).get("url")
                        if thumb: embed.set_image(url=thumb)
                        embed.set_author(name=snip.get("channelTitle", "YouTube"))
                        embed.set_footer(text=snip.get("publishedAt", "")[:10])
                        await ch.send(embed=embed)
        except Exception as e:
            print(f"[Feed] YouTube error: {e}")

    @check_ptt.before_loop
    @check_youtube.before_loop
    async def _before(self): await self.bot.wait_until_ready()

    @app_commands.command(name="推播測試", description="（管理員）手動觸發 PTT 推播")
    @app_commands.checks.has_permissions(administrator=True)
    async def manual_push(self, itx: discord.Interaction):
        await itx.response.send_message("正在觸發推播…", ephemeral=True)
        await self.check_ptt()


async def setup(bot):
    await bot.add_cog(Feed(bot))
