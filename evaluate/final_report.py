import re
import json
import os
import pandas as pd
from openai import OpenAI

# ================= 配置区域 =================
API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx" # 你的 API Key
BASE_URL = "https://api.openai.com/v1"  # 你的 Base URL
MODEL_NAME = "gpt-4o" # 建议使用 GPT-4o 或 Claude-3.5 Sonnet 以获得最佳分析深度

INPUT_FILE = "summary.md"
OUTPUT_FILE = "Deep_Security_Report.md"
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
    pattern = re.compile(r"##\s+(.*?)\n[\s\S]*?Average ASR across scorers:\s*([\d\.]+)", re.MULTILINE)
    matches = pattern.findall(content)
    
    data = []
    for header, asr in matches:
        header = header.strip()
        
        # === 核心修改：动态解析逻辑 ===
        if "/" in header:
            # 既然规范了命名，直接用 / 切分即可
            parts = header.split("/")
            
            # Model 部分：直接取斜杠前的内容
            # 例如: "gpt-4o-mini" -> "GPT-4o-mini" (可选做简单的首字母大写处理)
            model_raw = parts[0].strip()
            
            # Attack 部分：取斜杠后的内容
            # 例如: "cipher"
            attack_raw = parts[1].strip()
            
            # 格式化名称 (为了报告好看，调用下方的美化函数)
            model = format_model_name(model_raw)
            attack = format_attack_name(attack_raw)
        else:
            # 兜底逻辑：如果忘记加斜杠，为了不报错，暂且把整体当做模型名
            model = header
            attack = "Unknown Attack"

        data.append({
            "Model": model,
            "Attack": attack,
            "ASR": float(asr)
        })
    
    return data

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

def generate_report_with_llm(data_list):
    """
    将清洗后的数据喂给 LLM，要求其模仿专业风格生成报告
    """
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    
    # 预计算一些统计数据辅助 LLM (可选，但推荐)
    df = pd.DataFrame(data_list)
    csv_data = df.to_csv(index=False)

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
(生成一个 Markdown 表格，行是攻击方法，列是模型，单元格是 ASR。如果数据缺失用 - 表示)

## 2. 模型防御能力排名 (Model Defense Ranking)
(计算每个模型的平均 ASR，**由低到高**排序。ASR 越低越好)
- **[模型名] (Avg ASR: X.XX) 👑**
  - **表现评价**：(一句话点评，例如：在所有攻击中表现如铜墙铁壁，或：在复杂攻击下表现出色，但容易被简单模板攻破)

## 3. 攻击方法威胁度排名 (Attack Effectiveness)
(计算每个攻击方法的平均 ASR，**由高到低**排序。ASR 越高越危险)
- **[攻击方法] (Avg ASR: X.XX) 🚨**
  - **威胁等级**：(极高/高/中/低)
  - **原理分析**：(简述为什么这个攻击有效，例如：利用 ASCII 字符绕过语义审查，或：利用角色扮演诱导模型)

## 4. 关键洞察 (Key Insights)
(这是最重要的部分，请分析数据的矛盾点)
- **能力与安全的权衡**：(分析是否有模型因为“太聪明/指令遵循能力太强”而导致 ASR 变高？)
- **防御的“偏科”现象**：(指出某些模型防住了复杂的 PAIR 但防不住简单的 Jailbroken 的现象)
- **非自然语言的漏洞**：(如果 ArtPrompt/Cipher ASR 高，指出模型对非语义输入的防御缺失)

### 输入数据
"""
    
    user_prompt = f"评测数据如下（CSV格式）：\n{csv_data}\n\n请开始生成报告。"

    print("🧠 正在进行深度分析与报告撰写...")
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.4 # 稍微低一点，保证数据准确性
    )
    return response.choices[0].message.content

def main():
    print(f"📂 读取文件: {INPUT_FILE} ...")
    if not os.path.exists(INPUT_FILE):
        print("❌ 文件不存在")
        return

    # 1. 解析数据
    data = parse_markdown_to_df(INPUT_FILE)
    if not data:
        print("⚠️ 未提取到数据，请检查 md 文件格式。")
        return
    print(f"✅ 提取到 {len(data)} 条评测记录。")

    # 2. 生成报告
    report = generate_report_with_llm(data)

    # 3. 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"🎉 报告已生成: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()