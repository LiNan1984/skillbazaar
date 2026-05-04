"""
SkillBazaar 端到端测试套件 v2
覆盖: Auth, Products, Points, Sandbox, Encryption, Chat, CLI
"""
import json
import sys
import os
import urllib.request
import urllib.error
import urllib.parse
import subprocess

API = "http://localhost:8000/api"
TOKEN = "UDehnpnUptjMdPV2GhcrTFpPTXzkpZqYcdPwo2u2c5A"
USER_ID = "8565c756-1ab5-46d9-8f17-fe87ea947acd"

passed = 0
failed = 0
errors = []

def api(method, path, data=None, token=None):
    url = f"{API}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode() or "{}"
            return {"ok": True, "status": resp.status, "data": json.loads(raw)}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()[:500]
        try:
            detail = json.loads(body_text)
        except:
            detail = {"raw": body_text}
        return {"ok": False, "status": e.code, "error": detail}
    except Exception as e:
        return {"ok": False, "status": -1, "error": str(e)}

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        msg = f"  ❌ {name}" + (f" — {detail}" if detail else "")
        print(msg)
        errors.append(name)

# =====================================================
print("=" * 60)
print("🦐 SkillBazaar 端到端测试套件 v2")
print("=" * 60)

# --- 1. Health ---
print("\n📋 1. 健康检查")
try:
    with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as resp:
        health_data = json.loads(resp.read().decode())
        test("1.1 Health endpoint", health_data.get("status") == "ok", str(health_data))
except Exception as e:
    test("1.1 Health endpoint", False, str(e))

# --- 2. Auth ---
print("\n📋 2. 认证系统")
r = api("GET", "/v2/auth/me", token=TOKEN)
test("2.1 获取当前用户", r["ok"], str(r.get("error",""))[:100])
if r["ok"]:
    uid = r["data"].get("user_id", r["data"].get("id", ""))
    test("2.2 用户ID正确", uid == USER_ID, f"got={uid}")

# --- 3. Products ---
print("\n📋 3. 商品系统")
r = api("GET", "/products/")
test("3.1 商品列表", r["ok"], str(r.get("error",""))[:80])
if r["ok"]:
    prods = r["data"] if isinstance(r["data"], list) else r["data"].get("products", [])
    test("3.2 商品数量>0", len(prods) > 0, f"count={len(prods)}")

r = api("GET", "/products/1")
test("3.3 商品详情", r["ok"], str(r.get("error",""))[:80])

# --- 4. Points ---
print("\n📋 4. 积分系统")
r = api("GET", "/activities/points/balance", token=TOKEN)
test("4.1 积分余额查询", r["ok"], str(r.get("error",""))[:80])
if r["ok"]:
    balance = r["data"].get("balance", 0)
    test("4.2 余额>0", balance > 0, f"balance={balance}")
    print(f"  ℹ️  积分余额: {balance}")

r = api("POST", "/activities/checkin", token=TOKEN)
test("4.3 每日签到", r["ok"] or r.get("status") == 400, str(r.get("error",""))[:80])

# --- 5. Points → Sandbox Redemption ---
print("\n📋 5. 积分→沙盒兑换")
r = api("POST", "/activities/points/redeem", {"amount": 1, "redeem_type": "sandbox"}, token=TOKEN)
test("5.1 积分兑换1小时沙盒时长", r["ok"], str(r.get("error",""))[:150])
if r["ok"]:
    test("5.2 返回sandbox_hours_received", "sandbox_hours_received" in r["data"], str(r["data"]))
    test("5.3 虾塘消息", "虾" in r["data"].get("message", ""), r["data"].get("message",""))

# Verify quota updated
r = api("GET", "/sandbox/status", token=TOKEN)
test("5.4 沙盒配额>0", r["ok"] and r["data"].get("remaining_seconds", 0) > 0, 
     str(r.get("error",""))[:100] if not r["ok"] else f"quota={r['data'].get('remaining_seconds')}")

