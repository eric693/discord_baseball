"""
cogs/points.py — 點數系統：簽到、賺取、查詢、轉點
"""
import discord, os, time
from discord.ext import commands
from discord import app_commands
from datetime import date
from database import db

CHECKIN_PTS = int(os.getenv("DAILY_CHECKIN_POINTS", 10))
POST_PTS    = int(os.getenv("POST_POINTS", 2))
LIKE_PTS    = int(os.getenv("LIKE_RECEIVED_POINTS", 5))
COOLDOWN    = int(os.getenv("POST_COOLDOWN_SECONDS", 300))
_post_cd: dict[str, float] = {}


# ── helpers (imported by other cogs) ──────────────────────────────────────
def add_points(discord_id: str, amount: int, reason: str):
    with db() as c:
        c.execute("UPDATE members SET points=points+?,total_earned=total_earned+? WHERE discord_id=?",
                  (amount, max(0, amount), discord_id))
        c.execute("INSERT INTO point_transactions(discord_id,amount,reason) VALUES(?,?,?)",
                  (discord_id, amount, reason))


def deduct_points(discord_id: str, amount: int, reason: str) -> bool:
    with db() as c:
        row = c.execute("SELECT points FROM members WHERE discord_id=?", (discord_id,)).fetchone()
        if not row or row["points"] < amount:
            return False
        c.execute("UPDATE members SET points=points-? WHERE discord_id=?", (amount, discord_id))
        c.execute("INSERT INTO point_transactions(discord_id,amount,reason) VALUES(?,?,?)",
                  (discord_id, -amount, reason))
        return True


def get_balance(discord_id: str) -> int:
    with db() as c:
        row = c.execute("SELECT points FROM members WHERE discord_id=?", (discord_id,)).fetchone()
        return row["points"] if row else 0


