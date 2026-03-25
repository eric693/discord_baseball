"""
cogs/draft.py — CPBL 模擬選秀遊戲模組
"""
import discord, os, io
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from database import db

_timers: dict[int, datetime] = {}   # session_id -> deadline


class PlayerSelect(discord.ui.Select):
    def __init__(self, session_id, team_id, players):
        self.session_id = session_id
        self.team_id    = team_id
        opts = [discord.SelectOption(
            label=p["name"][:25],
            description=f"{p['position']} | {p['team_origin']}",
            value=str(p["id"])
        ) for p in players if not p["drafted_by"]][:25]
        super().__init__(placeholder="選擇你要選的球員", options=opts or [discord.SelectOption(label="無可選球員", value="none")])

    async def callback(self, itx: discord.Interaction):
        if self.values[0] == "none":
            return await itx.response.send_message("目前沒有可選球員。", ephemeral=True)
        pid = int(self.values[0])
        sid, tid = self.session_id, self.team_id
        with db() as c:
            sess  = c.execute("SELECT * FROM draft_sessions WHERE id=? AND status='active'", (sid,)).fetchone()
            if not sess: return await itx.response.send_message("選秀已結束。", ephemeral=True)
            team  = c.execute("SELECT * FROM draft_teams WHERE id=?", (tid,)).fetchone()
            if str(team["gm_discord_id"]) != str(itx.user.id):
                return await itx.response.send_message("現在不是你的回合。", ephemeral=True)
            player = c.execute("SELECT * FROM draft_players WHERE id=? AND session_id=? AND drafted_by IS NULL", (pid, sid)).fetchone()
            if not player: return await itx.response.send_message("該球員已被選走。", ephemeral=True)
            pick_no = c.execute("SELECT COUNT(*) as n FROM draft_players WHERE session_id=? AND drafted_by IS NOT NULL", (sid,)).fetchone()["n"] + 1
            c.execute("UPDATE draft_players SET drafted_by=?,pick_number=? WHERE id=?", (tid, pick_no, pid))
            teams = c.execute("SELECT * FROM draft_teams WHERE session_id=? ORDER BY pick_order", (sid,)).fetchall()
            curr_order  = team["pick_order"]
            next_order  = (curr_order % len(teams)) + 1
            c.execute("UPDATE draft_sessions SET current_pick=? WHERE id=?", (next_order, sid))
            remaining   = c.execute("SELECT * FROM draft_players WHERE session_id=? AND drafted_by IS NULL", (sid,)).fetchall()
            next_team   = next((t for t in teams if t["pick_order"] == next_order), None)

        _timers.pop(sid, None)
        embed = discord.Embed(title=f"第 {pick_no} 順位選秀", color=0x00C851)
        embed.add_field(name="隊伍", value=team["team_name"], inline=True)
        embed.add_field(name="球員", value=player["name"], inline=True)
        embed.add_field(name="位置", value=player["position"] or "-", inline=True)
        await itx.response.send_message(embed=embed)

        if not remaining:
            # Draft is complete
            with db() as c:
                c.execute("UPDATE draft_sessions SET status='completed' WHERE id=?", (sid,))
            draft_ch_id = os.getenv("DRAFT_CHANNEL_ID")
            if draft_ch_id:
                ch = itx.guild.get_channel(int(draft_ch_id))
                if ch:
                    await ch.send("**選秀結束！** 使用 `/選秀結果` 查看各隊完整陣容。")
            return

        if next_team and next_team["gm_discord_id"]:
            draft_ch_id = os.getenv("DRAFT_CHANNEL_ID")
            if draft_ch_id:
                ch = itx.guild.get_channel(int(draft_ch_id))
                if ch:
                    deadline = datetime.utcnow() + timedelta(seconds=sess["time_per_pick"])
                    _timers[sid] = deadline
                    view = discord.ui.View(timeout=None)
                    view.add_item(PlayerSelect(sid, next_team["id"], list(remaining)))
                    mins = sess["time_per_pick"] // 60
                    await ch.send(
                        content=f'<@{next_team["gm_discord_id"]}> 換 **{next_team["team_name"]}** 選了！限時 **{mins}** 分鐘。',
                        view=view
                    )


