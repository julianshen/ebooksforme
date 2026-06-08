#!/usr/bin/env python3
"""Hermes Agent 源碼深度解析 EPUB 生成器"""
import os, ebooklib
from ebooklib import epub

OUT = "/tmp/ebooksforme/hermes-agent-analysis/hermes-agent-source-code-analysis.epub"
os.makedirs(os.path.dirname(OUT), exist_ok=True)

CSS = """
body { font-family: 'Noto Sans CJK SC','Source Han Sans',sans-serif; line-height:1.8; font-size:10pt; }
h1 { font-size:18pt; color:#8b5cf6; border-bottom:2px solid #8b5cf6; padding-bottom:5px; margin-top:30px; }
h2 { font-size:14pt; color:#a78bfa; margin-top:25px; }
h3 { font-size:12pt; color:#c4b5fd; }
pre { background:#1e1b2e; padding:10px; border-left:3px solid #8b5cf6; font-size:8pt; overflow-x:auto; white-space:pre-wrap; color:#e0d4ff; }
code { background:#2d2a3e; padding:1px 3px; font-size:8.5pt; color:#d4c4ff; }
p { text-align:justify; margin:8px 0; }
table { border-collapse:collapse; width:100%; font-size:9pt; margin:10px 0; }
th,td { border:1px solid #3d3a5e; padding:6px; text-align:left; }
th { background:#2d2a4e; color:#c4b5fd; }
td { background:#1a1730; color:#e0d4ff; }
ul,ol { margin:5px 0; }
li { margin:2px 0; }
hr { border:none; border-top:1px solid #3d3a5e; margin:20px 0; }
"""

book = epub.EpubBook()
book.set_identifier('hermes-agent-analysis-2026')
book.set_title('Hermes Agent 源碼深度解析：開源 AI Agent 框架的設計與實作')
book.set_language('zh-TW')
book.add_author('tGD Analysis')

css_item = epub.EpubItem(uid='style_default', file_name='style/default.css',
                          media_type='text/css', content=CSS.encode('utf-8'))
book.add_item(css_item)

H1 = lambda c: f'<h1>{c}</h1>'; H2 = lambda c: f'<h2>{c}</h2>'; H3 = lambda c: f'<h3>{c}</h3>'
P = lambda c: f'<p>{c}</p>'; HR = lambda: '<hr/>'
PRE = lambda c: f'<pre><code>{c.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}</code></pre>'
IC = lambda c: f'<code>{c}</code>'
UL = lambda items: '<ul>'+''.join('<li>'+i+'</li>' for i in items)+'</ul>'
OL = lambda items: '<ol>'+''.join('<li>'+i+'</li>' for i in items)+'</ol>'
TBL = lambda h,rows: '<table><thead><tr>'+''.join(f'<th>{c}</th>' for c in h)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{c}</td>' for c in r)+'</tr>' for r in rows)+'</tbody></table>'
CB = lambda t,s: P(f'<b>{t}</b>')+PRE(s)

def mkchapter(title, fname, body):
    html = f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" lang="zh-TW"><head><title>{title}</title><link rel="stylesheet" type="text/css" href="style/default.css"/></head><body>{body}</body></html>'
    ch = epub.EpubHtml(title=title, file_name=fname, lang='zh-TW')
    ch.content = html.encode('utf-8')
    ch.add_item(css_item)
    book.add_item(ch)
    book.toc.append(ch)
    book.spine.append(ch)

