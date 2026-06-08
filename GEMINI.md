(1) 在所有的交流、代码审查和问题解答中，请务必保持极其严谨、客观和中性的专业语调。避免使用任何戏谑、夸张、情绪化或过于口语化的表达。优先保证逻辑的严密性与技术分析的准确性。

(2) 只要我提到 @gem-doc，请务必按照 skill /Users/zhijiebian/.gemini/skills/gem-doc/SKILL.md 的规则，根据提示，保存相关内容到一个新文件，或追加到一个已经存在的文件

(3) 绝对不把Gemini API Key直接定义到source文件里 永远用BBAI.get_gemini_api_key_from_file()取得

(4) 不要写raw Gemini API call, 永远用BBAI.call_gemini

(5) 对于网页的修改任务，请不要自动打开browser测试，这个通常需要太长时间了，你改好后，我来测试