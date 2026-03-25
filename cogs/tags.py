"""
cogs/tags.py — 啦啦隊美圖區強制標籤輔助
"""
import discord, os
from discord.ext import commands
from discord import app_commands

GALLERY_TAGS = ["135底片相機", "數位單眼", "手機拍攝", "運動攝影", "啦啦隊", "球場景色", "其他"]


class TagSelectView(discord.ui.View):
    def __init__(self, author_id, message):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.msg = message
        opts = [discord.SelectOption(label=t, value=t) for t in GALLERY_TAGS]
        sel = discord.ui.Select(placeholder="請選擇照片類型標籤", options=opts, min_values=1, max_values=2)
        sel.callback = self._on_select
        self.add_item(sel)

    async def _on_select(self, itx: discord.Interaction):
        if itx.user.id != self.author_id:
            return await itx.response.send_message("這不是你的發文。", ephemeral=True)
        tags = " ".join(f"[{t}]" for t in self.children[0].values)
        self.stop()
        await itx.response.edit_message(
            embed=discord.Embed(title="標籤已設定", description=f"你的照片標籤：{tags}", color=0x00C851),
            view=None)
        try:
            new_content = f"{tags}\n{self.msg.content}"[:2000]
            await self.msg.edit(content=new_content)
        except discord.Forbidden:
            pass


class Tags(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        gch_id = os.getenv("GALLERY_CHANNEL_ID")
        if not gch_id or str(message.channel.id) != gch_id: return
        if not message.attachments: return
        if any(f"[{t}]" in message.content for t in GALLERY_TAGS): return
        view = TagSelectView(message.author.id, message)
        embed = discord.Embed(title="請選擇照片類型標籤",
            description="你發布了照片，請在 2 分鐘內選擇標籤，方便其他人找到你的作品。", color=0xFFA500)
        try:
            await message.author.send(embed=embed, view=view)
        except discord.Forbidden:
            await message.reply(embed=embed, view=view, mention_author=True, delete_after=120)

    @app_commands.command(name="標籤說明", description="查看美圖區支援的所有標籤")
    async def tag_help(self, itx: discord.Interaction):
        lines = [f"• `[{t}]`" for t in GALLERY_TAGS]
        await itx.response.send_message(
            embed=discord.Embed(title="照片區標籤說明", description="\n".join(lines), color=0x5865F2,
                                footer=discord.EmbedFooter(text="發文時在內容前加上標籤，例如：[數位單眼] 今天的練習賽...")),
            ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tags(bot))
