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
        # 禁用图片加载提升速度
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
        except: 
            print("[ERROR] 登录超时或 Cookie 失效")
            return False

    def get_hl_count(self):
        print("[SEARCH] 查询虎粮数量...")
        try:
            self.driver.get(cfg.URLS["pay_index"])
            time.sleep(5)
            # 点击包裹页签
            btn = self.wait.until(EC.element_to_be_clickable((By.ID, cfg.PAY_PAGE["pack_tab"])))
            self.driver.execute_script("arguments[0].click();", btn)
            time.sleep(3)
            # 识别虎粮数量
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
        """打卡逻辑"""
        try:
            # 找到勋章容器进行悬停
            badge = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "FanClubHd--UAIAw8vo8FGSKqVwLp7A")))
            self.driver.execute_script("var e=document.createEvent('MouseEvents');e.initMouseEvent('mouseover',true,false,window,0,0,0,0,0,false,false,false,false,0,null);arguments[0].dispatchEvent(e);", badge)
            time.sleep(2.5)
            # 点击打卡按钮
            btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'Btn--giEMQ9MN7LbLqKHP79BQ') and contains(text(), '打卡')]")))
            self.driver.execute_script("arguments[0].click();", btn)
            return "✅ 打卡成功"
        except: return "ℹ️ 已打卡"

    def send_to_room_in_situ(self, count):
        """原地送礼逻辑：使用 player-package-btn 定位"""
        if count <= 0: return "无粮跳过"
        try:
            # 1. 点击包裹按钮 (ID: player-package-btn)
            pack_btn = self.wait.until(EC.element_to_be_clickable((By.ID, "player-package-btn")))
            self.driver.execute_script("arguments[0].click();", pack_btn)
            time.sleep(2.5)

            # 2. 查找虎粮项 (基于 m-gift-item 结构)
            # 逻辑：寻找包含“虎粮”文本的 p 标签，然后定位到其父级 m-gift-item 容器
            hl_xpath = "//div[contains(@class, 'm-gift-item')]//p[text()='虎粮']/.."
            hl_item = self.wait.until(EC.presence_of_element_located((By.XPATH, hl_xpath)))
            self.driver.execute_script("arguments[0].click();", hl_item)
            time.sleep(1.5)

            # 3. 设置数量 (尝试操作数量输入框)
            try:
                # 寻找面板上的输入框或选择框
                num_input = self.driver.find_element(By.CSS_SELECTOR, "input[placeholder*='数量'], .gift-count-input, .custom-input")
                num_input.click()
                num_input.send_keys(Keys.CONTROL + "a")
                num_input.send_keys(Keys.BACKSPACE)
                num_input.send_keys(str(count))
                time.sleep(0.5)
            except:
                pass # 没找到输入框则尝试直接赠送默认数量

            # 4. 点击赠送按钮
            # 匹配包含“赠送”文字的按钮或 class
            send_xpath = "//button[contains(text(), '赠送')] | //div[contains(@class, 'btn-send')] | //a[contains(@class, 'sendBtn')]"
            send_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, send_xpath)))
            self.driver.execute_script("arguments[0].click();", send_btn)
            
            # 5. 二次确认逻辑（如果有）
            try:
                time.sleep(1)
                confirm = self.driver.find_element(By.XPATH, "//button[contains(text(), '确定')] | //div[contains(@class, 'confirm')]")
                self.driver.execute_script("arguments[0].click();", confirm)
            except:
                pass
                
            return f"🚀 送出 {count} 个"
        except Exception as e:
            return "❌ 送礼失败"

    def run(self):
        try:
            if not self.login(): return
            total_hl = self.get_hl_count()
            
            n = len(self.rooms)
            for i, rid in enumerate(self.rooms):
                # 虎粮分配方案
                num = (total_hl // n + (1 if i < (total_hl % n) else 0)) if total_hl > 0 else 0
                print(f"\n>>> 房间: {rid} (任务: 送礼{num} + 打卡)")
                
                try:
                    self.driver.get(cfg.URLS["room_base"].format(rid))
                    # 关键：直播间加载慢，给足 10 秒等待
                    time.sleep(10) 
                    
                    # 1. 尝试送礼
                    g_res = self.send_to_room_in_situ(num)
                    
                    # 2. 执行打卡
                    c_res = self.daily_check_in()
                    
                    msg = f"{g_res}； {c_res} (房间 {rid})"
                    print(f"结果: {msg}")
                    self.msg_logs.append(msg)
                    
                    # 每个房间间隔一下，防止太快被封
                    time.sleep(3)
                except Exception as e:
                    print(f"房间 {rid} 执行异常: {str(e)[:50]}")
                    self.msg_logs.append(f"❌ 房间 {rid} 异常")
        finally:
            if hasattr(self, 'driver'): self.driver.quit()
            self.send_notification()
            print("\n[EXIT] 任务结束，浏览器已关闭")

if __name__ == '__main__':
    HuYaAuto().run()
