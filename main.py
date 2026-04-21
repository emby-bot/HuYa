#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import requests

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

import config as cfg

class HuYaAuto:
    def __init__(self):
        self.debug = False
        self.msg_logs = []
        self.enable_push = False  # 按照要求默认关闭
        
        self.cookie = os.getenv('HUYA_COOKIE', '').strip()
        self.rooms = self._parse_rooms(os.getenv('HUYA_ROOMS', ''))
        self.send_key = os.getenv('SEND_KEY', '').strip()

        if not self.cookie:
            print("[ERROR] 未设置 HUYA_COOKIE"); sys.exit(1)
        
        if not self.rooms:
            self.rooms = [518512, 518511]

        self.driver = self._init_browser()
        self.wait = WebDriverWait(self.driver, 15)

    def _parse_rooms(self, rooms_str):
        if not rooms_str: return []
        return [int(s.strip()) for s in rooms_str.split(',') if s.strip().isdigit()]

    def _init_browser(self):
        chrome_options = Options()
        if not self.debug: chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--mute-audio')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.set_page_load_timeout(50)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def send_notification(self):
        if not self.enable_push or not self.send_key: return
        try:
            content = "\n\n".join(self.msg_logs)
            requests.post(f'https://sctapi.ftqq.com/{self.send_key}.send', data={'text': '虎牙任务报告', 'desp': content}, timeout=10)
        except: pass

    def login(self):
        print("[LOGIN] 正在登录...")
        try:
            self.driver.get(cfg.URLS["user_index"])
            time.sleep(2)
            for line in self.cookie.split(';'):
                if '=' not in line: continue
                name, val = line.split('=', 1)
                self.driver.add_cookie({'name': name.strip(), 'value': val.strip(), 'domain': '.huya.com', 'path': '/'})
            self.driver.refresh()
            self.wait.until(EC.presence_of_element_located((By.ID, cfg.LOGIN["huya_num"])))
            print("[SUCCESS] 登录成功")
            return True
        except: return False

    def get_hl_count(self):
        print("[SEARCH] 正在查询虎粮数量...")
        self.driver.get(cfg.URLS["pay_index"])
        time.sleep(4)
        try:
            pack_tab = self.wait.until(EC.element_to_be_clickable((By.ID, cfg.PAY_PAGE["pack_tab"])))
            self.driver.execute_script("arguments[0].click();", pack_tab)
            time.sleep(2)
            n = self.driver.execute_script('''
                let items = document.querySelectorAll('li[data-num]');
                for (let item of items) {
                    if ((item.title || item.innerText).includes('虎粮')) return item.getAttribute('data-num');
                }
                return 0;
            ''')
            count = int(n) if n else 0
            print(f"[COUNT] 识别到虎粮: {count}")
            return count
        except: return 0

    def send_to_room_in_situ(self, count):
        """精准匹配 HTML 结构的送礼函数"""
        if count <= 0: return "无粮跳过"
        try:
            # 1. 唤醒包裹
            self.driver.execute_script("document.querySelector('#player-package-btn').click();")
            time.sleep(3)

            # 2. 定位虎粮 (精准匹配 <p>虎粮</p> 并点击其父级 div.m-gift-item)
            # 这里使用了 JS 的 XPath 查找，比单纯的 CSS 类名更稳
            found = self.driver.execute_script('''
                var pTags = document.querySelectorAll(".m-gift-item p");
                for (let p of pTags) {
                    if (p.innerText.trim() === "虎粮") {
                        p.parentElement.click();
                        return true;
                    }
                }
                return false;
            ''')
            
            if not found:
                print("  [DEBUG] 无法在 m-gift-item 中定位到包含'虎粮'文字的 p 标签")
                return "❌ 未找到虎粮"
            
            time.sleep(1.5)

            # 3. 填入数量 (强制 Focus 注入)
            set_res = self.driver.execute_script(f'''
                var inp = document.querySelector("input.z-cur[placeholder*='自定义']");
                if (inp) {{
                    inp.focus();
                    inp.value = "{count}";
                    inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return true;
                }}
                return false;
            ''')
            if not set_res: print("  [DEBUG] 数量输入框(自定义)定位失败")
            time.sleep(1)

            # 4. 赠送 (使用原脚本 class)
            send_btn = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, cfg.GIFT["send_class"])))
            self.driver.execute_script("arguments[0].click();", send_btn)
            
            # 检查是否有二次确认弹窗
            time.sleep(1.5)
            self.driver.execute_script(f'''
                var confirm = document.querySelector(".{cfg.GIFT['confirm_class']}");
                if (confirm) confirm.click();
            ''')

            return f"🚀 送出 {count} 个"
        except Exception as e:
            print(f"  [DEBUG] 过程异常: {str(e)[:100]}")
            return "❌ 送礼失败"

    def daily_check_in(self):
        try:
            badge = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "FanClubHd--UAIAw8vo8FGSKqVwLp7A")))
            self.driver.execute_script("var e=document.createEvent('MouseEvents');e.initMouseEvent('mouseover',true,false,window,0,0,0,0,0,false,false,false,false,0,null);arguments[0].dispatchEvent(e);", badge)
            time.sleep(3)
            btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'Btn--giEMQ9MN7LbLqKHP79BQ') and contains(text(), '打卡')]")))
            self.driver.execute_script("arguments[0].click();", btn)
            return "✅ 打卡成功"
        except: return "ℹ️ 已打卡"

    def run(self):
        print("=" * 40 + "\n[HUYA] 虎牙自动任务启动\n" + "=" * 40)
        try:
            if not self.login(): return
            total = self.get_hl_count()
            for i, rid in enumerate(self.rooms):
                num = (total // len(self.rooms) + (1 if i < (total % len(self.rooms)) else 0)) if total > 0 else 0
                print(f"\n>>> 房间: {rid} (任务: 送礼{num} + 打卡)")
                try:
                    self.driver.get(cfg.URLS["room_base"].format(rid))
                    time.sleep(12) # 增加直播间加载等待
                    g_res = self.send_to_room_in_situ(num)
                    c_res = self.daily_check_in()
                    msg = f"{g_res}； {c_res} (房间 {rid})"
                    print(f"结果: {msg}")
                    self.msg_logs.append(msg)
                except: self.msg_logs.append(f"❌ 房间 {rid} 异常")
                time.sleep(3)
        finally:
            if hasattr(self, 'driver'): self.driver.quit()
            self.send_notification()

if __name__ == '__main__':
    HuYaAuto().run()
