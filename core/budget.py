"""BudgetGuard 预算器：控制 AI 调用次数与费用，超限自动降级。

省 token 约束的核心：单场直播云端调用 < 50 次、费用 < 2 元。
达到上限后 can_call_cloud() 返回 False，协调器就不再走云端（L3），
自动回落到 L1 模板 / L2 本地（0 元）。
"""


class BudgetGuard:
    def __init__(self, max_calls=50, max_cost=2.0):
        self.max_calls = max_calls   # 最大调用次数
        self.max_cost = max_cost     # 最大费用（元）
        self._calls = 0              # 已调用次数
        self._spent = 0.0            # 已花费（元）

    def can_call_cloud(self):
        """是否还允许调用云端：次数与费用都未超限。"""
        return self._calls < self.max_calls and self._spent < self.max_cost

    def record_call(self, cost=0.0):
        """记录一次云端调用及其估算费用。"""
        self._calls += 1
        self._spent += cost

    @property
    def remaining_calls(self):
        """剩余可调用次数。"""
        return max(0, self.max_calls - self._calls)

    @property
    def spent(self):
        """已花费金额（元）。"""
        return self._spent
