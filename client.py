"""
UniLife Terminal Client - 简易终端前端
用于测试和调试后端 API
"""
import requests
import json
import sys
import os
from datetime import datetime
from typing import Optional

# Fix Windows terminal encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# API 配置
API_BASE_URL = "http://localhost:8000/api/v1"
USER_ID_FILE = ".unilife_user_id.txt"  # 保存用户 ID 的文件


class Colors:
    """终端颜色代码"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_banner():
    """打印欢迎横幅"""
    banner = f"""
{Colors.CYAN}╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   {Colors.BOLD}UniLife - AI Life Scheduling Assistant{Colors.END}              {Colors.CYAN}║
║   {Colors.BOLD}Terminal Client v1.0{Colors.END}                                  {Colors.CYAN}║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝{Colors.END}

{Colors.YELLOW}输入 'help' 查看可用命令，输入 'quit' 或 'exit' 退出{Colors.END}
"""
    print(banner)


def print_help():
    """显示帮助信息"""
    help_text = f"""
{Colors.BOLD}可用命令：{Colors.END}
{Colors.GREEN}聊天命令：{Colors.END}
  任何自然语言输入                          - 与 Jarvis 对话
  示例:
    • 帮我安排明天下午3点开会
    • 我今天有什么安排
    • 查询本周的会议
    • 取消今天的会议
    • 我现在状态怎么样
    • 撤销刚才的操作

{Colors.GREEN}系统命令：{Colors.END}
  {Colors.CYAN}help{Colors.END}                                     - 显示此帮助信息
  {Colors.CYAN}history{Colors.END}                                  - 查看对话历史
  {Colors.CYAN}clear{Colors.END}                                    - 清除对话历史
  {Colors.CYAN}events{Colors.END}                                   - 查看所有事件
  {Colors.CYAN}snapshots{Colors.END}                                - 查看快照历史
  {Colors.CYAN}energy{Colors.END}                                   - 查看能量状态
  {Colors.CYAN}quit, exit{Colors.END}                              - 退出程序

