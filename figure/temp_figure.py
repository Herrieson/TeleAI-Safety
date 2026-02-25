import matplotlib.pyplot as plt
import numpy as np

# 数据准备
models = ['deepseek-v3.2', 'llama-3.3-70b', 'miro-235b', 'qwen3-235b']
bias = [0.38, 0.03, -0.17, -0.03]
avg_asr = [0.41, 0.37, 0.46, 0.52]
avg_frr = [0.57, 0.57, 0.42, 0.51]

x = np.arange(len(models))  # 标签的 x 轴位置
width = 0.25  # 柱子的宽度

# 创建图表
fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width, bias, width, label='Bias', color='#2b7bba')
rects2 = ax.bar(x, avg_asr, width, label='Avg ASR', color='#48a381')
rects3 = ax.bar(x + width, avg_frr, width, label='Avg FRR', color='#a29b7c')

# 添加文本、标题和自定义 x 轴标签
ax.set_ylabel('Metric Value')
ax.set_title('Model Performance: Bias, Avg ASR, and Avg FRR')
ax.set_xticks(x)
ax.set_xticklabels(models, rotation=45, ha='right')
ax.legend()

# 为柱子添加数值标签
def autolabel(rects):
    """在每个柱子上方/下方附加一个文本标签，显示其高度。"""
    for rect in rects:
        height = rect.get_height()
        # 处理负值（例如 Bias 的负数），将标签放在柱子底部
        if height < 0:
            y_pos = height - 0.01
            va = 'top'
        else:
            y_pos = height + 0.01
            va = 'bottom'
        ax.annotate(f'{height:.2f}',
                    xy=(rect.get_x() + rect.get_width() / 2, y_pos),
                    xytext=(0, 0),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va=va, fontsize=8, color='gray')

autolabel(rects1)
autolabel(rects2)
autolabel(rects3)

# 优化布局并显示网格
ax.yaxis.grid(True, linestyle='--', alpha=0.3)
ax.set_axisbelow(True)
fig.tight_layout()

# 显示图表
plt.show()

plt.savefig('model_performance.png', dpi=300)