class Draft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timer_check.start()

    def cog_unload(self):
        self.timer_check.cancel()

    @tasks.loop(seconds=30)
    async def timer_check(self):
        now = datetime.utcnow()
        for sid, deadline in list(_timers.items()):
            if now >= deadline:
                _timers.pop(sid, None)
                await self._auto_skip(sid)

    @timer_check.before_loop
    async def before(self): await self.bot.wait_until_ready()

    async def _auto_skip(self, sid: int):
        with db() as c:
            sess  = c.execute("SELECT * FROM draft_sessions WHERE id=? AND status='active'", (sid,)).fetchone()
            if not sess: return
            teams = c.execute("SELECT * FROM draft_teams WHERE session_id=? ORDER BY pick_order", (sid,)).fetchall()
            curr  = sess["current_pick"]
            next_ = (curr % len(teams)) + 1
            c.execute("UPDATE draft_sessions SET current_pick=? WHERE id=?", (next_, sid))
            current_team = next((t for t in teams if t["pick_order"] == curr), None)
        gid = os.getenv("GUILD_ID"); dch = os.getenv("DRAFT_CHANNEL_ID")
        if not gid or not dch: return
        guild = self.bot.get_guild(int(gid))
        if not guild: return
        ch = guild.get_channel(int(dch))
        if ch and current_team:
            await ch.send(f'**{current_team["team_name"]}** 超時未選，自動跳過回合。')

    # ── Admin setup commands ───────────────────────────────────────────────

    @app_commands.command(name="新增選秀", description="（管理員）建立新選秀賽事")
    @app_commands.checks.has_permissions(administrator=True)
    async def create(self, itx: discord.Interaction, title: str, rounds: int = 3, time_per_pick: int = 180):
        with db() as c:
            cur = c.execute("INSERT INTO draft_sessions(title,rounds,time_per_pick) VALUES(?,?,?)", (title, rounds, time_per_pick))
            sid = cur.lastrowid
        await itx.response.send_message(
            f"選秀 **{title}** 已建立（ID：{sid}）\n回合數：{rounds} | 限時：{time_per_pick//60} 分鐘\n\n"
            f"接著使用 `/新增選秀隊伍` 設定各隊 GM，再用 `/匯入球員 {sid}` 匯入球員清單。", ephemeral=True)

    @app_commands.command(name="新增選秀隊伍", description="（管理員）新增選秀隊伍並指派 GM")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_team(self, itx: discord.Interaction, session_id: int, team_name: str, gm: discord.Member, pick_order: int):
        with db() as c:
            c.execute("INSERT INTO draft_teams(session_id,team_name,gm_discord_id,pick_order) VALUES(?,?,?,?)",
                      (session_id, team_name, str(gm.id), pick_order))
        await itx.response.send_message(f"隊伍 **{team_name}** 已加入（GM：{gm.mention}，順位：{pick_order}）", ephemeral=True)

    @app_commands.command(name="匯入球員", description="（管理員）匯入球員\n格式每行：姓名,位置,母隊（以換行分隔）")
    @app_commands.checks.has_permissions(administrator=True)
    async def import_players(self, itx: discord.Interaction, session_id: int, csv_data: str):
        lines = [l.strip() for l in csv_data.strip().split("\n") if l.strip()]
        count = 0
        with db() as c:
            for line in lines:
                parts = [p.strip() for p in line.split(",")]
                if not parts[0]: continue
                c.execute("INSERT INTO draft_players(session_id,name,position,team_origin) VALUES(?,?,?,?)",
                          (session_id, parts[0], parts[1] if len(parts)>1 else "", parts[2] if len(parts)>2 else ""))
                count += 1
        await itx.response.send_message(f"成功匯入 **{count}** 位球員至選秀 #{session_id}。", ephemeral=True)

    @app_commands.command(name="開始選秀", description="（管理員）正式啟動選秀")
    @app_commands.checks.has_permissions(administrator=True)
    async def start(self, itx: discord.Interaction, session_id: int):
        with db() as c:
            sess    = c.execute("SELECT * FROM draft_sessions WHERE id=? AND status='setup'", (session_id,)).fetchone()
            if not sess: return await itx.response.send_message("找不到此選秀或已啟動。", ephemeral=True)
            teams   = c.execute("SELECT * FROM draft_teams WHERE session_id=? ORDER BY pick_order", (session_id,)).fetchall()
            players = c.execute("SELECT * FROM draft_players WHERE session_id=? AND drafted_by IS NULL", (session_id,)).fetchall()
            c.execute("UPDATE draft_sessions SET status='active',current_pick=1 WHERE id=?", (session_id,))
        if not teams: return await itx.response.send_message("請先新增選秀隊伍。", ephemeral=True)
        first = teams[0]
        embed = discord.Embed(title=f"選秀開始：{sess['title']}", color=0x5865F2)
        embed.description = (f"共 **{len(teams)}** 隊 | **{len(players)}** 位球員 | 每回合限時 **{sess['time_per_pick']//60}** 分鐘")
        for t in teams:
            embed.add_field(name=f"順位 {t['pick_order']}：{t['team_name']}", value=f"GM：<@{t['gm_discord_id']}>", inline=True)
        dch_id = os.getenv("DRAFT_CHANNEL_ID")
        if dch_id:
            ch = itx.guild.get_channel(int(dch_id))
            if ch:
                view = discord.ui.View(timeout=None)
                view.add_item(PlayerSelect(session_id, first["id"], list(players)))
                deadline = datetime.utcnow() + timedelta(seconds=sess["time_per_pick"])
                _timers[session_id] = deadline
                await ch.send(
                    content=f'<@{first["gm_discord_id"]}> 選秀開始！**{first["team_name"]}** 有 **{sess["time_per_pick"]//60}** 分鐘進行第一順位選秀。',
                    embed=embed, view=view)
        await itx.response.send_message("選秀已啟動！", ephemeral=True)

    @app_commands.command(name="選秀結果", description="查看選秀完整結果")
    async def results(self, itx: discord.Interaction, session_id: int):
        await itx.response.defer()
        with db() as c:
            sess  = c.execute("SELECT * FROM draft_sessions WHERE id=?", (session_id,)).fetchone()
            picks = c.execute(
                "SELECT p.*,t.team_name FROM draft_players p JOIN draft_teams t ON p.drafted_by=t.id "
                "WHERE p.session_id=? AND p.drafted_by IS NOT NULL ORDER BY p.pick_number",
                (session_id,)).fetchall()
        if not sess: return await itx.followup.send("找不到此選秀。")
        embed = discord.Embed(title=f"選秀結果：{sess['title']}", color=0xFFD700)
        rosters: dict[str, list[str]] = {}
        for p in picks:
            rosters.setdefault(p["team_name"], []).append(f"#{p['pick_number']} {p['name']} ({p['position'] or '-'})")
        for team_name, roster in rosters.items():
            embed.add_field(name=team_name, value="\n".join(roster), inline=True)
        await itx.followup.send(embed=embed)

    @app_commands.command(name="選秀球員列表", description="查看當前選秀可選球員")
    async def player_list(self, itx: discord.Interaction, session_id: int):
        with db() as c:
            players = c.execute(
                "SELECT name,position,team_origin FROM draft_players WHERE session_id=? AND drafted_by IS NULL ORDER BY id",
                (session_id,)).fetchall()
        if not players: return await itx.response.send_message("沒有可選球員了。", ephemeral=True)
        lines = [f"`{i+1}.` **{p['name']}** — {p['position'] or '-'} | {p['team_origin'] or '-'}" for i, p in enumerate(players)]
        # Split into chunks if too long
        chunk, chunks = [], []
        for l in lines:
            if sum(len(x) for x in chunk) + len(l) > 900:
                chunks.append("\n".join(chunk)); chunk = [l]
            else:
                chunk.append(l)
        if chunk: chunks.append("\n".join(chunk))
        embeds = []
        for i, ch in enumerate(chunks):
            e = discord.Embed(title=f"可選球員列表（{i+1}/{len(chunks)}）", description=ch, color=0x5865F2)
            embeds.append(e)
        await itx.response.send_message(embeds=embeds[:10])


async def setup(bot):
    await bot.add_cog(Draft(bot))
