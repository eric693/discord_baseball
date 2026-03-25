"""
cogs/betting.py — 賭盤系統：開盤、下注、結算、關盤
"""
import discord, json, os
from discord.ext import commands
from discord import app_commands
from database import db
from cogs.points import add_points, deduct_points, get_balance

BET_MIN = int(os.getenv("BET_MIN", 10))
BET_MAX = int(os.getenv("BET_MAX", 5000))


class BetAmountModal(discord.ui.Modal, title="輸入投注金額"):
    amt = discord.ui.TextInput(label="投注點數", placeholder="輸入整數點數", max_length=6)

    def __init__(self, event_id, option, odds):
        super().__init__()
        self.event_id = event_id
        self.option   = option
        self.odds     = odds

    async def on_submit(self, itx: discord.Interaction):
        try:    amount = int(self.amt.value)
        except: return await itx.response.send_message("請輸入有效數字。", ephemeral=True)
        if not (BET_MIN <= amount <= BET_MAX):
            return await itx.response.send_message(f"投注需在 {BET_MIN}～{BET_MAX} 點之間。", ephemeral=True)
        uid = str(itx.user.id)
        if get_balance(uid) < amount:
            return await itx.response.send_message("點數不足。", ephemeral=True)
        with db() as c:
            ev = c.execute("SELECT * FROM bet_events WHERE id=? AND status='open'", (self.event_id,)).fetchone()
            if not ev: return await itx.response.send_message("賭盤已關閉。", ephemeral=True)
            if c.execute("SELECT id FROM bets WHERE event_id=? AND discord_id=?", (self.event_id, uid)).fetchone():
                return await itx.response.send_message("你已在此賭盤下注過。", ephemeral=True)
        if not deduct_points(uid, amount, f"賭盤下注：{ev['title']} - {self.option}"):
            return await itx.response.send_message("扣點失敗。", ephemeral=True)
        payout = int(amount * self.odds)
        with db() as c:
            c.execute("INSERT INTO bets(event_id,discord_id,option,amount,payout) VALUES(?,?,?,?,?)",
                      (self.event_id, uid, self.option, amount, payout))
        embed = discord.Embed(title="下注成功", color=0x00C851)
        embed.add_field(name="賭盤", value=ev["title"], inline=False)
        embed.add_field(name="選擇", value=self.option, inline=True)
        embed.add_field(name="投注", value=f"{amount} 點", inline=True)
        embed.add_field(name="賠率", value=f"{self.odds}x", inline=True)
        embed.add_field(name="若獲勝", value=f"{payout} 點", inline=True)
        embed.add_field(name="目前餘額", value=f"{get_balance(uid)} 點", inline=True)
        await itx.response.send_message(embed=embed, ephemeral=True)


class OptionSelect(discord.ui.Select):
    def __init__(self, event_id, options, odds):
        self.event_id = event_id
        self.odds_map = odds
        opts = [discord.SelectOption(label=o[:25], description=f"賠率 {odds.get(o,1.0)}x", value=o[:100]) for o in options]
        super().__init__(placeholder="選擇投注選項", options=opts)

    async def callback(self, itx: discord.Interaction):
        chosen = self.values[0]
        await itx.response.send_modal(BetAmountModal(self.event_id, chosen, self.odds_map.get(chosen, 1.0)))


