"""
cogs/tickets.py — 售票亭：防詐格式驗證、信用評價、黑名單
"""
import discord, re, os
from discord.ext import commands
from discord import app_commands
from database import db
from cogs.points import add_points

REQUIRED = {
    "日期": r"\d{1,2}[/\-月]\d{1,2}",
    "票價": r"\d{3,}",
    "座位/區域": r"(內野|外野|本壘|一壘|三壘|看台|\d+[區排])",
}


def validate(content: str) -> list[str]:
    return [f for f, pat in REQUIRED.items() if not re.search(pat, content)]


class TicketModal(discord.ui.Modal, title="發布球票讓渡"):
    game_date    = discord.ui.TextInput(label="比賽日期", placeholder="例：5/15")
    home_team    = discord.ui.TextInput(label="主場球隊", placeholder="例：統一獅")
    away_team    = discord.ui.TextInput(label="客場球隊", placeholder="例：中信兄象")
    seat_info    = discord.ui.TextInput(label="座位（區域/排號/座號）", placeholder="例：內野一壘側 G排 23號")
    price_qty    = discord.ui.TextInput(label="票價 x 張數", placeholder="例：380 x 2")
    contact      = discord.ui.TextInput(label="聯絡方式", placeholder="Discord ID 或私訊")

    async def on_submit(self, itx: discord.Interaction):
        uid = str(itx.user.id)
        with db() as c:
            m = c.execute("SELECT is_banned FROM members WHERE discord_id=?", (uid,)).fetchone()
        if m and m["is_banned"]:
            return await itx.response.send_message("你目前在黑名單中，無法發布。", ephemeral=True)
        combined = f"{self.game_date.value} {self.seat_info.value} {self.price_qty.value}"
        missing  = validate(combined)
        if missing:
            return await itx.response.send_message(f"格式不完整，缺少：{'、'.join(missing)}，請重新填寫。", ephemeral=True)
        try:
            parts = self.price_qty.value.replace("X","x").split("x")
            price = int(re.sub(r"[^\d]","",parts[0]))
            qty   = int(parts[1].strip()) if len(parts)>1 else 1
        except:
            return await itx.response.send_message("票價 x 張數格式有誤，請用「380 x 2」格式。", ephemeral=True)
        with db() as c:
            cur = c.execute(
                "INSERT INTO ticket_listings(discord_id,game_date,team_home,team_away,seat_section,price,quantity,contact) VALUES(?,?,?,?,?,?,?,?)",
                (uid, self.game_date.value, self.home_team.value, self.away_team.value, self.seat_info.value, price, qty, self.contact.value))
            lid = cur.lastrowid
        embed = discord.Embed(title=f"球票讓渡 #{lid}", color=0x5865F2)
        embed.add_field(name="比賽", value=f"{self.home_team.value} vs {self.away_team.value}", inline=True)
        embed.add_field(name="日期", value=self.game_date.value, inline=True)
        embed.add_field(name="座位", value=self.seat_info.value, inline=False)
        embed.add_field(name="票價", value=f"{price} 元 x {qty} 張", inline=True)
        embed.add_field(name="聯絡", value=self.contact.value, inline=True)
        embed.set_footer(text=f"發布者：{itx.user} | /推薦 或 /檢舉 進行評價")
        await itx.response.send_message(embed=embed)


