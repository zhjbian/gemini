(1) 在所有的交流、代码审查和问题解答中，请务必保持极其严谨、客观和中性的专业语调。避免使用任何戏谑、夸张、情绪化或过于口语化的表达。优先保证逻辑的严密性与技术分析的准确性。

(2) 只要我提到 @gem-doc，请务必按照 skill /Users/zhijiebian/.gemini/skills/gem-doc/SKILL.md 的规则，根据提示，保存相关内容到一个新文件，或追加到一个已经存在的文件

(3) 绝对不把Gemini API Key直接定义到source文件里 永远用BBAI.get_gemini_api_key_from_file()取得

(4) 不要写raw Gemini API call, 永远用BBAI.call_gemini

(5) 对于网页的修改任务，请不要自动打开browser测试，这个通常需要太长时间了，你改好后，我来测试

(6) 如果我在请你根据某一天的ES或市场走势，或order flow数据及其他数据，来改进我的trading信号系统的时候，http://127.0.0.1:5005/bbt_signals 上的 (a)Order Flow实时盘面判断 (b)SPX Gamma方向判断 (c)综合交易决策, 你提供的方案不能只是为了适应特定某一天的数据，你的方案理论上要合理，要考虑通用性；另外即使某一天的例子只是上涨的例子，你的方案也要包含反方向下跌的情况。

(7）为避免 LaTeX 公式渲染导致的乱码问题，务必将回答中所有公式和符号转换为纯文本形式

(8) 关与Adam Set
# Context: Market Analyst - Adam Set (@Adaamset)

## 1. 角色定义 (Identity & Profile)
- **名称:** Adam Set
- **社媒/推特:** https://x.com/Adaamset
- **定位:** 顶尖宏观趋势与订单流（Order Flow）交易员、市场结构分析师。
- **主要关注品种:** $ES (S&P 500 期货)、$NQ (Nasdaq 期货) 以及高流动性权重股（如 $TSLA、$AMD 等）。

## 2. 核心交易理论与市场视角 (Trading Philosophy)
- **拍卖市场理论 (Auction Market Theory):** 擅长通过拍卖平衡区（Auction Balances）、价值区（Value Areas）和关键阻力/支撑位来评估市场定位。
- **订单流与流动性陷阱 (Order Flow & Liquidity):** 深度聚焦市场微观结构，敏锐捕捉“有毒集会 (Poisoned Rallies)”、“流动性陷阱 (Liquidity Traps)”以及机构暗池与暗盘的真实意图。
- **多空偏见 (Market Bias):** 他的分析通常能给出清晰的大盘日内或周度多空方向主基调（Market Bias）。


(9) Smashelito(@smashelito) 另外一个X的order flow trader，他每周末post weekly分析，每天post daily分析。
和Adam Set不一样，他不做涨跌的方向性预测，但他分享基于order flow的pivot，上涨点位和下跌点位。