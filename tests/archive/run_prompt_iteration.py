#!/usr/bin/env python
"""
Prompt 迭代测试脚本

自动执行 10 次迭代测试，每次：
1. 清理数据库
2. 重启服务器
3. 执行测试用例
4. 评分并记录
5. 修改 prompt
6. 更新文档

所有记录写入 tests/prompt_iteration_test.md
"""
import subprocess
import time
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import sys
import shlex

# ============= 配置 =============
SERVER_URL = "http://127.0.0.1:8000"
TEST_USER_ID = "iteration_test_user"
TEST_DOC_PATH = Path(__file__).parent / "prompt_iteration_test.md"
PROMPT_PATH = Path(__file__).parent / "prompts" / "jarvis_system.txt"
DB_PATH = Path(__file__).parent.parent / "unilife.db"
# 使用绝对路径和 /tmp 目录避免权限问题
TEST_DB_PATH = Path("/tmp/unilife_test.db")
TOTAL_ITERATIONS = 10

# ============= 测试用例 =============
TEST_CASES = [
    {
        "name": "用例1：首次创建（无时间）",
        "input": "每天健身",
        "virtual_time": "2026-01-15 08:00",
        "context": "首次使用",
        "focus": ["简洁性", "自主性"]
    },
    {
        "name": "用例2：模糊时间",
        "input": "傍晚健身",
        "virtual_time": "2026-01-15 16:00",
        "context": "首次使用",
        "focus": ["自主性", "简洁性"]
    },
    {
        "name": "用例3：闲聊测试",
        "input": "今天天气真好",
        "virtual_time": "2026-01-15 10:00",
        "context": "首次使用",
        "focus": ["人性化", "简洁性"]
    },
    {
        "name": "用例4：查询事件",
        "input": "今天有什么安排",
        "virtual_time": "2026-01-15 08:00",
        "context": "已有2个事件",
        "focus": ["简洁性"]
    },
    {
        "name": "用例5：修改事件",
        "input": "把健身改成7点半",
        "virtual_time": "2026-01-15 08:30",
        "context": "已有8点健身",
        "focus": ["简洁性", "自主性"]
    },
    {
        "name": "用例6：模糊查询",
        "input": "查一下明天的",
        "virtual_time": "2026-01-15 20:00",
        "context": "明天有3个事件",
        "focus": ["人性化"]
    },
    {
        "name": "用例7：删除新习惯",
        "input": "把健身删了",
        "virtual_time": "2026-01-20 08:00",
        "context": "习惯坚持5天，完成率80%",
        "focus": ["人性化", "自主性"]
    },
    {
        "name": "用例8：批量取消",
        "input": "我今天不舒服，今天的安排都取消吧",
        "virtual_time": "2026-01-15 09:00",
        "context": "今天有3个事件",
        "focus": ["人性化", "简洁性"]
    },
    {
        "name": "用例9：记住偏好",
        "input": "明天也健身",
        "virtual_time": "2026-01-16 08:00",
        "context": "昨天傍晚健身（18:00）",
        "focus": ["自主性"]
    },
    {
        "name": "用例10：出差调整",
        "input": "下周我要去北京，这周的安排调整一下",
        "virtual_time": "2026-01-15 14:00",
        "context": "下周有5个事件",
        "focus": ["人性化", "自主性"]
    }
]

# ============= 评分标准 =============
SCORING_GUIDES = {
    "简洁性": {
        "30-35": "回复极简，一句话说清楚",
        "25-29": "回复简洁，有少量必要信息",
        "20-24": "回复稍长，有一些不必要的内容",
        "15-19": "回复冗长，有很多废话",
        "0-14": "回复非常啰嗦，像机器人"
    },
    "自主性": {
        "35-40": "几乎不追问，直接用默认值",
        "30-34": "很少追问，只在必要时问一次",
        "25-29": "偶尔追问，但问题合理",
        "20-24": "经常追问细节",
        "0-19": "反复追问，像问答机器人"
    },
    "人性化": {
        "22-25": "像真人助手，懂用户，适度关心",
        "18-21": "比较像人，偶尔有些机械",
        "15-17": "有一些人性化，但不够自然",
        "10-14": "比较机械，缺少人情味",
        "0-9": "完全像机器人"
    }
}


