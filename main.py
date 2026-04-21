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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

import config as cfg

class HuYaAuto:
    def __init__(self):
        self.debug = ""
        self.msg_logs = []
        # --- 推送控制开关 ---
        self.enable_push = False 
        
        self.cookie = os.getenv('HUYA_COOKIE', '').strip()
        self.rooms = self._parse_rooms(os.getenv('HUYA_ROOMS', ''))
        self.send_key = os.getenv('SEND_KEY', '').strip()

        if not self.cookie:
            print("[ERROR] 未设置 HUYA_COOKIE"); sys.exit(1)
        
        self.driver = self._init_browser()
        # 恢复最初的 5 秒等待
        self.wait = WebDriverWait(self.driver, 5)

    def _parse_rooms(self, rooms_str):
        if not rooms_str: return [518512, 518511]
        return [int(s.strip()) for s in rooms_str.split(',') if s.strip().isdigit()]

    def _init_browser(self):
        chrome_options = Options()
        if not self.debug: chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        # 最初脚本使用的是禁用 images
        chrome_options.add_argument('--disable-images')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_argument('--window-size=1920,1080')
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def send_notification(self):
        if not self.enable_push or not self.send_key or not self.msg_logs: 
            return
        try:
            content = "\n\n".join(self.msg_logs)
            requests.post(f'https://sctapi.ftqq.com/{self.send_key}.send', 
                          data={'text': '虎牙任务报告', 'desp': content}, timeout=10)
            print("✅ 微信推送完成")
        except: pass

    def login(self):
        print("[LOGIN] 登录中")
        try:
            self.driver.get(cfg.URLS["user_index"])
            time.sleep(cfg.TIMING["implicit_wait"])
            for line in self.cookie.split(';'):
                if '=' not in line: continue
                name, val = line.split('=', 1)
                self.driver.add_cookie({'name': name.strip(), 'value': val.strip(), 'domain': '.huya.com', 'path': '/'})
            self.driver.refresh()
            time.sleep(cfg.TIMING["page_load_wait"])
            elem = self.wait.until(EC.presence_of_element_located((By.ID, cfg.LOGIN["huya_num"])))
            print(f"[SUCCESS] 登录成功: {elem.text}")
            return True
        except: return False

    def get_hl_count(self):
        print("[SEARCH] 查询虎粮数量")
        try:
            self.driver.get(cfg.URLS["pay_index"])
            time.sleep(3)
            pack_tab = WebDriverWait(self.driver, 15).until(EC.element_to_be_clickable((By.ID, cfg.PAY_PAGE["pack_tab"])))
            pack_tab.click()
            time.sleep(1.5)
            
            n = self.driver.execute_script('''
                let n = 0;
                const items = document.querySelectorAll('li[data-num]');
                for (let item of items) {
                    let title = item.title || item.innerText || '';
                    if (title.includes('虎粮')) return item.getAttribute('data-num');
                }
                return 0;
            ''')
            count = int(n) if n and str(n).isdigit() else 0
            print(f"[COUNT] 虎粮数量: {count}")
            return count
        except: return 0

    def daily_check_in(self):
        """打卡逻辑：保留当前稳定版本"""
        try:
            badge = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "FanClubHd--UAIAw8vo8FGSKqVwLp7A")))
            self.driver.execute_script("var e=document.createEvent('MouseEvents');e.initMouseEvent('mouseover',true,false,window,0,0,0,0,0,false,false,false,false,0,null);arguments[0].dispatchEvent(e);", badge)
            time.sleep(2)
            btn = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'Btn--giEMQ9MN7LbLqKHP79BQ') and contains(text(), '打卡')]")))
            self.driver.execute_script("arguments[0].click();", btn)
            return "✅ 打卡成功"
        except: return "ℹ️ 已完成"

    def send_to_room(self, room_id, count):
        """完全恢复最初的送礼核心逻辑"""
        print(f"[GIFT] 房间 {room_id} 发送 {count} 个")
        if count <= 0: return "无粮跳过"

        try:
            self.driver.get(cfg.URLS["room_base"].format(room_id))
            time.sleep(cfg.TIMING["room_enter_wait"])

            lp = self.driver.execute_script('return document.body.getAttribute("data-lp")')
            gid = self.driver.execute_script('return document.body.getAttribute("data-gid")')

            if not lp or not gid:
                return "❌ 参数获取失败"

            self.driver.get(cfg.URLS["gift_tab"].format(lp=lp, gid=gid))
            time.sleep(cfg.TIMING["page_load_wait"])

            # 查找虎粮项
            items = self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, cfg.GIFT["item_class"])))
            hu_liang = next((i for i in items if "虎粮" in i.text), None)
            
            if not hu_liang:
                return "❌ 未找到虎粮"

            # 最初脚本的悬停逻辑
            ActionChains(self.driver).move_to_element(hu_liang).pause(1).perform()
            time.sleep(1)

            # 自定义数量
            inp = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, cfg.GIFT["input_css"])))
            inp.click()
            inp.clear()
            inp.send_keys(str(count))

            # 赠送
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, cfg.GIFT["send_class"]))).click()
            time.sleep(1)

            # 确定
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, cfg.GIFT["confirm_class"]))).click()
            time.sleep(1)

            return f"🚀 送出 {count} 个"
        except Exception as e:
            return f"❌ 异常"

    def run(self):
        try:
            if not self.login(): return
            total = self.get_hl_count()
            
            n = len(self.rooms)
            for i, rid in enumerate(self.rooms):
                c = (total // n + (1 if i < (total % n) else 0)) if total > 0 else 0
                print(f"\n>>> 处理房间: {rid}")
                
                # 1. 执行送礼（使用最初逻辑）
                g_res = self.send_to_room(rid, c)
                
                # 2. 回到直播间打卡
                self.driver.get(cfg.URLS["room_base"].format(rid))
                time.sleep(5)
                c_res = self.daily_check_in()
                
                log_msg = f"{g_res}； {c_res} (房间 {rid})"
                print(log_msg)
                self.msg_logs.append(log_msg)
        finally:
            if hasattr(self, 'driver'): self.driver.quit()
            self.send_notification()

if __name__ == '__main__':
    HuYaAuto().run()
