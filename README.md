# CPBL 棒球社群 Discord Bot

完整的中職棒球 Discord 社群管理系統，包含 Discord Bot + Flask 後台管理面板。

---

## 專案結構

```
cpbl_bot/
├── bot.py                  # 主程式入口
├── database.py             # SQLite schema 與工具函式
├── requirements.txt        # Python 套件
├── .env.example            # 環境變數範本
│
├── cogs/                   # Discord Bot 功能模組
│   ├── welcome.py          # 迎賓、防機器人、球隊身分組
│   ├── points.py           # 點數系統（簽到、賺取、查詢）
│   ├── shop.py             # 點數商城兌換
│   ├── betting.py          # 賭盤下注系統
│   ├── tickets.py          # 售票亭、防詐、信用評價
│   ├── moderation.py       # 版主執法、關鍵字、工單
│   ├── election.py         # 版主選舉機制
│   ├── draft.py            # CPBL 模擬選秀遊戲
│   ├── feed.py             # PTT/YouTube 自動推播
│   ├── tags.py             # 論壇頻道強制標籤
│   └── vip.py              # VIP 自動升級 (Webhook)
│
└── web/                    # Flask 後台管理系統
    ├── app.py              # Flask 工廠函式
    ├── templates/          # Jinja2 HTML 模板
    │   ├── base.html       # 共用 layout
    │   ├── login.html
    │   ├── dashboard.html  # 儀表板（Chart.js 圖表）
    │   ├── members/        # 成員管理
    │   ├── shop/           # 商城管理
    │   ├── betting/        # 賭盤管理
    │   ├── mod/            # 違規與工單
    │   ├── keywords/       # 關鍵字詞庫
    │   ├── draft/          # 模擬選秀
    │   └── tickets/        # 售票亭
    └── routes/             # Flask Blueprint 路由
        ├── auth.py
        ├── dashboard.py
        ├── members.py
        ├── shop.py
        ├── betting.py
        ├── moderation.py
        ├── keywords.py
        ├── draft.py
        ├── tickets.py
        └── api.py          # REST API (VIP Webhook)
```

---

## 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 設定環境變數

```bash
cp .env.example .env
# 用文字編輯器填入以下資訊
```

#### 必填項目

