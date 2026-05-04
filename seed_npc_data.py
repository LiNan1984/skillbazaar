#!/usr/bin/env python3
"""SkillBazaar NPC Agent 数据填充脚本 — 创建真实用户、悬赏任务、丰富商品"""
import requests, json, random, time

BASE = "http://localhost:8000/api"

# ===== 1. 注册NPC用户 =====
npcs = [
    {"username": "quant_alice", "password": "npc2024alice", "nickname": "量化Alice"},
    {"username": "llm_bob", "password": "npc2024bob", "nickname": "大模型Bob"},
    {"username": "dev_charlie", "password": "npc2024charlie", "nickname": "全栈Charlie"},
    {"username": "data_diana", "password": "npc2024diana", "nickname": "数据Diana"},
    {"username": "security_eve", "password": "npc2024eve", "nickname": "安全Eve"},
    {"username": "product_frank", "password": "npc2024frank", "nickname": "产品Frank"},
    {"username": "ml_grace", "password": "npc2024grace", "nickname": "ML Grace"},
    {"username": "infra_heidi", "password": "npc2024heidi", "nickname": "运维Heidi"},
    {"username": "content_ivan", "password": "npc2024ivan", "nickname": "内容Ivan"},
    {"username": "api_judy", "password": "npc2024judy", "nickname": "API Judy"},
]

npc_tokens = {}
npc_ids = {}
print("=" * 60)
print("🎭 注册NPC用户")
print("=" * 60)
for npc in npcs:
    r = requests.post(f"{BASE}/v2/auth/register", json=npc)
    if r.status_code == 201:
        data = r.json()
        npc_tokens[npc["username"]] = data["token"]
        npc_ids[npc["username"]] = data["user_id"]
        print(f"  ✅ {npc['nickname']}({npc['username']}): {data['user_id'][:8]}...")
    else:
        # Try login
        r2 = requests.post(f"{BASE}/v2/auth/login", json={"username": npc["username"], "password": npc["password"]})
        if r2.status_code == 200:
            data = r2.json()
            npc_tokens[npc["username"]] = data["token"]
            npc_ids[npc["username"]] = data["user_id"]
            print(f"  ✅ {npc['nickname']} 已存在，登录成功")
        else:
            print(f"  ❌ {npc['nickname']} 注册/登录失败: {r.text[:100]}")

# Give all NPCs lots of coins
import sqlite3
conn = sqlite3.connect("/root/skillbazaar/backend/data/skillbazaar.db")
c = conn.cursor()
for uid in npc_ids.values():
    c.execute("UPDATE users SET coins = 999999 WHERE id = ?", (uid,))
conn.commit()
conn.close()
print("  💰 所有NPC用户已充值999999金币")

# ===== 2. 创建真实悬赏任务 =====
print("\n" + "=" * 60)
print("🏆 创建悬赏任务")
print("=" * 60)