class IterationTester:
    def __init__(self):
        self.iteration = 1
        self.conversation_id = None
        self.results = []

    def log(self, message: str):
        """打印日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def reset_database(self):
        """使用独立测试数据库并初始化"""
        self.log("准备测试数据库...")

        # 确保服务器已关闭
        subprocess.run(["pkill", "-9", "-f", "app.main"], capture_output=True)
        time.sleep(2)

        # 删除测试数据库（使用 /tmp 目录）
        try:
            if TEST_DB_PATH.exists():
                TEST_DB_PATH.unlink()
            # 也删除可能的 journal 文件
            for f in Path("/tmp").glob("unilife_test.db*"):
                f.unlink()
        except:
            pass
        time.sleep(1)

        # 设置环境变量使用测试数据库（绝对路径）
        import os
        os.environ["SQLITE_PATH"] = str(TEST_DB_PATH)

        # 初始化测试数据库
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from init_db import init_database
            init_database()
            self.log(f"测试数据库已创建: {TEST_DB_PATH}")
        except Exception as e:
            self.log(f"数据库初始化错误: {e}")
        finally:
            if str(Path(__file__).parent.parent) in sys.path:
                sys.path.remove(str(Path(__file__).parent.parent))

        self.conversation_id = None
        time.sleep(2)

    def _curl_get(self, url: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """使用 curl 发送 GET 请求"""
        try:
            cmd = [
                "curl", "-s", "-w", "\n%{http_code}",
                "--max-time", str(timeout),
                url
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 2
            )
            output = result.stdout.strip()
            if not output:
                return None
            lines = output.split('\n')
            status_line = lines[-1]
            body = '\n'.join(lines[:-1])
            if status_line == "200":
                return json.loads(body) if body else {}
            return None
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
            return None

    def _curl_post(self, url: str, data: Dict, timeout: int = 120) -> Optional[Dict[str, Any]]:
        """使用 curl 发送 POST 请求"""
        try:
            cmd = [
                "curl", "-s", "-w", "\n%{http_code}",
                "-X", "POST",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(data, ensure_ascii=False),
                "--max-time", str(timeout),
                url
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 5
            )
            output = result.stdout.strip()
            if not output:
                return None
            lines = output.split('\n')
            status_line = lines[-1]
            body = '\n'.join(lines[:-1])
            if status_line == "200":
                return json.loads(body) if body else None
            return {"error": f"HTTP {status_line}"}
        except subprocess.TimeoutExpired:
            return {"error": "timeout"}
        except (json.JSONDecodeError, Exception):
            return {"error": "response_error"}

    def restart_server(self):
        """重启服务器（使用测试数据库）"""
        self.log("启动服务器...")

        # 确保没有旧进程
        subprocess.run(["pkill", "-9", "-f", "app.main"], capture_output=True)
        time.sleep(2)

        # 设置环境变量使用测试数据库（绝对路径）
        import os
        env = os.environ.copy()
        env["SQLITE_PATH"] = str(TEST_DB_PATH)

        # 启动服务器
        self.server_process = subprocess.Popen(
            ["python", "-m", "app.main"],
            cwd=Path(__file__).parent.parent,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # 等待服务器启动（使用 curl）
        self.log("等待服务器启动...")
        for i in range(25):  # 最多等待25秒
            result = self._curl_get(f"{SERVER_URL}/health", timeout=2)
            if result is not None:
                self.log(f"服务器已启动 (耗时 {i+1}秒)")
                time.sleep(2)  # 额外等待确保完全就绪
                return
            time.sleep(1)

        self.log("警告：服务器可能未正常启动")

    def send_chat(self, message: str, virtual_time: str) -> Dict[str, Any]:
        """发送聊天消息（使用 curl，支持长时间等待）"""
        url = f"{SERVER_URL}/api/v1/chat"
        payload = {
            "message": message,
            "user_id": TEST_USER_ID,
            "current_time": virtual_time
        }
        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id

        # Multi-agent 响应可能很慢，设置 120 秒超时
        self.log(f"  [发送消息，等待AI回复...]")
        result = self._curl_post(url, payload, timeout=120)

        if result is None:
            return {
                "reply": "ERROR: No response",
                "actions": [],
                "suggestions": None,
                "conversation_id": self.conversation_id
            }

        if "error" in result:
            error_msg = result["error"]
            if error_msg == "timeout":
                return {
                    "reply": "ERROR: Request timeout (AI响应超时，可能multi-agent处理时间过长)",
                    "actions": [],
                    "suggestions": None,
                    "conversation_id": self.conversation_id
                }
            return {
                "reply": f"ERROR: {error_msg}",
                "actions": [],
                "suggestions": None,
                "conversation_id": self.conversation_id
            }

        # 成功响应
        if "conversation_id" in result:
            self.conversation_id = result["conversation_id"]

        return {
            "reply": result.get("reply", ""),
            "actions": result.get("actions", []),
            "suggestions": result.get("suggestions"),
            "conversation_id": self.conversation_id
        }

    def score_reply(self, case: Dict, reply: str) -> Dict[str, int]:
        """对回复进行评分（更严格版本）"""
        scores = {"简洁性": 0, "自主性": 0, "人性化": 0}

        # 检查是否有错误
        if reply.startswith("ERROR:") or "建议" in reply and "几点" in reply:
            # AI 还在追问建议，低分
            return {"简洁性": 10, "自主性": 5, "人性化": 10}

        reply_stripped = reply.strip()
        reply_len = len(reply_stripped)

        # ========== 更严格的简洁性评分 ==========
        # 只有一句话（没有换行符）且极短才能得高分
        has_newline = "\n" in reply_stripped
        sentence_count = reply_stripped.count("。") + reply_stripped.count(".") + reply_stripped.count("!") + reply_stripped.count("！")

        if case["name"] == "用例3：闲聊测试":
            # 闲聊应该极简或直接忽略
            if reply_len <= 10:
                scores["简洁性"] = 35
            elif reply_len <= 20:
                scores["简洁性"] = 30
            elif reply_len <= 40:
                scores["简洁性"] = 25
            else:
                scores["简洁性"] = 15
        elif case["name"] == "用例4：查询事件":
            # 查询应该简洁列表，有 ✓ 更好
            if "✓" in reply and reply_len <= 60 and not has_newline:
                scores["简洁性"] = 35
            elif reply_len <= 40 and not has_newline:
                scores["简洁性"] = 33
            elif reply_len <= 70:
                scores["简洁性"] = 28
            elif reply_len <= 100:
                scores["简洁性"] = 22
            else:
                scores["简洁性"] = 15
        else:
            # 其他用例：一句话搞定
            if not has_newline and sentence_count <= 1 and reply_len <= 25:
                scores["简洁性"] = 35
            elif not has_newline and reply_len <= 40:
                scores["简洁性"] = 32
            elif reply_len <= 60:
                scores["简洁性"] = 27
            elif reply_len <= 100:
                scores["简洁性"] = 20
            else:
                scores["简洁性"] = 12

        # ========== 更严格的自主性评分 ==========
        # 任何问号都是不好的
        question_count = reply.count("？") + reply.count("?")
        # 确认和请也是不好的
        confirm_count = reply.count("确认") + reply.count("请")
        # 有 suggestions 说明没直接执行
        has_suggestions = "建议" in reply or "几点" in reply

        # 严厉惩罚：有任何问号直接扣分
        if has_suggestions or question_count > 0:
            base_autonomy = 10  # 基础分很低
        else:
            base_autonomy = 35  # 没问号才有高分基础

        if case["name"] in ["用例2：模糊时间", "用例5：修改事件", "用例9：记住偏好"]:
            # 这些必须直接执行，零容忍
            if question_count == 0 and confirm_count == 0 and not has_suggestions:
                scores["自主性"] = 40
            elif question_count == 0 and not has_suggestions:
                scores["自主性"] = 35
            else:
                scores["自主性"] = base_autonomy
        elif case["name"] == "用例1：首次创建（无时间）":
            # 可以用默认值直接执行，不问最好
            if question_count == 0 and not has_suggestions:
                scores["自主性"] = 40
            elif question_count == 1 and not has_suggestions:
                scores["自主性"] = 30
            else:
                scores["自主性"] = base_autonomy
        else:
            if question_count == 0 and confirm_count == 0 and not has_suggestions:
                scores["自主性"] = 38
            else:
                scores["自主性"] = base_autonomy

        # ========== 更严格的人性化评分 ==========
        # 必须自然，不能机械
        robotic_keywords = ["作为AI", "语言模型", "无法", "请提供", "我需要", "请问", "建议您", "您可以"]

        if case["name"] == "用例8：批量取消":
            # 必须有关心
            if "早日康复" in reply or "保重" in reply or "好好休息" in reply:
                scores["人性化"] = 25
            elif reply_len < 30 and not any(kw in reply for kw in robotic_keywords):
                scores["人性化"] = 20
            else:
                scores["人性化"] = 12
        elif case["name"] == "用例3：闲聊测试":
            # 应该自然或极简
            robotic_count = sum(1 for kw in robotic_keywords if kw in reply)
            if robotic_count == 0 and reply_len < 30:
                scores["人性化"] = 25
            elif robotic_count == 0:
                scores["人性化"] = 20
            else:
                scores["人性化"] = 10
        else:
            robotic_count = sum(1 for kw in robotic_keywords if kw in reply)
            if robotic_count == 0 and reply_len < 50:
                scores["人性化"] = 23
            elif robotic_count == 0:
                scores["人性化"] = 18
            else:
                scores["人性化"] = 10

        return scores

    def run_iteration(self):
        """运行一次迭代"""
        self.log(f"========== 迭代 #{self.iteration} ==========")

        # 先重置数据库（会关闭服务器）
        self.reset_database()

        # 再启动服务器
        self.restart_server()

        # 执行测试用例
        iteration_results = []

        for i, case in enumerate(TEST_CASES):
            self.log(f"测试 {case['name']}: {case['input']}")

            try:
                data = self.send_chat(case["input"], case["virtual_time"])
                reply = data.get("reply", "")

                # 评分
                scores = self.score_reply(case, reply)
                total = sum(scores.values())

                self.log(f"  回复: {reply[:100]}...")
                self.log(f"  评分: 简洁{scores['简洁性']} 自主{scores['自主性']} 人性{scores['人性化']} = {total}/100")

                iteration_results.append({
                    "用例": case["name"],
                    "输入": case["input"],
                    "实际输出": reply[:100] + "..." if len(reply) > 100 else reply,
                    "简洁性": scores["简洁性"],
                    "自主性": scores["自主性"],
                    "人性化": scores["人性化"],
                    "总分": total
                })

            except Exception as e:
                self.log(f"  错误: {e}")
                iteration_results.append({
                    "用例": case["name"],
                    "输入": case["input"],
                    "实际输出": f"ERROR: {e}",
                    "简洁性": 0,
                    "自主性": 0,
                    "人性化": 0,
                    "总分": 0
                })

            # 用例之间等待（multi-agent 需要更多时间）
            time.sleep(2)

        # 计算平均分
        avg_total = sum(r["总分"] for r in iteration_results) / len(iteration_results)
        avg_concise = sum(r["简洁性"] for r in iteration_results) / len(iteration_results)
        avg_auto = sum(r["自主性"] for r in iteration_results) / len(iteration_results)
        avg_human = sum(r["人性化"] for r in iteration_results) / len(iteration_results)

        self.log(f"迭代 #{self.iteration} 完成！平均分: {avg_total:.1f}/100")

        # 更新文档
        self.update_document(iteration_results, avg_total, avg_concise, avg_auto, avg_human)

        return iteration_results, avg_total

    def update_document(self, results: List[Dict], avg_total: float,
                        avg_concise: float, avg_auto: float, avg_human: float):
        """更新测试文档"""
        content = TEST_DOC_PATH.read_text(encoding="utf-8")

        # 找到当前迭代的占位符并更新
        iteration_marker = f"### 迭代 #{self.iteration}"

        # 构建结果表格
        table_lines = []
        table_lines.append("| 用例 | 输入 | 实际输出 | 简洁性 | 自主性 | 人性化 | 总分 | 备注 |")
        table_lines.append("|------|------|----------|--------|--------|--------|------|------|")

        for r in results:
            table_lines.append(f"| {r['用例']} | {r['输入']} | {r['实际输出']} | {r['简洁性']}/35 | {r['自主性']}/40 | {r['人性化']}/25 | {r['总分']}/100 | |")

        table_str = "\n".join(table_lines)

        # 问题分析
        problems = self.analyze_problems(results)
        problems_str = "\n".join(f"{i+1}. {p}" for i, p in enumerate(problems, 1))

        # 构建迭代记录
        iteration_record = f"""### 迭代 #{self.iteration}
