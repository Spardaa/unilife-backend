"""
Prompt Service - Load and manage AI prompts from external files
支持模板变量替换功能
"""
from pathlib import Path
from typing import Dict, Optional, Any
from app.config import settings
import json


class PromptService:
    """Service for loading prompts from text files with template variable support"""

    def __init__(self):
        # Get the prompts directory (relative to project root)
        # __file__ is app/services/prompt.py, go up 3 levels to reach project root
        self.prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        self._cache: Dict[str, str] = {}

    def load_prompt(self, prompt_name: str, use_cache: bool = True) -> str:
        """
        Load a prompt from a text file

        Args:
            prompt_name: Name of the prompt file (without .txt extension)
            use_cache: Whether to use cached prompt if available

        Returns:
            Prompt content as string
        """
        # Check cache first
        if use_cache and prompt_name in self._cache:
            return self._cache[prompt_name]

        # Load from file
        prompt_file = self.prompts_dir / f"{prompt_name}.txt"

        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Cache the prompt
        if use_cache:
            self._cache[prompt_name] = content

        return content

    def render_template(
        self,
        template_name: str,
        **variables
    ) -> str:
        """
        渲染模板，替换变量占位符

        支持两种占位符格式：
        - {variable_name}: 简单变量替换
        - {{variable_name}}: 安全转义（替换为 {variable_name}）

        Args:
            template_name: 模板文件名（不带 .txt 扩展名）
            **variables: 模板变量键值对

        Returns:
            渲染后的提示词内容

        Example:
            >>> prompt_service.render_template(
            ...     "jarvis_system",
            ...     current_time="2026-01-21 15:00:00",
            ...     user_name="Alice"
            ... )
        """
        content = self.load_prompt(template_name)

        # 处理特殊变量（JSON 格式化）
        for key, value in variables.items():
            placeholder = f"{{{key}}}"

            if key.endswith("_json") or isinstance(value, (dict, list)):
                # JSON 格式化
                json_value = json.dumps(value, ensure_ascii=False, indent=2)
                content = content.replace(placeholder, json_value)
            elif isinstance(value, (int, float, bool)) or value is None:
                # 基本类型直接转换
                content = content.replace(placeholder, str(value))
            else:
                # 字符串类型
                content = content.replace(placeholder, str(value))

        return content

    def render_with_profile(
        self,
        template_name: str,
        user_profile: Optional[Dict[str, Any]] = None,
        user_decision_profile: Optional[Dict[str, Any]] = None,
        **extra_variables
    ) -> str:
        """
        使用用户画像渲染模板

        常用变量：
        - {user_profile}: 用户人格画像（JSON）
        - {user_decision}: 用户决策偏好（JSON）
        - {current_time}: 当前时间
        - {personality}: 人格摘要（文本）
        - {emotional_state}: 情绪状态
        - {stress_level}: 压力水平

        Args:
            template_name: 模板文件名
            user_profile: 用户人格画像
            user_decision_profile: 用户决策偏好
            **extra_variables: 额外变量

        Returns:
            渲染后的提示词
        """
        variables = {}

        # 添加用户画像相关变量
        if user_profile:
            variables["user_profile"] = user_profile
            variables["personality"] = self._extract_personality_summary(user_profile)
            variables["emotional_state"] = self._extract_emotional_state(user_profile)
            variables["stress_level"] = self._extract_stress_level(user_profile)

        # 添加决策偏好
        if user_decision_profile:
            variables["user_decision"] = user_decision_profile
            variables["decision_rules"] = self._extract_decision_rules(user_decision_profile)

        # 添加时间
        from datetime import datetime
        variables["current_time"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # 添加额外变量
        variables.update(extra_variables)

        return self.render_template(template_name, **variables)

    def _extract_personality_summary(self, profile: Dict[str, Any]) -> str:
        """从画像中提取人格摘要"""
        if not profile:
            return "未知"

        parts = []

        preferences = profile.get("preferences", {})
        social = preferences.get("social_preference", "")
        if social:
            social_map = {
                "introverted": "偏内向",
                "extroverted": "偏外向",
                "balanced": "社交平衡"
            }
            parts.append(f"社交倾向：{social_map.get(social, social)}")

        work_style = preferences.get("work_style", "")
        if work_style:
            parts.append(f"工作风格：{work_style}")

        return "、".join(parts) if parts else "灵活"

    def _extract_emotional_state(self, profile: Dict[str, Any]) -> str:
        """从画像中提取情绪状态"""
        # 这可以从最近的事件或日记中推断
        # 简化实现，返回默认值
        return "平静"

    def _extract_stress_level(self, profile: Dict[str, Any]) -> str:
        """从画像中提取压力水平"""
        # 这可以从最近的事件密度和能量消耗推断
        # 简化实现，返回默认值
        return "中等"

    def _extract_decision_rules(self, decision_profile: Dict[str, Any]) -> str:
        """从决策偏好中提取规则"""
        if not decision_profile:
            return "无特殊规则"

        rules = decision_profile.get("explicit_rules", [])
        if rules:
            return "\n".join(f"- {rule}" for rule in rules)

        # 从其他配置生成规则
        parts = []

        conflict = decision_profile.get("conflict_resolution", {})
        strategy = conflict.get("strategy", "")
        if strategy:
            strategy_map = {
                "ask": "遇到冲突时询问用户",
                "prioritize_urgent": "冲突时优先处理紧急事项",
                "prioritize_important": "冲突时优先处理重要事项",
                "merge": "冲突时尝试合并事项"
            }
            parts.append(strategy_map.get(strategy, strategy))

        return "\n".join(parts) if parts else "遵循默认规则"

    def reload_prompt(self, prompt_name: str) -> str:
        """
        Reload a prompt from file (bypass cache)

        Args:
            prompt_name: Name of the prompt file

        Returns:
            Prompt content as string
        """
        return self.load_prompt(prompt_name, use_cache=False)

    def clear_cache(self, prompt_name: Optional[str] = None):
        """
        Clear prompt cache

        Args:
            prompt_name: Specific prompt to clear, or None to clear all
        """
        if prompt_name:
            self._cache.pop(prompt_name, None)
        else:
            self._cache.clear()

    def get_prompt(self, prompt_name: str) -> str:
        """
        Get a prompt (alias for load_prompt)

        Args:
            prompt_name: Name of the prompt file

        Returns:
            Prompt content as string
        """
        return self.load_prompt(prompt_name)

    def list_prompts(self) -> list:
        """List all available prompt files"""
        if not self.prompts_dir.exists():
            return []

        return [f.stem for f in self.prompts_dir.glob("*.txt")]


# Global prompt service instance
prompt_service = PromptService()