{Colors.YELLOW}提示：直接输入自然语言即可与 Jarvis 交互！{Colors.END}
"""
    print(help_text)


def print_message(role: str, content: str):
    """格式化打印消息"""
    timestamp = datetime.now().strftime("%H:%M:%S")

    if role == "user":
        print(f"\n{Colors.BLUE}[{timestamp}] 你：{Colors.END}")
        print(f"{Colors.BOLD}{content}{Colors.END}")
    elif role == "assistant":
        print(f"\n{Colors.GREEN}[{timestamp}] Jarvis：{Colors.END}")
        print(content)
    elif role == "system":
        print(f"\n{Colors.YELLOW}◆ {content}{Colors.END}")
    elif role == "error":
        print(f"\n{Colors.RED}✗ 错误：{content}{Colors.END}")
    elif role == "success":
        print(f"\n{Colors.GREEN}✓ {content}{Colors.END}")


def print_actions(actions: list):
    """打印执行的操作"""
    if not actions:
        return

    print(f"\n{Colors.CYAN}━━━ 执行的操作 ━━━{Colors.END}")
    for action in actions:
        action_type = action.get("type", "unknown")
        if action_type == "create_event":
            event = action.get("event", {})
            print(f"{Colors.GREEN}+ 创建事件：{event.get('title', 'Untitled')}{Colors.END}")
        elif action_type == "update_event":
            event = action.get("event", {})
            print(f"{Colors.YELLOW}~ 更新事件：{event.get('title', 'Untitled')}{Colors.END}")
        elif action_type == "delete_event":
            event = action.get("event", {})
            print(f"{Colors.RED}- 删除事件：{event.get('title', 'Untitled')}{Colors.END}")
        else:
            print(f"• {action_type}")


def load_last_user_id() -> Optional[str]:
    """加载上次使用的用户 ID"""
    try:
        if os.path.exists(USER_ID_FILE):
            with open(USER_ID_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception:
        pass
    return None


def save_user_id(user_id: str):
    """保存用户 ID"""
    try:
        with open(USER_ID_FILE, 'w', encoding='utf-8') as f:
            f.write(user_id)
    except Exception:
        pass


def login() -> str:
    """登录界面 - 获取用户 ID"""
    print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}                    登录{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}\n")

    # 尝试加载上次使用的用户 ID
    last_user_id = load_last_user_id()

    if last_user_id:
        print(f"{Colors.YELLOW}检测到上次登录：{Colors.END}{Colors.BOLD}{last_user_id}{Colors.END}")
        choice = input(f"是否使用此账号？[{Colors.GREEN}Y{Colors.END}/n] ").strip().lower()

        if choice in ['', 'y', 'yes']:
            print(f"{Colors.GREEN}✓ 欢迎回来，{last_user_id}！{Colors.END}\n")
            return last_user_id

    # 输入用户 ID
    while True:
        user_id = input(f"{Colors.CYAN}请输入用户 ID：{Colors.END}").strip()

        if not user_id:
            print(f"{Colors.RED}✗ 用户 ID 不能为空{Colors.END}")
            continue

        # 简单验证
        if len(user_id) < 3:
            print(f"{Colors.YELLOW}⚠ 用户 ID 建议至少 3 个字符{Colors.END}")
            confirm = input("仍然使用此 ID？[y/N] ").strip().lower()
            if confirm not in ['y', 'yes']:
                continue

        # 保存用户 ID
        save_user_id(user_id)

        print(f"{Colors.GREEN}✓ 登录成功！欢迎，{user_id}{Colors.END}\n")
        return user_id


def send_chat_message(message: str, user_id: str) -> Optional[dict]:
    """发送聊天消息到后端"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={
                "message": message,
                "user_id": user_id,
                "context": None  # Optional field, send null instead of empty dict
            },
            timeout=600  # 10分钟超时，支持复杂任务
        )

        if response.status_code == 200:
            return response.json()
        else:
            print_message("error", f"API 返回错误: {response.status_code}")
            return None

    except requests.exceptions.ConnectionError:
        print_message("error", "无法连接到服务器，请确保后端正在运行")
        return None
    except requests.exceptions.Timeout:
        print_message("error", "请求超时")
        return None
    except Exception as e:
        print_message("error", f"发生错误: {str(e)}")
        return None


def get_chat_history(user_id: str) -> Optional[dict]:
    """获取对话历史"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/chat/history",
            params={"user_id": user_id, "limit": 50}
        )

        if response.status_code == 200:
            return response.json()
        else:
            print_message("error", f"获取历史失败: {response.status_code}")
            return None

    except Exception as e:
        print_message("error", f"发生错误: {str(e)}")
        return None


def clear_chat_history(user_id: str) -> bool:
    """清除对话历史"""
    try:
        response = requests.delete(
            f"{API_BASE_URL}/chat/history",
            params={"user_id": user_id}
        )

        if response.status_code == 200:
            return True
        else:
            print_message("error", f"清除历史失败: {response.status_code}")
            return False

    except Exception as e:
        print_message("error", f"发生错误: {str(e)}")
        return False


def get_all_events(user_id: str) -> Optional[dict]:
    """获取所有事件"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/events",
            params={"user_id": user_id}
        )

        if response.status_code == 200:
            return response.json()
        else:
            print_message("error", f"获取事件失败: {response.status_code}")
            return None

    except Exception as e:
        print_message("error", f"发生错误: {str(e)}")
        return None


