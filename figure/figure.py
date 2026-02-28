import matplotlib.pyplot as plt
import seaborn as sns

# 数据准备
models = ['deepseek-v3.2', 'glm-4.7', 'llama-3.3-70b', 'qwen3-235b']
std_devs = [0.189, 0.057, 0.091, 0.119]

# 设置绘图风格
sns.set_theme(style="whitegrid")
plt.figure(figsize=(10, 5), dpi=300)

# 绘制条形图
ax = sns.barplot(x=std_devs, y=models, palette="YlOrRd_r")

# 添加数值标签
for p in ax.patches:
    width = p.get_width()
    plt.text(width + 0.005, p.get_y() + p.get_height() / 2, 
             f'{width:.4f}', 
             ha='left', va='center', fontweight='bold', color='black')

# 设置标题和标签
plt.title('Standard Deviation of Model ASR Across Attack Methods', fontsize=14, fontweight='bold', pad=15)
plt.xlabel('Standard Deviation (ASR)', fontsize=12)
plt.ylabel('Models', fontsize=12)

# 调整布局并展示
plt.xlim(0, 0.22)
plt.tight_layout()
plt.show()

plt.savefig('model_asr_std_dev.png', dpi=300)