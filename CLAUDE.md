# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UniLife is an AI-powered life scheduling assistant backend using FastAPI and DeepSeek LLM. It implements a multi-agent system with LLM + Tools architecture (similar to Cursor Agent), featuring a sophisticated "dual-time architecture" for flexible event display with rigid data storage.

**Tech Stack**: FastAPI, SQLAlchemy (SQLite/PostgreSQL), DeepSeek API, Pydantic, OpenAI-compatible Tools API

## Common Development Commands

### Start Development Server
```bash
python -m app.main
# or
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: http://localhost:8000/docs

### Database Operations
```bash
# Initialize database with sample data
python init_db.py

# Run migrations in order when upgrading versions
python migrate_db.py                    # Base migration (6 new fields)
python migrate_routine.py               # Routine/habit system
python migrate_enhanced_features.py     # Energy evaluation + user profiles
python migrate_conversations.py         # Conversation persistence
```

### Testing
```bash
pytest                                   # Run all tests
pytest test_dual_time_architecture.py   # Run specific test
pytest test_enhanced_features.py
pytest test_routine.py
```

### Interactive Client
```bash
python client.py                        # Terminal client for testing chat
```

## Architecture Overview

### Design Philosophy: "Like a Human"

**Core Principle**: The AI should think like a human (processing lots of information internally) but speak concisely (only what's necessary).

```
┌─────────────────────────────────────────┐
│ Human-like Thinking Mode:                │
│  - Process extensive information         │
│  - Analyze context, retrieve habits      │
│  - Predict options, assess risks         │
│  - Do many things silently               │
├─────────────────────────────────────────┤
│ Human-like Output Mode:                  │
│  - Think a lot, speak key points         │
│  - Do more, speak less (high quality)    │
│  - Make user feel "he really gets me"    │
│  - Build trust and dependency            │
└─────────────────────────────────────────┘
```

**Key Differences from Traditional QA AI**:
- **Not** a question-answering bot → **Action-oriented** AI assistant
- **Not** explaining everything → **Silent learning**, occasional feedback
- **Not**反复追问 → **Default confirm mode**, execute with reasonable defaults
- **Not** long responses → **Concise replies**, essential info only

**Decision Thresholds**:
- Create/Modify events: ≥ 70% confidence → auto-execute
- Delete events: ≥ 80% confidence → auto-execute
- Below threshold: Use reasonable defaults, don't ask

**Silent Learning**:
- AI correctly predicts → Record silently, don't tell user
- AI estimates, user doesn't correct → Record silently
- AI estimates, user corrects → Say "(已记住)"
- AI makes mistake → Explain "I've adjusted for you..."

**Special Scenarios**:
- **Delete long-term habit**: Confirm if ≥ 30 days OR ≥ 80% completion rate
- **Fuzzy query**: Show all info, don't let user fall into 30% error
- **Batch operations**: Understand context, respond with brief human touch

See `prompts/jarvis_system.txt` for complete prompt specification.

### Multi-Agent System (LLM + Tools)

The core architecture follows Cursor Agent-style patterns:

- **JarvisAgent** (`app/agents/jarvis.py`): Main agent that orchestrates tool calls through OpenAI-compatible function calling
- **20 Tools** (`app/agents/tools.py`): Registered via `ToolRegistry`, exposed to LLM for database operations
- **Specialist Agents**: EnergyEvaluator, SmartScheduler, ContextExtractor, DurationEstimator

**Key Pattern**: The conversation loop in `JarvisAgent.chat()` (lines 66-122) supports multi-step reasoning with up to 30 iterations. Each iteration includes LLM decision, tool execution, and result feedback.

**Critical Implementation**: The `_build_messages()` method (lines 138-200) must preserve full conversation history including `tool_calls` and `tool` role messages for LLM context continuity.

### Dual-Time Architecture (Flexible Display, Rigid Computation)

"对外柔性，对内刚性" - Flexible display for users, rigid data for algorithms.

**Display Layer**: Shows `10:00 开会（约1小时，到11:00左右）` - user-friendly, reduces anxiety
**Data Layer**: Stores exact `start_time`, `end_time`, `duration` - supports conflict detection, energy evaluation

**Duration Source Tracking** (`app/models/event.py:136-161`):
- `user_exact`: User specified (confidence: 1.0)
- `ai_estimate`: AI estimated from historical data (confidence: 0.0-1.0)
- `default`: Fallback value (confidence: 0.5)
- `user_adjusted`: User modified AI's estimate (keeps `ai_original_estimate` for learning)

**Files**: `DUAL_TIME_ARCHITECTURE.md`, `app/models/event.py`, `app/agents/duration_estimator.py`

### Four-Layer Routine/Habit System

Sophisticated recurring event model in `app/models/routine.py`:
1. **Template Layer**: Rule definition (repeat rules, flexibility, makeup strategies)
2. **Instance Layer**: Concrete instances generated from templates
3. **Execution Layer**: Actual execution records (completed, cancelled, rescheduled, skipped)
4. **Memory Layer**: Learns user patterns for intelligent suggestions

### User Profile Learning (Observation-Based)

`ContextExtractorAgent` learns user profiles by observation, not questioning:
- **Relationship**: single/dating/married/complicated
- **Identity**: occupation/industry/position
- **Preference**: activity types/social style/work style
- **Habit**: sleep schedule/work hours/exercise frequency

Files: `app/models/user_profile.py`, `app/agents/context_extractor.py`, `app/services/profile_service.py`

### Conversation Persistence

Supports 15+ message exchanges with full context. Stores `tool_calls` and `tool` results for LLM continuity. See `app/models/conversation.py` and `app/services/conversation_service.py`.

## Tool Registration Pattern

All 20 tools are registered in `app/agents/tools.py` using:

```python
tool_registry.register(
    name="tool_name",
    description="...",
    parameters={...},  # JSON Schema for OpenAI API
    func=tool_function
)
```

Tool categories: Event Management (6), Energy Management (4), Snapshots (2), User Preferences (2), Suggestions (1), Routines (5)

## Smart Time Parsing

`TimeParser` class (`app/services/time_parser.py`) handles:
- Exact times: "明天下午3点", "15:30"
- Relative dates: "今天", "明天", "后天", "大后天"
- Weekdays: "下周三", "本周五"
- Fuzzy times: "傍晚", "上午晚些时候"
- Time ranges: "本周三到周五"

## Energy Evaluation System

Dual-dimensional assessment (Physical + Mental), each with:
- Level: Low/Medium/High
- Score: 0-10 scale
- Description + influencing factors

See `app/agents/energy_evaluator.py`, `app/agents/smart_scheduler.py`

## Environment Configuration

Required `.env` variables:
```bash
DEEPSEEK_API_KEY=sk-***           # REQUIRED - LLM provider
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DB_TYPE=sqlite                    # or postgresql
SQLITE_PATH=unilife.db
JWT_SECRET_KEY=dev_secret_123     # CHANGE in production
```

## Important Architecture Notes

1. **Migration Strategy**: Python scripts (not Alembic) for simplicity - run in version order
2. **LLM Provider**: DeepSeek API (OpenAI-compatible), supports full Tools API
3. **Retry Logic**: Exponential backoff with 3 retries, 10-min total timeout in `app/services/llm.py`
4. **Time Zone**: Uses `pytz` for timezone handling
5. **Database**: Async SQLAlchemy 2.0 with SQLite for dev, PostgreSQL for production

## API Structure

- **Main endpoint**: `POST /api/v1/chat` - Conversational interface
- **REST endpoints**: Events CRUD, Users, Snapshots, Statistics
- **WebSocket**: Not implemented (planned for real-time updates)
