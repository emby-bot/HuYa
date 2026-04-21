#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
虎牙虎粮自动发放 + 粉丝团自动打卡 - 性能优化调试版
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
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

import config as cfg

class HuYaAuto:
    """虎牙助手：优化加载策略 + JS强行触发打卡"""

    def __init__(self):
        self.debug = ""
        self.msg_logs = [] 

        # 获取配置
        self.cookie = os.getenv('HUYA_COOKIE', '').strip()
        self.rooms = self._parse_rooms(os.getenv('HUYA_ROOMS', ''))
        self.send_key = os.getenv('SEND_KEY', '').strip()

        if not self.cookie:
            print("[ERROR] 未设置 HUYA_COOKIE")
            sys.exit(1)

        if not self.rooms:
            print("[WARN] 未设置房间号，使用默认房间")
            self.rooms = [518512, 518511]

        self.driver = self._init_browser()
        self.wait = WebDriverWait(self.driver, 20) 

    def _parse_rooms(self, rooms_str):
        rooms = []
        for s in rooms_str.split(','):
            s = s.strip()
            if s:
                try:
                    rooms.append(int(s))
                except ValueError:
                    print(f"[WARN] 跳过无效房间号: {s}")
        return rooms

    def _init_browser(self):
        chrome_options = Options()
        if not self.debug:
            chrome_options.add_argument('--headless=new')

        # 【关键】加载策略设为 none，防止被虎牙直播流卡死导致 Renderer Timeout
        chrome_options.page_load_strategy = 'none'

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--mute-audio')
        chrome_options.add_argument('--blink-settings=imagesEnabled=false')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        print("[START] 启动浏览器 (Strategy: None)")
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        # 增加超时容忍度
        driver.set_page_load_timeout(120)
        return driver

    def send_notification(self):
        """发送 Server 酱推送 (当前已按要求注释)"""
        # print("[PUSH] 推送功能已暂行注释，跳过发送")
        # if not self.send_key or not self.msg_logs:
        #     return
        # title = "虎牙发放汇总"
        # content = "\n\n".join(self.msg_logs)
        # push_url = f'https://sctapi.ftqq.com/{self.send_key}.send'
        # try:
        #     requests.post(push_url, data={'text': title, 'desp': content}, timeout=10)
        #     print("✅ 推送通知发送成功")
        # except Exception as e:
        #     print(f"❌ 推送异常: {e}")
        pass

    def login(self):
        print("[LOGIN] 登录中...")
        self.driver.get(cfg.URLS["user_index"])
        time.sleep(5) # 等待页面初步加载

        cnt = 0
        for line in self.cookie.split(';'):
            line = line.strip()
            if '=' not in line: continue
            name, val = line.split('=', 1)
            try:
                self.driver.add_cookie({
                    'name': name.strip(), 'value': val.strip(),
                    'domain': '.huya.com', 'path': '/'
                })
                cnt += 1
            except: continue

        print(f"[COOKIE] 已添加 {cnt} 个Cookie")
        self.driver.refresh()
        # 等待登录成功的特征元素
        try:
            self.wait.until(EC.presence_of_element_located((By.ID, cfg.LOGIN["huya_num"])))
            print("[SUCCESS] 登录成功")
            return True
        except:
            print("[ERROR] 登录验证超时")
            return False

    def get_hl_count(self):
        print("[SEARCH] 查询虎粮数量...")
        self.driver.get(cfg.URLS["pay_index"])
        time.sleep(5)
        try:
            # 强行点击背包
            pack_tab = self.wait.until(EC.element_to_be_clickable((By.ID, cfg.PAY_PAGE["pack_tab"])))
            self.driver.execute_script("arguments[0].click();", pack_tab)
            time.sleep(3)
        except:
            return 0

        n = self.driver.execute_script('''
            const items = document.querySelectorAll('li[data-num]');
            for (let item of items) {
                if ((item.title || item.innerText).includes('虎粮')) return item.getAttribute('data-num');
            }
            return 0;
        ''')
        print(f"[COUNT] 虎粮余额: {n}")
        return int(n) if str(n).isdigit() else 0

    def daily_check_in(self, room_id):
        """精准悬停打卡 (JS模拟版)"""
        try:
            FANS_BADGE_CSS = ".FanClubHd--UAIAw8vo8FGSKqVwLp7A"
            CHECKIN_BTN_CSS = ".Btn--giEMQ9MN7LbLqKHP79BQ"

            # 1. 确保元素在视图中
            badge = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, FANS_BADGE_CSS)))
            self.driver.execute_script("arguments[0].scrollIntoView();", badge)
            
            # 2. 使用 JS 模拟 MouseOver 悬停，这在 Headless 模式下比 ActionChains 更稳
            hover_js = "var evObj = document.createEvent('MouseEvents');" \
                       "evObj.initMouseEvent('mouseover',true,false,window,0,0,0,0,0,false,false,false,false,0,null);" \
                       "arguments[0].dispatchEvent(evObj);"
            self.driver.execute_script(hover_js, badge)
            print(f"[CHECKIN] 房间 {room_id} 已触发悬停")
            time.sleep(2)

            # 3. 点击打卡按钮
            checkin_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, CHECKIN_BTN_CSS)))
            self.driver.execute_script("arguments[0].click();", checkin_btn)
            
            msg = f"✅ 房间 {room_id} 打卡成功"
            print(msg)
            self.msg_logs.append(msg)
        except:
            print(f"[INFO] 房间 {room_id} 未发现打卡入口或已打卡")

    def _execute_send_gift(self, room_id, count):
        """执行送礼核心动作"""
        # 获取房间参数
        lp = self.driver.execute_script('return document.body.getAttribute("data-lp")')
        gid = self.driver.execute_script('return document.body.getAttribute("data-gid")')
        
        if not lp or not gid: return

        self.driver.get(cfg.URLS["gift_tab"].format(lp=lp, gid=gid))
        time.sleep(5)
        
        try:
            items = self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, cfg.GIFT["item_class"])))
            hu_liang = next((i for i in items if "虎粮" in i.text), None)
            if hu_liang:
                # 悬停并输入
                ActionChains(self.driver).move_to_element(hu_liang).perform()
                inp = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, cfg.GIFT["input_css"])))
                self.driver.execute_script("arguments[0].value = '';", inp)
                inp.send_keys(str(count))
                
                # 点击赠送和确定
                send_btn = self.driver.find_element(By.CLASS_NAME, cfg.GIFT["send_class"])
                self.driver.execute_script("arguments[0].click();", send_btn)
                time.sleep(1)
                confirm_btn = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, cfg.GIFT["confirm_class"])))
                self.driver.execute_script("arguments[0].click();", confirm_btn)
                
                msg = f"🚀 房间 {room_id} 送礼成功: {count}"
                print(msg)
                self.msg_logs.append(msg)
        except Exception as e:
            print(f"[WARN] 房间 {room_id} 送礼失败: {e}")

    def send_to_room(self, room_id, count):
        try:
            print(f"\n>>> 正在处理: {room_id}")
            self.driver.get(cfg.URLS["room_base"].format(room_id))
            # 手动等待 body，配合 'none' 策略
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(8) # 留足异步加载时间

            # 1. 先送礼
            if count > 0:
                self._execute_send_gift(room_id, count)
            
            # 2. 后打卡 (重新获取直播间主体，防止 iframe 污染)
            self.driver.get(cfg.URLS["room_base"].format(room_id))
            time.sleep(5)
            self.daily_check_in(room_id)

        except Exception as e:
            print(f"[CRASH] 房间 {room_id} 异常: {e}")

    def run(self):
        try:
            if not self.login(): return False
            
            total = self.get_hl_count()
            if total <= 0:
                print("⚠️ 暂无虎粮，仅执行打卡测试")
                for rid in self.rooms:
                    self.send_to_room(rid, 0)
            else:
                n = len(self.rooms)
                per, rem = total // n, total % n
                for i, rid in enumerate(self.rooms):
                    count = per + (1 if i < rem else 0)
                    self.send_to_room(rid, count)
            return True
        finally:
            if hasattr(self, 'driver'):
                self.driver.quit()
            # self.send_notification() # 推送已注释

if __name__ == '__main__':
    main_res = HuYaAuto().run()
    sys.exit(0 if main_res else 1)
