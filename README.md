# AI 数据前沿周报自动程序

这是一个本地运行的 AI 数据领域周报程序。它每周抓取近 7 天 arXiv 上与 AI 数据相关的新论文，生成 Markdown 源文件和可在线阅读的 HTML 周报，更新静态网页，并把结果提交、推送到 GitHub 仓库。GitHub Pages 只负责展示页面，调度在本地完成。

## 目录结构

```text
.
├── data/weeks.json              # 周报索引，供网页读取
├── weekly/                      # 每周 Markdown 源文件和 HTML 阅读页
├── scripts/update_weekly.py     # 抓取论文并生成本周 Markdown
├── scripts/build_site.py        # 根据 weeks.json 生成首页和周报 HTML
├── scripts/ai_weekly_agent.py   # 本地自动程序入口：抓取、构建、提交、推送
├── scripts/install_macos_schedule.py
└── index.html                   # GitHub Pages 首页
```

## 本地手动运行

```bash
python3 scripts/ai_weekly_agent.py
```

只更新网页和提交已有内容，不重新抓取：

```bash
python3 scripts/ai_weekly_agent.py --no-fetch
```

只测试生成，不推送：

```bash
python3 scripts/ai_weekly_agent.py --no-push
```

## 安装每周日定时任务

macOS 下运行：

```bash
python3 scripts/install_macos_schedule.py
```

默认每周日 **10:00 本地时间** 执行一次。日志会写入：

```text
logs/weekly-agent.out.log
logs/weekly-agent.err.log
```

## GitHub Pages 设置

仓库推送到 GitHub 后，在 GitHub 页面设置：

1. 打开仓库 `Settings`
2. 进入 `Pages`
3. Source 选择 `Deploy from a branch`
4. Branch 选择 `main`
5. Folder 选择 `/root`

发布后，页面地址通常是：

```text
https://perfectar.github.io/ai-data-weekly-tracker/
```

## 说明

- 自动抓取来源：arXiv API。
- 检索范围：`cs.AI`、`cs.CL`、`cs.LG`、`cs.CV`、`stat.ML`。
- 过滤逻辑：根据数据选择、数据质量、合成数据、数据治理、数据集、标注、隐私、多模态语料等关键词打分。
- 每周文件名使用 ISO 周格式，例如 `weekly/2026-W20.md` 和 `weekly/2026-W20.html`。
- 邮件通知中的本周周报链接指向 HTML 阅读页，Markdown 仅作为源文件保留。
- 后续可以把关键词、趋势规则和摘要逻辑继续增强成更强的 agent。
