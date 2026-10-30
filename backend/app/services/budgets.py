"""Mission-wide accounting shared by all roles, repairs and clarification resumes."""

import asyncio
from time import monotonic


class BudgetExceeded(RuntimeError):
    pass


class BudgetMeter:
    def __init__(self, mission, store, token):
        self.mission = mission
        self.store = store
        self.token = token
        self.started = monotonic()
        self.previous_time = mission.budgets.time_used_seconds
        self.lock = asyncio.Lock()

    def elapsed(self):
        return self.previous_time + monotonic() - self.started

    async def _save(self):
        self.mission.budgets.time_used_seconds = self.elapsed()
        await self.store.commit(self.mission.id, self.token, budgets=self.mission.budgets)

    def _check(self):
        budgets = self.mission.budgets
        if self.elapsed() >= budgets.max_time_seconds:
            raise BudgetExceeded(f"Mission active-time budget exhausted ({self.elapsed():.1f}/{budgets.max_time_seconds} seconds)")
        if budgets.input_tokens_used + budgets.output_tokens_used >= budgets.max_tokens:
            used = budgets.input_tokens_used + budgets.output_tokens_used
            raise BudgetExceeded(f"Mission reported-token budget exhausted ({used}/{budgets.max_tokens} tokens)")

    async def before_model(self):
        async with self.lock:
            self._check()
            budgets = self.mission.budgets
            if budgets.model_turns_used >= budgets.max_model_turns:
                raise BudgetExceeded(f"Mission model-turn budget exhausted ({budgets.model_turns_used}/{budgets.max_model_turns} turns)")
            # Reserve before sending: errors/cancellation do not refund an attempted turn.
            budgets.model_turns_used += 1
            await self._save()

    async def after_model(self, response):
        async with self.lock:
            self.mission.budgets.input_tokens_used += response.input_tokens
            self.mission.budgets.output_tokens_used += response.output_tokens
            await self._save()
            self._check()

    async def before_tool(self):
        async with self.lock:
            self._check()
            budgets = self.mission.budgets
            if budgets.tool_calls_used >= budgets.max_tool_calls:
                raise BudgetExceeded(f"Mission tool-call budget exhausted ({budgets.tool_calls_used}/{budgets.max_tool_calls} calls)")
            budgets.tool_calls_used += 1
            await self._save()

    async def flush(self):
        async with self.lock:
            await self._save()


class BudgetedAdapter:
    def __init__(self, adapter, meter):
        self.adapter = adapter
        self.meter = meter

    async def chat(self, *args, **kwargs):
        await self.meter.before_model()
        response = await self.adapter.chat(*args, **kwargs)
        await self.meter.after_model(response)
        return response
