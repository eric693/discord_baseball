"""
cogs/moderation.py — 版主執法指令、關鍵字回應、工單
"""
import discord, os, datetime
from discord.ext import commands
from discord import app_commands
from database import db
from cogs.points import deduct_points


def is_mod(member: discord.Member) -> bool:
    if member.guild_permissions.administrator: return True
    rid = os.getenv("ROLE_MODERATOR")
    if rid:
        r = member.guild.get_role(int(rid))
        if r and r in member.roles: return True
    return False


class TicketModal(discord.ui.Modal, title="建立客服工單"):
    category = discord.ui.TextInput(label="類別", placeholder="商城兌換 / 黃牛檢舉 / 其他")
    title_in = discord.ui.TextInput(label="標題", max_length=100)
    desc     = discord.ui.TextInput(label="詳細說明", style=discord.TextStyle.paragraph, required=False)

    async def on_submit(self, itx: discord.Interaction):
        uid = str(itx.user.id)
        with db() as c:
            cur = c.execute("INSERT INTO support_tickets(discord_id,category,title,description) VALUES(?,?,?,?)",
                            (uid, self.category.value, self.title_in.value, self.desc.value))
            tid = cur.lastrowid
        await itx.response.send_message(
            embed=discord.Embed(title=f"工單 #{tid} 已建立", description=f"類別：{self.category.value}\n標題：{self.title_in.value}\n\n管理員將盡快處理。", color=0x5865F2),
            ephemeral=True)
        log_id = os.getenv("LOG_CHANNEL_ID")
        if log_id:
            ch = itx.guild.get_channel(int(log_id))
            if ch:
                await ch.send(embed=discord.Embed(title=f"新工單 #{tid}", description=f"提交者：{itx.user.mention}\n類別：{self.category.value}\n標題：{self.title_in.value}\n說明：{self.desc.value or '（無）'}", color=0xFFA500))


