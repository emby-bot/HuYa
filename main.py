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
        # ============ 配置项 ============
        self.debug = False  # 开启调试
        self.enable_push = True  # 推送开关已开启
        # ================================

        self.msg_logs = []
        self.cookie = os.getenv('HUYA_COOKIE', '').strip()
        self.rooms = self._parse_rooms(os.getenv('HUYA_ROOMS', ''))
        self.send_key = os.getenv('SEND_KEY', '').strip()

        # 自定义每个房间赠送虎粮数量：
        # 0 或留空 = 自动把背包虎粮平均分配到所有房间
        # >0 = 每个房间最多赠送这个数量，虎粮不足时后面的房间只打卡不送
        self.gift_count = self._parse_positive_int(os.getenv('HUYA_GIFT_COUNT', '0'), default=0)

        if not self.cookie:
            print("[ERROR] 未设置 HUYA_COOKIE"); sys.exit(1)
        if not self.rooms:
            self.rooms = [518512, 518511]

        self.driver = self._init_browser()
        self.wait = WebDriverWait(self.driver, 15)

    def _parse_rooms(self, rooms_str):
        if not rooms_str:
            return []
        return [int(s.strip()) for s in rooms_str.split(',') if s.strip().isdigit()]

    def _parse_positive_int(self, value, default=0):
        try:
            n = int(str(value or "").strip())
            return n if n > 0 else default
        except Exception:
            return default

    def _init_browser(self):
        chrome_options = Options()
        if not self.debug:
            chrome_options.add_argument('--headless=new')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        return driver

    def send_notification(self):
        """Server酱推送方法"""
        if not self.enable_push or not self.send_key:
            return

        print("[PUSH] 正在发送推送通知...")
        try:
            content = "\n\n".join(self.msg_logs)
            url = f"https://sctapi.ftqq.com/{self.send_key}.send"
            data = {
                "title": "虎牙自动任务报告",
                "desp": content
            }
            res = requests.post(url, data=data, timeout=10)
            if res.status_code == 200:
                print("[SUCCESS] 推送发送成功")
            else:
                print(f"[FAILED] 推送失败，状态码: {res.status_code}")
        except Exception as e:
            print(f"[ERROR] 推送异常: {e}")

    def login(self):
        print("[LOGIN] 正在登录...")
        try:
            self.driver.get(cfg.URLS["user_index"])
            time.sleep(2)
            for line in self.cookie.split(';'):
                if '=' not in line:
                    continue
                name, val = line.split('=', 1)
                self.driver.add_cookie({'name': name.strip(), 'value': val.strip(), 'domain': '.huya.com', 'path': '/'})
            self.driver.refresh()
            self.wait.until(EC.presence_of_element_located((By.ID, cfg.LOGIN["huya_num"])))
            print("[SUCCESS] 登录成功")
            return True
        except Exception as e:
            print(f"[ERROR] 登录失败: {e}")
            return False

    def get_hl_count(self):
        print("[SEARCH] 正在查询虎粮数量...")
        self.driver.get(cfg.URLS["pay_index"])
        time.sleep(4)
        try:
            pack_tab = self.wait.until(EC.element_to_be_clickable((By.ID, cfg.PAY_PAGE["pack_tab"])))
            pack_tab.click()
            time.sleep(2)
            n = self.driver.execute_script('''
                const items = document.querySelectorAll('li[data-num]');
                for (let item of items) {
                    let title = item.title || item.innerText || '';
                    if (title.includes('虎粮')) return item.getAttribute('data-num');
                }
                return 0;
            ''')
            count = int(n) if n else 0
            print(f"[COUNT] 识别到虎粮: {count}")
            return count
        except Exception:
            print("[ERROR] 虎粮数量识别失败，按 0 处理，继续进入房间打卡")
            return 0

    def build_gift_plan(self, total):
        """
        生成每个房间要赠送的虎粮数量。
        - total <= 0：所有房间都不送，但照常打卡
        - HUYA_GIFT_COUNT > 0：每个房间最多送指定数量，剩余不足则后面的房间只打卡
        - HUYA_GIFT_COUNT 未设置/为 0：保持原来的平均分配逻辑
        """
        plan = {rid: 0 for rid in self.rooms}
        if total <= 0 or not self.rooms:
            return plan

        if self.gift_count > 0:
            remaining = total
            for rid in self.rooms:
                if remaining <= 0:
                    break
                num = min(self.gift_count, remaining)
                plan[rid] = num
                remaining -= num
            return plan

        base = total // len(self.rooms)
        extra = total % len(self.rooms)
        for i, rid in enumerate(self.rooms):
            plan[rid] = base + (1 if i < extra else 0)
        return plan

    def send_to_room_in_situ(self, rid, count):
        if count <= 0:
            return "🎁 未赠送虎粮（无虎粮或未分配数量）"
        try:
            self.driver.get(cfg.URLS["room_base"].format(rid))
            time.sleep(5)
            lp = self.driver.execute_script('return document.body.getAttribute("data-lp")')
            gid = self.driver.execute_script('return document.body.getAttribute("data-gid")')
            if not lp or not gid:
                return "❌ 获取直播间参数失败，未送出虎粮"

            self.driver.get(cfg.URLS["gift_tab"].format(lp=lp, gid=gid))
            time.sleep(4)

            items = self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, cfg.GIFT["item_class"])))
            hu_liang = next((i for i in items if "虎粮" in i.text), None)
            if not hu_liang:
                return "❌ 未找到虎粮礼物，未送出虎粮"

            ActionChains(self.driver).move_to_element(hu_liang).pause(1).click().perform()
            time.sleep(1)

            inp = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, cfg.GIFT["input_css"])))
            inp.click()
            inp.clear()
            inp.send_keys(str(count))
            time.sleep(1)

            send_btn = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, cfg.GIFT["send_class"])))
            send_btn.click()
            time.sleep(1)

            try:
                confirm = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, cfg.GIFT["confirm_class"])))
                confirm.click()
            except Exception:
                pass

            print(f"  [WAIT] 正在结算房间 {rid}，原地等待 12 秒...")
            time.sleep(12)
            return f"🚀 房间 {rid} 送出虎粮 {count} 个"
        except Exception as e:
            if self.debug:
                print(f"  [DEBUG] 送礼异常: {e}")
            return "❌ 送虎粮过程异常"

    def daily_check_in(self, rid):
        try:
            self.driver.get(cfg.URLS["room_base"].format(rid))
            time.sleep(6)
            badge = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "FanClubHd--UAIAw8vo8FGSKqVwLp7A")))
            ActionChains(self.driver).move_to_element(badge).perform()
            time.sleep(3)
            btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), '打卡')]")))
            btn.click()
            time.sleep(1)
            return "✅ 打卡成功"
        except Exception:
            return "ℹ️ 已打卡或未找到打卡入口"

    def run(self):
        print("=" * 40 + f"\n[HUYA] 虎牙自动任务启动 (Debug: {self.debug})\n" + "=" * 40)
        try:
            if not self.login():
                self.msg_logs.append("登录失败")
                return

            total = self.get_hl_count()
            gift_plan = self.build_gift_plan(total)

            self.msg_logs.append(f"今日虎粮总数: {total}")
            if self.gift_count > 0:
                self.msg_logs.append(f"自定义赠送数量: 每个房间最多 {self.gift_count} 个")
                print(f"[CONFIG] 自定义赠送数量：每个房间最多 {self.gift_count} 个")
            else:
                self.msg_logs.append("赠送模式: 自动平均分配")
                print("[CONFIG] 赠送模式：自动平均分配")

            if total <= 0:
                print("[INFO] 暂无虎粮，但仍会进入所有房间打卡")

            for rid in self.rooms:
                num = gift_plan.get(rid, 0)
                print(f"\n>>> 房间: {rid} (计划赠送虎粮: {num})")

                # 核心改动：无论有没有虎粮，都进入房间打卡
                c_res = self.daily_check_in(rid)

                # 有分配到虎粮才赠送；没虎粮/没分配也不影响打卡
                g_res = self.send_to_room_in_situ(rid, num) if num > 0 else "🎁 未赠送虎粮（无虎粮或未分配数量）"

                msg = f"房间 {rid}: {c_res}；{g_res}"
                print(f"结果: {msg}")
                self.msg_logs.append(msg)
                time.sleep(2)
        finally:
            # 无论是否运行成功，最后都尝试推送并关闭浏览器
            if self.enable_push:
                self.send_notification()
            if hasattr(self, 'driver'):
                self.driver.quit()

if __name__ == '__main__':
    HuYaAuto().run()
