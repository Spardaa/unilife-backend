# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UniLife is an AI-powered life scheduling assistant backend using FastAPI and DeepSeek LLM. It implements a **1+1 agent orchestration system** (UnifiedAgent + Observer) with LLM + Tools architecture, featuring a sophisticated "dual-time architecture" for flexible event display with rigid data storage.

**Tech Stack**: FastAPI, SQLAlchemy 2.0 (SQLite/PostgreSQL), DeepSeek API, Pydantic v2, APScheduler, OpenAI-compatible Tools API

**Deployment**: Supports both traditional server (with background tasks) and serverless environments (Railway, Render, etc.)

**Humanization Features**: Per-user soul.md (personality), memory.md (diary), identity.md (AI identity) - see "User Data Files" section

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
python migrations/migrate_add_decision_profile.py    # Decision preferences
python migrations/migrate_add_event_date.py          # Event date field
python migrations/migrate_add_is_template.py         # Template/is_template flag
python migrations/migrate_add_completion_tracking.py # Completion tracking
```

### Testing
```bash
pytest                                    # Run all tests
pytest tests/test_tools_timezone.py       # Run specific test file
python test_observer.py                   # Test observer agent
python test_memory.py                     # Test memory service
```

### Interactive Client
```bash
python client.py                                # Terminal client for testing chat
python get_test_token.py [user_id]              # Generate test JWT token (30 days validity)
```

### Serverless Deployment
The backend includes serverless adapters for cloud functions:

**Files:**
- `serverless.py` - Mangum adapter for Tencent Cloud SCF / Alibaba Cloud FC / AWS Lambda
- `serverless_cron.py` - Cron handler for scheduled habit replenishment

**Configuration:**
- Set `SERVERLESS=True` in `.env` to disable background scheduler
- Mangum `lifespan="off"` to avoid conflicts with cloud function startup
- API Gateway base path: `/api/v1`

## Architecture Overview

### 1+1 Agent Orchestration (Current)

The system uses `AgentOrchestrator` in `app/agents/orchestrator.py` with a streamlined architecture:

```
User Message → Orchestrator
                    ↓
        ContextFilterAgent (选择性注入记忆)
                    ↓
            UnifiedAgent
        (意图 + 工具 + 回复)
                    ↓
            Response (sync)
                    ↓
            Observer (async)
        (写日记 + 灵魂演化)
```

**Why 1+1 instead of 4-layer**: LLM calls reduced from 3-4 to 1-2, response latency significantly improved.

**Agent Responsibilities**:

1. **UnifiedAgent** (`app/agents/unified_agent.py`): All-in-one agent
   - Combines Router/Executor/Persona capabilities in single LLM call
   - Direct tool execution with max 30 iterations
   - Generates humanized responses
   - Injects user profile + decision preferences + soul + memory

2. **ContextFilterAgent** (`app/agents/context_filter_agent.py`): Smart context injection
   - Selectively injects relevant memory content
   - Reduces token usage by 40-60%
   - Decides what context is needed before UnifiedAgent

3. **ObserverAgent** (`app/agents/observer.py`): Async profile learning
   - Triggered after conversation ends or periodically
   - Writes diary entries to `memory.md`
   - Evolves AI personality in `soul.md`
   - Updates `UserProfile` preferences

4. **ProactiveCheckAgent** (`app/agents/proactive_check.py`): Heartbeat-like proactive behavior
   - Checks for important upcoming events
   - Can trigger proactive notifications

### Design Philosophy: "Like a Human"

**Core Principle**: The AI should think like a human (processing lots of information internally) but speak concisely (only what's necessary).

```
Thinking Mode (Internal):  →  Output Mode (External):
- Process extensive info    →  Think a lot, speak key points
- Analyze context           →  Do more, speak less
- Predict options           →  Make user feel understood
```

**Decision Thresholds**:
- Create/Modify events: ≥ 70% confidence → auto-execute
- Delete events: ≥ 80% confidence → auto-execute
- Below threshold: Use reasonable defaults, don't ask

**Silent Learning**:
- AI correctly predicts → Record silently
- User corrects AI → Say "(已记住)"
- AI makes mistake → "已为你调整..."

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

Two separate profile models updated by ObserverAgent:

**UserProfile** (`app/models/user_profile.py`): Personality and emotional state
- Relationship status, identity (occupation/industry)
- Preferences (activity types, social style, work style)
- Habits (sleep schedule, work hours, exercise frequency)
- Personality traits (emotional state, communication style)

**UserDecisionProfile** (`app/models/user_decision_profile.py`): Decision preferences
- Time preferences (start of day, deep work window)
- Meeting preferences (stacking style, max back-to-back)
- Energy profile (peak hours, energy by day)
- Conflict resolution strategy
- Scenario-based preferences

### Conversation Persistence

Supports 15+ message exchanges with full context. Stores `tool_calls` and `tool` results for LLM continuity. See `app/models/conversation.py` and `app/services/conversation_service.py`.

**Critical**: Messages must include `tool_calls` and `tool` role messages for multi-step reasoning context.

### User Data Files (Per-User Personalization)

Each user has a dedicated directory at `data/users/{user_id}/` containing:

| File | Service | Purpose |
|------|---------|---------|
| `soul.md` | `soul_service.py` | AI personality, values, evolves over time |
| `memory.md` | `memory_service.py` | Diary entries, weekly summaries |
| `identity.md` | `identity_service.py` | AI name, emoji, creature, vibe |

**Access Pattern**:
```python
from app.services.soul_service import soul_service
from app.services.memory_service import memory_service
from app.services.identity_service import identity_service

soul = soul_service.get_soul(user_id)
memory = memory_service.get_memory(user_id)
identity = identity_service.get_identity(user_id)
```

**File Structure** (`memory.md`):
```markdown
# UniLife Memory

