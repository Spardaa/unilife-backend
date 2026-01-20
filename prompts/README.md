# Prompts Directory

This directory contains all AI prompts used by UniLife agents.

## File Structure

```
prompts/
├── router_agent.txt           # RouterAgent intent classification prompt
├── router_agent_function.txt   # Simplified RouterAgent prompt
├── scheduler_parse_event.txt   # ScheduleAgent event parsing prompt
├── jarvis_persona.txt          # Jarvis personality and behavior
└── README.md                    # This file
```

## Prompt Files

### 1. router_agent.txt
**Usage**: RouterAgent class - Intent classification
**Purpose**: Defines how the RouterAgent should classify user intents and map them to appropriate actions.

### 2. scheduler_parse_event.txt
**Usage**: ScheduleAgent class - Event parsing
**Purpose**: Instructions for extracting event information from natural language messages.

### 3. jarvis_persona.txt
**Usage**: Chat API - Conversation handling
**Purpose**: Defines Jarvis's personality, speaking style, and behavior patterns.

## How to Edit Prompts

1. **Directly edit the `.txt` file** in this directory
2. **Reload the prompt** (if server is running):
   - Either restart the server, or
   - The prompt will be automatically reloaded on next request (due to caching)

## Prompt Caching

Prompts are cached in memory after first load for better performance:
- **First load**: Read from file
- **Subsequent loads**: Use cached version

To clear the cache and reload a prompt, see the `PromptService` class in `app/services/prompt.py`.

## Best Practices

1. **Keep prompts focused**: Each prompt should have a single, clear purpose
2. **Use clear examples**: Include examples in prompts to guide AI behavior
3. **Specify output format**: Clearly define the expected response format (JSON, text, etc.)
4. **Add constraints**: Specify what the model should NOT do
5. **Version control**: All prompt changes are tracked in Git

## Adding New Prompts

1. Create a new `.txt` file in this directory
2. Load it in your code:
   ```python
   from app.services.prompt import prompt_service

   prompt = prompt_service.load_prompt("your_prompt_name")
   ```
3. Use the prompt in your LLM calls

## Examples

### Loading a prompt
```python
from app.services.prompt import prompt_service

# Load the router agent prompt
system_prompt = prompt_service.load_prompt("router_agent")

# Use it in LLM call
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_message}
]
```

### Reloading a prompt (bypass cache)
```python
# Force reload from file
prompt = prompt_service.reload_prompt("router_agent")
```

### Listing all available prompts
```python
all_prompts = prompt_service.list_prompts()
print(f"Available prompts: {all_prompts}")
```
