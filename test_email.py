import asyncio
import sys
sys.path.insert(0, '/root/skillbazaar/backend')
from services.email_service import send_email

async def main():
    result = await send_email(
        to_email="198651178@qq.com",
        subject="✅ SkillBazaar 邮箱推送测试",
        html_body="""
        <div style="max-width:600px;margin:0 auto;font-family:sans-serif;">
            <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:24px;border-radius:12px 12px 0 0;text-align:center;">
                <h1 style="color:#fff;margin:0;">🤖 SkillBazaar</h1>
                <p style="color:rgba(255,255,255,0.85);">AI技能集市 · 邮箱推送服务</p>
            </div>
            <div style="background:#fff;padding:24px;border:1px solid #e8e8e8;">
                <p>您好！这是来自 SkillBazaar 的测试邮件。</p>
                <p>✅ 邮箱推送服务配置成功！</p>
                <p>您订阅的 Cron 商品将在每天9点自动推送到此邮箱。</p>
            </div>
        </div>
        """,
        text_body="SkillBazaar 邮箱推送测试 - 配置成功！"
    )
    print(f"Email sent: {'✅ SUCCESS' if result else '❌ FAILED'}")

asyncio.run(main())
