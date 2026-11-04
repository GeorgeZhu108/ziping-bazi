# 子平推演

一款综合《穷通宝鉴》《滴天髓》《三命通会》《中国古代算命术》等古籍理论的八字命理分析程序。

## 功能特点

- **完整 12 步演算流水线**：历法转换 → 四柱排盘 → 大运排列 → 十神标注 → 藏干展开 → 刑冲合害 → 神煞计算 → 五行强弱 → 格局判定 → 用神推荐 → 大运流年 → 综合报告
- **每步均可溯源**：每一步结果都标注了理论来源，可反查至具体古籍章节
- **Web 可视化界面**：输入出生信息即可查看完整推演结果，支持导出 JSON
- **支持男女命**：按阳男阴女顺行、阴男阳女逆行的古法排大运

## 技术栈

- Python 3.13+
- Flask（Web 服务）
- lunar-python（历法/八字计算）
- HTML/CSS/JavaScript（前端）

## 安装依赖

```bash
pip install flask lunar-python
```

或在已创建的虚拟环境中：

```bash
C:/Users/zzh10/.workbuddy/binaries/python/envs/default/Scripts/pip.exe install flask lunar-python
```

## 启动方式

### 方式一：直接运行 Python

```bash
C:/Users/zzh10/.workbuddy/binaries/python/envs/default/Scripts/python.exe "D:/Study/Claw University/ziping-app/app.py"
```

### 方式二：双击运行 start.bat

双击项目目录下的 `start.bat`，浏览器会自动打开 http://127.0.0.1:5000

## 项目结构

```
ziping-app/
├── app.py              # Flask Web 服务
├── engine.py           # 12 步演算引擎
├── data.py             # 命理知识库（古籍规则、神煞、穷通宝鉴等）
├── templates/
│   └── index.html      # Web 界面
├── static/
│   └── style.css       # 样式
└── README.md           # 本文件
```

## 命令行调用示例

```python
from engine import calculate_bazi

result = calculate_bazi(
    year=1990, month=7, day=15, hour=10,
    minute=0, gender="男", current_year=2026
)
print(result)
```

## 免责声明

本程序仅用于传统文化研究与学习，推演结果不构成任何人生决策建议。
