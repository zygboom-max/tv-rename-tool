#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件发送脚本 - 小爪子出品 🐾
"""

import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from getpass import getpass

# ─────────────────────────────────────────────────────────────
# 配置区域 - 请修改以下信息
# ─────────────────────────────────────────────────────────────

# 发件人邮箱（163 邮箱）
SENDER_EMAIL = ""  # 例如：yourname@163.com

# 发件人邮箱的授权码（不是登录密码！）
# 163 邮箱获取方式：设置 → POP3/SMTP/IMAP → 开启 SMTP → 获取授权码
SENDER_PASSWORD = ""

# SMTP 服务器配置
SMTP_SERVER = "smtp.163.com"
SMTP_PORT = 465  # SSL 端口

# 收件人
RECEIVER_EMAIL = "zygboom@163.com"

# 邮件主题
SUBJECT = "电视剧批量重命名工具 - 小爪子出品 🐾"

# 附件路径
ATTACHMENT_PATH = "tv_rename_tool.tar.gz"

# ─────────────────────────────────────────────────────────────

def send_email():
    """发送邮件"""
    
    # 检查配置
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("❌ 请先配置发件人邮箱和授权码！")
        print("\n📧 163 邮箱授权码获取方式：")
        print("   1. 登录 163 邮箱网页版")
        print("   2. 设置 → POP3/SMTP/IMAP")
        print("   3. 开启 SMTP 服务")
        print("   4. 获取授权码（不是登录密码！）")
        print("\n然后编辑 send_email.py 填入 SENDER_EMAIL 和 SENDER_PASSWORD")
        return False
    
    # 检查附件
    if not Path(ATTACHMENT_PATH).exists():
        print(f"❌ 附件不存在：{ATTACHMENT_PATH}")
        return False
    
    print(f"📧 准备发送邮件...")
    print(f"   发件人：{SENDER_EMAIL}")
    print(f"   收件人：{RECEIVER_EMAIL}")
    print(f"   主题：{SUBJECT}")
    print(f"   附件：{ATTACHMENT_PATH}")
    
    try:
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = SUBJECT
        
        # 邮件正文
        body = """
你好！

这是电视剧批量重命名工具，由小爪子 🐾 出品。

功能亮点：
- 支持 Alist / OpenList / 百度网盘
- 批量重命名剧集文件
- 彩色美化输出
- 健壮的异常处理

使用方法：
1. 解压压缩包
2. 安装依赖：pip install requests colorama
3. 配置 config.json（填入你的 token）
4. 运行：python tv_rename.py

详细说明请查看 README_TV_RENAME.md

祝使用愉快！

──
小爪子 🐾
        """
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # 添加附件
        with open(ATTACHMENT_PATH, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename={Path(ATTACHMENT_PATH).name}'
        )
        msg.attach(part)
        
        # 发送邮件
        print("\n📤 正在发送...")
        
        if SMTP_PORT == 465:
            # SSL 连接
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30)
        else:
            # TLS 连接
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
            server.starttls()
        
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        
        print("\n✅ 邮件发送成功！")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("\n❌ 认证失败！请检查邮箱账号和授权码是否正确")
        print("   注意：是授权码，不是登录密码！")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"\n❌ 连接 SMTP 服务器失败：{e}")
        return False
    except Exception as e:
        print(f"\n❌ 发送失败：{e}")
        return False


if __name__ == "__main__":
    success = send_email()
    sys.exit(0 if success else 1)