class Tickets(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        ch_id = os.getenv("TICKET_LISTING_CHANNEL_ID")
        if not ch_id or str(message.channel.id) != ch_id: return
        if message.content.startswith("/") or not message.content.strip(): return
        missing = validate(message.content)
        if not missing: return
        try: await message.delete()
        except discord.Forbidden: pass
        warn = (f"{message.author.mention} 球票發文格式不完整（缺少：{'、'.join(missing)}），已自動刪除。\n"
                "請使用 `/發票` 指令重新發布。")
        try: await message.author.send(warn)
        except discord.Forbidden:
            await message.channel.send(warn, delete_after=15)
        with db() as c:
            c.execute("INSERT OR IGNORE INTO members(discord_id,username) VALUES(?,?)", (str(message.author.id), str(message.author)))
            c.execute("INSERT INTO violations(discord_id,type,detail) VALUES(?,?,?)",
                      (str(message.author.id), "ticket_format", f"缺少：{', '.join(missing)}"))

    @app_commands.command(name="發票", description="發布球票讓渡資訊")
    async def post_ticket(self, itx: discord.Interaction):
        await itx.response.send_modal(TicketModal())

    @app_commands.command(name="推薦", description="對交易對象給予好評")
    async def recommend(self, itx: discord.Interaction, member: discord.Member, comment: str = ""):
        if member.id == itx.user.id: return await itx.response.send_message("不能評價自己。", ephemeral=True)
        rater, rated = str(itx.user.id), str(member.id)
        with db() as c:
            if c.execute("SELECT id FROM ratings WHERE rater_id=? AND rated_id=? AND created_at>datetime('now','-7 days')", (rater, rated)).fetchone():
                return await itx.response.send_message("7 天內已評價過此用戶。", ephemeral=True)
            c.execute("INSERT OR IGNORE INTO members(discord_id,username) VALUES(?,?)", (rated, str(member)))
            c.execute("INSERT INTO ratings(rater_id,rated_id,is_positive,comment) VALUES(?,?,1,?)", (rater, rated, comment))
            c.execute("UPDATE members SET credit_score=MIN(credit_score+5,200) WHERE discord_id=?", (rated,))
        add_points(rated, 3, f"收到 {itx.user} 的好評")
        await itx.response.send_message(embed=discord.Embed(title="評價已記錄", description=f"已給 {member.mention} 正評！信用分+5。", color=0x00C851))

    @app_commands.command(name="檢舉", description="檢舉球票詐騙或黃牛")
    async def report(self, itx: discord.Interaction, member: discord.Member, reason: str):
        rated = str(member.id)
        with db() as c:
            c.execute("INSERT OR IGNORE INTO members(discord_id,username) VALUES(?,?)", (rated, str(member)))
            c.execute("INSERT INTO violations(discord_id,type,detail,mod_id) VALUES(?,?,?,?)",
                      (rated, "scalper_report", reason, str(itx.user.id)))
            c.execute("UPDATE members SET credit_score=MAX(credit_score-10,0) WHERE discord_id=?", (rated,))
        await itx.response.send_message(embed=discord.Embed(title="檢舉已提交", description=f"已向管理員提交對 {member.mention} 的檢舉。\n原因：{reason}", color=0xFFA500), ephemeral=True)

    @app_commands.command(name="黑名單", description="（管理員）將用戶加入黑名單並禁言")
    @app_commands.checks.has_permissions(administrator=True)
    async def blacklist(self, itx: discord.Interaction, member: discord.Member, reason: str = "黃牛/詐騙"):
        import datetime
        uid = str(member.id)
        with db() as c:
            c.execute("UPDATE members SET is_banned=1 WHERE discord_id=?", (uid,))
            c.execute("INSERT INTO violations(discord_id,type,detail,mod_id) VALUES(?,?,?,?)", (uid, "blacklist", reason, str(itx.user.id)))
        bl_id = os.getenv("ROLE_BLACKLIST")
        if bl_id:
            r = itx.guild.get_role(int(bl_id))
            if r: await member.add_roles(r)
        try: await member.timeout(datetime.timedelta(days=28), reason=reason)
        except discord.Forbidden: pass
        await itx.response.send_message(embed=discord.Embed(title="黑名單執行完畢", description=f"{member.mention} 已被標記並禁言 28 天。\n原因：{reason}", color=0xFF0000))

    @app_commands.command(name="信用查詢", description="查詢用戶信用評分")
    async def credit(self, itx: discord.Interaction, member: discord.Member = None):
        target = member or itx.user
        uid = str(target.id)
        with db() as c:
            row = c.execute("SELECT credit_score,is_banned FROM members WHERE discord_id=?", (uid,)).fetchone()
            pos = c.execute("SELECT COUNT(*) as n FROM ratings WHERE rated_id=? AND is_positive=1", (uid,)).fetchone()["n"]
            neg = c.execute("SELECT COUNT(*) as n FROM violations WHERE discord_id=?", (uid,)).fetchone()["n"]
        if not row: return await itx.response.send_message("找不到用戶資料。", ephemeral=True)
        embed = discord.Embed(title=f"{target.display_name} 的信用資料", color=0xFF0000 if row["is_banned"] else 0x00C851)
        embed.add_field(name="信用評分", value=str(row["credit_score"]), inline=True)
        embed.add_field(name="好評數", value=str(pos), inline=True)
        embed.add_field(name="違規紀錄", value=str(neg), inline=True)
        if row["is_banned"]: embed.set_footer(text="此用戶目前在黑名單中")
        await itx.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
