#!/usr/bin/env python3
"""Insert bounties + applications directly into DB"""
import sqlite3, json, random

conn = sqlite3.connect("/root/skillbazaar/backend/data/skillbazaar.db")
c = conn.cursor()

# Get NPC user IDs
c.execute("SELECT id, username FROM users WHERE username IN ('quant_alice','llm_bob','dev_charlie','data_diana','security_eve','product_frank','ml_grace','infra_heidi','content_ivan','api_judy')")
npcs = {r[1]: r[0] for r in c.fetchall()}
print("NPCs:", list(npcs.keys()))

bounties = [
    ("量化交易策略回测Agent开发", "开发一个基于LangGraph的量化交易策略回测Agent，支持A股/美股数据源接入，能自动运行策略回测并生成收益报告。要求：1)支持至少3种技术指标策略 2)回测结果可视化 3)自动风控评估", "Agent", '["量化交易","LangGraph","回测","金融"]', 5000, 15000, "2026-06-01", "agent", "熟悉LangGraph、pandas、matplotlib；有量化交易开发经验优先"),
    ("RAG知识库构建与优化", "为企业内部文档（PDF/Word/Confluence）构建RAG系统，要求：1)多格式文档解析 2)混合检索（向量+关键词）3)答案溯源标注 4)支持增量更新", "Skill", '["RAG","LlamaIndex","知识库"]', 8000, 20000, "2026-05-20", "skill", "3年以上NLP经验，熟悉向量数据库"),
    ("AI客服智能体编排Workflow", "多轮对话客服智能体Workflow：意图识别→知识检索→回复生成→人工转接。集成企业微信/飞书，SLA<2秒", "Workflow", '["客服","飞书","Workflow"]', 10000, 30000, "2026-06-15", "workflow", "有客服系统开发经验"),
    ("GitHub仓库自动审计Cron", "定时Cron任务，每日扫描GitHub仓库检查依赖安全漏洞、代码质量、PR响应时间，报告推送飞书/Slack", "Cron", '["GitHub","安全审计","DevOps"]', 3000, 8000, "2026-05-15", "cron", "熟悉GitHub API"),
    ("多模态文档理解Agent", "理解图文混排文档Agent：表格提取、图表解读、关键条款标注、风险提示。输出结构化JSON+摘要", "Agent", '["多模态","OCR","GPT-4V"]', 12000, 35000, "2026-06-30", "agent", "熟悉GPT-4V API"),
    ("竞品监控Cron服务", "定时监控竞品动态：价格追踪、新功能提醒、用户评价情感分析、竞品周报自动生成", "Cron", '["竞品分析","爬虫","情感分析"]', 4000, 10000, "2026-05-25", "cron", "熟悉Playwright爬虫"),
    ("智能代码审查Agent", "自动代码审查Agent：接入GitHub Webhook→分析PR代码质量→检测安全漏洞→生成审查意见", "Agent", '["代码审查","GitHub","自动化"]', 6000, 18000, "2026-06-10", "agent", "熟悉AST解析"),
    ("自动化A/B测试Workflow", "A/B测试全流程自动化：实验设计→流量分配→指标收集→统计显著性→结果报告", "Workflow", '["A/B测试","统计分析"]', 5000, 12000, "2026-05-30", "workflow", "统计学背景"),
    ("AI内容审核Agent", "AI生成内容审核Agent：涉黄/涉政/涉暴检测、幻觉识别、版权比对、处置建议。误判率<1%", "Agent", '["内容审核","安全合规"]', 8000, 25000, "2026-06-20", "agent", "有内容安全审核经验"),
    ("数据管道ETL Workflow", "通用数据管道Workflow：Airflow风格DAG编排、内置ETL算子、失败重试+断点续传、数据质量检查", "Workflow", '["ETL","DAG","数据质量"]', 6000, 15000, "2026-06-05", "workflow", "3年数据工程经验"),
]

poster_names = list(npcs.keys())
for i, (title, desc, cat, tags, bmin, bmax, deadline, stype, reqs) in enumerate(bounties):
    poster = random.choice(poster_names)
    poster_id = npcs[poster]
    c.execute("""INSERT INTO bounties 
        (poster_id, title, description, category, tags, budget_min, budget_max, deadline, status, skill_type, requirements)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
        (poster_id, title, desc, cat, tags, bmin, bmax, deadline, stype, reqs))
    print(f"  ✅ [{i+1}] {title} (¥{bmin}-{bmax}) by {poster}")

conn.commit()

# Add bounty applications
c.execute("SELECT id, poster_id, title FROM bounties WHERE status='open'")
all_bounties = c.fetchall()
for bounty in all_bounties:
    bid, poster_id, title = bounty
    applicants = [n for n in poster_names if npcs[n] != poster_id]
    num_apps = random.randint(2, 4)
    for app_name in random.sample(applicants, min(num_apps, len(applicants))):
        app_id = npcs[app_name]
        c.execute("""INSERT INTO bounty_applications 
            (bounty_id, developer_id, message, proposed_price, estimated_days, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', datetime('now'))""",
            (bid, app_id, f"我是{app_name}，有丰富相关经验，希望承接此任务。", 
             random.randint(5000, 30000), random.randint(3, 14)))
    print(f"  📋 {title[:25]}... 收到{num_apps}份申请")

conn.commit()

# Stats
c.execute("SELECT COUNT(*) FROM bounties")
print(f"Total bounties: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM bounty_applications")
print(f"Total applications: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM products WHERE status='active'")
print(f"Total products: {c.fetchone()[0]}")
conn.close()
print("\n✅ 悬赏数据填充完成！")
