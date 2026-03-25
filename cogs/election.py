"""
cogs/election.py — 版主選舉機制
"""
import discord, os
from discord.ext import commands
from discord import app_commands
from discord.ext import tasks
from datetime import datetime, timedelta
from database import db


class VoteView(discord.ui.View):
    def __init__(self, election_id, candidates):
        super().__init__(timeout=None)
        for c in candidates:
            b = discord.ui.Button(label=c["name"][:25], style=discord.ButtonStyle.primary, custom_id=f"vote_{election_id}_{c['id']}")
            b.callback = self._make_cb(election_id, c["id"], c["name"])
            self.add_item(b)

    def _make_cb(self, eid, cid, cname):
        async def cb(itx: discord.Interaction):
            voter = str(itx.user.id)
            with db() as c:
                if not c.execute("SELECT id FROM elections WHERE id=? AND status='active'", (eid,)).fetchone():
                    return await itx.response.send_message("選舉已結束。", ephemeral=True)
                if c.execute("SELECT id FROM election_votes WHERE election_id=? AND voter_id=?", (eid, voter)).fetchone():
                    return await itx.response.send_message("你已投過票了。", ephemeral=True)
                c.execute("INSERT INTO election_votes(election_id,voter_id,candidate_id) VALUES(?,?,?)", (eid, voter, cid))
                c.execute("UPDATE candidates SET votes=votes+1 WHERE id=?", (cid,))
            await itx.response.send_message(f"已投票給 **{cname}**！", ephemeral=True)
        return cb


class Election(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_elections.start()

    def cog_unload(self):
        self.check_elections.cancel()

    @tasks.loop(minutes=5)
    async def check_elections(self):
        with db() as c:
            ended = c.execute("SELECT id FROM elections WHERE status='active' AND ends_at<=datetime('now')").fetchall()
        for e in ended:
            await self._settle(e["id"])

    @check_elections.before_loop
    async def before(self): await self.bot.wait_until_ready()

    async def _settle(self, eid):
        with db() as c:
            winner = c.execute("SELECT * FROM candidates WHERE election_id=? ORDER BY votes DESC LIMIT 1", (eid,)).fetchone()
            elec   = c.execute("SELECT * FROM elections WHERE id=?", (eid,)).fetchone()
            c.execute("UPDATE elections SET status='ended' WHERE id=?", (eid,))
        if not winner: return
        gid = os.getenv("GUILD_ID")
        if not gid: return
        guild = self.bot.get_guild(int(gid))
        if not guild: return
        rid = os.getenv("ROLE_MODERATOR")
        if rid and winner["discord_id"]:
            m = guild.get_member(int(winner["discord_id"]))
            if m:
                r = guild.get_role(int(rid))
                if r: await m.add_roles(r)
        ech_id = os.getenv("ELECTION_CHANNEL_ID")
        if ech_id:
            ch = guild.get_channel(int(ech_id))
            if ch:
                embed = discord.Embed(title=f"選舉結果：{elec['title']}", color=0xFFD700)
                embed.description = f"獲勝者：**{winner['name']}**\n得票：**{winner['votes']}**\n\n恭喜 <@{winner['discord_id']}> 成為新任版主！"
                await ch.send(embed=embed)

    @app_commands.command(name="開選舉", description="（管理員）開始版主選舉（報名期）")
    @app_commands.checks.has_permissions(administrator=True)
    async def open_election(self, itx: discord.Interaction, title: str, vote_duration_hours: int = 48):
        with db() as c:
            cur = c.execute("INSERT INTO elections(title) VALUES(?)", (title,))
            eid = cur.lastrowid
        embed = discord.Embed(title=f"選舉開始：{title}", color=0x5865F2)
        embed.description = (f"選舉 ID：**{eid}**\n\n"
                             f"想參選版主的人請使用 `/參選 {eid}` 報名！\n"
                             f"管理員準備好後使用 `/啟動投票 {eid} {vote_duration_hours}` 開始投票。")
        await itx.response.send_message(embed=embed)

    @app_commands.command(name="參選", description="報名版主選舉")
    async def register(self, itx: discord.Interaction, election_id: int):
        uid = str(itx.user.id)
        with db() as c:
            if not c.execute("SELECT id FROM elections WHERE id=? AND status='accepting_candidates'", (election_id,)).fetchone():
                return await itx.response.send_message("找不到可報名的選舉。", ephemeral=True)
            if c.execute("SELECT id FROM candidates WHERE election_id=? AND discord_id=?", (election_id, uid)).fetchone():
                return await itx.response.send_message("你已報名此選舉。", ephemeral=True)
            c.execute("INSERT INTO candidates(election_id,discord_id,name) VALUES(?,?,?)", (election_id, uid, itx.user.display_name))
        await itx.response.send_message(f"已成功報名選舉 #{election_id}！等待管理員啟動投票。", ephemeral=True)

    @app_commands.command(name="啟動投票", description="（管理員）正式啟動投票")
    @app_commands.checks.has_permissions(administrator=True)
    async def activate(self, itx: discord.Interaction, election_id: int, hours: int = 48):
        ends = (datetime.utcnow() + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        with db() as c:
            elec = c.execute("SELECT * FROM elections WHERE id=?", (election_id,)).fetchone()
            cands = c.execute("SELECT * FROM candidates WHERE election_id=?", (election_id,)).fetchall()
            c.execute("UPDATE elections SET status='active',ends_at=? WHERE id=?", (ends, election_id))
        if not cands: return await itx.response.send_message("目前沒有候選人。", ephemeral=True)
        embed = discord.Embed(title=f"版主選舉：{elec['title']}", color=0xFFD700)
        embed.description = f"投票截止：**{ends}** (UTC)\n\n每人只能投一票，點下方按鈕投票！"
        for c_ in cands:
            embed.add_field(name=c_["name"], value=f"<@{c_['discord_id']}>", inline=True)
        view = VoteView(election_id, list(cands))
        ech_id = os.getenv("ELECTION_CHANNEL_ID")
        if ech_id:
            ch = itx.guild.get_channel(int(ech_id))
            if ch: await ch.send(embed=embed, view=view)
        await itx.response.send_message("投票已啟動！", ephemeral=True)

    @app_commands.command(name="選舉票數", description="查看目前選舉票數")
    async def results(self, itx: discord.Interaction, election_id: int):
        with db() as c:
            elec  = c.execute("SELECT * FROM elections WHERE id=?", (election_id,)).fetchone()
            cands = c.execute("SELECT * FROM candidates WHERE election_id=? ORDER BY votes DESC", (election_id,)).fetchall()
        if not elec: return await itx.response.send_message("找不到此選舉。", ephemeral=True)
        embed = discord.Embed(title=f"選舉票數：{elec['title']}", description=f"狀態：{elec['status']}", color=0x5865F2)
        for i, c_ in enumerate(cands):
            embed.add_field(name=f"{i+1}. {c_['name']}", value=f"{c_['votes']} 票", inline=True)
        await itx.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Election(bot))
