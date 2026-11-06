# 子平推演

一款综合《穷通宝鉴》《滴天髓》《三命通会》《中国古代算命术》等古籍理论的八字命理分析程序。

## 功能特点

- **完整 12 步演算流水线**：历法转换 → 四柱排盘 → 大运排列 → 十神标注 → 藏干展开 → 刑冲合害 → 神煞计算 → 五行强弱 → 格局判定 → 用神推荐 → 大运流年 → 综合报告
- **每步均可溯源**：每一步结果都标注了理论来源，可反查至具体古籍章节
- **Web 可视化界面**：输入出生信息即可查看完整推演结果，支持浏览器「打印 / 导出 PDF」
- **支持男女命**：按阳男阴女顺行、阴男阳女逆行的古法排大运

## 技术栈

- Python 3.13+
- Flask（Web 服务）
- lunar-python（历法/八字计算）
- HTML/CSS/JavaScript（前端）

## 安装依赖

建议使用 Python 3.13+ 与虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install flask lunar-python
```

## 启动方式

### 方式一：直接运行 Python

```bash
python app.py
```

默认监听 `http://127.0.0.1:5000`，浏览器访问即可。

### 方式二：双击运行 start.bat

双击项目目录下的 `start.bat`，浏览器会自动打开 http://127.0.0.1:5000

## 项目结构

```
ziping-app/
├── app.py              # Flask Web 服务（/api/calculate 等接口）
├── engine.py           # 12 步八字演算引擎
├── ziwei.py            # 紫微斗数排盘引擎
├── data.py             # 命理知识库（古籍规则、神煞、穷通宝鉴等）
├── chengu.py           # 称骨算命
├── calendar_fix.py     # 真太阳时 / 晚子时等历法校正
├── build_report.py     # 生成并参 HTML 报告
├── templates/
│   └── index.html      # Web 界面
├── static/
│   └── style.css       # 样式
└── tests/              # 单元测试与前端渲染回归
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

## 致谢 / 第三方库

- 紫微斗数排盘核心常量与算法移植自 [iztro](https://github.com/SylarLong/iztro)（MIT，作者 SylarLong）与 [Renhuai123/ziwei-doushu](https://github.com/Renhuai123/ziwei-doushu)，已通过单元测试校验。
- 历法与八字计算依赖 [lunar-python](https://github.com/6tail/lunar-python)。
- 八字演算体系参考《穷通宝鉴》《滴天髓》《三命通会》《中国古代算命术》等古籍，每一步均标注理论来源。

如使用本项目的紫微斗数部分，请遵守 iztro / ziwei-doushu 的许可条款。
