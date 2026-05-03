"""
大麦抢票系统 - 多策略模块

本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。
请勿用于任何商业或非法用途。使用前请阅读项目根目录下的 DISCLAIMER.md。

技术要点：
- 策略模式（Strategy Pattern）设计
- 工厂模式（Factory Pattern）创建策略实例
- 三种策略：并发（Concurrent）、轮询（Polling）、随机（Random）
- asyncio 信号量控制并发数

作者：小吴 (Xiao Wu)
许可证：MIT
"""

import asyncio
import random
import time
from typing import Dict, List, Any, Optional
try:
    from backend.抢票 import attempt_purchase
except ImportError:
    try:
        from .抢票 import attempt_purchase
    except ImportError:
        import sys
        import os
        # 添加当前目录到sys.path以确保可以导入utils
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from 抢票 import attempt_purchase


class TicketStrategy:
    """抢票策略基类"""

    def __init__(self, config: Dict):
        self.config = config
        engine = config.get('engine', {})
        self.concurrency = int(engine.get('concurrency', 3) or config.get('concurrency', 3))
        self.max_concurrency = self.concurrency
        self.interval = float(engine.get('interval', 0.1) or config.get('interval', 0.1))
        self.retry_count = int(engine.get('retry_count', 999) or config.get('retry_count', 999))

    async def execute(self, context) -> List[bool]:
        """
        执行抢票策略

        Args:
            context: BrowserContext对象

        Returns:
            任务结果列表
        """
        raise NotImplementedError


class ConcurrentStrategy(TicketStrategy):
    """并发抢票策略（默认策略）"""

    async def execute(self, context) -> List[bool]:
        """并发执行多个抢票任务"""
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def task_with_semaphore(task_id: int):
            async with semaphore:
                return await attempt_purchase(context, self.config, task_id)

        tasks = []
        for task_id in range(1, self.concurrency + 1):
            tasks.append(task_with_semaphore(task_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 将异常转换为False
        processed_results = []
        for r in results:
            if isinstance(r, Exception):
                processed_results.append(False)
            else:
                processed_results.append(r)

        return processed_results


class PollingStrategy(TicketStrategy):
    """轮询抢票策略 - 按顺序执行任务，每个任务完成后等待指定间隔"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.polling_interval = float(config.get('polling_interval', 1.0))

    async def execute(self, context) -> List[bool]:
        """顺序执行抢票任务，每个任务完成后等待"""
        results = []

        for task_id in range(1, self.concurrency + 1):
            try:
                result = await attempt_purchase(context, self.config, task_id)
                results.append(result)
            except Exception as e:
                results.append(False)

            # 如果不是最后一个任务，则等待轮询间隔
            if task_id < self.concurrency:
                await asyncio.sleep(self.polling_interval)

        return results


class RandomStrategy(TicketStrategy):
    """随机抢票策略 - 随机延迟和随机任务执行顺序"""

    def __init__(self, config: Dict):
        super().__init__(config)
        # 使用配置中的random_delay作为最大延迟的默认值
        default_max_delay = float(config.get('random_delay', 3.0))
        self.min_delay = float(config.get('min_delay', 0.1))
        self.max_delay = float(config.get('max_delay', default_max_delay))
        self.random_order = config.get('random_order', True)

    async def execute(self, context) -> List[bool]:
        """随机策略执行抢票任务"""
        task_ids = list(range(1, self.concurrency + 1))
        if self.random_order:
            random.shuffle(task_ids)

        async def execute_task(task_id: int):
            # 随机延迟
            delay = random.uniform(self.min_delay, self.max_delay)
            await asyncio.sleep(delay)

            try:
                return await attempt_purchase(context, self.config, task_id)
            except Exception as e:
                return False

        # 创建任务
        tasks = [execute_task(task_id) for task_id in task_ids]
        results = await asyncio.gather(*tasks)

        return results


class StrategyFactory:
    """策略工厂类"""

    STRATEGIES = {
        'concurrent': ConcurrentStrategy,
        'polling': PollingStrategy,
        'random': RandomStrategy
    }

    @classmethod
    def create_strategy(cls, config: Dict) -> TicketStrategy:
        """根据配置创建策略实例"""
        strategy_name = config.get('strategy', 'concurrent').lower()

        if strategy_name not in cls.STRATEGIES:
            raise ValueError(f"未知的策略: {strategy_name}。可选策略: {list(cls.STRATEGIES.keys())}")

        strategy_class = cls.STRATEGIES[strategy_name]
        return strategy_class(config)

    @classmethod
    def get_available_strategies(cls) -> List[str]:
        """获取可用策略列表"""
        return list(cls.STRATEGIES.keys())


# 兼容旧版run_tasks函数
async def run_tasks(context, config: Dict) -> List[bool]:
    """兼容旧版接口，使用策略模式执行任务"""
    strategy = StrategyFactory.create_strategy(config)
    return await strategy.execute(context)