| 變數 | 說明 |
|------|------|
| `DISCORD_TOKEN` | Discord Bot Token（[Discord Developer Portal](https://discord.com/developers/applications)） |
| `GUILD_ID` | 你的伺服器 ID |
| `SECRET_KEY` | Flask Session 密鑰（隨機字串） |
| `ADMIN_PASSWORD` | Web 後台登入密碼 |

#### 頻道 ID 設定

| 變數 | 建議頻道名稱 |
|------|-------------|
| `WELCOME_CHANNEL_ID` | #歡迎新球迷 |
| `NEWS_CHANNEL_ID` | #中職新聞 |
| `TICKET_LISTING_CHANNEL_ID` | #球票讓渡 |
| `GALLERY_CHANNEL_ID` | #啦啦隊美圖 |
| `ELECTION_CHANNEL_ID` | #版主選舉 |
| `DRAFT_CHANNEL_ID` | #模擬選秀 |
| `LOG_CHANNEL_ID` | #管理日誌 |

#### 身分組 ID 設定

| 變數 | 說明 |
|------|------|
| `ROLE_LIONS` | 統一獅球迷 |
| `ROLE_ELEPHANTS` | 中信兄象球迷 |
| `ROLE_GUARDIANS` | 樂天桃猿球迷 |
| `ROLE_HAWKS` | 味全龍球迷 |
| `ROLE_MONKEYS` | 富邦悍將球迷 |
| `ROLE_BEARS` | 台鋼雄鷹球迷 |
| `ROLE_UNVERIFIED` | 未驗證（限制頻道） |
| `ROLE_VERIFIED` | 已驗證（基本發言） |
| `ROLE_VIP` | VIP 訂閱用戶 |
| `ROLE_MODERATOR` | 版主 |
| `ROLE_BLACKLIST` | 黑名單（全區禁言） |

### 3. Discord Bot 權限

在 Developer Portal Bot 頁籤開啟：
- **Message Content Intent**
- **Server Members Intent**
- **Presence Intent**

OAuth2 URL 產生時選 `bot` + `applications.commands`，Bot 建議給予 `Administrator` 權限。

### 4. 啟動

```bash
python bot.py
```

同時啟動 Discord Bot 與 Web 後台（預設 `http://localhost:5000`）。

登入：`http://localhost:5000/login`，帳密為 `.env` 中設定的值。

---

## Discord 斜線指令一覽

### 所有人可用

| 指令 | 說明 |
|------|------|
| `/簽到` | 每日簽到領取點數 |
| `/點數 [成員]` | 查詢點數餘額 |
| `/點數紀錄` | 查看最近 10 筆交易 |
| `/排行榜` | 點數 Top 10 |
| `/轉點 <成員> <數量>` | 轉移點數 |
| `/商城` | 查看並兌換商品 |
| `/我的訂單` | 查詢兌換訂單 |
| `/下注 <賭盤ID>` | 對賭盤下注 |
| `/賭盤列表` | 查看開放中賭盤 |
| `/我的下注` | 查看下注紀錄 |
| `/發票` | 發布球票讓渡 |
| `/推薦 <成員>` | 給予好評（信用+5） |
| `/檢舉 <成員> <原因>` | 檢舉黃牛/詐騙 |
| `/信用查詢 [成員]` | 查詢信用評分 |
| `/選隊` | 重新選擇支持球隊 |
| `/驗證` | 重新接收驗證題目 |
| `/參選 <選舉ID>` | 報名版主選舉 |
| `/選舉票數 <選舉ID>` | 查看目前票數 |
| `/工單` | 建立客服工單 |
| `/標籤說明` | 查看美圖區標籤 |
| `/選秀結果 <賽事ID>` | 查看選秀完整陣容 |
| `/選秀球員列表 <賽事ID>` | 查看可選球員 |

### 版主指令

| 指令 | 說明 |
|------|------|
| `/警告 <成員> <原因>` | 發出警告（信用-5） |
| `/禁言 <成員> <分鐘> [原因]` | 禁言成員 |
| `/解禁 <成員>` | 解除禁言 |
| `/違規查詢 <成員>` | 查看違規紀錄 |
| `/關閉工單 <ID> [備註]` | 關閉工單 |
| `/工單列表` | 查看待處理工單 |
| `/黑名單 <成員> [原因]` | 封禁 + 禁言 + 黑名單 |

### 管理員專用

| 指令 | 說明 |
|------|------|
| `/開盤 <標題> <選項> <賠率>` | 開立賭盤（選項與賠率用逗號分隔） |
| `/結算 <賭盤ID> <結果>` | 結算派彩 |
| `/關盤 <賭盤ID>` | 取消賭盤退款 |
| `/給點 <成員> <數量>` | 手動給點 |
| `/扣點 <成員> <數量>` | 手動扣點 |
| `/設關鍵字 <觸發詞> <回應>` | 設定迷因自動回應 |
| `/刪關鍵字 <觸發詞>` | 刪除關鍵字 |
| `/開選舉 <標題>` | 開始版主選舉報名期 |
| `/啟動投票 <選舉ID> [時數]` | 正式開票 |
| `/新增選秀 <標題>` | 建立選秀賽事 |
| `/新增選秀隊伍 <賽事ID> <隊名> <GM> <順位>` | 新增隊伍 |
| `/匯入球員 <賽事ID> <CSV>` | 匯入球員（姓名,位置,母隊 每行一筆） |
| `/開始選秀 <賽事ID>` | 正式啟動選秀 |
| `/給VIP <成員>` | 手動授予 VIP |
| `/移除VIP <成員>` | 移除 VIP |
| `/推播測試` | 手動觸發 PTT 推播 |

---

## VIP 金流 Webhook

外部網站付款後呼叫：

```http
POST http://your-server:5000/api/vip/grant
Content-Type: application/json
X-Webhook-Signature: sha256=<hmac>

{"discord_id": "123456789"}
```

簽名：`HMAC-SHA256(request_body_bytes, VIP_WEBHOOK_SECRET)`，加 `sha256=` 前綴。

---

## 點數獲取規則

| 行為 | 點數 | 冷卻 |
|------|------|------|
| 每日簽到 | +10 | 每天一次 |
| 頻道發言 | +2 | 5 分鐘 |
| 被按讚（大拇指） | +5 | 無 |
| 交易獲得好評 | +3 | 7 天/對象 |

以上數值均可透過 `.env` 調整。

---

## PTT 推播

每 5 分鐘檢查 RSS，標籤含 `[情報]` `[炸裂]` `[新聞]` `[討論]` `[閒聊]` 自動推播至 `NEWS_CHANNEL_ID`。

## YouTube 推播（選填）

申請 YouTube Data API v3 金鑰後填入 `YOUTUBE_API_KEY` 與 `YT_CHANNEL_IDS`。

---

## 注意事項

1. 賭盤系統為**虛擬點數娛樂**，不涉及真實金錢
2. SQLite 適合 1000 人以下；更大規模建議遷移至 PostgreSQL
3. 部署前務必更改 `SECRET_KEY`、`ADMIN_PASSWORD`、`VIP_WEBHOOK_SECRET`
4. Bot 需要 Administrator 權限才能執行禁言、管理身分組等功能
