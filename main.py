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
        # 推送开关：如果要关闭推送，将此处设为 False/True
        self.enable_push = False 

        if self.debug:
            try:
                with open("cookie", "r", encoding="utf-8") as f:
                    self.cookie = f.read().strip()
            except FileNotFoundError:
                self.cookie = ""
            self.rooms = [518512]
        else:
            self.cookie = os.getenv('HUYA_COOKIE', '').strip()
            self.rooms = self._parse_rooms(os.getenv('HUYA_ROOMS', ''))

        self.send_key = os.getenv('SEND_KEY', '').strip()

        if not self.cookie:
            print("[ERROR] 未设置 HUYA_COOKIE"); sys.exit(1)
        if not self.rooms:
            self.rooms = [518512, 518511]

        self.driver = self._init_browser()
        self.wait = WebDriverWait(self.driver, 20)

    def _parse_rooms(self, rooms_str):
        return [int(s.strip()) for s in rooms_str.split(',') if s.strip().isdigit()]

    def _init_browser(self):
        chrome_options = Options()
        if not self.debug:
            chrome_options.add_argument('--headless=new')
        
        # 优化策略：不等待流媒体加载，只抓 DOM
        chrome_options.page_load_strategy = 'none'
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--mute-audio')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.set_page_load_timeout(100)
        return driver

    def send_notification(self):
        """发送汇总推送"""
        if not self.enable_push or not self.send_key or not self.msg_logs:
            return
        try:
            # 过滤掉空的日志行
            content = "\n\n".join([line for line in self.msg_logs if line.strip()])
            requests.post(f'https://sctapi.ftqq.com/{self.send_key}.send', 
                          data={'text': '虎牙自动任务汇总', 'desp': content}, timeout=10)
            print("✅ 结果已推送至微信")
        except:
            print("❌ 推送失败")

    def login(self):
        print("[LOGIN] 登录中...")
        self.driver.get(cfg.URLS["user_index"])
        time.sleep(5)
        for line in self.cookie.split(';'):
            if '=' not in line: continue
            name, val = line.split('=', 1)
            try:
                self.driver.add_cookie({'name': name.strip(), 'value': val.strip(), 'domain': '.huya.com', 'path': '/'})
            except: continue
        self.driver.refresh()
        try:
            self.wait.until(EC.presence_of_element_located((By.ID, cfg.LOGIN["huya_num"])))
            print("[SUCCESS] 登录成功")
            return True
        except:
            print("[ERROR] 登录验证超时"); return False

    def get_hl_count(self):
        print("[SEARCH] 查询虎粮数量...")
        self.driver.get(cfg.URLS["pay_index"])
        time.sleep(8) # 给支付页面充足的背包加载时间
        try:
            tab = self.wait.until(EC.element_to_be_clickable((By.ID, cfg.PAY_PAGE["pack_tab"])))
            self.driver.execute_script("arguments[0].click();", tab)
            time.sleep(3)
            # 增强版提取：直接查 data-num
            n = self.driver.execute_script("""
                const items = document.querySelectorAll('li[data-num]');
                for (let x of items) {
                    if ((x.title || x.innerText).includes('虎粮')) return x.getAttribute('data-num');
                }
                return 0;
            """)
            count = int(n) if str(n).isdigit() else 0
            print(f"[COUNT] 识别到虎粮: {count}")
            return count
        except:
            print("[WARN] 背包解析失败"); return 0

    def daily_check_in(self, room_id):
        """精准打卡：类名定位 + 文本二次校验"""
        try:
            # 1. 悬停触发弹窗
            badge = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "FanClubHd--UAIAw8vo8FGSKqVwLp7A")))
            self.driver.execute_script("var e=document.createEvent('MouseEvents');e.initMouseEvent('mouseover',true,false,window,0,0,0,0,0,false,false,false,false,0,null);arguments[0].dispatchEvent(e);", badge)
            time.sleep(2.5)

            # 2. 点击包含“打卡”文本的按钮
            checkin_btn = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(@class, 'Btn--giEMQ9MN7LbLqKHP79BQ') and contains(text(), '打卡')]")
            ))
            self.driver.execute_script("arguments[0].click();", checkin_btn)
            return "✅ 打卡成功"
        except:
            return "❌ 未找到打卡按钮"

    def _execute_send_gift(self, room_id, count):
        """执行送礼：修正数量输入"""
        if count <= 0: return "跳过送礼"
        try:
            lp = self.driver.execute_script('return document.body.getAttribute("data-lp")')
            gid = self.driver.execute_script('return document.body.getAttribute("data-gid")')
            if not lp or not gid: return "❌ 获取参数失败"

            self.driver.get(cfg.URLS["gift_tab"].format(lp=lp, gid=gid))
            time.sleep(5)
            
            items = self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, cfg.GIFT["item_class"])))
            hl_icon = next((i for i in items if "虎粮" in i.text), None)
            
            if hl_icon:
                ActionChains(self.driver).move_to_element(hl_icon).perform()
                inp = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, cfg.GIFT["input_css"])))
                # 核心修正：注入 value 并触发 input 事件，防止虎牙重置数值
                self.driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", inp, str(count))
                time.sleep(1)
                
                send_btn = self.driver.find_element(By.CLASS_NAME, cfg.GIFT["send_class"])
                self.driver.execute_script("arguments[0].click();", send_btn)
                time.sleep(1)
                confirm = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, cfg.GIFT["confirm_class"])))
                self.driver.execute_script("arguments[0].click();", confirm)
                return f"🚀 虎粮赠送成功: {count} 个"
            return "❌ 未找到虎粮图标"
        except Exception as e:
            return f"❌ 送礼异常: {str(e)[:20]}"

    def run(self):
        try:
            if not self.login(): return False
            total_hl = self.get_hl_count()
            n = len(self.rooms)
            
            for i, rid in enumerate(self.rooms):
                print(f"\n>>> 处理房间: {rid}")
                
                # 计算该房间分配的虎粮
                count = 0
                if total_hl > 0:
                    count = total_hl // n + (1 if i < (total_hl % n) else 0)
                
                # 1. 进房间送礼
                self.driver.get(cfg.URLS["room_base"].format(rid))
                time.sleep(8)
                gift_res = self._execute_send_gift(rid, count)
                
                # 2. 刷新或重进页面进行打卡
                self.driver.get(cfg.URLS["room_base"].format(rid))
                time.sleep(6)
                checkin_res = self.daily_check_in(rid)
                
                # 3. 合并结果记录
                log_line = f"{gift_res} ； {checkin_res} (房间 {rid})"
                print(log_line)
                self.msg_logs.append(log_line)

            return True
        finally:
            if hasattr(self, 'driver'):
                self.driver.quit()
            self.send_notification()

if __name__ == '__main__':
    HuYaAuto().run()
