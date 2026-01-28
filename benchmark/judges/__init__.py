from benchmark.judges.base import Judge
from benchmark.judges.registry import JudgeRegistry
from benchmark.judges.llm_judge import LLMJudge
from benchmark.judges.rule_judge import RuleJudge

JudgeRegistry.register("llm", LLMJudge)
JudgeRegistry.register("rule", RuleJudge)

__all__ = ["Judge", "JudgeRegistry"]