bounties = [
    {
        "title": "量化交易策略回测Agent开发",
        "description": "开发一个基于LangGraph的量化交易策略回测Agent，支持A股/美股数据源接入，能自动运行策略回测并生成收益报告。要求：1)支持至少3种技术指标策略 2)回测结果可视化 3)自动风控评估",
        "category": "Agent",
        "tags": json.dumps(["量化交易", "LangGraph", "回测", "金融"]),
        "budget_min": 5000,
        "budget_max": 15000,
        "deadline": "2026-06-01",
        "skill_type": "agent",
        "requirements": "熟悉LangGraph、pandas、matplotlib；有量化交易开发经验优先"
    },
    {
        "title": "RAG知识库构建与优化",
        "description": "为企业内部文档（PDF/Word/Confluence）构建RAG系统，要求：1)多格式文档解析 2)混合检索（向量+关键词） 3)答案溯源标注 4)支持增量更新。使用LlamaIndex或LangChain，部署为API服务",
        "category": "Skill",
        "tags": json.dumps(["RAG", "LlamaIndex", "知识库", "企业应用"]),
        "budget_min": 8000,
        "budget_max": 20000,
        "deadline": "2026-05-20",
        "skill_type": "skill",
        "requirements": "3年以上NLP经验，熟悉向量数据库Milvus/Weaviate"
    },
    {
        "title": "AI客服智能体编排Workflow",
        "description": "设计并实现一个多轮对话客服智能体Workflow：意图识别→知识检索→回复生成→人工转接。要求集成企业微信/飞书，支持上下文记忆，SLA < 2秒响应",
        "category": "Workflow",
        "tags": json.dumps(["客服", "多轮对话", "飞书集成", "Workflow"]),
        "budget_min": 10000,
        "budget_max": 30000,
        "deadline": "2026-06-15",
        "skill_type": "workflow",
        "requirements": "有客服系统开发经验，熟悉LangGraph/CrewAI"
    },
    {
        "title": "GitHub仓库自动审计Cron",
        "description": "开发定时Cron任务，每日自动扫描指定GitHub组织下的所有仓库，检查：1)依赖安全漏洞 2)代码质量指标 3)PR/Issue响应时间。生成报告推送到飞书/Slack",
        "category": "Cron",
        "tags": json.dumps(["GitHub", "安全审计", "定时任务", "DevOps"]),
        "budget_min": 3000,
        "budget_max": 8000,
        "deadline": "2026-05-15",
        "skill_type": "cron",
        "requirements": "熟悉GitHub API、依赖分析工具(Snyk/Dependabot)"
    },
    {
        "title": "多模态文档理解Agent",
        "description": "构建能理解图文混排文档（如财报、合同）的Agent，支持：1)表格数据提取 2)图表解读 3)关键条款标注 4)风险提示。输出结构化JSON + 自然语言摘要",
        "category": "Agent",
        "tags": json.dumps(["多模态", "文档理解", "OCR", "GPT-4V"]),
        "budget_min": 12000,
        "budget_max": 35000,
        "deadline": "2026-06-30",
        "skill_type": "agent",
        "requirements": "熟悉GPT-4V/Claude Vision API，有OCR开发经验"
    },
    {
        "title": "竞品监控与分析Cron服务",
        "description": "定时监控竞品网站/APP的更新动态：1)价格变动追踪 2)新功能上线提醒 3)用户评价情感分析 4)自动生成竞品周报。支持配置监控频率和关键词",
        "category": "Cron",
        "tags": json.dumps(["竞品分析", "爬虫", "情感分析", "定时推送"]),
        "budget_min": 4000,
        "budget_max": 10000,
        "deadline": "2026-05-25",
        "skill_type": "cron",
        "requirements": "熟悉Playwright/Puppeteer爬虫，NLP情感分析"
    },
    {
        "title": "智能代码审查Agent",
        "description": "开发自动代码审查Agent：1)接入GitHub/GitLab Webhook 2)自动分析PR代码质量 3)检测安全漏洞和性能问题 4)生成审查意见并@相关开发者。支持自定义审查规则",
        "category": "Agent",
        "tags": json.dumps(["代码审查", "AST分析", "GitHub", "自动化"]),
        "budget_min": 6000,
        "budget_max": 18000,
        "deadline": "2026-06-10",
        "skill_type": "agent",
        "requirements": "熟悉AST解析、LLM代码理解能力，有DevSecOps经验"
    },
    {
        "title": "自动化A/B测试Workflow",
        "description": "设计A/B测试全流程自动化Workflow：实验设计→流量分配→指标收集→统计显著性判断→结果报告。集成Mixpanel/Amplitude，支持多变量测试",
        "category": "Workflow",
        "tags": json.dumps(["A/B测试", "统计分析", "产品优化", "自动化"]),
        "budget_min": 5000,
        "budget_max": 12000,
        "deadline": "2026-05-30",
        "skill_type": "workflow",
        "requirements": "统计学背景，熟悉A/B测试方法论和工具"
    },
    {
        "title": "AI生成内容审核Agent",
        "description": "开发AI生成内容（文本/图片）的审核Agent：1)涉黄/涉政/涉暴检测 2)幻觉内容识别 3)版权侵权比对 4)审核结果分类+处置建议。要求误判率<1%",
        "category": "Agent",
        "tags": json.dumps(["内容审核", "安全合规", "LLM幻觉检测", "版权"]),
        "budget_min": 8000,
        "budget_max": 25000,
        "deadline": "2026-06-20",
        "skill_type": "agent",
        "requirements": "有内容安全审核系统开发经验，熟悉合规要求"
    },
    {
        "title": "数据管道编排Workflow模板",
        "description": "构建通用数据管道编排Workflow模板：1)支持Airflow/Prefect风格DAG 2)内置常用ETL算子 3)失败重试+断点续传 4)数据质量检查节点。可复用、可配置",
        "category": "Workflow",
        "tags": json.dumps(["数据管道", "ETL", "DAG", "数据质量"]),
        "budget_min": 6000,
        "budget_max": 15000,
        "deadline": "2026-06-05",
        "skill_type": "workflow",
        "requirements": "3年以上数据工程经验，熟悉Airflow/dbt"
    },
]