## UniLife 眼中的用户
(用户画像总结)

## Weekly Summary
(压缩的历史记忆)

## Recent Diary
### 2026-03-01 Saturday
今天和用户聊了很多关于……
```

## Tool Registration Pattern

All 26 tools are registered in `app/agents/tools.py` using:

```python
tool_registry.register(
    name="tool_name",
    description="...",  # Shown to LLM
    parameters={...},   # JSON Schema for OpenAI API
    func=tool_function
)
```

Tool categories:
- Event Management (6): create, query, update, delete, complete, check conflicts
- Routine Management (5): create template, get with routines, handle instance
- Time Management (1): parse_time
- Energy Management (4): evaluate consumption, analyze schedule, check energy
- User Preferences (3): analyze, record, provide suggestions
- Snapshots (2): create, restore

## Prompt Template System

**File**: `app/services/prompt.py`

Prompt files are in `prompts/agents/` directory:
- `unified.txt` - UnifiedAgent system prompt
- `observer.txt` - Observer behavior analysis
- `context_filter.txt` - Context filtering logic
- `boundaries.txt` - AI behavior boundaries
- `memory_consolidation.txt` - Memory consolidation prompts
- `notification_event.txt` / `notification_periodic.txt` - Notification prompts

**Examples** in `prompts/examples/`: time_parsing, routine, energy, edge_cases, event_management

**Available Variables**:
- `{current_time}`: Current datetime string
- `{user_profile}`: UserProfile JSON
- `{soul}`: User's soul.md content
- `{memory}`: Relevant memory content
- `{identity}`: AgentIdentity JSON

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
# LLM Configuration (REQUIRED)
DEEPSEEK_API_KEY=sk-***           # REQUIRED - LLM provider
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# Database
DB_TYPE=sqlite                    # or postgresql
SQLITE_PATH=unilife.db
POSTGRESQL_URL=postgresql+asyncpg://user:pass@host:5432/db  # for PostgreSQL

# Authentication
JWT_SECRET_KEY=dev_secret_123     # CHANGE in production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080          # 7 days

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=True

# Serverless Deployment (optional)
SERVERLESS=True                   # Set to disable background tasks in serverless env
```

Configuration is managed by `app/config.py` using `pydantic-settings`.

## Important Architecture Notes

1. **Migration Strategy**: Python scripts in `migrations/` (not Alembic) - run in version order
2. **LLM Provider**: DeepSeek API (OpenAI-compatible), supports full Tools API
3. **Retry Logic**: Exponential backoff with 3 retries, 10-min total timeout in `app/services/llm.py`
4. **Time Zone**: Uses `pytz` for timezone handling
5. **Database**: Async SQLAlchemy 2.0 with SQLite for dev, PostgreSQL for production
6. **Serverless Mode**: Set `SERVERLESS=True` to disable background task scheduler
7. **User Data Storage**: Per-user files in `data/users/{user_id}/` (soul.md, memory.md, identity.md)
8. **Agent Mode**: Uses 1+1 architecture (UnifiedAgent + Observer), not 4-layer

## API Structure

- **Main endpoint**: `POST /api/v1/chat` - Conversational interface
- **Authentication**: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- **Events**: CRUD operations, completion, conflict detection
- **Projects**: Project-based task organization
- **Notifications**: Push notification management
- **Users**: Profile management, AI identity configuration
- **Sync**: Cross-device data synchronization
- **Diaries**: Diary entry management

## Key Files Quick Reference

**Orchestration**:
- `app/agents/orchestrator.py` - Main coordinator (1+1 mode)
- `app/agents/base.py` - Base interfaces (ConversationContext, AgentResponse)

**Agent Implementations**:
- `app/agents/unified_agent.py` - Unified agent (replaces Router/Executor/Persona)
- `app/agents/context_filter_agent.py` - Smart context injection
- `app/agents/observer.py` - Profile learning + diary writing + soul evolution
- `app/agents/proactive_check.py` - Proactive notification checks
- `app/agents/notification_agent.py` - Notification generation

**Data Models**:
- `app/models/event.py` - Event model with dual-time
- `app/models/user_profile.py` - Simplified user preferences
- `app/models/identity.py` - AI identity (name, emoji, creature, vibe)
- `app/models/conversation.py` - Conversation persistence

**User Data Services** (per-user files):
- `app/services/soul_service.py` - soul.md management
- `app/services/memory_service.py` - memory.md (diary) management
- `app/services/identity_service.py` - identity.md management
- `app/services/user_data_service.py` - Base file operations

**Tools & Services**:
- `app/agents/tools.py` - Registered tools (30+)
- `app/services/llm.py` - LLM wrapper with retry
- `app/services/prompt.py` - Prompt template system
- `app/services/virtual_expansion.py` - Virtual event expansion for recurring events

**API**:
- `app/api/chat.py` - Main chat endpoint
- `app/api/events.py` - Events CRUD
- `app/api/users.py` - User management
- `app/api/auth.py` - Authentication (JWT)
- `app/api/devices.py` - Device management
- `app/api/notifications.py` - Notifications
- `app/api/habits.py` - Habit management
- `app/api/sync.py` - Data synchronization
- `app/main.py` - Application entry point

**Background Tasks**:
- `app/scheduler/background_tasks.py` - APScheduler wrapper

**Documentation**:
- `docs/Architecture.md` - Detailed architecture documentation (Chinese)
- `docs/AGENT_HUMANIZATION_ROADMAP.md` - Humanization improvement roadmap
- `docs/AGENT_UPGRADE_GUIDE.md` - Agent upgrade guide
- `DUAL_TIME_ARCHITECTURE.md` - Dual-time design specification
