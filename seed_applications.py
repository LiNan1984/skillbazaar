#!/usr/bin/env python3
"""Insert bounty applications into DB"""
import sqlite3, random

conn = sqlite3.connect("/root/skillbazaar/backend/data/skillbazaar.db")
c = conn.cursor()

c.execute("SELECT id, username FROM users WHERE username IN ('quant_alice','llm_bob','dev_charlie','data_diana','security_eve','product_frank','ml_grace','infra_heidi','content_ivan','api_judy')")
npcs = {r[1]: r[0] for r in c.fetchall()}

c.execute("SELECT id, poster_id, title, budget_min, budget_max FROM bounties WHERE status='open'")
all_bounties = c.fetchall()

for bounty in all_bounties:
    bid, poster_id, title, bmin, bmax = bounty
    applicants = [n for n in npcs.keys() if npcs[n] != poster_id]
    num_apps = random.randint(2, 4)
    for app_name in random.sample(applicants, min(num_apps, len(applicants))):
        app_id = npcs[app_name]
        c.execute("""INSERT INTO bounty_applications 
            (bounty_id, developer_id, proposal, estimated_days, quoted_price, portfolio, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', datetime('now'))""",
            (bid, app_id, f"我是{app_name}，有丰富相关经验，希望承接此任务。已有3个类似项目交付经验。", 
             random.randint(3, 14), random.randint(bmin, bmax), "多个生产级AI Agent项目经验"))
    print(f"  📋 {title[:25]}... 收到{num_apps}份申请")

conn.commit()
c.execute("SELECT COUNT(*) FROM bounty_applications")
print(f"\nTotal applications: {c.fetchone()[0]}")
conn.close()