# --- 6. Sandbox ---
print("\n📋 6. 沙盒系统")
r = api("GET", "/sandbox/status", token=TOKEN)
test("6.1 沙盒状态查询", r["ok"], str(r.get("error",""))[:100])
if r["ok"]:
    test("6.2 remaining_seconds字段", "remaining_seconds" in r["data"], str(r["data"]))
    test("6.3 remaining_hours字段", "remaining_hours" in r["data"])

# --- 7. Sandbox Start ---
print("\n📋 7. 沙盒启动")
r = api("POST", "/sandbox/start?language=python", token=TOKEN)
test("7.1 启动沙盒", r["ok"], str(r.get("error",""))[:150])
if r["ok"]:
    test("7.2 返回sandbox_id", "sandbox_id" in r["data"], str(r["data"]))
    test("7.3 状态为running", r["data"].get("status") == "running", r["data"].get("status",""))
    test("7.4 虾塘消息", "虾" in r["data"].get("message", ""), r["data"].get("message",""))
    sandbox_id = r["data"].get("sandbox_id", "")
else:
    sandbox_id = ""

# Check status after start
if r["ok"]:
    r2 = api("GET", "/sandbox/status", token=TOKEN)
    test("7.5 沙盒运行中", r2["ok"] and r2["data"].get("sandbox") is not None, 
         str(r2.get("error",""))[:100] if not r2["ok"] else str(r2["data"])[:100])

# --- 8. 虾塘加密 ---
print("\n📋 8. 虾塘加密系统")
test_code = '''
import json
data = {"shrimp": "power", "pond": "secure", "value": 42}
print(json.dumps(data, ensure_ascii=False))
'''
r = api("POST", "/sandbox/encrypt-agent", {"source_code": test_code}, token=TOKEN)
test("8.1 加密Agent源码", r["ok"], str(r.get("error",""))[:100])
if r["ok"]:
    test("8.2 返回encrypted_blob", "encrypted_blob" in r["data"])
    test("8.3 返回content_hash", "content_hash" in r["data"])
    test("8.4 返回salt", "salt" in r["data"])
    test("8.5 虾塘消息", "虾" in r["data"].get("message", ""))
    encrypted_blob = r["data"].get("encrypted_blob", "")
    
    # Test decrypt
    if encrypted_blob:
        r3 = api("POST", "/sandbox/decrypt-agent?encrypted_blob=" + urllib.parse.quote(encrypted_blob), token=TOKEN)
        test("8.6 解密Agent源码", r3["ok"], str(r3.get("error",""))[:100])
        if r3["ok"]:
            test("8.7 解密内容正确", "shrimp" in r3["data"].get("source_code", ""))
else:
    encrypted_blob = ""

# --- 9. Sandbox Execute ---
print("\n📋 9. 沙盒代码执行")
r = api("POST", "/sandbox/execute", {
    "code": "print('Hello from shrimp pond! 🦐')",
    "language": "python"
}, token=TOKEN)
test("9.1 代码执行请求", r["ok"], str(r.get("error",""))[:150])
if r["ok"]:
    test("9.2 返回status字段", "status" in r["data"])
    test("9.3 有stdout", "stdout" in r["data"], str(r["data"])[:200])
    if r["data"].get("stdout"):
        test("9.4 stdout含预期输出", "Hello" in r["data"]["stdout"] or "shrimp" in r["data"]["stdout"],
             f"stdout={r['data']['stdout'][:100]}")
    test("9.5 返回remaining_quota", "remaining_quota" in r["data"])

# --- 10. Encrypted Execute ---
print("\n📋 10. 加密代码执行")
if encrypted_blob:
    r = api("POST", "/sandbox/execute", {
        "code": encrypted_blob,
        "encrypted": True,
        "language": "python"
    }, token=TOKEN)
    test("10.1 加密代码执行请求", r["ok"], str(r.get("error",""))[:150])
    if r["ok"]:
        test("10.2 执行成功", r["data"].get("status") == "success" or "stdout" in r["data"])
else:
    test("10.1 加密代码执行请求", False, "无encrypted_blob")

