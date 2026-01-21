import argparse
import os
import re
import pandas as pd
from openai import OpenAI, AzureOpenAI

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# ================= 配置区域 =================
# 推荐使用环境变量，避免明文密钥
DEFAULT_INPUT_FILE = os.path.join(PROJECT_ROOT, "evaluation_report", "asr", "summary.md")
DEFAULT_OUTPUT_FILE = os.path.join(PROJECT_ROOT, "evaluation_report", "asr", "Deep_Security_Report.md")
DEFAULT_MODEL_NAME = "gpt-4o"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_AZURE_API_VERSION = "2024-12-01-preview"
# ===========================================

def parse_markdown_to_df(file_path):
    """
    通用解析器：基于 'Model/Attack' 标准命名规范提取数据。
    
    预期 Markdown 格式：
    ## gpt-4o-mini/cipher
    Average ASR across scorers: 0.05
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 正则提取 ## 标题 和 ASR 数值
    pattern = re.compile(
        r"##\s+(.*?)\n[\s\S]*?Average ASR across scorers:\s*([\d\.]+)",
        re.MULTILINE,
    )
    matches = pattern.findall(content)
    
    data = []
    unknown_headers = []
    for header, asr in matches:
        header = header.strip()
        
        # === 核心修改：动态解析逻辑 ===
        parsed = parse_header(header)
        if parsed is None:
            unknown_headers.append(header)
            continue
        model, attack = parsed

        data.append({
            "Model": model,
            "Attack": attack,
            "ASR": float(asr)
        })
    
    return data, unknown_headers

def parse_header(header):
    """
    尝试从 header 中解析出 (model, attack)。无法解析时返回 None。
    支持：
    - Model/attack
    - Model/attack_modelsize
    - attack_model
    """
    header = header.strip()
    known_attacks = [
        "cipher",
        "deepinception",
        "deep_inception",
        "jailbroken",
        "pair",
        "rene",
        "artprompt",
        "dra",
        "dan",
    ]

    if "/" in header:
        model_raw, attack_part = [part.strip() for part in header.split("/", 1)]
        attack_raw, model_suffix = split_attack_and_model(attack_part, known_attacks)
        if attack_raw is None:
            return None
        model = format_model_name(join_model_parts(model_raw, model_suffix))
        attack = format_attack_name(attack_raw)
        return model, attack

    attack_raw, model_raw = split_attack_and_model(header, known_attacks)
    if attack_raw is None:
        return None
    model = format_model_name(model_raw)
    attack = format_attack_name(attack_raw)
    return model, attack

def split_attack_and_model(text, known_attacks):
    text_lower = text.lower()
    for attack in known_attacks:
        if text_lower.startswith(attack):
            model_raw = text[len(attack):].lstrip("_-")
            return normalize_attack_name(attack), model_raw
    if "_" in text:
        attack_part, model_part = text.split("_", 1)
        if attack_part.lower() in known_attacks:
            return normalize_attack_name(attack_part), model_part
    return None, None

def normalize_attack_name(name):
    return name.replace("_", "")

def join_model_parts(prefix, suffix):
    if not suffix:
        return prefix
    suffix = suffix.lstrip("_-")
    return f"{prefix}-{suffix}" if suffix else prefix

# === 辅助函数：负责“报告特点”中的美化工作 ===
# 即使代码逻辑通用，我们还是希望能输出 "PAIR (红队)" 这种带中文注释的专业风格
# 这里只做这就展示层面的映射，不影响核心解析逻辑

def format_model_name(name):
    """简单的模型名称标准化"""
    # 比如把 gpt-4o 统一大写为 GPT-4o
    if name.lower().startswith("gpt"):
        return name.upper().replace("-MINI", "-mini") # 保持 mini 小写更好看
    if "miro" in name.lower():
        return name.capitalize() # Miro-235b
    return name # 其他情况原样返回

def format_attack_name(name):
    """
    将简写映射为报告中的'深度分析'风格 (带中文解释)
    如果没有匹配到，就自动首字母大写返回，保证代码通用性
    """
    name_lower = name.lower()
    
    # 常用方法的映射表 (只需维护这一份字典)
    mapping = {
        "cipher": "Cipher (密码学)",
        "deepinception": "DeepInception (深层嵌套)",
        "jailbroken": "Jailbroken (越狱模板)",
        "pair": "PAIR (自动化红队)",
        "rene": "RENE (重写攻击)",
        "artprompt": "ArtPrompt (字符画)",
        "dra": "DRA (多轮推理)",
        "dan": "DAN (强制指令)"
    }
    
    # 模糊匹配或直接查找
    for key, val in mapping.items():
        if key in name_lower:
            return val
            
    # 如果是全新的攻击方法（不在字典里），代码也不会挂，而是返回 "Newattack"
    return name.capitalize()

def generate_report_with_llm(overview, args):
    """
    将清洗后的数据喂给 LLM，要求其模仿专业风格生成报告
    """
    client = build_openai_client(args)
    
    system_prompt = """
你是一位顶级 AI 安全专家。请根据提供的评测数据（ASR - 攻击成功率），撰写一份**大模型鲁棒性深度测试报告**。

### 核心原则
1. **风格复刻**：必须模仿以下风格：
   - 使用 Emoji 增强可读性（👑 代表最强防御，🚨 代表最高危攻击，💡 代表洞察）。
   - 语言简练有力，使用“偏科”、“绝对防御”、“规模效应”等专业术语。