for i, bounty in enumerate(bounties):
    # Pick a random NPC as poster
    poster = random.choice(list(npc_ids.keys()))
    token = npc_tokens[poster]
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE}/bounties", json=bounty, headers=headers)
    if r.status_code in (200, 201):
        data = r.json()
        print(f"  ✅ [{i+1}] {bounty['title']} (预算¥{bounty['budget_min']}-{bounty['budget_max']}) by {poster}")
    else:
        print(f"  ❌ [{i+1}] {bounty['title']}: {r.text[:150]}")

# ===== 3. 上传高质量Agent/Workflow商品（NPC卖家）=====
print("\n" + "=" * 60)
print("🏪 NPC上传高质量商品")
print("=" * 60)

high_quality_products = [
    # Agent类
    {"name": "LangGraph多Agent协作框架", "description": "基于LangGraph构建的多Agent协作框架，支持Supervisor/Chain/Parallel三种编排模式。内置工具调用、记忆管理、错误恢复。适用于复杂业务流程自动化。", "category": "Agent", "sub_category": "多Agent", "price": 299, "original_price": 599, "seller_name": "全栈Charlie", "tags": json.dumps(["LangGraph", "多Agent", "协作", "编排"]), "source_platform": "原创", "pricing_model": "one_time", "downloads": 2847, "rating": 4.9, "sales": 1523, "demand_score": 95},
    {"name": "AutoGPT自主任务执行Agent", "description": "自主规划与执行复杂任务的AI Agent，支持目标分解、工具调用、自我反思。可接入浏览器、代码执行器、文件系统。已验证可用于市场调研、数据分析等场景。", "category": "Agent", "sub_category": "自主Agent", "price": 399, "original_price": 799, "seller_name": "量化Alice", "tags": json.dumps(["AutoGPT", "自主执行", "任务规划", "工具调用"]), "source_platform": "原创", "pricing_model": "one_time", "downloads": 3521, "rating": 4.8, "sales": 1876, "demand_score": 98},
    {"name": "CrewAI团队协作Agent组", "description": "5个专业Agent组成虚拟团队：研究员、分析师、作者、审核员、项目经理。自动分工协作完成报告撰写、市场分析等任务。支持自定义Agent角色和流程。", "category": "Agent", "sub_category": "团队协作", "price": 499, "original_price": 899, "seller_name": "产品Frank", "tags": json.dumps(["CrewAI", "团队", "协作", "自动化"]), "source_platform": "原创", "pricing_model": "subscription", "downloads": 1923, "rating": 4.7, "sales": 987, "demand_score": 88},
    {"name": "代码安全审计Agent", "description": "自动扫描代码仓库的安全漏洞：SQL注入、XSS、硬编码密钥、依赖漏洞。支持GitHub/GitLab集成，PR自动审查。基于Semgrep+LLM双重检测，误报率<3%。", "category": "Agent", "sub_category": "安全", "price": 199, "original_price": 399, "seller_name": "安全Eve", "tags": json.dumps(["安全审计", "代码扫描", "DevSecOps", "Semgrep"]), "source_platform": "原创", "pricing_model": "one_time", "downloads": 4210, "rating": 4.9, "sales": 2340, "demand_score": 96},
    {"name": "智能客服对话Agent", "description": "多轮对话客服Agent，支持意图识别→知识检索→回复生成→人工转接。内置100+行业知识模板，5分钟接入企业微信/飞书。SLA < 1.5秒响应。", "category": "Agent", "sub_category": "客服", "price": 349, "original_price": 699, "seller_name": "API Judy", "tags": json.dumps(["客服", "对话", "飞书", "企业微信"]), "source_platform": "原创", "pricing_model": "subscription", "downloads": 5678, "rating": 4.8, "sales": 3120, "demand_score": 99},
    
    # Workflow类
    {"name": "CI/CD全流程自动化Workflow", "description": "从代码提交到生产部署的全流程自动化：代码检查→单元测试→构建镜像→灰度发布→健康检查→全量发布。支持GitHub Actions/GitLab CI，内置回滚机制。", "category": "Workflow", "sub_category": "DevOps", "price": 249, "original_price": 499, "seller_name": "运维Heidi", "tags": json.dumps(["CI/CD", "自动化", "DevOps", "部署"]), "source_platform": "原创", "pricing_model": "one_time", "downloads": 3102, "rating": 4.9, "sales": 1678, "demand_score": 94},
    {"name": "数据处理ETL Workflow模板", "description": "通用ETL数据管道模板：支持CSV/JSON/API/数据库多源接入，内置清洗、转换、聚合算子。支持Airflow风格DAG编排，失败自动重试+断点续传。", "category": "Workflow", "sub_category": "数据工程", "price": 179, "original_price": 359, "seller_name": "数据Diana", "tags": json.dumps(["ETL", "数据管道", "Airflow", "数据质量"]), "source_platform": "原创", "pricing_model": "one_time", "downloads": 2890, "rating": 4.7, "sales": 1456, "demand_score": 90},
    {"name": "A/B测试全流程Workflow", "description": "实验设计→流量分配→指标收集→统计显著性判断→结果报告的完整A/B测试Workflow。集成Mixpanel/Amplitude，支持贝叶斯和频率学派两种分析方法。", "category": "Workflow", "sub_category": "产品", "price": 199, "original_price": 399, "seller_name": "产品Frank", "tags": json.dumps(["A/B测试", "统计分析", "产品优化"]), "source_platform": "原创", "pricing_model": "one_time", "downloads": 1567, "rating": 4.6, "sales": 823, "demand_score": 82},
    {"name": "内容营销自动化Workflow", "description": "关键词研究→选题生成→内容撰写→SEO优化→多平台发布的自动化营销Workflow。支持小红书/微信公众号/知乎/头条，AI生成+人工审核模式。", "category": "Workflow", "sub_category": "营销", "price": 299, "original_price": 599, "seller_name": "内容Ivan", "tags": json.dumps(["营销", "SEO", "内容生成", "多平台"]), "source_platform": "原创", "pricing_model": "subscription", "downloads": 2234, "rating": 4.8, "sales": 1190, "demand_score": 91},
    {"name": "模型训练MLOps Workflow", "description": "数据版本管理→特征工程→模型训练→评估→注册→部署的完整MLOps Workflow。集成MLflow/W&B，支持GPU自动调度和超参搜索。", "category": "Workflow", "sub_category": "MLOps", "price": 349, "original_price": 699, "seller_name": "ML Grace", "tags": json.dumps(["MLOps", "训练", "MLflow", "GPU"]), "source_platform": "原创", "pricing_model": "one_time", "downloads": 1876, "rating": 4.7, "sales": 945, "demand_score": 87},
    
    # 高价Skill
    {"name": "GPT-4 Turbo精调Prompt工程套件", "description": "经过500+场景验证的Prompt工程模板库，覆盖客服、写作、编程、分析4大类32个子场景。每个模板含System Prompt + Few-shot示例 + 调优参数。平均效果提升40%。", "category": "Skill", "sub_category": "Prompt工程", "price": 149, "original_price": 299, "seller_name": "大模型Bob", "tags": json.dumps(["Prompt", "GPT-4", "模板", "工程化"]), "source_platform": "原创", "pricing_model": "one_time", "downloads": 8901, "rating": 4.9, "sales": 5678, "demand_score": 99},
    {"name": "LangChain RAG最佳实践模板", "description": "生产级RAG系统模板：混合检索(向量+BM25)、查询改写、重排序、答案溯源。支持PDF/Word/HTML/Markdown多格式，已验证可处理百万级文档。", "category": "Skill", "sub_category": "RAG", "price": 199, "original_price": 399, "seller_name": "大模型Bob", "tags": json.dumps(["RAG", "LangChain", "混合检索", "生产级"]), "source_platform": "原创", "pricing_model": "one_time", "downloads": 6543, "rating": 4.8, "sales": 3456, "demand_score": 97},
    {"name": "Dify应用开发脚手架", "description": "Dify平台应用开发脚手架：预设5种应用模板（客服/写作/知识库/数据分析/代码助手），内置API网关、用户管理、用量计费。开箱即用，5分钟上线。", "category": "Skill", "sub_category": "低代码", "price": 99, "original_price": 199, "seller_name": "全栈Charlie", "tags": json.dumps(["Dify", "低代码", "脚手架", "快速开发"]), "source_platform": "原创", "pricing_model": "one_time", "downloads": 7234, "rating": 4.7, "sales": 4123, "demand_score": 95},
]