# ── Ch0: 前言 ──
c0 = H1('前言')
c0 += P('Hermes Agent 是 Nous Research 開發的開源 AI Agent 框架，與 Claude Code、Codex CLI、OpenCode 同屬於自主編碼與任務執行代理的類別。它可以在終端機、即時通訊平台和 IDE 中運行，支援 20+ LLM Provider，並且具備技能（Skills）、記憶（Memory）、排程（Cron）等先進功能。')
c0 += P('本書以源碼為核心，從架構概覽開始，逐層深入每個子系統的設計與實作。每個章節都搭配關鍵的源碼片段、類別結構圖和設計模式分析。')
c0 += H2('本書章節組織')
c0 += OL([
    '第一章：Hermes Agent 總覽 — 專案定位、系統架構、與競品比較',
    '第二章：Conversation Loop — 對話主循環的完整流程',
    '第三章：Context Management — 上下文壓縮與系統提示快取',
    '第四章：Tool System — 工具註冊、分派與核心工具實作',
    '第五章：CLI 與斜線命令系統 — 命令行介面架構',
    '第六章：Gateway 多平台架構 — 即時通訊平台適配器',
    '第七章：Cron 排程系統 — 定時任務排程器',
    '第八章：Skills 與 Curator — 技能生命週期管理',
    '第九章：Credential Pooling 與模型路由',
    '第十章：安全系統 — 命令審批、檔案安全、威脅掃描',
    '第十一章：設定管理與 Session 儲存',
])
mkchapter('前言', 'ch00.xhtml', c0)

# ── Ch1: 總覽 ──
c1 = H1('第一章：Hermes Agent 總覽')
c1 += H2('1.1 專案定位')
c1 += P('Hermes Agent 是一個<b>開源、提供者無關、自我改進</b>的 AI Agent 框架。其核心設計目標是：')
c1 += UL(['自我改進 — 透過技能（Skills）系統從經驗中學習', '跨平台 — 同一 agent 可在 CLI、Telegram、Discord 等 14+ 平台運行', '提供者無關 — 支援 20+ LLM Provider，可在工作流程中動態切換', '可擴展 — 插件、MCP 伺服器、自訂工具、Webhook 觸發器'])
c1 += H2('1.2 系統架構')
c1 += CB('整體架構', """run_agent.py (AIAgent)
    |
    +-- agent/ (對話循環 + Context + Memory)
    |   +-- conversation_loop.py  -- 主循環
    |   +-- context_compressor.py -- 上下文壓縮
    |   +-- agent_init.py         -- 初始化
    |   +-- credential_pool.py    -- 憑證池
    |   +-- auxiliary_client.py   -- 輔助模型路由
    |   +-- curator.py            -- 技能維護
    |
    +-- tools/ (工具系統)
    |   +-- registry.py           -- 工具註冊
    |   +-- delegate_tool.py      -- 子代理
    |   +-- cronjob_tools.py      -- Cron 任務
    |   +-- browser_tool.py       -- 瀏覽器
    |   +-- code_execution_tool.py -- 程式碼執行
    |
    +-- hermes_cli/ (CLI 系統)
    |   +-- main.py               -- 入口點
    |   +-- commands.py           -- 斜線命令註冊
    |   +-- config.py             -- 設定管理
    |
    +-- gateway/ (多平台閘道)
    |   +-- platform_registry.py  -- 平台註冊
    |   +-- delivery.py           -- 訊息投遞
    |   +-- platforms/*.py        -- 14+ 平台適配器
    |
    +-- cron/ (排程系統)
    |   +-- jobs.py               -- 任務儲存
    |   +-- scheduler.py          -- 排程器
    |
    +-- skills/ (技能目錄)
    +-- tests/ (測試套件, ~3000 個)""")
c1 += H2('1.3 版本資訊')
c1 += P('本書分析基於 Hermes Agent v0.16.0 (2026.6.5)，commit 7230fcb7。')
mkchapter('第一章：總覽', 'ch01.xhtml', c1)

