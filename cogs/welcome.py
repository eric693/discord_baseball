"""
cogs/welcome.py — 迎賓 + 防機器人驗證 + 球隊身分組
"""
import discord, os, random
from discord.ext import commands
from discord import app_commands
from database import db

TEAMS = {
    "lions":     {"name": "統一獅",   "color": 0xFFD700, "env": "ROLE_LIONS"},
    "elephants": {"name": "中信兄象", "color": 0x0033A0, "env": "ROLE_ELEPHANTS"},
    "guardians": {"name": "樂天桃猿", "color": 0xE4002B, "env": "ROLE_GUARDIANS"},
    "hawks":     {"name": "味全龍",   "color": 0x006400, "env": "ROLE_HAWKS"},
    "monkeys":   {"name": "富邦悍將", "color": 0xFF6600, "env": "ROLE_MONKEYS"},
    "bears":     {"name": "台鋼雄鷹", "color": 0x8B0000, "env": "ROLE_BEARS"},
}

QUIZ = [
    {"q": "中職哪支球隊的主色是黃色？",  "opts": ["統一獅","中信兄象","樂天桃猿","富邦悍將"], "ans": "統一獅",  "hint": "想想太陽的顏色"},
    {"q": "樂天桃猿的主場在哪個縣市？",  "opts": ["台北","台中","桃園","台南"],              "ans": "桃園",   "hint": "球隊名稱就有提示"},
    {"q": "富邦悍將的代表色是？",        "opts": ["橘色","藍色","紅色","黃色"],              "ans": "橘色",   "hint": "像夕陽一樣鮮豔"},
    {"q": "台鋼雄鷹的主場城市是？",      "opts": ["高雄","台南","嘉義","屏東"],              "ans": "高雄",   "hint": "南台灣最大城市"},
    {"q": "CPBL 全名中文是什麼？",       "opts": ["中華職棒大聯盟","中華職業棒球聯盟","台灣職棒聯盟","中華棒球協會"], "ans": "中華職棒大聯盟", "hint": "英文縮寫 CPBL"},
]


class TeamView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=300)
        for key, info in TEAMS.items():
            b = discord.ui.Button(label=info["name"], style=discord.ButtonStyle.secondary, custom_id=f"team_{key}")
            b.callback = self._make_cb(key, info)
            self.add_item(b)

    def _make_cb(self, key, info):
        async def cb(itx: discord.Interaction):
            role_id = os.getenv(info["env"])
            if not role_id:
                return await itx.response.send_message("身分組尚未設定，請聯絡管理員。", ephemeral=True)
            role = itx.guild.get_role(int(role_id))
            if not role:
                return await itx.response.send_message("找不到身分組，請聯絡管理員。", ephemeral=True)
            for t_key, t_info in TEAMS.items():
                rid = os.getenv(t_info["env"])
                if rid:
                    r = itx.guild.get_role(int(rid))
                    if r and r in itx.user.roles:
                        await itx.user.remove_roles(r)
            await itx.user.add_roles(role)
            with db() as c:
                c.execute("UPDATE members SET team=? WHERE discord_id=?", (key, str(itx.user.id)))
            embed = discord.Embed(title="球隊身分組已更新", description=f"你現在是 **{info['name']}** 的球迷！", color=info["color"])
            await itx.response.send_message(embed=embed, ephemeral=True)
        return cb


class QuizView(discord.ui.View):
    def __init__(self, member, q):
        super().__init__(timeout=120)
        self.member = member
        self.q = q
        for opt in q["opts"]:
            b = discord.ui.Button(label=opt, style=discord.ButtonStyle.primary, custom_id=f"quiz_{opt}")
            b.callback = self._make_cb(opt)
            self.add_item(b)

    def _make_cb(self, option):
        async def cb(itx: discord.Interaction):
            if itx.user.id != self.member.id:
                return await itx.response.send_message("這不是你的題目。", ephemeral=True)
            if option == self.q["ans"]:
                v_id = os.getenv("ROLE_VERIFIED")
                u_id = os.getenv("ROLE_UNVERIFIED")
                if v_id:
                    r = itx.guild.get_role(int(v_id))
                    if r: await itx.user.add_roles(r)
                if u_id:
                    r = itx.guild.get_role(int(u_id))
                    if r and r in itx.user.roles: await itx.user.remove_roles(r)
                embed = discord.Embed(title="驗證成功", description="歡迎加入！現在可以自由發言了。\n請選擇你支持的球隊：", color=0x00C851)
                self.stop()
                await itx.response.edit_message(embed=embed, view=None)
                wch_id = os.getenv("WELCOME_CHANNEL_ID")
                if wch_id:
                    ch = itx.guild.get_channel(int(wch_id))
                    if ch:
                        tv = TeamView(itx.guild)
                        e2 = discord.Embed(title="選擇你支持的球隊", description="點擊按鈕，獲得對應球隊顏色的身分組。", color=0x5865F2)
                        await ch.send(content=f"{itx.user.mention}", embed=e2, view=tv)
            else:
                embed = discord.Embed(title="答錯了", description=f"提示：{self.q['hint']}\n請重新用 `/驗證` 再試一次。", color=0xFF4444)
                await itx.response.edit_message(embed=embed, view=None)
        return cb


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _ensure(self, m: discord.Member):
        with db() as c:
            c.execute("INSERT OR IGNORE INTO members(discord_id,username) VALUES(?,?)", (str(m.id), str(m)))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        gid = os.getenv("GUILD_ID")
        if gid and str(member.guild.id) != gid:
            return
        self._ensure(member)
        uid_r = os.getenv("ROLE_UNVERIFIED")
        if uid_r:
            r = member.guild.get_role(int(uid_r))
            if r: await member.add_roles(r)
        q = random.choice(QUIZ)
        embed = discord.Embed(
            title="歡迎來到 CPBL 棒球社群！",
            description=f"你好，{member.display_name}！\n\n請先回答一道中職常識題，通過後才能發言。\n\n**{q['q']}**",
            color=0x5865F2
        )
        view = QuizView(member, q)
        try:
            await member.send(embed=embed, view=view)
        except discord.Forbidden:
            wch_id = os.getenv("WELCOME_CHANNEL_ID")
            if wch_id:
                ch = member.guild.get_channel(int(wch_id))
                if ch:
                    await ch.send(content=f"{member.mention}", embed=embed, view=view)

    @app_commands.command(name="選隊", description="重新選擇支持的球隊")
    async def choose_team(self, itx: discord.Interaction):
        view = TeamView(itx.guild)
        embed = discord.Embed(title="選擇你的主隊", description="點擊按鈕獲得球隊身分組：", color=0x5865F2)
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="驗證", description="重新接收驗證題目")
    async def reverify(self, itx: discord.Interaction):
        q = random.choice(QUIZ)
        embed = discord.Embed(title="身分驗證", description=f"**{q['q']}**", color=0x5865F2)
        view = QuizView(itx.user, q)
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
