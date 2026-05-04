"""Seed licenses and transactions so '我的库' (My Library) has real purchased items"""
import sqlite3
import uuid
from datetime import datetime, timedelta
import random

conn = sqlite3.connect("/root/skillbazaar/backend/data/skillbazaar.db")
c = conn.cursor()

# Build nickname -> user_id mapping for ALL users
c.execute("SELECT id, nickname, username FROM users WHERE nickname IS NOT NULL")
nick_map = {}
for uid, nick, uname in c.fetchall():
    if nick:
        nick_map[nick] = uid

print(f"Nickname map: {len(nick_map)} entries")

c.execute("SELECT id, name, price, category, seller_name FROM products WHERE status='active' ORDER BY RANDOM() LIMIT 50")
products = c.fetchall()
print(f"Products: {len(products)}")

# Get all user IDs that have nicknames
c.execute("SELECT id FROM users WHERE id IN (SELECT id FROM users WHERE nickname IS NOT NULL)")
all_user_ids = [r[0] for r in c.fetchall()]
print(f"All users with nicknames: {len(all_user_ids)}")

transactions = []
licenses = []
now = datetime.utcnow()

# For each real user, create purchases
for buyer_id in all_user_ids:
    bought_count = random.randint(3, 8)
    bought = random.sample(products, min(bought_count, len(products)))
    for pid, name, price, cat, seller_name in bought:
        # Find seller_id from nickname
        seller_id = nick_map.get(seller_name)
        if not seller_id or seller_id == buyer_id:
            # Use a random different user as seller
            potential_sellers = [u for u in all_user_ids if u != buyer_id]
            if potential_sellers:
                seller_id = random.choice(potential_sellers)
            else:
                continue
        
        license_token = f"SKBZ-{cat.upper()[:3]}-{uuid.uuid4().hex[:12].upper()}"
        days_ago = random.randint(1, 30)
        created = (now - timedelta(days=days_ago)).isoformat()
        expires = (now + timedelta(days=365-days_ago)).isoformat()
        max_calls = random.choice([100, 500, 1000, 5000, -1])
        
        transactions.append((buyer_id, seller_id, pid, price, "purchase", "completed", created))
        licenses.append((buyer_id, pid, "standard", license_token, expires, max_calls, random.randint(0, 50), "active", created))
        
        c.execute("UPDATE user_profiles SET total_earned = total_earned + ?, total_sales = total_sales + 1 WHERE user_id = ?", (price, seller_id))

# Extra purchases for quant_alice (our screenshot user)
c.execute("SELECT id FROM users WHERE username='quant_alice'")
qa = c.fetchone()
if qa:
    qa_id = qa[0]
    bought = random.sample(products, min(15, len(products)))
    for pid, name, price, cat, seller_name in bought:
        seller_id = nick_map.get(seller_name)
        if not seller_id or seller_id == qa_id:
            potential_sellers = [u for u in all_user_ids if u != qa_id]
            seller_id = random.choice(potential_sellers) if potential_sellers else None
            if not seller_id: continue
        
        license_token = f"SKBZ-{cat.upper()[:3]}-{uuid.uuid4().hex[:12].upper()}"
        days_ago = random.randint(1, 14)
        created = (now - timedelta(days=days_ago)).isoformat()
        expires = (now + timedelta(days=365-days_ago)).isoformat()
        max_calls = random.choice([100, 500, 1000, -1])
        
        transactions.append((qa_id, seller_id, pid, price, "purchase", "completed", created))
        licenses.append((qa_id, pid, "standard", license_token, expires, max_calls, random.randint(0, 30), "active", created))

# Insert
c.executemany("INSERT INTO transactions (buyer_id, seller_id, product_id, amount, type, status, created_at) VALUES (?,?,?,?,?,?,?)", transactions)
c.executemany("INSERT INTO licenses (user_id, product_id, license_type, license_token, expires_at, max_calls, calls_count, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)", licenses)

# Update all users stats and coins
for buyer_id in all_user_ids + ([qa_id] if qa else []):
    spent = sum(t[3] for t in transactions if t[0] == buyer_id)
    purchases = sum(1 for t in transactions if t[0] == buyer_id)
    c.execute("UPDATE user_profiles SET total_spent = ?, total_purchases = ? WHERE user_id = ?", (spent, purchases, buyer_id))
    c.execute("UPDATE users SET coins = 999999 WHERE id = ?", (buyer_id,))

conn.commit()
print(f"\nCreated {len(licenses)} licenses and {len(transactions)} transactions")

if qa:
    c.execute("SELECT COUNT(*) FROM licenses WHERE user_id = ?", (qa_id,))
    print(f"quant_alice licenses: {c.fetchone()[0]}")
    c.execute("SELECT p.category, COUNT(*) FROM licenses l JOIN products p ON l.product_id = p.id WHERE l.user_id = ? GROUP BY p.category", (qa_id,))
    print(f"By category: {c.fetchall()}")

c.execute("SELECT COUNT(*) FROM licenses")
print(f"Total licenses: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM transactions")
print(f"Total transactions: {c.fetchone()[0]}")
conn.close()
