"""ct8.pl 免费主机自动续期：登录 DevilWEB 面板一次即续期 90 天。

续期机制（已核实）：90 天内正确登录一次 DevilWEB 面板或 SSH 就是续期，
不需要走 ADMIN.NET.PL 计费面板（那是另一套账号，免费用户很可能没有）。

需要的 GitHub Secrets（仓库 Settings → Secrets and variables → Actions）：
  CT8_USERNAME   ct8 面板账号，如 asen0122
  CT8_PASSWORD   ct8 面板密码（激活邮件里系统发的那个）
  TG_BOT_TOKEN   Telegram Bot Token（@senmuse_bot）
  TG_CHAT_ID     Telegram Chat ID

运行方式：GitHub Actions 每月 1 号 22:30 UTC 自动跑；奇数月登录面板续期
（约 60 天一次），偶数月只更新 time.txt 保活（防止仓库 60 天无活动导致
定时任务被 GitHub 停用）。每次登录成功/失败都发 TG 通知，成功时带上新有效期。
"""
import asyncio
import os
import re
import sys
from datetime import datetime, timedelta

import requests

CT8_USERNAME = os.getenv('CT8_USERNAME', '').strip()
CT8_PASSWORD = os.getenv('CT8_PASSWORD', '').strip()
CT8_PANEL = os.getenv('CT8_PANEL', 'panel.ct8.pl').strip() or 'panel.ct8.pl'
TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN', '').strip()
TG_CHAT_ID = os.getenv('TG_CHAT_ID', '').strip()

MARKER = '.tg_sent'


def beijing_now():
    return (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')


def send_telegram(text):
    """发 TG 通知；成功返回 True（并写 marker 供 workflow 兜底步骤判断），否则 False。"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print('未配置 TG Secrets，跳过通知')
        return False
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage',
            json={'chat_id': TG_CHAT_ID, 'text': text},
            headers={'Content-Type': 'application/json'},
            timeout=30,
        )
        if r.status_code == 200:
            with open(MARKER, 'w', encoding='utf-8') as f:
                f.write('sent')
            print('TG 通知已发送')
            return True
        print(f'TG 发送失败: HTTP {r.status_code} {r.text[:200]}')
    except Exception as e:
        print(f'TG 发送出错: {e}')
    return False


def check_reachability():
    """未配置账号时：只测 GitHub Runner 能否直连面板登录页（不走代理）。"""
    url = f'https://{CT8_PANEL}/login/?next=/'
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        print(f'直连测试: GET {url} -> HTTP {r.status_code}')
        return r.status_code
    except Exception as e:
        print(f'直连测试失败: {e}')
        return None


async def login_and_get_expiry(username, password, panel):
    """用无头浏览器登录面板；成功返回 (True, 有效期文本或 '')；失败返回 (False, '')。"""
    from pyppeteer import launch

    browser = None
    page = None
    try:
        browser = await launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        page = await browser.newPage()
        await page.goto(f'https://{panel}/login/?next=/', {'timeout': 60000})
        user_input = await page.querySelector('#id_username')
        if user_input:
            await page.evaluate('(el) => { el.value = ""; }', user_input)
        await page.type('#id_username', username)
        await page.type('#id_password', password)
        btn = await page.querySelector('form[data-login-form] button[type="submit"]')
        if not btn:
            raise Exception('找不到登录按钮')
        await btn.click()
        try:
            await page.waitForNavigation({'timeout': 60000})
        except Exception:
            pass
        # 到面板首页抓“Valid until ...”有效期；能抓到即登录成功
        expiry = ''
        try:
            await page.goto(f'https://{panel}/next/', {'timeout': 60000})
            await asyncio.sleep(2)
            text = await page.evaluate('() => document.body.innerText')
            m = re.search(r'Valid until\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})', text or '')
            days = re.search(r'in\s+(\d+)\s+days', text or '')
            if m:
                expiry = m.group(1)
                if days:
                    expiry += f'（剩余 {days.group(1)} 天）'
        except Exception as e:
            print(f'抓取有效期失败（不影响登录结果）: {e}')
        logged_in = bool(expiry)
        if not logged_in:
            # 兜底：旧版面板用 logout 链接判断
            try:
                logged_in = await page.evaluate(
                    '''() => document.querySelector('a[href="/logout/"]') !== null'''
                )
            except Exception:
                logged_in = False
        return logged_in, expiry
    finally:
        if page:
            await page.close()
        if browser:
            await browser.close()


async def main():
    if not CT8_USERNAME or not CT8_PASSWORD:
        print('未配置 CT8_USERNAME / CT8_PASSWORD Secrets，无法登录。先测网络直连：')
        status = check_reachability()
        if status == 200:
            print('结论：GitHub Runner 可直连面板登录页（不走代理），填好 Secrets 后即可实测登录。')
        else:
            print('结论：GitHub Runner 直连面板登录页异常，请检查网络或面板状态。')
        return 2

    ok, expiry = False, ''
    try:
        ok, expiry = await login_and_get_expiry(CT8_USERNAME, CT8_PASSWORD, CT8_PANEL)
    except Exception as e:
        msg = f'ct8 自动续期：登录过程异常：{e}\n时间（北京时间）：{beijing_now()}'
        print(msg)
        send_telegram(msg)
        return 1

    now = beijing_now()
    if ok:
        msg = f'ct8 自动续期：登录成功 ✅\n账号：{CT8_USERNAME}\n时间（北京时间）：{now}'
        if expiry:
            msg += f'\n有效期至：{expiry}'
        print(msg)
        send_telegram(msg)
        return 0
    msg = (f'ct8 自动续期：登录失败 ❌\n账号：{CT8_USERNAME}\n'
           f'时间（北京时间）：{now}\n请检查账号密码是否正确，或面板是否屏蔽了 GitHub IP。')
    print(msg)
    send_telegram(msg)
    return 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