# --- 11. OpenAI Chat Completions ---
print("\n📋 11. OpenAI兼容聊天接口")
r = api("POST", "/sandbox/v1/chat/completions", {
    "model": "GLM-5.1-FP8",
    "messages": [{"role": "user", "content": "回复OK两个字母即可"}]
}, token=TOKEN)
test("11.1 Chat completions请求", r["ok"], str(r.get("error",""))[:150])
if r["ok"]:
    test("11.2 返回choices或error", "choices" in r["data"] or "error" in r["data"], 
         str(r["data"])[:200])
    if "choices" in r["data"]:
        content = r["data"]["choices"][0].get("message", {}).get("content", "")
        test("11.3 有回复内容", len(content) > 0, f"content={content[:50]}")
        test("11.4 id字段", "id" in r["data"])
        test("11.5 model字段", "model" in r["data"])
    else:
        print(f"  ℹ️  LLM API错误(可接受): {str(r['data'].get('error',''))[:100]}")

# --- 12. Duplicate sandbox prevention ---
print("\n📋 12. 单用户单沙盒限制")
r = api("POST", "/sandbox/start?language=python", token=TOKEN)
test("12.1 重复启动返回已有沙盒", r["ok"] and r["data"].get("sandbox_id") == sandbox_id,
     str(r.get("error",""))[:100] if not r["ok"] else f"id={r['data'].get('sandbox_id')}")

# --- 13. Sandbox Stop ---
print("\n📋 13. 沙盒停止")
r = api("DELETE", "/sandbox/stop", token=TOKEN)
test("13.1 停止沙盒", r["ok"], str(r.get("error",""))[:100])
if r["ok"]:
    test("13.2 虾塘消息", "虾" in r["data"].get("message", "") or "destroyed" in str(r["data"]),
         r["data"].get("message",""))

# Verify sandbox stopped
r = api("GET", "/sandbox/status", token=TOKEN)
if r["ok"]:
    test("13.3 沙盒已停止", r["data"].get("sandbox") is None, str(r["data"])[:100])

# --- 14. Other systems ---
print("\n📋 14. 其他系统")
r = api("GET", "/bounties/")
test("14.1 悬赏列表", r["ok"], str(r.get("error",""))[:80])

r = api("GET", "/agents/", token=TOKEN)
test("14.2 Agent列表", r["ok"], str(r.get("error",""))[:80])

# --- 15. CLI ---
print("\n📋 15. skbz CLI")
result = subprocess.run(["skbz", "--help"], capture_output=True, text=True, timeout=5)
test("15.1 skbz --help", result.returncode == 0, result.stderr[:80] if result.returncode else "")
test("15.2 help含子命令", "sandbox" in result.stdout and "encrypt" in result.stdout)

result = subprocess.run(["skbz", "sandbox", "status", "--help"], capture_output=True, text=True, timeout=5)
test("15.3 skbz sandbox status --help", result.returncode == 0)

# --- 16. Edge cases ---
print("\n📋 16. 边界测试")

# Stop when no sandbox running
r = api("DELETE", "/sandbox/stop", token=TOKEN)
test("16.1 无沙盒时停止返回not_found", r["ok"] and r["data"].get("status") == "not_found",
     str(r.get("data",r.get("error","")))[:80])

# Unauthorized access
r = api("GET", "/sandbox/status", token="invalid_token_12345")
test("16.2 无效token拒绝", not r["ok"], f"status={r.get('status')}")

# Invalid language
r = api("POST", "/sandbox/start?language=brainfuck", token=TOKEN)
# Should still work (falls back to python)
test("16.3 未知语言降级处理", r["ok"], str(r.get("error",""))[:100])

# Clean up: stop any running sandbox
api("DELETE", "/sandbox/stop", token=TOKEN)

# =====================================================
print("\n" + "=" * 60)
print(f"🦐 测试结果: {passed} 通过, {failed} 失败, 共 {passed+failed} 项")
if errors:
    print(f"❌ 失败项:")
    for e in errors:
        print(f"   - {e}")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
