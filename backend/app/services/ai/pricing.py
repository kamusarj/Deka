"""Manual DEVELOPMENT configuration, not commercial prices."""
from decimal import Decimal, InvalidOperation
from app.core.config import settings

PLAN_ALLOWANCES = {'FREE': 50, 'BASIC': 500, 'PRO': 1500}
from app.services.ai.policy import OPERATIONS
CREDIT_COST = {name: policy.credits for name, policy in OPERATIONS.items()}

class AICostCalculator:
    def __init__(self, pricing=None):
        self.pricing = settings.AI_MODEL_PRICING if pricing is None else pricing

    def calculate(self, provider, model, usage):
        prices = self.pricing.get(f'{provider}:{model}')
        if not prices or usage.input_tokens is None or usage.output_tokens is None:
            return None
        try:
            input_price = Decimal(prices['input'])
            output_price = Decimal(prices['output'])
            cached_price = Decimal(prices.get('cached_input', prices['input']))
            if any(not price.is_finite() or price < 0 for price in (input_price, output_price, cached_price)):
                return None
        except (KeyError, InvalidOperation, TypeError, ValueError):
            return None
        cached = min(usage.cached_tokens or 0, usage.input_tokens)
        return ((usage.input_tokens - cached) * input_price + cached * cached_price
                + usage.output_tokens * output_price) / Decimal(1_000_000)