2. **ASR 解释**：
   - ASR (Attack Success Rate) 越低 = 模型越安全。
   - ASR 越高 = 模型越危险。

### 报告结构要求
请严格按照以下 Markdown 格式输出：

# 🛡️ 大模型越狱攻击鲁棒性测试报告

## 1. 核心数据概览 (Summary Table)
(直接使用输入中的 Markdown 表格，不要改动表格结构)

## 2. 模型防御能力排名 (Model Defense Ranking)
(直接使用输入中的排名清单，并补充一句表现评价)

## 3. 攻击方法威胁度排名 (Attack Effectiveness)
(直接使用输入中的排名清单，并补充威胁等级与原理分析)

## 4. 关键洞察 (Key Insights)
(这是最重要的部分，请分析数据的矛盾点)
- **能力与安全的权衡**：(分析是否有模型因为“太聪明/指令遵循能力太强”而导致 ASR 变高？)
- **防御的“偏科”现象**：(指出某些模型防住了复杂的 PAIR 但防不住简单的 Jailbroken 的现象)
- **非自然语言的漏洞**：(如果 ArtPrompt/Cipher ASR 高，指出模型对非语义输入的防御缺失)

### 输入数据（请严格使用）
"""
    
    user_prompt = (
        f"Summary Table:\n{overview['table']}\n\n"
        f"Model Defense Ranking:\n{overview['model_ranking']}\n\n"
        f"Attack Effectiveness:\n{overview['attack_ranking']}\n\n"
        "请开始生成报告。"
    )

    print("🧠 正在进行深度分析与报告撰写...")
    response = client.chat.completions.create(
        model=args.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.4 # 稍微低一点，保证数据准确性
    )
    return response.choices[0].message.content

def build_openai_client(args):
    if args.provider == "azure":
        if not args.api_key or not args.azure_endpoint:
            raise ValueError("Azure 模式需要提供 --api-key 与 --azure-endpoint")
        return AzureOpenAI(
            api_key=args.api_key,
            azure_endpoint=args.azure_endpoint,
            api_version=args.azure_api_version,
        )
    if not args.api_key:
        raise ValueError("OpenAI 模式需要提供 --api-key")
    return OpenAI(api_key=args.api_key, base_url=args.base_url)

def parse_args():
    parser = argparse.ArgumentParser(description="生成大模型越狱攻击鲁棒性测试报告")
    parser.add_argument("--input", default=DEFAULT_INPUT_FILE, help="评测汇总 Markdown 路径")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_FILE, help="报告输出路径")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME, help="模型或 Azure 部署名")
    parser.add_argument("--provider", choices=["openai", "azure"], default="openai")
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"))
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--azure-endpoint", default=os.getenv("AZURE_OPENAI_ENDPOINT"))
    parser.add_argument("--azure-api-version", default=os.getenv("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION))
    return parser.parse_args()

def build_summary_table(df):
    pivot = df.pivot_table(
        index="Attack",
        columns="Model",
        values="ASR",
        aggfunc="mean",
    )
    pivot = pivot.sort_index()
    columns = ["Attack Method"] + list(pivot.columns)
    rows = []
    for attack in pivot.index:
        row = [attack]
        for model in pivot.columns:
            value = pivot.loc[attack, model]
            row.append("-" if pd.isna(value) else f"{value:.4f}")
        rows.append(row)
    return render_markdown_table(columns, rows)

def render_markdown_table(columns, rows):
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, sep] + body)

def build_model_ranking(df):
    ranking = (
        df.groupby("Model", as_index=False)["ASR"]
        .mean()
        .sort_values("ASR", ascending=True)
    )
    lines = []
    for _, row in ranking.iterrows():
        lines.append(f"- **{row['Model']} (Avg ASR: {row['ASR']:.4f}) 👑**")
    return "\n".join(lines)

def build_attack_ranking(df):
    ranking = (
        df.groupby("Attack", as_index=False)["ASR"]
        .mean()
        .sort_values("ASR", ascending=False)
    )
    lines = []
    for _, row in ranking.iterrows():
        lines.append(f"- **{row['Attack']} (Avg ASR: {row['ASR']:.4f}) 🚨**")
    return "\n".join(lines)

def main():
    args = parse_args()
    print(f"📂 读取文件: {args.input} ...")
    if not os.path.exists(args.input):
        print("❌ 文件不存在")
        return

    # 1. 解析数据
    data, unknown_headers = parse_markdown_to_df(args.input)
    if not data:
        print("⚠️ 未提取到数据，请检查 md 文件格式。")
        return
    print(f"✅ 提取到 {len(data)} 条评测记录。")
    if unknown_headers:
        print(f"⚠️ 有 {len(unknown_headers)} 条标题无法解析，已跳过：")
        for header in unknown_headers:
            print(f"  - {header}")

    # 2. 生成报告
    try:
        df = pd.DataFrame(data)
        overview = {
            "table": build_summary_table(df),
            "model_ranking": build_model_ranking(df),
            "attack_ranking": build_attack_ranking(df),
        }
        report = generate_report_with_llm(overview, args)
    except Exception as exc:
        print(f"❌ 报告生成失败: {exc}")
        return

    # 3. 保存
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"🎉 报告已生成: {args.output}")

if __name__ == "__main__":
    main()
