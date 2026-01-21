"""
UniLife Terminal Client - 简易终端前端
用于测试和调试后端 API
"""
import requests
import json
import sys
from datetime import datetime
from typing import Optional

# Fix Windows terminal encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# API 配置
API_BASE_URL = "http://localhost:8000/api/v1"
USER_ID = "test_user_001"


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


def send_chat_message(message: str) -> Optional[dict]:
    """发送聊天消息到后端"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={
                "message": message,
                "user_id": USER_ID,
                "context": None  # Optional field, send null instead of empty dict
            },
            timeout=30
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


def get_chat_history() -> Optional[dict]:
    """获取对话历史"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/chat/history",
            params={"user_id": USER_ID, "limit": 50}
        )

        if response.status_code == 200:
            return response.json()
        else:
            print_message("error", f"获取历史失败: {response.status_code}")
            return None

    except Exception as e:
        print_message("error", f"发生错误: {str(e)}")
        return None


def clear_chat_history() -> bool:
    """清除对话历史"""
    try:
        response = requests.delete(
            f"{API_BASE_URL}/chat/history",
            params={"user_id": USER_ID}
        )

        if response.status_code == 200:
            return True
        else:
            print_message("error", f"清除历史失败: {response.status_code}")
            return False

    except Exception as e:
        print_message("error", f"发生错误: {str(e)}")
        return False


def get_all_events() -> Optional[dict]:
    """获取所有事件"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/events",
            params={"user_id": USER_ID}
        )

        if response.status_code == 200:
            return response.json()
        else:
            print_message("error", f"获取事件失败: {response.status_code}")
            return None

    except Exception as e:
        print_message("error", f"发生错误: {str(e)}")
        return None


def get_snapshots() -> Optional[dict]:
    """获取快照历史"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/snapshots",
            params={"user_id": USER_ID}
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
    """格式化显示事件列表"""
    events = events_data.get("events", [])

    if not events:
        print_message("system", "暂无事件")
        return

    print(f"\n{Colors.CYAN}━━━ 事件列表 ({len(events)}) ━━━{Colors.END}")

    for i, event in enumerate(events, 1):
        title = event.get("title", "Untitled")
        status = event.get("status", "UNKNOWN")
        start_time = event.get("start_time")
        end_time = event.get("end_time")

        # 格式化时间
        time_str = ""
        if start_time and end_time:
            start = datetime.fromisoformat(start_time).strftime("%m/%d %H:%M")
            end = datetime.fromisoformat(end_time).strftime("%H:%M")
            time_str = f"{start} - {end}"
        elif end_time:
            ddl = datetime.fromisoformat(end_time).strftime("%m/%d %H:%M")
            time_str = f"截止: {ddl}"

        # 状态图标
        status_icon = "✓" if status == "COMPLETED" else "○"

        print(f"{status_icon} {i}. {Colors.BOLD}{title}{Colors.END} ({time_str})")

    print()


def format_snapshots_display(snapshots_data: dict):
    """格式化显示快照列表"""
    snapshots = snapshots_data.get("snapshots", [])

    if not snapshots:
        print_message("system", "暂无快照历史")
        return

    print(f"\n{Colors.CYAN}━━━ 快照历史 ({len(snapshots)}) ━━━{Colors.END}")

    for i, snapshot in enumerate(snippets, 1):
        snapshot_id = snapshot.get("id", "")[:8]
        trigger = snapshot.get("trigger_message", "")
        created_at = snapshot.get("created_at", "")

        if created_at:
            time_str = datetime.fromisoformat(created_at).strftime("%H:%M:%S")
        else:
            time_str = "Unknown"

        print(f"{i}. [{snapshot_id}] {time_str} - {trigger}")

    print()


def main():
    """主函数"""
    print_banner()

    # 检查服务器连接
    print_message("system", "正在连接服务器...")
    if not check_server_health():
        print_message("error", "无法连接到服务器，请确保后端正在运行 (python -m app.main)")
        sys.exit(1)

    print_message("success", "已连接到服务器")

    # 主循环
    while True:
        try:
            # 获取用户输入
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
                history_data = get_chat_history()
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
                if clear_chat_history():
                    print_message("success", "对话历史已清除")
                continue

            elif user_input.lower() == "events":
                events_data = get_all_events()
                if events_data:
                    format_events_display(events_data)
                continue

            elif user_input.lower() == "snapshots":
                snapshots_data = get_snapshots()
                if snapshots_data:
                    format_snapshots_display(snapshots_data)
                continue

            elif user_input.lower() == "energy":
                # 使用聊天接口查询能量
                result = send_chat_message("我现在状态怎么样")
                if result:
                    print_message("assistant", result.get("reply", ""))
                continue

            # 发送聊天消息
            print_message("user", user_input)

            result = send_chat_message(user_input)

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

        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}使用 'quit' 或 'exit' 退出{Colors.END}")
        except EOFError:
            print(f"\n\n{Colors.YELLOW}再见！{Colors.END}")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}程序已退出{Colors.END}")
        sys.exit(0)