# ── Cog ───────────────────────────────────────────────────────────────────
class Points(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _ensure(self, m: discord.Member):
        with db() as c:
            c.execute("INSERT OR IGNORE INTO members(discord_id,username) VALUES(?,?)", (str(m.id), str(m)))

    @app_commands.command(name="簽到", description="每日簽到，領取點數")
    async def checkin(self, itx: discord.Interaction):
        self._ensure(itx.user)
        uid = str(itx.user.id)
        today = str(date.today())
        with db() as c:
            if c.execute("SELECT id FROM checkins WHERE discord_id=? AND date=?", (uid, today)).fetchone():
                return await itx.response.send_message(
                    embed=discord.Embed(title="今日已簽到", description=f"明天再來！目前點數：**{get_balance(uid)}**", color=0xFFA500),
                    ephemeral=True)
            c.execute("INSERT INTO checkins(discord_id,date) VALUES(?,?)", (uid, today))
        add_points(uid, CHECKIN_PTS, "每日簽到")
        with db() as c:
            c.execute("UPDATE members SET last_active=datetime('now') WHERE discord_id=?", (uid,))
        await itx.response.send_message(
            embed=discord.Embed(title="簽到成功", description=f"獲得 **{CHECKIN_PTS}** 點！目前餘額：**{get_balance(uid)}**", color=0x00C851))

    @app_commands.command(name="點數", description="查詢自己或他人的點數")
    async def check_pts(self, itx: discord.Interaction, member: discord.Member = None):
        target = member or itx.user
        self._ensure(target)
        uid = str(target.id)
        with db() as c:
            row = c.execute("SELECT points,total_earned,credit_score FROM members WHERE discord_id=?", (uid,)).fetchone()
        embed = discord.Embed(title=f"{target.display_name} 的點數資料", color=0x5865F2)
        embed.add_field(name="目前餘額", value=f"{row['points']} 點", inline=True)
        embed.add_field(name="累計獲得", value=f"{row['total_earned']} 點", inline=True)
        embed.add_field(name="信用評分", value=str(row["credit_score"]), inline=True)
        await itx.response.send_message(embed=embed)

    @app_commands.command(name="點數紀錄", description="查詢最近 10 筆點數紀錄")
    async def history(self, itx: discord.Interaction):
        uid = str(itx.user.id)
        with db() as c:
            rows = c.execute(
                "SELECT amount,reason,created_at FROM point_transactions WHERE discord_id=? ORDER BY created_at DESC LIMIT 10",
                (uid,)).fetchall()
        if not rows:
            return await itx.response.send_message("目前沒有點數紀錄。", ephemeral=True)
        lines = [f"`{r['created_at'][:10]}` {'+'if r['amount']>0 else ''}{r['amount']}點 — {r['reason']}" for r in rows]
        await itx.response.send_message(
            embed=discord.Embed(title="最近 10 筆點數紀錄", description="\n".join(lines), color=0x5865F2),
            ephemeral=True)

    @app_commands.command(name="排行榜", description="點數排行榜 Top 10")
    async def leaderboard(self, itx: discord.Interaction):
        with db() as c:
            rows = c.execute("SELECT username,points FROM members ORDER BY points DESC LIMIT 10").fetchall()
        medals = ["1.", "2.", "3."]
        lines = [f"{medals[i] if i<3 else f'{i+1}.'} **{r['username']}** — {r['points']} 點" for i, r in enumerate(rows)]
        await itx.response.send_message(
            embed=discord.Embed(title="點數排行榜 Top 10", description="\n".join(lines), color=0xFFD700))

    @app_commands.command(name="轉點", description="轉移點數給其他玩家")
    async def transfer(self, itx: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0: return await itx.response.send_message("金額須大於 0。", ephemeral=True)
        if member.id == itx.user.id: return await itx.response.send_message("不能轉給自己。", ephemeral=True)
        self._ensure(itx.user); self._ensure(member)
        uid = str(itx.user.id)
        if not deduct_points(uid, amount, f"轉點給 {member}"):
            return await itx.response.send_message("點數不足。", ephemeral=True)
        add_points(str(member.id), amount, f"收到來自 {itx.user} 的轉點")
        await itx.response.send_message(
            embed=discord.Embed(title="轉點成功", description=f"已轉 **{amount}** 點給 {member.mention}\n餘額：**{get_balance(uid)}** 點", color=0x00C851))

    @app_commands.command(name="給點", description="（管理員）手動給予點數")
    @app_commands.checks.has_permissions(administrator=True)
    async def give(self, itx: discord.Interaction, member: discord.Member, amount: int, reason: str = "管理員給點"):
        self._ensure(member)
        add_points(str(member.id), amount, reason)
        await itx.response.send_message(f"已給予 {member.mention} **{amount}** 點（{reason}）", ephemeral=True)

    @app_commands.command(name="扣點", description="（管理員）手動扣除點數")
    @app_commands.checks.has_permissions(administrator=True)
    async def take(self, itx: discord.Interaction, member: discord.Member, amount: int, reason: str = "管理員扣點"):
        self._ensure(member)
        if not deduct_points(str(member.id), amount, reason):
            return await itx.response.send_message("該玩家點數不足。", ephemeral=True)
        await itx.response.send_message(f"已從 {member.mention} 扣除 **{amount}** 點（{reason}）", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        uid = str(message.author.id)
        now = time.time()
        if now - _post_cd.get(uid, 0) < COOLDOWN: return
        _post_cd[uid] = now
        with db() as c:
            c.execute("INSERT OR IGNORE INTO members(discord_id,username) VALUES(?,?)", (uid, str(message.author)))
            c.execute("UPDATE members SET last_active=datetime('now') WHERE discord_id=?", (uid,))
        add_points(uid, POST_PTS, "頻道發言")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot: return
        if str(reaction.emoji) != "\U0001f44d": return
        author = reaction.message.author
        if author.bot or author.id == user.id: return
        with db() as c:
            c.execute("INSERT OR IGNORE INTO members(discord_id,username) VALUES(?,?)", (str(author.id), str(author)))
        add_points(str(author.id), LIKE_PTS, "發言被按讚")


async def setup(bot):
    await bot.add_cog(Points(bot))