# ── Ch2: Conversation Loop ──
c2 = H1('第二章：Conversation Loop — 對話主循環')
c2 += P('對話主循環是 Hermes Agent 的心臟，位於 agent/conversation_loop.py（4,892 行）。每條用戶訊息調用一次 run_conversation()，執行以下流程：')
c2 += CB('對話循環架構', """Phase 1: Preflight 預處理 (行 379-565)
  - 安裝安全 stdio, 確保 session DB 存在
  - 設置 runtime main provider
  - 恢復主 provider（如前一輪觸發 fallback）
  - 淨化 user message 中的 surrogate 字符
  - 生成 task_id + turn_id
  - 重置重試計數器 (invalid_tool, invalid_json, empty_content, thinking_prefill)
  - 創建 IterationBudget
  - 恢復記憶提示計數器
  - 追加用戶訊息到 messages

Phase 2: System Prompt 管理 (行 574-588)
  - 檢查 _cached_system_prompt 是否有效
  - 有效 -> 直接復用（Anthropic prompt cache 命中）
  - 無效 -> 重新構建並持久化到 session DB

Phase 3: Preflight 上下文壓縮 (行 590-688)
  - 檢查消息長度是否超過 threshold
  - 若超過 -> 最多三輪壓縮

Phase 4: 主工具調用循環 (行 801-4512)
  while (api_call_count < max_iterations):
    - 準備 API messages + system prompt
    - 調用 _perform_api_call()
    - 驗證 response 形狀
    - 處理各種錯誤類型 (401/402/413/429 等)
    - 處理 finish_reason="length"
    - 追蹤 token 用量
    - 檢查是否包含工具調用 -> 執行
    - 無工具調用 -> 最終回應

Phase 5: 事後處理 (行 4513-4888)
  - Budget 耗盡處理
  - 持久化 session
  - 提取 reasoning
  - 背景記憶/技能 review""")
c2 += H2('2.1 錯誤處理鏈')
c2 += P('錯誤處理是一系列 if-elif 檢查（行 2050-3301），每種錯誤嘗試一種恢復策略：')
c2 += TBL(['錯誤類型', '恢復策略'], [
    ['UnicodeEncodeError', '淨化 surrogate/non-ASCII 字符'],
    ['圖片拒絕', '切換 text-only 模式'],
    ['圖片過大', '壓縮圖片'],
    ['401 授權錯誤', '刷新 token / credential pool rotation'],
    ['402/429 配額限制', 'credential pool rotation / fallback provider'],
    ['413 context_overflow', '壓縮上下文 + 重試'],
    ['llama.cpp grammar 錯誤', '清除 pattern/format'],
    ['Content policy blocked', '嘗試 fallback provider'],
])
c2 += H2('2.2 Continuation 機制')
c2 += P('當 finish_reason="length" 時（行 1629-1878），Hermes 會區分三種情況：')
c2 += UL(['思維預算耗盡 — 返回用戶友好錯誤，請用戶簡化查詢', '文本截斷 — 最多 3 次 continuation，自動追加「繼續」請求', '工具調用截斷 — 最多 3 次重試，boost max_tokens'])
mkchapter('第二章：Conversation Loop', 'ch02.xhtml', c2)

# ── Ch3: Context Management ──
c3 = H1('第三章：Context Management — 上下文壓縮與快取')
c3 += H2('3.1 策略模式架構')
c3 += P('ContextEngine（agent/context_engine.py）是抽象基底類別，ContextCompressor（agent/context_compressor.py）是預設實現，可透過 plugin 系統替換。')
c3 += CB('ContextCompressor 壓縮演算法', """should_compress() (行 728-748):
  - 估算 prompt tokens
  - 若 < threshold_tokens -> 不壓縮
  - 若最近兩次壓縮無效（節省 < 10%）-> 跳過

compress() 兩階段:
  1. _prune_old_tool_results() (行 754-920, 無需 LLM):
     - 去重: 相同內容的 tool result 只保留最新一份
     - 摘要化: 大型 tool result -> 一行摘要
     - 截斷工具參數: 大型 write_file 內容
     - 移除圖片: 舊的 screenshots -> 文字佔位符

  2. _generate_summary() (行 1217-1300, 需 LLM):
     - 保護頭: protect_first_n (預設 3) + system prompt
     - 保護尾: 基於 token budget (threshold 的 20%)
     - LLM 摘要: 使用輔助模型對中間輪次進行摘要
     - 格式: Active Task + Goal + Constraints + Completed Actions
     - 失敗處理: fallback 到主模型 -> 確定性摘要""")
