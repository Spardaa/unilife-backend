"""
Prompt Service - Load and manage AI prompts from external files
"""
from pathlib import Path
from typing import Dict, Optional
from app.config import settings


class PromptService:
    """Service for loading prompts from text files"""

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
