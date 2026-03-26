import type { Locale } from "@/lib/i18n";

export type AttackMethodInfo = {
  method: string;
  summary_zh: string;
  summary_en: string;
  paper_title?: string;
  paper_url?: string;
  repo_url?: string;
};

const ATTACK_METHOD_INFO: Record<string, AttackMethodInfo> = {
  artprompt: {
    method: "artprompt",
    summary_zh: "通过风格化/艺术化表达重写原始请求，尝试绕过直接敏感意图检测。",
    summary_en: "Rewrites the original request into stylized/art-like prompts to evade direct intent filters."
  },
  cipher: {
    method: "cipher",
    summary_zh: "将敏感请求转换为编码或变体文本，再诱导模型在解码语境下回复。",
    summary_en: "Transforms risky requests into encoded/variant text and elicits responses under a decoding context."
  },
  deep_inception: {
    method: "deep_inception",
    summary_zh: "使用多层嵌套叙事和角色设定，让模型在复杂上下文中偏离安全对齐。",
    summary_en: "Uses deeply nested narratives and roles to drift model behavior away from safety alignment.",
    paper_title: "DeepInception: Hypnotize Large Language Model to Be Jailbreaker",
    paper_url: "https://arxiv.org/pdf/2311.03191",
    repo_url: "https://github.com/tmlr-group/DeepInception"
  },
  dra: {
    method: "dra",
    summary_zh: "通过伪装与重构请求语义，以较少查询实现有效越狱。",
    summary_en: "Applies disguise-and-reconstruction to achieve effective jailbreaks with fewer queries.",
    paper_title: "Making Them Ask and Answer: Jailbreaking Large Language Models in Few Queries via Disguise and Reconstruction",
    paper_url: "https://arxiv.org/abs/2402.18104",
    repo_url: "https://github.com/LLM-DRA/DRA"
  },
  gptfuzzer: {
    method: "gptfuzzer",
    summary_zh: "基于变异与筛选循环自动生成越狱提示词，类似 fuzzing 的红队流程。",
    summary_en: "Auto-generates jailbreak prompts with mutation-and-selection loops, similar to fuzzing.",
    paper_title: "GPTFUZZER: Red Teaming Large Language Models with Auto-Generated Jailbreak Prompts",
    paper_url: "https://arxiv.org/pdf/2309.10253.pdf",
    repo_url: "https://github.com/sherdencooper/GPTFuzz"
  },
  ica: {
    method: "ica",
    summary_zh: "利用少量 in-context 演示构造攻击上下文，诱导模型产生违规输出。",
    summary_en: "Builds adversarial in-context demonstrations to induce unsafe outputs.",
    paper_title: "Jailbreak and Guard Aligned Language Models with Only Few In-Context Demonstrations",
    paper_url: "https://arxiv.org/pdf/2310.06387"
  },
  jailbroken: {
    method: "jailbroken",
    summary_zh: "采用角色扮演与指令包装策略，测试安全训练在复杂提示下的失效情况。",
    summary_en: "Uses role-play and instruction wrapping to probe failures of safety alignment.",
    paper_title: "Jailbroken: How Does LLM Safety Training Fail?",
    paper_url: "https://arxiv.org/pdf/2307.02483.pdf"
  },
  laa: {
    method: "laa",
    summary_zh: "自适应地搜索和优化攻击字符串，逐步提高越狱成功率。",
    summary_en: "Adaptively searches and optimizes attack strings to improve jailbreak success.",
    paper_title: "Jailbreaking Leading Safety-Aligned LLMs with Simple Adaptive Attacks",
    paper_url: "https://arxiv.org/abs/2404.02151"
  },
  morpheus_gapfill: {
    method: "morpheus_gapfill",
    summary_zh: "通过多轮元认知提示和 gap-fill 结构，迭代构造更有效的攻击上下文。",
    summary_en: "Iteratively crafts stronger attack context via metacognitive prompting and gap-fill structure."
  },
  multilingual: {
    method: "multilingual",
    summary_zh: "借助跨语言翻译与语义迁移，尝试绕过单语安全策略。",
    summary_en: "Uses cross-lingual translation and semantic transfer to bypass monolingual safety rules."
  },
  overload: {
    method: "overload",
    summary_zh: "先加入认知负载任务再拼接目标请求，干扰模型的安全判断过程。",
    summary_en: "Adds cognitive-load tasks before the target request to interfere with safety judgement."
  },
  pair: {
    method: "pair",
    summary_zh: "通过多轮攻击者-目标者交互与反馈，逐步改写提示以提升攻击效果。",
    summary_en: "Uses iterative attacker-target interactions with feedback to refine jailbreak prompts.",
    paper_title: "PAIR",
    paper_url: "https://arxiv.org/abs/2310.08419"
  },
  past_tense: {
    method: "past_tense",
    summary_zh: "将请求改写为过去时叙述，降低直接违规表达的可见性。",
    summary_en: "Rewrites prompts into past-tense narration to reduce direct unsafe phrasing."
  },
  random_search: {
    method: "random_search",
    summary_zh: "在候选攻击空间中进行随机探索，并保留表现更好的提示变体。",
    summary_en: "Randomly explores attack candidates and keeps stronger prompt variants.",
    paper_title: "Jailbreaking Leading Safety-Aligned LLMs with Simple Adaptive Attacks",
    paper_url: "https://arxiv.org/abs/2404.02151"
  },
  rene: {
    method: "rene",
    summary_zh: "使用模板与重写流程进行迭代提示优化，兼顾稳定性与可迁移性。",
    summary_en: "Uses template-driven iterative rewriting to optimize prompts with stable transferability."
  },
  scav: {
    method: "scav",
    summary_zh: "基于指令映射与检索式改写构造攻击输入，强调批量可复用流程。",
    summary_en: "Builds attacks via instruction mapping and retrieval-style rewriting for batch reuse."
  },
  tap: {
    method: "tap",
    summary_zh: "采用树搜索策略扩展与筛选攻击路径，实现自动化黑盒越狱。",
    summary_en: "Uses tree-search style expansion and selection for automated black-box jailbreaks.",
    paper_title: "Tree of Attacks: Jailbreaking Black-Box LLMs Automatically",
    paper_url: "https://arxiv.org/abs/2312.02119",
    repo_url: "https://github.com/RICommunity/TAP"
  }
};

const FALLBACK_INFO: AttackMethodInfo = {
  method: "",
  summary_zh: "该方法的详细说明尚未在前端配置，可查看后端 methods 源码。",
  summary_en: "Detailed metadata is not configured yet. Please check backend method source files."
};

export function getAttackMethodInfo(method: string): AttackMethodInfo {
  const key = method.toLowerCase();
  const row = ATTACK_METHOD_INFO[key];
  if (row) {
    return row;
  }
  return {
    ...FALLBACK_INFO,
    method
  };
}

export function getMethodSummary(method: string, locale: Locale): string {
  const info = getAttackMethodInfo(method);
  return locale === "zh" ? info.summary_zh : info.summary_en;
}