c3 += H2('3.2 System Prompt 快取')
c3 += P('關鍵設計決策：system prompt 是<b>字節穩定</b>的，每輪傳送完全相同的字串。這保證了 Anthropic/KV cache 的 prefix 一致性，大幅降低多輪對話成本（~75%）。Plugin 的 context 注入到 user message，永不注入 system prompt。')
mkchapter('第三章：Context Management', 'ch03.xhtml', c3)

# ── Ch4: Tool System ──
c4 = H1('第四章：Tool System — 工具系統')
c4 += H2('4.1 三層架構')
c4 += CB('工具系統三層', """工具檔案 (*.py)  ->  ToolRegistry (registry.py)  ->  model_tools.py (分派層)
   (module-level          (singleton registry)          (get_tool_definitions
    registry.register())                                     + handle_function_call)""")
c4 += H2('4.2 註冊機制')
c4 += P('discover_builtin_tools()（registry.py 行 57-74）透過 AST 靜態分析自動發現 tools/ 目錄下的工具模組。每個工具註冊時包含 name、toolset、schema、handler、check_fn（TTL 30 秒快取）。')
c4 += H2('4.3 核心工具')
c4 += TBL(['工具', '檔案', '行數', '核心機制'], [
    ['Delegate Task', 'delegate_tool.py', '2829', 'ThreadPoolExecutor + 深度控制 + 活性監控'],
    ['Cron Job', 'cronjob_tools.py', '901', '雙層威脅掃描 + script path 驗證'],
    ['Code Execution', 'code_execution_tool.py', '1831', 'UDS/File 雙傳輸 + 環境清洗'],
    ['Browser', 'browser_tool.py', '3863', '多 provider + accessible tree'],
    ['CDP Browser', 'browser_cdp_tool.py', '569', 'WebSocket passthrough'],
])
mkchapter('第四章：Tool System', 'ch04.xhtml', c4)

# ── Ch5: CLI ──
c5 = H1('第五章：CLI 與斜線命令系統')
c5 += H2('5.1 啟動流程')
c5 += P('hermes_cli/main.py（16,036 行）的啟動流程極為嚴謹：')
c5 += OL([
    '_set_process_title() — 設定 process name 為 "hermes"',
    'configure_windows_stdio() — Windows UTF-8 相容',
    '_cleanup_quarantined_exes() — 清除殘留更新檔',
    'Termux 快啟路徑（TUI/CLI fast launch，跳過 import 節省 ~600ms）',
    'build_top_level_parser() — 建立 argparse parser',
    '註冊所有子命令',
    'parse_args() + dispatch',
])
c5 += H2('5.2 斜線命令系統')
c5 += P('COMMAND_REGISTRY（hermes_cli/commands.py）是集中式單一真相來源，包含 ~70 個斜線命令：')
c5 += TBL(['類別', '數量', '範例'], [
    ['Session', '28', '/new, /retry, /undo, /compress, /background'],
    ['Config', '11', '/model, /personality, /reasoning, /voice, /yolo'],
    ['Tools & Skills', '11', '/tools, /skills, /cron, /plugins, /reload'],
    ['Info', '11', '/help, /status, /usage, /version, /debug'],
])
c5 += P('所有消費端（help 文字、自動補全、Telegram 選單、Slack mapping）都從這個 registry 自動衍生。')
mkchapter('第五章：CLI 與命令系統', 'ch05.xhtml', c5)

