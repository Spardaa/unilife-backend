# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UniLife is an AI-powered life scheduling assistant backend using FastAPI and DeepSeek LLM. It implements a **4-layer multi-agent orchestration system** with LLM + Tools architecture (similar to Cursor Agent), featuring a sophisticated "dual-time architecture" for flexible event display with rigid data storage.

**Tech Stack**: FastAPI, SQLAlchemy 2.0 (SQLite/PostgreSQL), DeepSeek API, Pydantic v2, APScheduler, OpenAI-compatible Tools API

**Deployment**: Supports both traditional server (with background tasks) and serverless environments (Railway, Render, etc.)

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
pytest                                           # Run all tests
pytest test_dual_time_architecture.py           # Run specific test
pytest test_conversation.py                     # Conversation persistence
pytest test_time_parser.py                      # Time parsing tests
pytest test_integration_dual_time.py            # Integration tests
pytest test_scenarios_dual_time.py              # Scenario-based tests
```

### Interactive Client
```bash
python client.py                                # Terminal client for testing chat
```

## Architecture Overview

### 4-Layer Agent Orchestration

The system uses `AgentOrchestrator` in `app/agents/orchestrator.py` to coordinate four specialized agents:

```
User Message → Orchestrator
                    ↓
        ┌───────────┼───────────┐
        ↓           ↓           ↓
    Router     Executor     Persona
   (intent)    (tools)     (empathy)
        │           │           │
        └───────────┼───────────┘
                    ↓
            Response (sync)
                    ↓
            Observer (async)
                    ↓
        Update User Profiles
```

**Agent Responsibilities**:

1. **RouterAgent** (`app/agents/router.py`): Intent classification and routing
   - Outputs routing decision: `EXECUTOR` / `PERSONA` / `BOTH`
   - Context filtering to reduce token usage by 40-60%

2. **ExecutorAgent** (`app/agents/executor.py`): Rational tool execution
   - No emotion, pure logic
   - Injects user decision preferences (from `UserDecisionProfile`)
   - Has access to 26 tools for database operations
   - Max 30 iterations for multi-step reasoning

3. **PersonaAgent** (`app/agents/persona.py`): Human-like response generation
   - Warm, concise replies (1-3 sentences)
   - Injects user personality profile (from `UserProfile`)
   - No tool access, pure conversation

4. **ObserverAgent** (`app/agents/observer.py`): Async profile learning
   - Triggered after conversation ends or 8-15 messages
   - Updates both `UserProfile` (personality) and `UserDecisionProfile` (preferences)

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

Dynamic variable injection into agent prompts:

```python
# For ExecutorAgent - injects decision preferences
prompt_service.render_template(
    "agents/executor",
    user_decision=decision_profile_dict,
    current_time=now_str
)

# For PersonaAgent - injects personality
prompt_service.render_with_profile(
    "agents/persona",
    user_profile=profile_dict,
    current_time=now_str
)
```

**Available Variables**:
- `{current_time}`: Current datetime string
- `{user_profile}`: Full UserProfile JSON
- `{user_decision}`: Full UserDecisionProfile JSON
- `{personality}`: Personality summary
- `{emotional_state}`: Current emotional state
- `{stress_level}`: Current stress level

Prompt files are in `prompts/agents/` directory (router.txt, executor.txt, persona.txt, observer.txt).

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

1. **Migration Strategy**: Python scripts (not Alembic) for simplicity - run in version order
2. **LLM Provider**: DeepSeek API (OpenAI-compatible), supports full Tools API
3. **Retry Logic**: Exponential backoff with 3 retries, 10-min total timeout in `app/services/llm.py`
4. **Time Zone**: Uses `pytz` for timezone handling
5. **Database**: Async SQLAlchemy 2.0 with SQLite for dev, PostgreSQL for production
6. **Serverless Mode**: Set `SERVERLESS=True` to disable background task scheduler
7. **Habit Replenishment**: Background scheduler runs daily at 2 AM to maintain 20 pending habit instances per batch

## API Structure

- **Main endpoint**: `POST /api/v1/chat` - Conversational interface
- **Authentication**: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- **REST endpoints**: Events CRUD, Users, Snapshots, Statistics, Conversations, Diaries
- **Device Management**: Device registration and fingerprinting
- **Notifications**: Notification CRUD and delivery
- **Habits**: Habit template and instance management
- **Sync**: Cross-device data synchronization
- **WebSocket**: Not implemented (planned for real-time updates)

## Key Files Quick Reference

**Orchestration**:
- `app/agents/orchestrator.py` - Main coordinator
- `app/agents/base.py` - Base interfaces (Intent, RoutingDecision, ConversationContext, AgentResponse)

**Agent Implementations**:
- `app/agents/router.py` - Intent classification
- `app/agents/executor.py` - Tool execution
- `app/agents/persona.py` - Response generation
- `app/agents/observer.py` - Profile learning

**Data Models**:
- `app/models/event.py` - Event model with dual-time
- `app/models/routine.py` - Four-layer routine system
- `app/models/user_profile.py` - Personality profile
- `app/models/user_decision_profile.py` - Decision preferences
- `app/models/conversation.py` - Conversation persistence

**Tools & Services**:
- `app/agents/tools.py` - 26 registered tools
- `app/services/llm.py` - LLM wrapper with retry
- `app/services/prompt.py` - Prompt template system
- `app/services/conversation_service.py` - Conversation persistence
- `app/services/decision_profile_service.py` - Decision preferences

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
- `app/tasks/habit_replenishment.py` - Daily habit instance replenishment (2 AM)

**Documentation**:
- `docs/Architecture.md` - Detailed architecture documentation (Chinese)
- `DUAL_TIME_ARCHITECTURE.md` - Dual-time design specification
