#!/usr/bin/env python3
"""
黄金价格实时监控与新闻分析
支持价格曲率计算、趋势预警和投资建议
"""

import requests
import json
import time
import argparse
import numpy as np
from datetime import datetime
from collections import deque
from typing import Optional, Dict, List, Tuple


class GoldPriceMonitor:
    """黄金价格监控器"""
    
    # API 配置
    GOLD_API_URL = "https://m.cmbchina.com/api/rate/gold"
    NEWS_API_URL = "https://api-one-wscn.awtmt.com/apiv1/content/articles/hot?period=all"
    
    # 请求头
    HEADERS = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://m.cmbchina.com/goldrate.html',
        'sec-ch-ua': '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    }
    
    def __init__(self, interval: int = 60, threshold: float = 2.0, window: int = 20):
        """
        初始化监控器
        
        Args:
            interval: 查询间隔（秒）
            threshold: 曲率预警阈值（标准差倍数）
            window: 计算平均曲率的时间窗口（数据点数）
        """
        self.interval = interval
        self.threshold = threshold
        self.window = window
        
        # 数据存储
        self.prices = deque(maxlen=window * 2)
        self.timestamps = deque(maxlen=window * 2)
        self.curvatures = deque(maxlen=window)
        
        self.last_alert_time = 0
        self.alert_cooldown = 300  # 预警冷却时间（5分钟）
        self.query_count = 0  # 查询计数器
        self.last_news_time = 0  # 上次获取新闻的时间
    
    def get_gold_price(self) -> Optional[Dict]:
        """获取实时黄金价格"""
        try:
            response = requests.get(
                self.GOLD_API_URL,
                headers=self.HEADERS,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ 获取黄金价格失败: {e}")
            return None
    
    def get_news(self) -> Optional[List[Dict]]:
        """获取华尔街见闻新闻"""
        try:
            response = requests.get(
                self.NEWS_API_URL,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return data.get('data', {}).get('items', [])
        except Exception as e:
            print(f"❌ 获取新闻失败: {e}")
            return None
    
    def extract_price(self, data: Dict) -> Optional[float]:
        """从API响应中提取 Au(T+D) 价格"""
        try:
            # 处理招商银行API的数据结构: {'body': {'data': [...]}}
            if 'body' in data and 'data' in data['body']:
                items = data['body']['data']
                if isinstance(items, list):
                    for item in items:
                        # 使用 goldNo 或 variety 来匹配 Au(T+D)
                        if item.get('goldNo') == 'AUTD' or item.get('variety') == 'Au(T+D)':
                            return float(item['curPrice'])
            
            # 尝试其他数据结构
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                return float(item.get('curPrice') or item.get('CurPrice') or item.get('price'))
            elif isinstance(data, dict):
                if 'data' in data:
                    items = data['data']
                    if isinstance(items, list) and len(items) > 0:
                        return float(items[0].get('curPrice') or items[0].get('CurPrice') or items[0].get('price'))
                return float(data.get('curPrice') or data.get('CurPrice') or data.get('price'))
            return None
        except (KeyError, TypeError, ValueError) as e:
            print(f"⚠️ 价格解析失败: {e}, 数据: {data}")
            return None
    
    def calculate_curvature(self) -> Optional[Tuple[float, str]]:
        """
        计算价格曲率（二阶导数近似）
        
        Returns:
            (曲率值, 趋势描述)
        """
        if len(self.prices) < 3:
            return None
        
        # 获取最近3个价格点
        prices = list(self.prices)[-3:]
        
        # 计算一阶导数（变化率）
        first_derivative_1 = prices[1] - prices[0]
        first_derivative_2 = prices[2] - prices[1]
        
        # 计算二阶导数（曲率）
        curvature = first_derivative_2 - first_derivative_1
        
        # 判断趋势
        if curvature > 0.01:
            trend = "上涨加速"
        elif curvature > 0:
            trend = "上涨减速"
        elif curvature > -0.01:
            trend = "下跌减速"
        else:
            trend = "下跌加速"
        
        return curvature, trend
    
    def check_alert(self, curvature: float) -> Tuple[bool, float, float]:
        """
        检查是否需要预警
        
        Returns:
            (是否预警, 平均曲率, 标准差倍数)
        """
        if len(self.curvatures) < self.window // 2:
            return False, 0.0, 0.0
        
        # 计算历史平均曲率和标准差
        history = list(self.curvatures)
        mean_curvature = np.mean(history)
        std_curvature = np.std(history)
        
        if std_curvature == 0:
            return False, mean_curvature, 0.0
        
        # 计算偏差（标准差倍数）
        deviation = abs(curvature - mean_curvature) / std_curvature
        
        # 判断是否超过阈值
        should_alert = deviation > self.threshold
        
        return should_alert, mean_curvature, deviation
    
    def analyze_news(self, news_items: Optional[List[Dict]]) -> str:
        """分析新闻内容，生成投资建议"""
        # 处理 None 或空列表
        if not news_items:
            return ""
        
        # 如果 news_items 是字典，尝试提取 items
        if isinstance(news_items, dict):
            news_items = news_items.get('data', {}).get('items', []) or news_items.get('items', [])
        
        if not news_items:
            return ""
        
        # 提取新闻标题和摘要
        news_texts = []
        for item in news_items[:5]:  # 取前5条
            if isinstance(item, dict):
                title = item.get('title', '') or item.get('content_title', '')
                if title:
                    news_texts.append(f"- {title}")
        
        if not news_texts:
            return ""
        
        # 关键词分析（简单规则）
        bullish_keywords = ['上涨', '突破', '新高', '避险', '通胀', '降息', '宽松', '美联储', '黄金', '利好']
        bearish_keywords = ['下跌', '回调', '压力', '加息', '紧缩', '抛售', '回落', '利空']
        
        bullish_count = sum(1 for keyword in bullish_keywords 
                          for text in news_texts if keyword in text)
        bearish_count = sum(1 for keyword in bearish_keywords 
                          for text in news_texts if keyword in text)
        
        # 生成建议
        suggestions = []
        if bullish_count > bearish_count:
            sentiment = "偏多"
            suggestions.append("市场情绪偏多，关注上涨机会")
        elif bearish_count > bullish_count:
            sentiment = "偏空"
            suggestions.append("市场情绪偏空，注意风险控制")
        else:
            sentiment = "中性"
            suggestions.append("市场情绪中性，建议观望")
        
        # 根据价格趋势调整建议
        if len(self.prices) >= 2:
            price_change = self.prices[-1] - self.prices[-2]
            if price_change > 1:
                suggestions.append(f"价格快速上涨(+{price_change:.2f}元)，建议分批获利了结或观望")
            elif price_change < -1:
                suggestions.append(f"价格快速下跌({price_change:.2f}元)，可考虑逢低布局")
            else:
                suggestions.append("价格波动较小，可维持现有仓位")
        
        news_summary = "\n   ".join(news_texts[:3]) if news_texts else "暂无新闻"
        
        return f"""\n📰 市场情绪: {sentiment}
   {news_summary}
   
💡 投资建议:
   {chr(10).join('   - ' + s for s in suggestions)}
   - 风险提示: 以上建议仅供参考，投资需谨慎"""
    
    def print_status(self, price: float, curvature_info: Optional[Tuple], 
                     alert_info: Tuple, news_analysis: str):
        """打印当前状态"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n{'='*60}")
        print(f"⏰ {now}")
        print(f"💰 当前金价 (Au T+D): {price:.2f} 元/克")
        
        if len(self.prices) >= 2:
            change = price - self.prices[-2]
            change_pct = (change / self.prices[-2]) * 100
            change_str = f"+{change:.2f}" if change >= 0 else f"{change:.2f}"
            print(f"   涨跌: {change_str} 元 ({change_pct:+.3f}%)")
        
        if curvature_info:
            curvature, trend = curvature_info
            print(f"📊 价格曲率: {curvature:.4f} ({trend})")
            
            should_alert, mean_curvature, deviation = alert_info
            print(f"   平均曲率: {mean_curvature:.4f}")
            print(f"   曲率偏差: {deviation:.2f}σ")
            
            if should_alert:
                current_time = time.time()
                if current_time - self.last_alert_time > self.alert_cooldown:
                    print(f"\n⚠️  ⚠️  ⚠️  预警触发！曲率异常！⚠️  ⚠️  ⚠️")
                    self.last_alert_time = current_time
                else:
                    print(f"   (预警冷却中，{int(self.alert_cooldown - (current_time - self.last_alert_time))}秒后恢复)")
            
            # 显示新闻分析（如果有）
            if news_analysis:
                print(news_analysis)
        else:
            # 数据不足时的提示
            remaining = 3 - len(self.prices)
            print(f"   ⏳ 正在收集数据... 还需 {remaining} 次查询开始曲率分析")
            
            # 显示简单的趋势判断
            if len(self.prices) == 2:
                change = self.prices[1] - self.prices[0]
                if change > 0:
                    print(f"   📈 趋势: 上涨 {change:.2f} 元")
                elif change < 0:
                    print(f"   📉 趋势: 下跌 {abs(change):.2f} 元")
                else:
                    print(f"   ➡️ 趋势: 持平")
            
            # 即使没有足够数据，也显示新闻分析（如果有）
            if news_analysis:
                print(news_analysis)
        
        print(f"{'='*60}")
    
    def run(self):
        """运行监控循环"""
        print("🚀 启动黄金价格监控...")
        print(f"   查询间隔: {self.interval}秒")
        print(f"   预警阈值: {self.threshold}σ")
        print(f"   时间窗口: {self.window}个数据点")
        print(f"   按 Ctrl+C 停止监控\n")
        
        try:
            while True:
                self.query_count += 1
                
                # 获取黄金价格
                price_data = self.get_gold_price()
                if price_data:
                    price = self.extract_price(price_data)
                    
                    if price:
                        self.prices.append(price)
                        self.timestamps.append(datetime.now())
                        
                        # 计算曲率
                        curvature_info = self.calculate_curvature()
                        
                        # 检查预警
                        if curvature_info:
                            curvature, _ = curvature_info
                            self.curvatures.append(curvature)
                            alert_info = self.check_alert(curvature)
                        else:
                            alert_info = (False, 0.0, 0.0)
                        
                        # 获取新闻分析
                        # 1. 预警时获取
                        # 2. 每10次查询获取一次（即使没有预警）
                        # 3. 距离上次获取新闻超过5分钟
                        news_analysis = ""
                        current_time = time.time()
                        should_fetch_news = (
                            alert_info[0] or  # 预警时
                            self.query_count % 10 == 0 or  # 每10次查询
                            (current_time - self.last_news_time > 300)  # 超过5分钟
                        )
                        
                        if should_fetch_news:
                            news_items = self.get_news()
                            news_analysis = self.analyze_news(news_items)
                            self.last_news_time = current_time
                        
                        # 打印状态
                        self.print_status(price, curvature_info, alert_info, news_analysis)
                    else:
                        print(f"⚠️ 无法解析价格数据")
                
                # 等待下一次查询
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            print("\n\n👋 监控已停止")
            if len(self.prices) > 0:
                print(f"\n📈 监控统计:")
                print(f"   最高价: {max(self.prices):.2f} 元/克")
                print(f"   最低价: {min(self.prices):.2f} 元/克")
                print(f"   平均价: {np.mean(self.prices):.2f} 元/克")
                print(f"   数据点数: {len(self.prices)}")


def main():
    parser = argparse.ArgumentParser(description='黄金价格实时监控')
    parser.add_argument('--interval', type=int, default=60,
                        help='查询间隔（秒），默认60秒')
    parser.add_argument('--threshold', type=float, default=2.0,
                        help='曲率预警阈值（标准差倍数），默认2.0')
    parser.add_argument('--window', type=int, default=20,
                        help='计算平均曲率的时间窗口（数据点数），默认20')
    
    args = parser.parse_args()
    
    monitor = GoldPriceMonitor(
        interval=args.interval,
        threshold=args.threshold,
        window=args.window
    )
    monitor.run()


if __name__ == '__main__':
    main()