# ── Ch6: Gateway ──
c6 = H1('第六章：Gateway 多平台架構')
c6 += P('Gateway 是 Hermes 的多平台即時通訊閘道，支援 14+ 平台：Telegram、Discord、Slack、WhatsApp、Signal、Matrix、微信、企業微信、飛書、釘釘、Email、SMS、Home Assistant 等。')
c6 += H2('6.1 平台註冊表')
c6 += P('PlatformRegistry（platform_registry.py，259 行）採用 singleton + factory pattern。Plugin 可以動態註冊新平台：每個 PlatformEntry 包含 name、label、adapter_factory、check_fn、required_env。')
c6 += H2('6.2 訊息投遞')
c6 += P('DeliveryRouter（delivery.py，433 行）支援多種目標格式：origin（來源）、local（本地檔案）、telegram（主頻道）、telegram:123456（特定 chat）、telegram:123456:thread（特定 thread）。內建 silence-narration 過濾，防止 bot-to-bot 無限回音。')
c6 += H2('6.3 Hook 系統')
c6 += P('HookRegistry（hooks.py，210 行）支援事件類型：gateway:startup、session:start、agent:start、command:*（wildcard）。Hook 目錄：~/.hermes/hooks/<name>/，包含 HOOK.yaml + handler.py。')
mkchapter('第六章：Gateway', 'ch06.xhtml', c6)

# ── Ch7: Cron ──
c7 = H1('第七章：Cron 排程系統')
c7 += H2('7.1 任務儲存')
c7 += P('Cron 任務以 JSON 儲存在 ~/.hermes/cron/jobs.json。支援 duration 格式（"30m"、"2h"）和標準 cron 表達式（透過 croniter）。任務欄位包含 id、name、schedule、prompt、skills、script、state、workdir、profile、no_agent 等。')
c7 += H2('7.2 排程器架構')
c7 += P('Scheduler（scheduler.py，2,256 行）使用雙執行緒池：_parallel_pool（獨立任務並行執行）、_sequential_pool（env/context 變異任務順序執行）。tick() 每 60s 被 gateway background thread 呼叫。Cron 環境總是禁用 cronjob、messaging、clarify 三個工具集。')
c7 += H2('7.3 安全性')
c7 += P('包含注入掃描器 CrobPromptInjectionBlocked、_IMMUTABLE_JOB_FIELDS（id 不可變更防路徑遍歷）、檔案鎖 ~/.hermes/cron/.tick.lock 防止多 process 重疊、SILENT_MARKER 機制。')
mkchapter('第七章：Cron 排程', 'ch07.xhtml', c7)

# ── Ch8: Skills ──
c8 = H1('第八章：Skills 與 Curator')
c8 += H2('8.1 技能目錄結構')
c8 += PRE("""skills/
+-- autonomous-ai-agents/hermes-agent/SKILL.md
+-- creative/comfyui/SKILL.md   (含 scripts/, tests/)
+-- devops/kanban-orchestrator/SKILL.md
+-- software-development/plan/SKILL.md
+-- ... (26+ 技能目錄)""")
c8 += P('每個 skill 目錄包含 SKILL.md（必要，含 YAML frontmatter）、scripts/、references/、templates/、tests/。')
c8 += H2('8.2 載入機制')
c8 += P('採用 progressive disclosure 架構：skills_list() 只回傳 metadata，skill_view() 載入完整內容。每個 SKILL.md 自動註冊一個斜線命令（/<skill-name>），與 gateway 的 Telegram/Discord 命令選單整合。')
c8 += H2('8.3 Curator 背景維護')
c8 += P('Curator（agent/curator.py，1,843 行）負責技能背景維護：追蹤使用情況、標記閒置技能為 stale、歸檔過時技能。支援 CLI 指令：hermes curator status/run/pause/pin/archive/restore。僅操作 created_by:"agent" 的技能，bundled + hub 安裝的不可變。')
mkchapter('第八章：Skills 與 Curator', 'ch08.xhtml', c8)

