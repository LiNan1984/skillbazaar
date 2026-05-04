"""Email service using QQ SMTP with aiosmtplib for async"""
from __future__ import annotations
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465
SMTP_USER = "198651178@qq.com"
SMTP_PASS = "wjyecmdgicijfaeg"
SMTP_FROM = "SkillBazaar <198651178@qq.com>"


async def send_email(to: str, subject: str, body_html: str) -> bool:
    """Send email via QQ SMTP SSL"""
    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASS,
            use_tls=True,
        )
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email send failed to {to}: {e}")
        return False


async def send_cron_push_email(to: str, cron_name: str, content: str) -> bool:
    """Send cron push notification email"""
    subject = f"🎯 {cron_name} - 每日推送"
    html = f"""
    <div style="max-width:600px;margin:0 auto;font-family:sans-serif;background:#09090b;color:#fafafa;padding:32px;border-radius:16px;">
      <div style="text-align:center;margin-bottom:24px;">
        <h1 style="color:#6366f1;margin:0;font-size:24px;">🎯 {cron_name}</h1>
        <p style="color:#71717a;margin:8px 0 0;">SkillBazaar 每日精选推送</p>
      </div>
      <div style="background:#18181b;border-radius:12px;padding:24px;margin-bottom:24px;">
        {content}
      </div>
      <div style="text-align:center;color:#71717a;font-size:12px;">
        <p>由 SkillBazaar AI技能集市 自动推送</p>
        <a href="https://skillbazaar.harness-agent.app" style="color:#6366f1;">skillbazaar.harness-agent.app</a>
      </div>
    </div>
    """
    return await send_email(to, subject, html)
