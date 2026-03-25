"""
cogs/help.py — /說明 指令，依身分顯示可用指令列表
"""
import discord, os
from discord.ext import commands
from discord import app_commands


def is_mod(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    rid = os.getenv("ROLE_MODERATOR")
    if rid:
        r = member.guild.get_role(int(rid))
        if r and r in member.roles:
            return True
    return False


GENERAL_COMMANDS = [
    ("簽到",           "每日簽到領取點數"),
    ("點數",           "查詢自己或他人的點數餘額"),
    ("點數紀錄",       "查看最近 10 筆點數交易"),
    ("排行榜",         "點數 Top 10 排行榜"),
    ("轉點",           "轉移點數給其他玩家"),
    ("商城",           "查看並兌換商城商品"),
    ("我的訂單",       "查詢兌換訂單狀態"),
    ("賭盤列表",       "查看目前開放中的賭盤"),
    ("下注",           "對指定賭盤下注"),
    ("我的下注",       "查看自己的下注紀錄"),
    ("發票",           "發布球票讓渡資訊"),
    ("推薦",           "對交易對象給予好評（信用+5）"),
    ("檢舉",           "檢舉黃牛或詐騙行為"),
    ("信用查詢",       "查詢自己或他人的信用評分"),
    ("選隊",           "重新選擇支持的球隊"),
    ("驗證",           "重新接收身分驗證題目"),
    ("參選",           "報名版主選舉"),
    ("選舉票數",       "查看目前選舉的得票數"),
    ("工單",           "建立客服工單"),
    ("標籤說明",       "查看美圖區支援的所有照片標籤"),
    ("選秀結果",       "查看選秀完整陣容結果"),
    ("選秀球員列表",   "查看選秀中可選的球員"),
    ("說明",           "顯示這個指令列表"),
]

MOD_COMMANDS = [
    ("警告",       "對成員發出警告（信用-5）"),
    ("禁言",       "禁言成員（需指定分鐘數）"),
    ("解禁",       "解除成員禁言"),
    ("違規查詢",   "查看成員的所有違規紀錄"),
    ("黑名單",     "封禁用戶並加入黑名單（禁言28天）"),
    ("關閉工單",   "關閉指定工單"),
    ("工單列表",   "查看所有待處理工單"),
]

ADMIN_COMMANDS = [
    ("開盤",           "開立新賭盤（設定選項與賠率）"),
    ("結算",           "結算賭盤並自動派彩"),
    ("關盤",           "取消賭盤並退還所有下注"),
    ("給點",           "手動給予玩家點數"),
    ("扣點",           "手動扣除玩家點數"),
    ("設關鍵字",       "新增迷因關鍵字自動回應"),
    ("刪關鍵字",       "刪除關鍵字"),
    ("開選舉",         "開始版主選舉報名期"),
    ("啟動投票",       "正式啟動版主投票"),
    ("新增選秀",       "建立新的模擬選秀賽事"),
    ("新增選秀隊伍",   "新增選秀隊伍並指派 GM"),
    ("匯入球員",       "輸入 CSV 格式匯入球員名單"),
    ("開始選秀",       "正式啟動選秀流程"),
    ("給vip",          "手動授予 VIP 身分"),
    ("移除vip",        "移除 VIP 身分"),
    ("推播測試",       "手動觸發 PTT 新聞推播"),
]


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="說明", description="查看所有可用的 Bot 指令")
    async def help_cmd(self, itx: discord.Interaction):
        is_admin = itx.user.guild_permissions.administrator
        is_moderator = is_mod(itx.user)

        # ── 一般指令 ──
        embed = discord.Embed(
            title="CPBL Bot 指令說明",
            description="所有指令均以 `/` 開頭，點擊後可看到參數說明。",
            color=0x5865F2,
        )

        general_lines = "\n".join(f"`/{name}` — {desc}" for name, desc in GENERAL_COMMANDS)
        embed.add_field(name="一般指令（所有人）", value=general_lines, inline=False)

        # ── 版主指令 ──
        if is_moderator:
            mod_lines = "\n".join(f"`/{name}` — {desc}" for name, desc in MOD_COMMANDS)
            embed.add_field(name="版主指令", value=mod_lines, inline=False)

        # ── 管理員指令 ──
        if is_admin:
            admin_lines = "\n".join(f"`/{name}` — {desc}" for name, desc in ADMIN_COMMANDS)
            embed.add_field(name="管理員指令", value=admin_lines, inline=False)

        embed.set_footer(text="指令有問題？使用 /工單 聯絡管理員")
        await itx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))