class Moderation(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="警告", description="（版主）對成員發出警告")
    async def warn(self, itx: discord.Interaction, member: discord.Member, reason: str):
        if not is_mod(itx.user): return await itx.response.send_message("你沒有執法權限。", ephemeral=True)
        uid = str(member.id)
        with db() as c:
            c.execute("INSERT INTO violations(discord_id,type,detail,mod_id) VALUES(?,?,?,?)", (uid, "warning", reason, str(itx.user.id)))
            cnt = c.execute("SELECT COUNT(*) as n FROM violations WHERE discord_id=? AND type='warning'", (uid,)).fetchone()["n"]
            c.execute("UPDATE members SET credit_score=MAX(credit_score-5,0) WHERE discord_id=?", (uid,))
        await itx.response.send_message(embed=discord.Embed(title="警告已記錄", description=f"{member.mention} 第 {cnt} 次警告\n原因：{reason}", color=0xFFA500))
        try: await member.send(f"你收到第 {cnt} 次警告，原因：{reason}")
        except discord.Forbidden: pass

    @app_commands.command(name="禁言", description="（版主）禁言成員")
    async def mute(self, itx: discord.Interaction, member: discord.Member, minutes: int, reason: str = "違規"):
        if not is_mod(itx.user): return await itx.response.send_message("你沒有執法權限。", ephemeral=True)
        try:
            await member.timeout(datetime.timedelta(minutes=minutes), reason=reason)
        except discord.Forbidden:
            return await itx.response.send_message("無法禁言此成員（權限不足）。", ephemeral=True)
        uid = str(member.id)
        with db() as c:
            c.execute("INSERT INTO violations(discord_id,type,detail,mod_id) VALUES(?,?,?,?)", (uid, "mute", f"{minutes}分鐘|{reason}", str(itx.user.id)))
        await itx.response.send_message(embed=discord.Embed(title="禁言已執行", description=f"{member.mention} 禁言 **{minutes}** 分鐘\n原因：{reason}", color=0xFF6600))

    @app_commands.command(name="解禁", description="（版主）解除禁言")
    async def unmute(self, itx: discord.Interaction, member: discord.Member):
        if not is_mod(itx.user): return await itx.response.send_message("你沒有執法權限。", ephemeral=True)
        await member.timeout(None)
        await itx.response.send_message(f"已解除 {member.mention} 的禁言。")

    @app_commands.command(name="違規查詢", description="（版主）查詢成員違規紀錄")
    async def violations(self, itx: discord.Interaction, member: discord.Member):
        if not is_mod(itx.user): return await itx.response.send_message("你沒有查詢權限。", ephemeral=True)
        uid = str(member.id)
        with db() as c:
            rows = c.execute("SELECT type,detail,created_at FROM violations WHERE discord_id=? ORDER BY created_at DESC LIMIT 15", (uid,)).fetchall()
        if not rows: return await itx.response.send_message(f"{member.mention} 沒有違規紀錄。", ephemeral=True)
        lines = [f"`{r['created_at'][:10]}` **{r['type']}** — {r['detail']}" for r in rows]
        await itx.response.send_message(embed=discord.Embed(title=f"{member.display_name} 的違規紀錄", description="\n".join(lines), color=0xFF0000), ephemeral=True)

    @app_commands.command(name="工單", description="建立客服工單")
    async def create_ticket(self, itx: discord.Interaction):
        await itx.response.send_modal(TicketModal())

    @app_commands.command(name="關閉工單", description="（版主）關閉工單")
    async def close_ticket(self, itx: discord.Interaction, ticket_id: int, note: str = ""):
        if not is_mod(itx.user): return await itx.response.send_message("你沒有執法權限。", ephemeral=True)
        with db() as c:
            c.execute("UPDATE support_tickets SET status='closed',assigned_to=?,closed_at=datetime('now') WHERE id=?",
                      (str(itx.user.id), ticket_id))
        await itx.response.send_message(f"工單 #{ticket_id} 已關閉。{' 備註：'+note if note else ''}")

    @app_commands.command(name="工單列表", description="（版主）查看待處理工單")
    async def ticket_list(self, itx: discord.Interaction):
        if not is_mod(itx.user): return await itx.response.send_message("你沒有查詢權限。", ephemeral=True)
        with db() as c:
            rows = c.execute("SELECT id,discord_id,category,title,created_at FROM support_tickets WHERE status='open' ORDER BY created_at DESC LIMIT 20").fetchall()
        if not rows: return await itx.response.send_message("目前沒有待處理工單。", ephemeral=True)
        lines = [f"`#{r['id']}` [{r['category']}] **{r['title']}** — <@{r['discord_id']}> ({r['created_at'][:10]})" for r in rows]
        await itx.response.send_message(embed=discord.Embed(title="待處理工單", description="\n".join(lines), color=0x5865F2), ephemeral=True)

    @app_commands.command(name="設關鍵字", description="（管理員）設定迷因關鍵字自動回應")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_keyword(self, itx: discord.Interaction, trigger: str, response: str):
        with db() as c:
            c.execute("INSERT OR REPLACE INTO keywords(trigger,response) VALUES(?,?)", (trigger, response))
        await itx.response.send_message(f"關鍵字 `{trigger}` 已設定。", ephemeral=True)

    @app_commands.command(name="刪關鍵字", description="（管理員）刪除關鍵字")
    @app_commands.checks.has_permissions(administrator=True)
    async def del_keyword(self, itx: discord.Interaction, trigger: str):
        with db() as c:
            c.execute("DELETE FROM keywords WHERE trigger=?", (trigger,))
        await itx.response.send_message(f"關鍵字 `{trigger}` 已刪除。", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        content = message.content.lower()
        with db() as c:
            kws = c.execute("SELECT trigger,response FROM keywords WHERE is_active=1").fetchall()
        for kw in kws:
            if kw["trigger"].lower() in content:
                await message.channel.send(kw["response"])
                break


async def setup(bot):
    await bot.add_cog(Moderation(bot))
