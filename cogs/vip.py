"""
cogs/vip.py — VIP 自動升級（金流 Webhook 接收）
由 web/routes/api.py 觸發，此 cog 提供 assign_vip 給 Flask 呼叫
"""
import discord, os
from discord.ext import commands
from discord import app_commands
from database import db


class VIP(commands.Cog):
    def __init__(self, bot): self.bot = bot

    async def assign_vip(self, discord_id: str) -> bool:
        """Called by Flask webhook route to promote a user to VIP."""
        gid = os.getenv("GUILD_ID"); rid = os.getenv("ROLE_VIP")
        if not gid or not rid: return False
        guild = self.bot.get_guild(int(gid))
        if not guild: return False
        member = guild.get_member(int(discord_id))
        if not member:
            try: member = await guild.fetch_member(int(discord_id))
            except: return False
        role = guild.get_role(int(rid))
        if not role: return False
        await member.add_roles(role)
        with db() as c:
            c.execute("UPDATE members SET is_vip=1 WHERE discord_id=?", (discord_id,))
        try:
            await member.send("你的 VIP 訂閱已啟用！感謝支持，享受專屬頻道與功能。")
        except discord.Forbidden:
            pass
        return True

    async def revoke_vip(self, discord_id: str) -> bool:
        gid = os.getenv("GUILD_ID"); rid = os.getenv("ROLE_VIP")
        if not gid or not rid: return False
        guild = self.bot.get_guild(int(gid))
        if not guild: return False
        member = guild.get_member(int(discord_id))
        if not member: return False
        role = guild.get_role(int(rid))
        if role and role in member.roles:
            await member.remove_roles(role)
        with db() as c:
            c.execute("UPDATE members SET is_vip=0 WHERE discord_id=?", (discord_id,))
        return True

    @app_commands.command(name="給vip", description="（管理員）手動授予 VIP 身分")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_vip(self, itx: discord.Interaction, member: discord.Member):
        ok = await self.assign_vip(str(member.id))
        if ok:
            await itx.response.send_message(f"已授予 {member.mention} VIP 身分。", ephemeral=True)
        else:
            await itx.response.send_message("授予失敗，請確認 ROLE_VIP 已設定。", ephemeral=True)

    @app_commands.command(name="移除vip", description="（管理員）移除 VIP 身分")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_vip(self, itx: discord.Interaction, member: discord.Member):
        ok = await self.revoke_vip(str(member.id))
        msg = f"已移除 {member.mention} 的 VIP 身分。" if ok else "移除失敗。"
        await itx.response.send_message(msg, ephemeral=True)


async def setup(bot):
    await bot.add_cog(VIP(bot))