# ── Ch9: Credential Pooling ──
c9 = H1('第九章：Credential Pooling 與模型路由')
c9 += H2('9.1 Credential Pool')
c9 += P('CredentialPool（credential_pool.py，2,183 行）支援多種選取策略：FILL_FIRST、ROUND_ROBIN、RANDOM、LEAST_USED。當 API 調用失敗時自動觸發 rotation，標記當前 credential 為 exhausted 並進入冷卻（401: 5 分鐘，429: 1 小時，default: 1 小時）。')
c9 += H2('9.2 輔助模型路由')
c9 += P('AuxiliaryClient（auxiliary_client.py，5,828 行）提供自動解析鏈，支援所有輔助任務（context compression、vision、session search）：用戶主 provider -> OpenRouter -> Nous Portal -> 自訂端點 -> Anthropic -> 直接 API-key providers。')
c9 += H2('9.3 Fallback Chain')
c9 += P('在 agent_init.py（行 881-904）初始化，支援多層 fallback：所有重試用盡、速率限制、上下文超長壓縮失敗、非可重試錯誤、空回應等時機都會觸發 fallback。')
mkchapter('第九章：Credential Pooling', 'ch09.xhtml', c9)

# ── Ch10: Security ──
c10 = H1('第十章：安全系統')
c10 += H2('10.1 命令審批（tools/approval.py，1,697 行）')
c10 += P('三層防禦：')
c10 += UL([
    'Hardline patterns — 無條件封鎖，連 yolo 模式也無法繞過：rm -rf /、mkfs、dd、fork bomb、shutdown',
    'Dangerous patterns — 47 條規則，yolo 可繞過：遞迴刪除、chmod/chown 危險操作、SQL DROP/DELETE',
    'sudo stdin guard — 當 SUDO_PASSWORD 未設定時封鎖 sudo -S',
])
c10 += H2('10.2 檔案安全（agent/file_safety.py，640 行）')
c10 += P('寫入封鎖：SSH keys、shell rc、網路憑證、sudoers、~/.hermes/ 控制面檔案。讀取封鎖：Skills .hub/index-cache、auth.json、.env 系列檔案。跨 profile 寫入防護：skills/plugins/cron/memories 目錄受保護。')
c10 += H2('10.3 Cron 注入掃描（tools/cronjob_tools.py）')
c10 += P('雙層威脅掃描：使用者輸入掃描（嚴格模式，檢查命令注入、欺騙、秘密讀取）、技能組裝掃描（寬鬆模式，防止技能內容中的安全文檔誤報）。支援隱藏 Unicode 防禦（ZWJ 字符檢測）。')
c10 += H2('10.4 Secret Redaction')
c10 += P('security.redact_secrets 配置控制 API keys、tokens 等敏感資訊的自動遮罩，關閉狀態 tool output 原樣傳遞。')
mkchapter('第十章：安全系統', 'ch10.xhtml', c10)

# ── Ch11: Config & State ──
c11 = H1('第十一章：設定管理與 Session 儲存')
c11 += H2('11.1 設定管理（hermes_cli/config.py，6,298 行）')
c11 += P('三重快取系統：_LOAD_CONFIG_CACHE（(path, mtime_ns, size) 為 key，避免重複 yaml.safe_load，每次 ~13ms）、_RAW_CONFIG_CACHE、_CONFIG_LOCK（RLock）。安全措施：_ENV_VAR_NAME_DENYLIST（禁止寫入 LD_PRELOAD、PATH 等危險 env var）、_backup_corrupt_config()（corrupt 文件自動備份）。Managed Mode 支援 NixOS 聲明式設定。')
c11 += H2('11.2 Session 儲存（hermes_state.py，4,284 行）')
c11 += P('基於 SQLite，檔案位於 ~/.hermes/state.db。Schema 版本 14。關鍵設計：WAL 模式 + fallback（若因 NFS/SMB/FUSE 失敗自動降級到 DELETE journal）、FTS5 全文搜尋、Session 分裂（壓縮觸發，透過 parent_session_id 鏈分裂）、thread-safe 快取。')
c11 += HR()
c11 += P('<i>本書由 tGD Analysis 於 2026 年 6 月自動生成，基於 Hermes Agent v0.16.0 源碼。所有程式碼片段均來自 Hermes Agent 開源專案。</i>')
mkchapter('第十一章：設定與 Session', 'ch11.xhtml', c11)

book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())
epub.write_epub(OUT, book, {})
print(f'Done: {OUT}')