def get_snapshots(user_id: str) -> Optional[dict]:
    """获取快照历史"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/snapshots",
            params={"user_id": user_id}
        )

        if response.status_code == 200:
            return response.json()
        else:
            print_message("error", f"获取快照失败: {response.status_code}")
            return None

    except Exception as e:
        print_message("error", f"发生错误: {str(e)}")
        return None


def check_server_health() -> bool:
    """检查服务器健康状态"""
    try:
        # Health check is at root, not under /api/v1
        response = requests.get("http://localhost:8000/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def format_events_display(events_data: dict):
    """格式化显示事件列表（使用双层时间架构）"""
    events = events_data.get("events", [])

    if not events:
        print_message("system", "暂无事件")
        return

    print(f"\n{Colors.CYAN}━━━ 事件列表 ({len(events)}) ━━━{Colors.END}")

    for i, event in enumerate(events, 1):
        title = event.get("title", "Untitled")
        status = event.get("status", "UNKNOWN")
        start_time = event.get("start_time")
        duration = event.get("duration")
        duration_source = event.get("duration_source", "default")
        duration_confidence = event.get("duration_confidence", 1.0)
        display_mode = event.get("display_mode", "flexible")

        # 状态图标
        status_icon = "✓" if status == "COMPLETED" else "○"

        # 解析开始时间
        if start_time:
            start_dt = datetime.fromisoformat(start_time)
            time_str = start_dt.strftime("%H:%M")
        else:
            time_str = "待定"
            duration = None

        # 格式化时长显示（双层架构）
        if display_mode == "flexible" and duration:
            # 判断是否显示"AI估计"标注（置信度阈值 0.7）
            show_ai_note = (
                duration_source == "ai_estimate" and
                duration_confidence < 0.7
            )

            # 友好的时长显示
            if duration < 60:
                duration_text = f"{duration}分钟"
            elif duration % 60 == 0:
                duration_text = f"{duration // 60}小时"
            else:
                hours = duration // 60
                mins = duration % 60
                duration_text = f"{hours}小时{mins}分钟"

            # 根据时长来源和置信度显示
            if show_ai_note:
                time_display = f"{time_str} {title}（约{duration_text}，AI估计）"
            elif duration_source == "ai_estimate":
                time_display = f"{time_str} {title}（约{duration_text}）"
            elif duration_source == "default":
                time_display = f"{time_str} {title}（约{duration_text}）"
            else:
                time_display = f"{time_str} {title}（{duration_text}）"

            print(f"{status_icon} {i}. {Colors.BOLD}{time_display}{Colors.END}")
        elif duration:
            # 兜底显示
            if duration < 60:
                duration_text = f"{duration}分钟"
            else:
                duration_text = f"{duration // 60}小时"
            print(f"{status_icon} {i}. {Colors.BOLD}{time_str} {title}{Colors.END}（{duration_text}）")
        else:
            print(f"{status_icon} {i}. {Colors.BOLD}{time_str} {title}{Colors.END}")

    print()


def format_snapshots_display(snapshots_data: dict):
    """格式化显示快照列表"""
    snapshots = snapshots_data.get("snapshots", [])

    if not snapshots:
        print_message("system", "暂无快照历史")
        return

    print(f"\n{Colors.CYAN}━━━ 快照历史 ({len(snapshots)}) ━━━{Colors.END}")

    for i, snapshot in enumerate(snapshots, 1):
        snapshot_id = snapshot.get("id", "")[:8]
        trigger = snapshot.get("trigger_message", "")
        created_at = snapshot.get("created_at", "")

        if created_at:
            time_str = datetime.fromisoformat(created_at).strftime("%H:%M:%S")
        else:
            time_str = "Unknown"

        print(f"{i}. [{snapshot_id}] {time_str} - {trigger}")

    print()


def print_suggestions(suggestions: list):
    """打印建议选项"""
    if not suggestions:
        return

    print(f"\n{Colors.CYAN}━━━ 请选择 ━━━{Colors.END}")
    for i, suggestion in enumerate(suggestions, 1):
        label = suggestion.get("label", "")
        description = suggestion.get("description", "")
        probability = suggestion.get("probability")

        # 构建显示文本
        base_text = f"  {Colors.GREEN}{i}.{Colors.END} {Colors.BOLD}{label}{Colors.END}"

        # 添加概率显示
        if probability is not None:
            # 根据概率选择不同的颜色
            if probability >= 70:
                prob_color = Colors.GREEN
            elif probability >= 40:
                prob_color = Colors.YELLOW
            else:
                prob_color = Colors.RED
            base_text += f" [{prob_color}{probability}%{Colors.END}]"

        # 添加描述
        if description:
            print(f"{base_text} - {description}")
        else:
            print(base_text)
    print()


def handle_suggestions(result: dict):
    """处理响应中的 suggestions"""
    suggestions = result.get("suggestions")
    if suggestions:
        print_suggestions(suggestions)


def print_auto_action(result: dict):
    """打印自动执行的操作和备选方案"""
    auto_action = result.get("auto_action")
    alternative_options = result.get("alternative_options")
    confidence = result.get("confidence")

    if auto_action:
        print(f"\n{Colors.CYAN}━━━ 智能决策 ━━━{Colors.END}")
        print(f"{Colors.GREEN}✓ 已自动执行{Colors.END}")
        if confidence:
            print(f"  置信度：{confidence}%（基于您的历史习惯）")

        # 显示自动执行的 action
        action_type = auto_action.get("type", "unknown")
        description = auto_action.get("description", "")
        if description:
            print(f"  操作：{description}")

        print()

        # 如果有备选方案，显示
        if alternative_options:
            print(f"{Colors.YELLOW}如果不满意，可以选择其他方案：{Colors.END}")
            for i, option in enumerate(alternative_options, 1):
                label = option.get("label", "")
                value = option.get("value", "")
                print(f"  {Colors.CYAN}{i}.{Colors.END} {label}")
                if value and value != label:
                    print(f"      → {value}")
            print(f"  {Colors.CYAN}0.{Colors.END} 保持当前操作\n")


def main():
    """主函数"""
    print_banner()

    # 登录
    user_id = login()

    # 显示当前用户信息
    print(f"{Colors.CYAN}━━━ 当前用户 ━━━{Colors.END}")
    print(f"  用户 ID: {Colors.BOLD}{user_id}{Colors.END}")
    print()

    # 检查服务器连接
    print_message("system", "正在连接服务器...")
    if not check_server_health():
        print_message("error", "无法连接到服务器，请确保后端正在运行 (python -m app.main)")
        sys.exit(1)

    print_message("success", "已连接到服务器")

    # 选项模式状态
    option_mode = False
    current_suggestions = None
    alternative_mode = False
    current_alternatives = None
    original_result = None

    # 主循环
    while True:
        try:
            # 获取用户输入
            if option_mode:
                user_input = input(f"\n{Colors.YELLOW}请选择 [1-{len(current_suggestions)}] 或输入自定义内容:{Colors.END} ").strip()
            elif alternative_mode:
                user_input = input(f"\n{Colors.YELLOW}选择备选方案 [0-{len(current_alternatives)}] 或按回车继续:{Colors.END} ").strip()
            else:
                user_input = input(f"\n{Colors.BOLD}> {Colors.END}").strip()

            if not user_input:
                continue

            # 处理命令
            if user_input.lower() in ["quit", "exit", "q"]:
                print_message("system", "再见！")
                break

            elif user_input.lower() == "help":
                print_help()
                continue

            elif user_input.lower() == "history":
                history_data = get_chat_history(user_id)
                if history_data:
                    history = history_data.get("history", [])
                    print(f"\n{Colors.CYAN}━━━ 对话历史 ({len(history)} 条) ━━━{Colors.END}")
                    for msg in history[-20:]:  # 显示最近20条
                        role = msg.get("role", "unknown")
                        content = msg.get("content", "")
                        if role == "user":
                            print(f"{Colors.BLUE}你：{Colors.END} {content}")
                        else:
                            print(f"{Colors.GREEN}Jarvis：{Colors.END} {content}")
                continue

            elif user_input.lower() == "clear":
                if clear_chat_history(user_id):
                    print_message("success", "对话历史已清除")
                continue

            elif user_input.lower() == "events":
                events_data = get_all_events(user_id)
                if events_data:
                    format_events_display(events_data)
                continue

            elif user_input.lower() == "snapshots":
                snapshots_data = get_snapshots(user_id)
                if snapshots_data:
                    format_snapshots_display(snapshots_data)
                continue

            elif user_input.lower() == "energy":
                # 使用聊天接口查询能量
                result = send_chat_message("我现在状态怎么样", user_id)
                if result:
                    print_message("assistant", result.get("reply", ""))
                    # 处理选项
                    handle_suggestions(result)
                continue

            # 选项模式处理
            if option_mode and current_suggestions:
                # 检查是否输入的是数字
                try:
                    choice = int(user_input)
                    if 1 <= choice <= len(current_suggestions):
                        # 用户选择了选项
                        selected = current_suggestions[choice - 1]
                        selected_value = selected.get("value")

                        if selected_value is None:
                            # value 为 None，需要用户手动输入
                            label = selected.get("label", "")
                            print_message("system", f"请输入{label}：")
                            # 下一轮循环会获取用户输入
                            option_mode = False
                            current_suggestions = None
                            continue
                        else:
                            # 使用预定义的 value
                            user_input = selected_value
                            option_mode = False
                            current_suggestions = None
                            print_message("user", user_input)
                    else:
                        print_message("error", f"请输入 1-{len(current_suggestions)} 之间的数字")
                        continue
                except ValueError:
                    # 不是数字，当作自定义输入
                    option_mode = False
                    current_suggestions = None
                    print_message("user", user_input)

            # 备选方案模式处理
            elif alternative_mode and current_alternatives:
                # 如果用户直接按回车，保持当前操作
                if user_input == "" or user_input == "0":
                    print_message("success", "已保持当前操作")
                    alternative_mode = False
                    current_alternatives = None
                    original_result = None
                    continue

                try:
                    choice = int(user_input)
                    if 1 <= choice <= len(current_alternatives):
                        # 用户选择了备选方案
                        selected = current_alternatives[choice - 1]
                        selected_value = selected.get("value")

                        if selected_value:
                            # 执行备选方案
                            alternative_mode = False
                            current_alternatives = None
                            print_message("user", selected_value)
                            user_input = selected_value
                        else:
                            print_message("error", "无效的备选方案")
                            continue
                    else:
                        print_message("error", f"请输入 0-{len(current_alternatives)} 之间的数字")
                        continue
                except ValueError:
                    # 不是数字，当作新的输入
                    alternative_mode = False
                    current_alternatives = None
                    original_result = None
                    print_message("user", user_input)

            # 发送聊天消息
            result = send_chat_message(user_input, user_id)

            if result:
                # 打印回复
                reply = result.get("reply", "")
                print_message("assistant", reply)

                # 打印操作
                actions = result.get("actions", [])
                if actions:
                    print_actions(actions)

                # 打印快照ID
                snapshot_id = result.get("snapshot_id")
                if snapshot_id:
                    print_message("system", f"快照已创建: {snapshot_id[:8]}...")

                # 处理智能决策（自动执行 + 备选方案）
                auto_action = result.get("auto_action")
                alternative_options = result.get("alternative_options")

                if auto_action:
                    print_auto_action(result)

                    # 如果有备选方案，进入备选模式
                    if alternative_options:
                        alternative_mode = True
                        current_alternatives = alternative_options
                        original_result = result

                # 处理选项
                suggestions = result.get("suggestions")
                if suggestions:
                    option_mode = True
                    current_suggestions = suggestions
                    print_suggestions(suggestions)

        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}使用 'quit' 或 'exit' 退出{Colors.END}")
            option_mode = False
            current_suggestions = None
            alternative_mode = False
            current_alternatives = None
        except EOFError:
            print(f"\n\n{Colors.YELLOW}再见！{Colors.END}")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}程序已退出{Colors.END}")
        sys.exit(0)