class Betting(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="賭盤列表", description="查看開放中的賭盤")
    async def bet_list(self, itx: discord.Interaction):
        with db() as c:
            evs = c.execute("SELECT * FROM bet_events WHERE status='open' ORDER BY created_at DESC").fetchall()
        if not evs: return await itx.response.send_message("目前沒有開放中的賭盤。", ephemeral=True)
        embed = discord.Embed(title="開放中的賭盤", color=0xFFD700)
        for ev in evs:
            opts = json.loads(ev["options"]); odds = json.loads(ev["odds"])
            lines = [f"• {o} (賠率 {odds.get(o,1.0)}x)" for o in opts]
            embed.add_field(name=f"[#{ev['id']}] {ev['title']}", value="\n".join(lines), inline=False)
        await itx.response.send_message(embed=embed)

    @app_commands.command(name="下注", description="對賭盤下注")
    async def place_bet(self, itx: discord.Interaction, event_id: int):
        with db() as c:
            ev = c.execute("SELECT * FROM bet_events WHERE id=? AND status='open'", (event_id,)).fetchone()
        if not ev: return await itx.response.send_message("找不到此賭盤或已關閉。", ephemeral=True)
        opts = json.loads(ev["options"]); odds = json.loads(ev["odds"])
        embed = discord.Embed(title=ev["title"], description=ev["description"] or "", color=0xFFD700)
        embed.add_field(name="選項", value="\n".join(f"• {o} — 賠率 {odds.get(o,1.0)}x" for o in opts), inline=False)
        embed.set_footer(text=f"投注範圍：{BET_MIN}～{BET_MAX} 點 | 餘額：{get_balance(str(itx.user.id))} 點")
        view = discord.ui.View(timeout=120)
        view.add_item(OptionSelect(event_id, opts, odds))
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="我的下注", description="查看自己的下注記錄")
    async def my_bets(self, itx: discord.Interaction):
        uid = str(itx.user.id)
        with db() as c:
            rows = c.execute(
                "SELECT b.*,e.title FROM bets b JOIN bet_events e ON b.event_id=e.id WHERE b.discord_id=? ORDER BY b.created_at DESC LIMIT 10",
                (uid,)).fetchall()
        if not rows: return await itx.response.send_message("沒有下注紀錄。", ephemeral=True)
        st = {"pending":"等待結算","won":"獲勝","lost":"落敗","refunded":"退款"}
        lines = [f"`#{r['event_id']}` **{r['title'][:20]}** — {r['option']} ({r['amount']}→{r['payout']}點) {st.get(r['status'],r['status'])}" for r in rows]
        await itx.response.send_message(embed=discord.Embed(title="我的下注記錄", description="\n".join(lines), color=0x5865F2), ephemeral=True)

    # ── Admin ──────────────────────────────────────────────────────────────
    @app_commands.command(name="開盤", description="（管理員）開立新賭盤\n選項格式：主隊贏,客隊贏,平局\n賠率格式：1.5,2.0,3.0")
    @app_commands.checks.has_permissions(administrator=True)
    async def open_bet(self, itx: discord.Interaction, title: str, options: str, odds: str,
                       description: str = "", closes_at: str = None):
        opt_list  = [o.strip() for o in options.split(",")]
        odds_list = [float(o.strip()) for o in odds.split(",")]
        if len(opt_list) != len(odds_list):
            return await itx.response.send_message("選項與賠率數量不符。", ephemeral=True)
        opts_j = json.dumps(opt_list, ensure_ascii=False)
        odds_j = json.dumps(dict(zip(opt_list, odds_list)), ensure_ascii=False)
        with db() as c:
            cur = c.execute("INSERT INTO bet_events(title,description,options,odds,closes_at) VALUES(?,?,?,?,?)",
                            (title, description, opts_j, odds_j, closes_at))
            eid = cur.lastrowid
        embed = discord.Embed(title=f"賭盤已開立 #{eid}", description=title, color=0x00C851)
        embed.add_field(name="選項", value="\n".join(f"• {o} — {odds_list[i]}x" for i,o in enumerate(opt_list)))
        await itx.response.send_message(embed=embed)

    @app_commands.command(name="結算", description="（管理員）結算賭盤並派彩")
    @app_commands.checks.has_permissions(administrator=True)
    async def settle(self, itx: discord.Interaction, event_id: int, result: str):
        await itx.response.defer()
        with db() as c:
            ev = c.execute("SELECT * FROM bet_events WHERE id=? AND status='open'", (event_id,)).fetchone()
            if not ev: return await itx.followup.send("找不到此賭盤。")
            if result not in json.loads(ev["options"]):
                return await itx.followup.send(f"無效結果，有效選項：{ev['options']}")
            winners = c.execute("SELECT * FROM bets WHERE event_id=? AND option=? AND status='pending'", (event_id, result)).fetchall()
            losers  = c.execute("SELECT * FROM bets WHERE event_id=? AND option!=? AND status='pending'", (event_id, result)).fetchall()
            for b in winners:
                add_points(b["discord_id"], b["payout"], f"賭盤獲勝：{ev['title']}")
                c.execute("UPDATE bets SET status='won' WHERE id=?", (b["id"],))
            for b in losers:
                c.execute("UPDATE bets SET status='lost' WHERE id=?", (b["id"],))
            c.execute("UPDATE bet_events SET status='settled',result=?,settled_at=datetime('now') WHERE id=?", (result, event_id))
        embed = discord.Embed(title=f"賭盤結算完畢 #{event_id}", color=0x00C851)
        embed.add_field(name="賭盤", value=ev["title"], inline=False)
        embed.add_field(name="結果", value=result, inline=True)
        embed.add_field(name="獲勝人數", value=str(len(winners)), inline=True)
        embed.add_field(name="落敗人數", value=str(len(losers)), inline=True)
        await itx.followup.send(embed=embed)

    @app_commands.command(name="關盤", description="（管理員）取消賭盤並退還所有下注")
    @app_commands.checks.has_permissions(administrator=True)
    async def cancel_bet(self, itx: discord.Interaction, event_id: int):
        await itx.response.defer()
        with db() as c:
            ev = c.execute("SELECT * FROM bet_events WHERE id=? AND status='open'", (event_id,)).fetchone()
            if not ev: return await itx.followup.send("找不到此賭盤。")
            bets = c.execute("SELECT * FROM bets WHERE event_id=? AND status='pending'", (event_id,)).fetchall()
            for b in bets:
                add_points(b["discord_id"], b["amount"], f"賭盤取消退款：{ev['title']}")
                c.execute("UPDATE bets SET status='refunded' WHERE id=?", (b["id"],))
            c.execute("UPDATE bet_events SET status='cancelled' WHERE id=?", (event_id,))
        await itx.followup.send(f"賭盤 #{event_id} 已取消，退還 {len(bets)} 筆下注。")


async def setup(bot):
    await bot.add_cog(Betting(bot))
