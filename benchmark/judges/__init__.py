from benchmark.judges.base import Judge
from benchmark.judges.registry import JudgeRegistry
from benchmark.judges.llm_judge import LLMJudge
from benchmark.judges.rule_judge import RuleJudge
from benchmark.judges.noop_judge import NoopJudge

JudgeRegistry.register("llm", LLMJudge)
JudgeRegistry.register("rule", RuleJudge)
JudgeRegistry.register("noop", NoopJudge)

__all__ = ["Judge", "JudgeRegistry"]
