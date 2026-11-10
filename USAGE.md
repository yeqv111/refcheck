# 怎么用

分三种人：只想看效果的、想核查自己资料的、想改成自己领域的。

---

## A · 只想看看效果（0 门槛，2 分钟）

不用装任何东西，不用注册账号。

**直接打开报告：**

```bash
open examples/references_report.html    # macOS
start examples\references_report.html   # Windows
```

浏览器里就是一份完整的核查报告：20 条参考文献，11 条可溯源、7 条存疑、2 条查无出处，每条都带可点击的原始链接。

**想验证代码是真的能跑（还是只有截图）：**

```bash
cd refcheck
PYTHONPATH=src python3 -m unittest discover -s tests
```

49 个单元测试，0.01 秒跑完，**不联网、不消耗额度**。克隆下来就能验。

---

## B · 想核查自己的资料（需要腾讯云账号）

### 1. 开通服务

- 登录 [腾讯云](https://cloud.tencent.com)，完成实名认证
- 开通 **元宝搜索**，**选标准版**（极速版不支持 `Industry`/`Cnt`/`score`，做了也没用）
- 到「访问管理 → API 密钥管理」创建密钥，拿到 **SecretId + SecretKey**
- 日常免费额度 2000 次/月；有活动邀请码可提到 6000 次/月

### 2. 拿到代码

```bash
git clone https://github.com/yeqv111/refcheck.git
cd refcheck
```

不需要 `pip install`，纯标准库。想装成命令也可以用：

```bash
pip install -e .
refcheck refs -i refs.txt -r out
```

### 3. 准备输入文件

**核查参考文献** —— 建个 `refs.txt`，一行一条，GB/T 7714 格式最好：

```
[1] 吴礼高, 姚敏, 王朝夫. 55例非特异性慢性肉芽肿性炎中抗酸菌L型感染的探讨[J]. 诊断病理学杂志, 2001(2): 74-75.
[2] 武雅荣, 张永强, 郑英, 等. 肝硬化门静脉血栓形成机制研究进展[J]. 协和医学杂志, 2025, 16(2): 439-447.
```

格式不标准的也能吃——它会尽量从 `[J]` 之类的标记前后取标题，只是准确率会降。

**核查医学陈述** —— 建个 `answer.txt`，把 AI 给你的回答整段粘进去就行，不用排版：

```
患者对二氢吡啶类钙通道阻滞剂过敏，可换用血管紧张素Ⅱ受体拮抗剂，如缬沙坦。
用药期间需要监测血钾和肾功能。应避免使用噻嗪类利尿剂。
```

它会自动按句切分，抽出含药名/指标/疾病的句子去核查，纯客套话会跳过。

### 4. 跑

```bash
export TENCENTCLOUD_SECRET_ID="你的SecretId"        # Windows: set TENCENTCLOUD_SECRET_ID=...
export TENCENTCLOUD_SECRET_KEY="你的SecretKey"

# 核查参考文献
PYTHONPATH=src python3 -m refcheck refs   -i refs.txt   -r out

# 核查医学陈述
PYTHONPATH=src python3 -m refcheck claims -i answer.txt -r out
```

常用参数：

| 参数 | 作用 |
|---|---|
| `--limit 5` | 只跑前 5 条，先试水省额度 |
| `--cnt 10` | 每条取几个搜索结果，默认 10 |
| `--industry acad` | 限定学术领域（**查中文文献时别加，见下方坑**）|
| `--quiet` | 不打印进度条 |

### 5. 看结果

```
out/
├── references_report.html    ← 用浏览器打开，可截图分享
└── references_result.json    ← 结构化数据，想做统计就用它
```

终端里也会直接打印一份带颜色分级的报告。

---

## C · 想改成自己的领域

这个工具不是只能查医学。判定逻辑和领域无关，换掉词表就能用在别处（法律条文、技术文档、财报数字……）。

| 想改什么 | 改哪 |
|---|---|
| 认哪些站点是权威 | `src/refcheck/authority.py` 里的 `ACADEMIC_HOSTS` / `MEDIA_HOSTS` / `FARM_KEYWORDS` |
| 认哪些词是"实体" | `src/refcheck/extract.py` 里的 `METRIC_WORDS` / `DISEASE_WORDS` / `DRUG_CLASS` |
| 判定松紧 | `src/refcheck/match.py` 里的 `SIM_VERIFIED` / `SIM_DOUBT` |
| 报告长什么样 | `src/refcheck/report.py`（单文件 HTML，样式都在这） |

改完跑一遍 `python -m unittest discover -s tests`，别把已有行为弄坏。

---

## 四个必须知道的坑

**① 查中文文献，别加 `--industry acad`**

这是我踩出来的：学术模式会把知网、维普、万方过滤掉，返回一堆英文 DOI 聚合站，20 条能 0 命中。所以 `refs` 模式默认不加领域限制。

**② `score` 不是百分比**

文档写 0~1，实测同一 query 两次能返回 0.777 和 3.832。别拿它当阈值，只用来排序。

**③ 返回 10 条 ≠ 找到了**

一条编造的文献照样能返回 10 条结果，全是"主题相近"的。判据是标题/实体对不对得上。

**④ `Mode=1` 别碰**

文档说"优质权威垂直信源"，实测返回 0 条，而且照扣额度。

---

## 报错怎么办

| 报错 | 原因 | 处理 |
|---|---|---|
| `ResourceNotFound` | 服务没开通 | 去控制台开通元宝搜索 |
| `RequestLimitExceeded` | 调用太快 | 等几秒，或调大 `--delay` |
| `UnauthorizedOperation` | 密钥没权限 | 检查密钥是否有效、是否开通了服务 |
| 缺少凭据 | 环境变量没设 | 重新 `export`，或用 `--secret-id/--secret-key` |
| 结果全是"查无出处" | 可能踩了坑 ① | 去掉 `--industry acad` 重试 |

---

## 成本算一笔

- 20 条参考文献 = **20 次调用**
- 19 条陈述 = **19 次**
- 一次完整实验，成本约 **0.4 元**（按标准版 20 元/千次）

日常免费额度 2000 次/月，够跑一百次完整实验。

---

## 它不能做什么

说清楚边界，比吹功能重要：

- **不判断医学结论对错** —— 只验证"有没有出处"
- **不替代人工核对** —— "已核实"是说找到了对得上的来源，不是说结论一定成立
- **不保证全覆盖** —— 冷门文献、非中文资料，召回会差
- **不能用于诊疗** —— 输出仅供参考，不构成任何医疗建议

身体不适请去正规医院。这话不是免责套话，是这个工具的设计前提。
