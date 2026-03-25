"""
cogs/shop.py — 點數商城兌換系統
"""
import discord
from discord.ext import commands
from discord import app_commands
from database import db
from cogs.points import deduct_points, get_balance


class ConfirmView(discord.ui.View):
    def __init__(self, item):
        super().__init__(timeout=60)
        self.item = item

    @discord.ui.button(label="確認兌換", style=discord.ButtonStyle.success)
    async def confirm(self, itx: discord.Interaction, btn: discord.ui.Button):
        uid = str(itx.user.id)
        with db() as c:
            it = c.execute("SELECT * FROM shop_items WHERE id=? AND is_active=1", (self.item["id"],)).fetchone()
            if not it or it["stock"] == 0:
                return await itx.response.edit_message(content="商品已售完。", embed=None, view=None)
            if not deduct_points(uid, it["cost"], f"商城兌換：{it['name']}"):
                return await itx.response.edit_message(content="點數不足，兌換失敗。", embed=None, view=None)
            c.execute("INSERT INTO shop_orders(discord_id,item_id) VALUES(?,?)", (uid, it["id"]))
            if it["stock"] > 0:
                c.execute("UPDATE shop_items SET stock=stock-1 WHERE id=?", (it["id"],))
        self.stop()
        await itx.response.edit_message(
            embed=discord.Embed(title="兌換成功", description=f"成功兌換 **{it['name']}**！\n管理員將在 24 小時內處理訂單。", color=0x00C851),
            view=None)

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel(self, itx: discord.Interaction, btn: discord.ui.Button):
        self.stop()
        await itx.response.edit_message(content="已取消。", embed=None, view=None)


class ItemSelect(discord.ui.Select):
    def __init__(self, items):
        opts = [discord.SelectOption(label=it["name"][:25], description=f"{it['cost']} 點 | {(it['description'] or '')[:40]}", value=str(it["id"])) for it in items]
        super().__init__(placeholder="選擇商品", options=opts)

    async def callback(self, itx: discord.Interaction):
        with db() as c:
            item = c.execute("SELECT * FROM shop_items WHERE id=? AND is_active=1", (int(self.values[0]),)).fetchone()
        if not item:
            return await itx.response.send_message("商品已下架。", ephemeral=True)
        bal = get_balance(str(itx.user.id))
        embed = discord.Embed(title="確認兌換",
            description=f"商品：**{item['name']}**\n費用：**{item['cost']}** 點\n兌換後餘額：**{bal - item['cost']}** 點\n\n確定兌換嗎？",
            color=0xFFA500)
        await itx.response.send_message(embed=embed, view=ConfirmView(item), ephemeral=True)


class Shop(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="商城", description="查看並兌換商城商品")
    async def shop(self, itx: discord.Interaction):
        with db() as c:
            items = c.execute("SELECT * FROM shop_items WHERE is_active=1 ORDER BY cost").fetchall()
        if not items:
            return await itx.response.send_message("商城目前沒有商品。", ephemeral=True)
        bal = get_balance(str(itx.user.id))
        embed = discord.Embed(title="點數商城", description=f"你的點數：**{bal}** 點\n\n請從下方選擇商品：", color=0x5865F2)
        for it in items:
            stk = "無限" if it["stock"] == -1 else str(it["stock"])
            embed.add_field(name=f"{it['name']} — {it['cost']} 點", value=f"{it['description'] or '（無描述）'}\n庫存：{stk}", inline=False)
        view = discord.ui.View(timeout=120)
        view.add_item(ItemSelect(list(items)))
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="我的訂單", description="查詢兌換訂單")
    async def orders(self, itx: discord.Interaction):
        uid = str(itx.user.id)
        with db() as c:
            rows = c.execute(
                "SELECT o.id,i.name,o.status,o.created_at FROM shop_orders o JOIN shop_items i ON o.item_id=i.id WHERE o.discord_id=? ORDER BY o.created_at DESC LIMIT 10",
                (uid,)).fetchall()
        if not rows:
            return await itx.response.send_message("目前沒有兌換紀錄。", ephemeral=True)
        st = {"pending":"處理中","completed":"已完成","cancelled":"已取消"}
        lines = [f"`#{r['id']}` **{r['name']}** — {st.get(r['status'],r['status'])} ({r['created_at'][:10]})" for r in rows]
        await itx.response.send_message(embed=discord.Embed(title="我的兌換訂單", description="\n".join(lines), color=0x5865F2), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Shop(bot))