**日期**: {datetime.now().strftime("%Y-%m-%d")}
**Prompt 版本**: v1.{self.iteration}

#### 测试结果

{table_str}

**平均分**: {avg_total:.1f}/100
**简洁性**: {avg_concise:.1f}/35
**自主性**: {avg_auto:.1f}/40
**人性化**: {avg_human:.1f}/25

#### 问题分析
{problems_str}

#### Prompt 修改
{self.suggest_improvements(results)}

#### 下次改进方向
{self.get_next_direction()}
"""

        # 替换占位符
        if f"### 迭代 #{self.iteration}" in content:
            # 更新现有迭代
            pattern = r"(### 迭代 #" + str(self.iteration) + r".*?)(?=### 迭代 #" + str(self.iteration + 1) + r"|## 最终评分趋势)"
            content = re.sub(pattern, iteration_record + "\n", content, flags=re.DOTALL)
        else:
            # 添加新迭代
            if f"### 迭代 #{self.iteration - 1}" in content:
                # 在上一次迭代后添加
                content = content.replace(
                    "### 迭代 #" + str(self.iteration - 1),
                    "### 迭代 #" + str(self.iteration - 1) + "\n" + iteration_record
                )
            else:
                # 找到第一个迭代占位符
                content = content.replace(
                    "### 迭代 #1\n**日期**: 2026-01-23\n**Prompt 版本**: v1.0（初始版本）",
                    iteration_record
                )

        # 更新评分趋势
        trend_line = "| #" + str(self.iteration) + f" | {avg_total:.1f} | {avg_concise:.1f} | {avg_auto:.1f} | {avg_human:.1f} |"

        # 检查趋势表是否已有这一行
        if f"| #{self.iteration} |" in content:
            content = re.sub(
                r"\| #" + str(self.iteration) + r"\|.*?\|",
                trend_line,
                content
            )
        else:
            # 添加到趋势表
            trend_header = "| 迭代 | 平均分 | 简洁性 | 自主性 | 人性化 |"
            content = re.sub(
                rf"(\{trend_header}.*?\n)\|",
                r"\1" + trend_line + "\n|",
                content,
                flags=re.DOTALL
            )

        TEST_DOC_PATH.write_text(content, encoding="utf-8")
        self.log("文档已更新")

    def analyze_problems(self, results: List[Dict]) -> List[str]:
        """分析问题（更严格的版本）"""
        problems = []

        avg_scores = {
            "简洁性": sum(r["简洁性"] for r in results) / len(results),
            "自主性": sum(r["自主性"] for r in results) / len(results),
            "人性化": sum(r["人性化"] for r in results) / len(results),
        }

        # 更严格的阈值
        if avg_scores["简洁性"] < 30:
            problems.append(f"⚠️ 回复过长（平均简洁性{avg_scores['简洁性']:.1f}/35，目标≥33）")
        elif avg_scores["简洁性"] < 33:
            problems.append(f"⚠️ 回复需要更短（平均简洁性{avg_scores['简洁性']:.1f}/35）")

        if avg_scores["自主性"] < 35:
            problems.append(f"⚠️ 仍在追问（平均自主性{avg_scores['自主性']:.1f}/40，目标≥38）")
        elif avg_scores["自主性"] < 38:
            problems.append(f"⚠️ 需要更主动（平均自主性{avg_scores['自主性']:.1f}/40）")

        if avg_scores["人性化"] < 20:
            problems.append(f"⚠️ 过于机械（平均人性化{avg_scores['人性化']:.1f}/25，目标≥23）")
        elif avg_scores["人性化"] < 23:
            problems.append(f"⚠️ 需要更自然（平均人性化{avg_scores['人性化']:.1f}/25）")

        if not problems:
            problems.append("✅ 表现优秀，保持")

        return problems

    def suggest_improvements(self, results: List[Dict]) -> str:
        """建议改进（更激进版本）"""
        avg_scores = {
            "简洁性": sum(r["简洁性"] for r in results) / len(results),
            "自主性": sum(r["自主性"] for r in results) / len(results),
            "人性化": sum(r["人性化"] for r in results) / len(results),
        }

        improvements = []

        # 激进阈值：不完美就改
        if avg_scores["简洁性"] < 33:
            improvements.append("- **激进**：强制限制每条回复≤15字，禁止换行")
            improvements.append("- **激进**：删除所有开场白和解释性语言")

        if avg_scores["自主性"] < 38:
            improvements.append("- **激进**：绝对禁止任何形式的追问和建议")
            improvements.append("- **激进**：强制使用默认值直接执行所有操作")
            improvements.append("- **激进**：完全移除 suggestions 功能")

        if avg_scores["人性化"] < 23:
            improvements.append("- **激进**：添加极简人性化回应（≤4字）")
            improvements.append("- **激进**：删除所有机械化用语")

        if not improvements:
            return "✅ 无需修改，已达到优秀水平"

        return "\n".join(improvements)

    def get_next_direction(self) -> str:
        """获取下次改进方向"""
        return "继续观察，逐步优化"

    def run_all_iterations(self):
        """运行所有迭代"""
        self.log(f"开始 {TOTAL_ITERATIONS} 次迭代测试...")
        self.log("=" * 50)

        for i in range(1, TOTAL_ITERATIONS + 1):
            self.iteration = i

            # 执行迭代
            results, avg_score = self.run_iteration()

            # 如果不是最后一次，修改 prompt
            if i < TOTAL_ITERATIONS:
                self.log("准备修改 prompt...")
                # 这里会自动根据测试结果修改 prompt
                self.improve_prompt(results)
            else:
                self.log("最后一次迭代，不修改 prompt")

            self.log("")

        self.log("=" * 50)
        self.log(f"所有 {TOTAL_ITERATIONS} 次迭代完成！")
        self.log(f"查看详细结果: {TEST_DOC_PATH}")

    def improve_prompt(self, results: List[Dict]):
        """根据测试结果改进 prompt（更激进的版本）"""
        prompt = PROMPT_PATH.read_text(encoding="utf-8")

        avg_scores = {
            "简洁性": sum(r["简洁性"] for r in results) / len(results),
            "自主性": sum(r["自主性"] for r in results) / len(results),
            "人性化": sum(r["人性化"] for r in results) / len(results),
        }

        original_prompt = prompt

        # 激进改进策略：不完美就改
        improvements_made = []

        # 检查具体问题用例
        has_questions = any("？" in r.get("实际输出", "") or "?" in r.get("实际输出", "") for r in results)
        has_suggestions = any("建议" in r.get("实际输出", "") or "几点" in r.get("实际输出", "") for r in results)
        long_replies = any(len(r.get("实际输出", "")) > 50 for r in results)

        # ========== 激进策略1：自主性问题 ==========
        if avg_scores["自主性"] < 38 or has_questions or has_suggestions:
            # 自主性不够，必须强力修改

            # 1. 添加或加强禁止追问规则
            if "**绝对禁止**" not in prompt:
                if "## 核心理念" in prompt:
                    new_rule = '''
## 核心理念：像人一样

**绝对禁止**：
- **禁止向用户追问任何细节**
- **禁止使用 suggestions（建议选项）**
- **禁止说"几点？"、"什么时候？"等追问**
- **禁止说"建议您..."、"您可以..."等建议语**

**记住**：用户给的信息就是全部信息，用默认值执行！
'''
                    prompt = prompt.replace("## 核心理念：像人一样", new_rule)
                    improvements_made.append("添加绝对禁止追问规则")
            else:
                # 加强现有规则
                if "禁止追问" not in prompt:
                    prompt = prompt.replace(
                        "**绝对禁止**：",
                        "**绝对禁止**：\n- **禁止追问任何细节** - 直接用默认值执行！"
                    )
                    improvements_made.append("加强禁止追问")

            # 2. 强制使用默认值
            if "用默认值直接执行" not in prompt:
                if "### 智能决策流程" in prompt:
                    prompt = prompt.replace(
                        "### 智能决策流程",
                        "### 智能决策流程\n\n**核心规则**：所有操作用默认值直接执行，不询问用户！"
                    )
                    improvements_made.append("添加默认值强制执行规则")

            # 3. 删除 suggestions 相关内容
            if "suggestions" in prompt and "禁止使用 suggestions" not in prompt:
                prompt = prompt.replace(
                    "何时不使用 suggestions",
                    "**禁止使用 suggestions** - 直接执行操作"
                )
                improvements_made.append("禁止使用 suggestions")

        # ========== 激进策略2：简洁性问题 ==========
        if avg_scores["简洁性"] < 32 or long_replies:
            # 简洁性不够，强力限制

            if "一句话" not in prompt or "每句话不超过15字" not in prompt:
                if "## 回复风格" in prompt:
                    new_style = '''## 回复风格：像人一样

**回复长度限制（必须遵守）**：
- **每次回复最多一句话，不超过20字**
- **禁止换行**
- **禁止解释为什么这样做**
- **禁止说"好的"、"收到"等无意义的话**

**格式示例**：
- 创建：✓ 已安排：明天7点健身
- 修改：✓ 已调整：改成7点半
- 删除：✓ 已删除：健身事件
- 闲聊：（直接忽略或极简回应）
'''
                    prompt = prompt.replace("## 回复风格：像人一样", new_style)
                    improvements_made.append("添加回复长度强制限制")
            else:
                # 更激进的长度限制
                prompt = prompt.replace("不超过20字", "不超过15字")
                improvements_made.append("缩短回复长度限制")

        # ========== 激进策略3：人性化问题 ==========
        if avg_scores["人性化"] < 22:
            # 添加人性化场景，但要保持简洁
            if "### 人性化场景" not in prompt:
                human_section = '''
### 人性化场景（极简版）

**突发情况**：
- 用户说"不舒服/累了" → "早日康复"（4字）
- 用户坚持习惯 → "继续保持"（4字）

**记住**：人性化也要简洁！
'''
                if "## 回复风格" in prompt:
                    prompt = prompt.replace("## 回复风格", "### 人性化场景（极简版）\n\n" + "## 回复风格")
                    improvements_made.append("添加极简人性化场景")

        # ========== 保存修改 ==========
        if prompt != original_prompt:
            self.log(f"  Prompt 已激进修改: {', '.join(improvements_made)}")
            PROMPT_PATH.write_text(prompt, encoding="utf-8")

            # 备份旧版本
            backup_path = PROMPT_PATH.parent / f"jarvis_system_v1.{self.iteration}.txt"
            original_prompt_path = PROMPT_PATH.parent / f"jarvis_system_v1.{self.iteration - 1}.txt"
            if not original_prompt_path.exists():
                original_prompt_path.write_text(original_prompt, encoding="utf-8")
        else:
            self.log(f"  Prompt 已完美 (简洁{avg_scores['简洁性']:.1f} 自主{avg_scores['自主性']:.1f} 人性{avg_scores['人性化']:.1f})")


if __name__ == "__main__":
    tester = IterationTester()
    tester.run_all_iterations()
