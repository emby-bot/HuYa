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
        # 将显式等待略微调高，以应对 GitHub Actions 的网络波动
        self.wait = WebDriverWait(self.driver, 20)

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
        # 禁用图片加载以提速并减少超时概率
        chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--window-size=1920,1080')
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        # 增加页面加载超时容忍度
        driver.set_page_load_timeout(60)
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
            time.sleep(3)
            for line in self.cookie.split(';'):
                if '=' not in line: continue
                name, val = line.split('=', 1)
                self.driver.add_cookie({'name': name.strip(), 'value': val.strip(), 'domain': '.huya.com', 'path': '/'})
            self.driver.refresh()
            self.wait.until(EC.presence_of_element_located((By.ID, cfg.LOGIN["huya_num"])))
            print("[SUCCESS] 登录成功")
            return True
        except Exception as e: 
            print(f"[ERROR] 登录异常: {str(e)[:50]}")
            return False

    def get_hl_count(self):
        """增强版查询：带重试机制"""
        print("[SEARCH] 正在查询虎粮数量...")
        for attempt in range(2): # 最多尝试 2 次
            try:
                self.driver.get(cfg.URLS["pay_index"])
                time.sleep(6) # 给资产页面充足的加载时间
                
                # 强制使用 JS 点击包裹页签，避免被遮挡
                btn = self.wait.until(EC.presence_of_element_located((By.ID, cfg.PAY_PAGE["pack_tab"])))
                self.driver.execute_script("arguments[0].click();", btn)
                time.sleep(4)
                
                n = self.driver.execute_script('''
                    const items = document.querySelectorAll('li[data-num]');
                    for (let item of items) {
                        let txt = item.title || item.innerText || '';
                        if (txt.includes('虎粮')) return item.getAttribute('data-num');
                    }
                    return null;
                ''')
                
                if n is not None:
                    count = int(n)
                    print(f"[COUNT] 识别到虎粮: {count}")
                    return count
                
                print(f"  [WARN] 第 {attempt+1} 次未发现虎粮元素，重试中...")
            except Exception as e:
                print(f"  [WARN] 第 {attempt+1} 次查询失败: {str(e)[:30]}")
                self.driver.refresh()
                time.sleep(3)
        
        print("[ERROR] 最终获取虎粮数量失败，设为 0")
        return 0

    def daily_check_in(self):
        """打卡逻辑"""
        try:
            badge = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "FanClubHd--UAIAw8vo8FGSKqVwLp7A")))
            self.driver.execute_script("var e=document.createEvent('MouseEvents');e.initMouseEvent('mouseover',true,false,window,0,0,0,0,0,false,false,false,false,0,null);arguments[0].dispatchEvent(e);", badge)
            time.sleep(3)
            btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'Btn--giEMQ9MN7LbLqKHP79BQ') and contains(text(), '打卡')]")))
            self.driver.execute_script("arguments[0].click();", btn)
            return "✅ 打卡成功"
        except: return "ℹ️ 已打卡"

    def send_to_room_in_situ(self, count):
        """原地送礼：基于你提供的 HTML 结构"""
        if count <= 0: return "无粮跳过"
        try:
            # 1. 点击包裹 (ID: player-package-btn)
            pack_btn = self.wait.until(EC.element_to_be_clickable((By.ID, "player-package-btn")))
            self.driver.execute_script("arguments[0].click();", pack_btn)
            time.sleep(3)

            # 2. 查找虎粮 (Class: m-gift-item)
            hl_xpath = "//div[contains(@class, 'm-gift-item')]//p[text()='虎粮']/.."
            hl_item = self.wait.until(EC.presence_of_element_located((By.XPATH, hl_xpath)))
            self.driver.execute_script("arguments[0].click();", hl_item)
            time.sleep(1.5)

            # 3. 输入数量
            try:
                num_input = self.driver.find_element(By.CSS_SELECTOR, "input[placeholder*='数量'], .gift-count-input, .custom-input")
                num_input.click()
                num_input.send_keys(Keys.CONTROL + "a")
                num_input.send_keys(Keys.BACKSPACE)
                num_input.send_keys(str(count))
                time.sleep(0.5)
            except: pass

            # 4. 点击赠送
            send_xpath = "//button[contains(text(), '赠送')] | //div[contains(@class, 'btn-send')] | //a[contains(@class, 'sendBtn')]"
            send_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, send_xpath)))
            self.driver.execute_script("arguments[0].click();", send_btn)
            
            # 5. 确认弹窗
            try:
                time.sleep(1.5)
                confirm = self.driver.find_element(By.XPATH, "//button[contains(text(), '确定')] | //div[contains(@class, 'confirm')]")
                self.driver.execute_script("arguments[0].click();", confirm)
            except: pass
                
            return f"🚀 送出 {count} 个"
        except: return "❌ 送礼失败"

    def run(self):
        try:
            if not self.login(): return
            
            # 核心：必须先拿到虎粮总数
            total_hl = self.get_hl_count()
            
            n = len(self.rooms)
            for i, rid in enumerate(self.rooms):
                num = (total_hl // n + (1 if i < (total_hl % n) else 0)) if total_hl > 0 else 0
                print(f"\n>>> 房间: {rid} (分配: {num})")
                
                try:
                    # 尝试进入直播间，设置独立超时
                    self.driver.get(cfg.URLS["room_base"].format(rid))
                    time.sleep(12) # 给直播间重度资源留出时间
                    
                    # 先送礼
                    g_res = self.send_to_room_in_situ(num)
                    # 后打卡
                    c_res = self.daily_check_in()
                    
                    msg = f"{g_res}； {c_res} (房间 {rid})"
                    print(f"结果: {msg}")
                    self.msg_logs.append(msg)
                    
                    time.sleep(3)
                except Exception as e:
                    err_msg = str(e)[:30]
                    print(f"  [ERROR] 房间 {rid} 运行超时或异常: {err_msg}")
                    self.msg_logs.append(f"❌ 房间 {rid} 超时/异常")
        finally:
            if hasattr(self, 'driver'): self.driver.quit()
            self.send_notification()
            print("\n[EXIT] 浏览器已关闭，流程结束")

if __name__ == '__main__':
    HuYaAuto().run()
