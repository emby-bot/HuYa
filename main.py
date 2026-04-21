#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import requests

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

import config as cfg

class HuYaAuto:
    def __init__(self):
        self.debug = ""
        self.msg_logs = []
        self.enable_push = False 
        
        self.cookie = os.getenv('HUYA_COOKIE', '').strip()
        self.rooms = self._parse_rooms(os.getenv('HUYA_ROOMS', ''))
        self.send_key = os.getenv('SEND_KEY', '').strip()

        if not self.cookie:
            print("[ERROR] 未设置 HUYA_COOKIE"); sys.exit(1)
        
        self.driver = self._init_browser()
        self.wait = WebDriverWait(self.driver, 15)

    def _parse_rooms(self, rooms_str):
        if not rooms_str: return [518512, 518511]
        return [int(s.strip()) for s in rooms_str.split(',') if s.strip().isdigit()]

    def _init_browser(self):
        chrome_options = Options()
        if not self.debug: chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--mute-audio')
        chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--window-size=1920,1080')
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.set_page_load_timeout(40)
        return driver

    def send_notification(self):
        if not self.enable_push or not self.send_key or not self.msg_logs: return
        try:
            content = "\n\n".join(self.msg_logs)
            requests.post(f'https://sctapi.ftqq.com/{self.send_key}.send', 
                          data={'text': '虎牙任务报告', 'desp': content}, timeout=10)
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
        print("[SEARCH] 查询虎粮数量...")
        try:
            self.driver.get(cfg.URLS["pay_index"])
            time.sleep(5)
            btn = self.wait.until(EC.element_to_be_clickable((By.ID, cfg.PAY_PAGE["pack_tab"])))
            self.driver.execute_script("arguments[0].click();", btn)
            time.sleep(3)
            n = self.driver.execute_script('''
                const items = document.querySelectorAll('li[data-num]');
                for (let item of items) {
                    if ((item.title || item.innerText).includes('虎粮')) return item.getAttribute('data-num');
                }
                return 0;
            ''')
            count = int(n) if n and str(n).isdigit() else 0
            print(f"[COUNT] 识别到虎粮: {count}")
            return count
        except: return 0

    def daily_check_in(self):
        try:
            badge = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "FanClubHd--UAIAw8vo8FGSKqVwLp7A")))
            self.driver.execute_script("var e=document.createEvent('MouseEvents');e.initMouseEvent('mouseover',true,false,window,0,0,0,0,0,false,false,false,false,0,null);arguments[0].dispatchEvent(e);", badge)
            time.sleep(2.5)
            btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'Btn--giEMQ9MN7LbLqKHP79BQ') and contains(text(), '打卡')]")))
            self.driver.execute_script("arguments[0].click();", btn)
            return "✅ 打卡成功"
        except: return "ℹ️ 已打卡"

    def send_to_room_in_situ(self, count):
        """原地送礼逻辑：通过直播间包裹面板"""
        if count <= 0: return "无粮跳过"
        try:
            # 1. 点击包裹按钮 (通常在礼物栏右侧)
            pack_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@data-node-type='bag-btn'] | //p[contains(text(), '包裹')]/..")))
            self.driver.execute_script("arguments[0].click();", pack_btn)
            time.sleep(2)

            # 2. 查找虎粮项
            hl_xpath = "//li[contains(@title, '虎粮')] | //div[contains(@title, '虎粮')] | //p[contains(text(), '虎粮')]/ancestor::li"
            hl_item = self.wait.until(EC.presence_of_element_located((By.XPATH, hl_xpath)))
            self.driver.execute_script("arguments[0].click();", hl_item)
            time.sleep(1)

            # 3. 设置数量 (如果有自定义输入框)
            try:
                # 虎牙包裹面板通常点击物品后，右侧或下方会出现赠送按钮和数量选择
                num_input = self.driver.find_element(By.CSS_SELECTOR, ".gift-count-input, .custom-input")
                num_input.click()
                num_input.send_keys(Keys.CONTROL + "a")
                num_input.send_keys(Keys.BACKSPACE)
                num_input.send_keys(str(count))
            except:
                # 如果没找到输入框，默认送出当前选中的（通常是1个或全部）
                pass

            # 4. 点击赠送按钮
            send_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '赠送')] | //div[contains(@class, 'btn-send')]")))
            self.driver.execute_script("arguments[0].click();", send_btn)
            time.sleep(2)
            
            return f"🚀 送出 {count} 个"
        except Exception as e:
            return "❌ 送礼失败"

    def run(self):
        try:
            if not self.login(): return
            total_hl = self.get_hl_count()
            
            n = len(self.rooms)
            for i, rid in enumerate(self.rooms):
                num = (total_hl // n + (1 if i < (total_hl % n) else 0)) if total_hl > 0 else 0
                print(f"\n>>> 房间: {rid} (分配: {num})")
                
                try:
                    self.driver.get(cfg.URLS["room_base"].format(rid))
                    time.sleep(10) # 直播间加载较慢，给足时间
                    
                    # 尝试送礼
                    g_res = self.send_to_room_in_situ(num)
                    # 执行打卡
                    c_res = self.daily_check_in()
                    
                    msg = f"{g_res}； {c_res} (房间 {rid})"
                    print(f"结果: {msg}")
                    self.msg_logs.append(msg)
                except:
                    self.msg_logs.append(f"❌ 房间 {rid} 异常")
        finally:
            if hasattr(self, 'driver'): self.driver.quit()
            self.send_notification()

if __name__ == '__main__':
    HuYaAuto().run()
