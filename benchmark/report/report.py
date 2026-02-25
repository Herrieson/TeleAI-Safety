import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

# --- 设置绘图风格与字体 ---
# 注意：如果您在本地运行且需要显示中文标签，请解开下方的字体设置注释并选择适合您系统的字体
# plt.rcParams['font.sans-serif'] = ['SimHei'] # Windows 常用中文字体
# plt.rcParams['font.sans-serif'] = ['Arial Unicode MS'] # macOS 常用中文字体
# plt.rcParams['axes.unicode_minus'] = False

def parse_pct(val, total=None):
    """
    将 '得分-满分' 字符串 (如 '39-319') 或 数值 转换为百分比 (0-100)
    """
    if pd.isna(val):
        return float("nan")
    if isinstance(val, str):
        raw = val.strip()
        if not raw:
            return float("nan")
        if "-" in raw:
            score_str, full_str = raw.split("-", 1)
            score = float(score_str.strip())
            full = float(full_str.strip())
            return (score / full) * 100 if full else float("nan")
    if total:
        # 如果是数值且提供了满分，则计算百分比
        return (float(val) / total) * 100
    # 如果已经是数值（如法学基础知识），直接返回
    return float(val)


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def validate_columns(df: pd.DataFrame, required, label):
    missing = [col for col in required if col not in df.columns]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"{label} 缺少列: {missing_list}")

def build_hallucination_chart(input_path: Path, output_path: Path, show: bool):
    df_h = read_table(input_path)
    df_h.rename(columns={"Unnamed: 0": "Model"}, inplace=True)

    required_cols = [
        "Model",
        "第一部分-法律条文问答（得分-满分）",
        "第一部分-法学基础知识问答（满分100）",
        "第二部分-法律场景推理（满分60）",
    ]
    validate_columns(df_h, required_cols, "幻觉测试结果")

    df_h_clean = pd.DataFrame()
    df_h_clean["Model"] = df_h["Model"]
    df_h_clean["Law Articles"] = df_h["第一部分-法律条文问答（得分-满分）"].apply(parse_pct)
    df_h_clean["Law Knowledge"] = df_h["第一部分-法学基础知识问答（满分100）"]
    df_h_clean["Law Reasoning"] = df_h["第二部分-法律场景推理（满分60）"].apply(
        lambda x: parse_pct(x, 60)
    )

    df_h_clean["Avg"] = df_h_clean.iloc[:, 1:].mean(axis=1, skipna=True)
    df_h_sorted = df_h_clean.sort_values(by="Avg", ascending=False).drop(columns=["Avg"])

    plt.figure(figsize=(12, 6))
    df_h_sorted.set_index("Model").plot(kind="bar", width=0.8, figsize=(12, 6))
    plt.title("Hallucination Test Results (Sorted by Avg Score)")
    plt.ylabel("Score (%)")
    plt.xticks(rotation=45, ha="right")
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.legend(title="Test Category")
    plt.tight_layout()
    plt.savefig(output_path)
    if show:
        plt.show()
    plt.close()


def build_code_chart(input_path: Path, output_path: Path, show: bool):
    df_c = read_table(input_path)
    df_c.rename(columns={"Unnamed: 0": "Model"}, inplace=True)
    validate_columns(df_c, ["Model"], "代码测试结果")

    df_c_clean = pd.DataFrame()
    df_c_clean["Model"] = df_c["Model"]

    for col in df_c.columns[1:]:
        lang_name = col.split("(")[0].strip()
        df_c_clean[lang_name] = df_c[col].apply(parse_pct)

    df_c_clean["Avg"] = df_c_clean.iloc[:, 1:].mean(axis=1, skipna=True)
    df_c_sorted = df_c_clean.sort_values(by="Avg", ascending=False).drop(columns=["Avg"])

    plt.figure(figsize=(15, 8))
    df_c_sorted.set_index("Model").plot(kind="bar", width=0.85, figsize=(15, 7))
    plt.title("Code Test Results (Sorted by Avg Score)")
    plt.ylabel("Score (%)")
    plt.xticks(rotation=45, ha="right")
    plt.legend(bbox_to_anchor=(1.01, 1), loc="upper left", borderaxespad=0, title="Language")
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(output_path)
    if show:
        plt.show()
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Generate benchmark report charts.")
    parser.add_argument(
        "--hallucination",
        default="幻觉测试结果汇总.xlsx",
        help="Hallucination test summary file (xlsx/csv).",
    )
    parser.add_argument(
        "--code",
        default="代码测试结果汇总.xlsx",
        help="Code test summary file (xlsx/csv).",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Output directory for chart images.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not display charts (useful for headless runs).",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    build_hallucination_chart(
        Path(args.hallucination),
        out_dir / "hallucination_chart.png",
        show=not args.no_show,
    )
    build_code_chart(
        Path(args.code),
        out_dir / "code_chart.png",
        show=not args.no_show,
    )


if __name__ == "__main__":
    main()