for i, prod in enumerate(high_quality_products):
    r = requests.post(f"{BASE}/products", json=prod)
    if r.status_code in (200, 201):
        data = r.json()
        print(f"  ✅ [{i+1}] {prod['name']} ¥{prod['price']} by {prod['seller_name']}")
    else:
        print(f"  ❌ [{i+1}] {prod['name']}: {r.text[:150]}")

# ===== 4. NPC申请悬赏 =====
print("\n" + "=" * 60)
print("📋 NPC申请悬赏任务")
print("=" * 60)

# Get bounties
r = requests.get(f"{BASE}/bounties")
bounty_list = r.json().get("bounties", r.json().get("items", []))
if isinstance(bounty_list, list) and len(bounty_list) > 0:
    for b in bounty_list[:5]:
        bounty_id = b["id"]
        # Random NPC applies
        applicant = random.choice(list(npc_tokens.keys()))
        token = npc_tokens[applicant]
        headers = {"Authorization": f"Bearer {token}"}
        apply_data = {
            "message": f"我是{applicant}，有相关经验，希望能承接此任务。",
            "proposed_price": random.randint(b["budget_min"], b["budget_max"]),
            "estimated_days": random.randint(3, 14)
        }
        r = requests.post(f"{BASE}/bounties/{bounty_id}/apply", json=apply_data, headers=headers)
        if r.status_code in (200, 201):
            print(f"  ✅ {applicant} 申请了 [{b['title'][:20]}...]")
        else:
            print(f"  ⚠️ {applicant} 申请失败: {r.text[:80]}")

print("\n" + "=" * 60)
print("🎉 NPC数据填充完成！")
print("=" * 60)
