#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
虎牙助手：修正送礼数量识别 & 打卡路径锁定
"""

import os
import sys
import time
import requests

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

import config as cfg

class HuYaAuto:
    def __init__(self):
        self.debug = ""
        self.msg_logs = [] 
        self.enable_push = False  # <--- 需要推送时改为 True

        self.cookie = os.getenv('HUYA_COOKIE', '').strip()
        self.rooms = self._parse_rooms(os.getenv('HUYA_ROOMS', ''))
        self.send_key = os.getenv('SEND_KEY', '').strip()

        if not self.cookie:
            print("[ERROR] 未设置 HUYA_COOKIE"); sys.exit(1)
        if not self.rooms:
            self.rooms = [518512]

        self.driver = self._init_browser()
        self.wait = WebDriverWait(self.driver, 20)

    def _parse_rooms(self, rooms_str):
        return [int(s.strip()) for s in rooms_str.split(',') if s.strip().isdigit()]

    def _init_browser(self):
        chrome_options = Options()
        if not self.debug: chrome_options.add_argument('--headless=new')
        chrome_options.page_load_strategy = 'none'
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--mute-audio')
        chrome_options.add_argument('--window-size=1920,1080')
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.set_page_load_timeout(100)
        return driver

    def send_notification(self):
        if not self.enable_push or not self.send_key or not self.msg_logs: return
        try:
            requests.post(f'https://sctapi.ftqq.com/{self.send_key}.send', 
                          data={'text': '虎牙汇总', 'desp': "\n\n".join(self.msg_logs)}, timeout=10)
            print("✅ 推送成功")
        except: print("❌ 推送失败")

    def login(self):
        print("[LOGIN] 登录中...")
        self.driver.get(cfg.URLS["user_index"])
        time.sleep(3)
        for line in self.cookie.split(';'):
            if '=' not in line: continue
            name, val = line.split('=', 1)
            try: self.driver.add_cookie({'name': name.strip(), 'value': val.strip(), 'domain': '.huya.com', 'path': '/'})
            except: continue
        self.driver.refresh()
        try:
            self.wait.until(EC.presence_of_element_located((By.ID, cfg.LOGIN["huya_num"])))
            return True
        except: return False

    def get_hl_count(self):
        self.driver.get(cfg.URLS["pay_index"])
        time.sleep(5)
        try:
            tab = self.wait.until(EC.element_to_be_clickable((By.ID, cfg.PAY_PAGE["pack_tab"])))
            self.driver.execute_script("arguments[0].click();", tab)
            time.sleep(3)
            n = self.driver.execute_script("const i=document.querySelectorAll('li[data-num]');for(let x of i){if((x.title||x.innerText).includes('虎粮'))return x.getAttribute('data-num');}return 0;")
            print(f"[COUNT] 虎粮: {n}")
            return int(n)
        except: return 0

    def daily_check_in(self, room_id):
        """精准路径打卡"""
        try:
            # 1. 悬停粉丝牌
            badge = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "FanClubHd--UAIAw8vo8FGSKqVwLp7A")))
            self.driver.execute_script("var e=document.createEvent('MouseEvents');e.initMouseEvent('mouseover',true,false,window,0,0,0,0,0,false,false,false,false,0,null);arguments[0].dispatchEvent(e);", badge)
            time.sleep(2.5)

            # 2. 精准定位“打卡”按钮 (ClassName + XPath 文本过滤)
            # 使用包含文字“打卡”的 <a> 标签，且带有特定的 Btn 类名
            checkin_btn = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(@class, 'Btn--giEMQ9MN7LbLqKHP79BQ') and contains(text(), '打卡')]")
            ))
            self.driver.execute_script("arguments[0].click();", checkin_btn)
            
            msg = f"✅ 房间 {room_id} 打卡成功"
            print(msg); self.msg_logs.append(msg)
        except:
            print(f"[INFO] 房间 {room_id} 打卡未成功 (可能无牌子或已打)")

    def _execute_send_gift(self, room_id, count):
        lp = self.driver.execute_script('return document.body.getAttribute("data-lp")')
        gid = self.driver.execute_script('return document.body.getAttribute("data-gid")')
        if not lp or not gid: return

        self.driver.get(cfg.URLS["gift_tab"].format(lp=lp, gid=gid))
        time.sleep(5)
        try:
            items = self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, cfg.GIFT["item_class"])))
            hl_icon = next((i for i in items if "虎粮" in i.text), None)
            if hl_icon:
                ActionChains(self.driver).move_to_element(hl_icon).perform()
                inp = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, cfg.GIFT["input_css"])))
                # 强行注入数值并触发 Event，确保虎牙识别到完整数字
                self.driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", inp, str(count))
                time.sleep(1)
                
                send_btn = self.driver.find_element(By.CLASS_NAME, cfg.GIFT["send_class"])
                self.driver.execute_script("arguments[0].click();", send_btn)
                time.sleep(1)
                confirm = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, cfg.GIFT["confirm_class"])))
                self.driver.execute_script("arguments[0].click();", confirm)
                
                msg = f"🚀 房间 {room_id} 送礼成功: {count}"
                print(msg); self.msg_logs.append(msg)
        except Exception as e: print(f"送礼异常: {e}")

    def run(self):
        if not self.login(): return False
        total = self.get_hl_count()
        n = len(self.rooms)
        for i, rid in enumerate(self.rooms):
            print(f"\n>>> 处理房间: {rid}")
            self.driver.get(cfg.URLS["room_base"].format(rid))
            time.sleep(8)
            
            count = 0
            if total > 0:
                count = total // n + (1 if i < (total % n) else 0)
                self._execute_send_gift(rid, count)
            
            # 重新回到直播间主页进行打卡
            self.driver.get(cfg.URLS["room_base"].format(rid))
            time.sleep(5)
            self.daily_check_in(rid)
        
        self.driver.quit()
        self.send_notification()
        return True

if __name__ == '__main__':
    HuYaAuto().run()
