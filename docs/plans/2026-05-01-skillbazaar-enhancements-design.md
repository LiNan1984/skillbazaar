# SkillBazaar Enhancements Design

**Date:** 2026-05-01
**Status:** Approved
**Architecture:** Single-service (FastAPI monolith)

## Overview

Four major enhancements to SkillBazaar:

1. **LangGraph Autonomous Shopping Agent** - Replace simple LLM call with multi-round planning agent
2. **Layered Encryption Engine (SkillVault)** - Protect uploaded skills with type-specific encryption
3. **User Upload/Sell System** - Enable users to upload, price, and sell skills/agents
4. **Chat Markdown Rendering** - Frontend renders rich markdown in chat responses

## Architecture Decision: No Sandbox for Customers

Per team discussion with Lu Zhipeng:
- Sandbox (DeerFlow/Cube) is only for **internal development and testing**
- Customer-facing skills use **high-code + SDK protocol** approach
- Prompt-based skills use server-side execution (buyer never sees source)
- Code skills use encrypted packages + license verification
- No automatic sandbox provisioning for external users

## Part 1: LangGraph Shopping Agent

### State Graph

```
UserMessage → IntentUnderstanding → ParameterExtraction → ProductSearch
→ ResultAnalysis → [loop back if poor results] → ReplyGeneration
```

### AgentState

```python
class AgentState(TypedDict):
    messages: list[dict]
    intent: str              # search/chat/followup/buy
    search_params: dict
    search_results: list
    iteration: int           # max 3 auto-corrections
    final_reply: str
```

### Nodes

1. **IntentUnderstanding** - GLM-5.1 classifies intent (search/chat/followup/buy)
2. **ParameterExtraction** - Extract category/keyword/price/sort with conversation context
3. **ProductSearch** - Call product_service.get_products()
4. **ResultAnalysis** - LLM evaluates result quality, decides to recommend or refine
5. **ReplyGeneration** - Generate Markdown reply with product cards, prices, ratings

### Key Features

- Max 3 auto-correction iterations (too few results → relax conditions)
- Context-aware: "the cheap one" → append previous category
- Markdown output: price highlights, product cards, rating stars
- Purchase guidance: "Want to try this 29 coin one?" with buy link

### LLM Configuration

- Model: GLM-5.1-FP8 via api.finmall.com
- Max tokens: 2048 (increased for richer responses)
- History: last 10 messages for context
- Temperature: 0.7 for natural conversation

## Part 2: Layered Encryption Engine (SkillVault)

### 2.1 Prompt Skills (Server-Side Execution)

- Upload: SKILL.md → AES-256-GCM encrypt → store encrypted_blob + metadata
- Key management: server master_key + per-skill salt (stored in env/config)
- Execution: buyer calls API → verify license → decrypt → inject into LLM system prompt → return result
- Buyer only sees output, never the original prompt

### 2.2 Code Skills (Encrypted Package + License)

- Upload: .zip/.py → generate skill_id + encryption_key → AES-256 encrypt → store encrypted_package
- Metadata: SKILL.meta (unencrypted, contains API description, parameters)
- Purchase: generate License (user_id + skill_id + expiry + optional hardware fingerprint)
- Delivery: encrypted package + license token
- Execution: local SDK → verify license with platform → get decryption key (per-session) → decrypt in memory only

### 2.3 SDK Skills (Protocol Control)

- User deploys their own code, registers endpoint with platform
- Platform handles: permission verification, billing (per-call virtual coins), usage analytics
- No code hosting by platform

### 2.4 Encryption Details

- Algorithm: AES-256-GCM (authenticated encryption, tamper-proof)
- Key derivation: PBKDF2 with per-skill salt, 100k iterations
- Key storage: server-side only, never exposed to buyers
- Content hash: SHA-256 of original content for integrity verification

## Part 3: Database Schema Additions

```sql
-- Skill assets (encrypted storage)
CREATE TABLE skill_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    skill_type TEXT NOT NULL,           -- 'prompt'/'code'/'sdk'
    encrypted_blob BLOB NOT NULL,       -- AES-256 encrypted content
    encryption_iv TEXT NOT NULL,        -- initialization vector (hex)
    encryption_salt TEXT NOT NULL,      -- salt (hex)
    skill_meta TEXT,                    -- JSON: API desc, params, version
    content_hash TEXT NOT NULL,         -- SHA-256 of original content
    file_size INTEGER,                  -- original file size in bytes
    version TEXT DEFAULT '1.0.0',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Licenses
CREATE TABLE licenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    license_type TEXT NOT NULL,         -- 'permanent'/'trial'/'subscription'
    license_token TEXT UNIQUE NOT NULL, -- UUID token
    expires_at TEXT,                    -- null = never expires
    max_calls INTEGER,                 -- null = unlimited
    calls_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',       -- 'active'/'revoked'/'expired'
    created_at TEXT DEFAULT (datetime('now'))
);

-- Execution log
CREATE TABLE skill_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_id INTEGER REFERENCES licenses(id),
    user_id TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    execution_type TEXT NOT NULL,       -- 'api_call'/'sdk_call'
    input_params TEXT,                  -- JSON
    output_summary TEXT,               -- summary only, no full output
    duration_ms INTEGER,
    status TEXT,                        -- 'success'/'failed'/'timeout'
    created_at TEXT DEFAULT (datetime('now'))
);
```

## Part 4: Upload/Sell Flow

### Upload Page (Frontend)

1. Select type: Prompt Skill / Code Package / SDK Endpoint
2. Fill info: name, description, category, price, tags
3. Upload content:
   - Prompt: SKILL.md editor or file upload
   - Code: .zip/.py/.js package upload
   - SDK: API endpoint URL + interface docs
4. Preview & pricing:
   - Set trial count (e.g., 3 free uses)
   - Pricing: one-time purchase / per-call billing
5. Publish → backend encrypts → goes live

### Revenue Model

- Seller earns 90% of virtual coins, platform takes 10%
- Revenue tracked in transactions table
- Seller dashboard in "My Library" page

### API Endpoints (New)

```
POST /api/skills/upload          # Upload skill (multipart/form-data)
GET  /api/skills/{id}/execute    # Execute skill (prompt type)
POST /api/skills/{id}/license    # Generate/purchase license
GET  /api/licenses/{token}/verify # Verify license validity
POST /api/skills/{id}/call       # SDK skill call (proxy)
GET  /api/skills/my              # Seller's uploaded skills
GET  /api/skills/{id}/stats      # Sales stats for seller
```

## Part 5: Chat Markdown Rendering

- Use react-markdown library for rich rendering in ChatPanel
- Support: tables, bold, inline code, links, headings
- Custom renderers for product cards (detected from structured data)
- Syntax highlighting for code blocks (optional)

## Dependencies

### Backend (Python)

```
langgraph >= 0.2.0
langchain-core >= 0.3.0
langchain-openai >= 0.2.0       # for OpenAI-compatible API
cryptography >= 43.0            # AES-256-GCM encryption
```

### Frontend (JS)

```
react-markdown >= 9.0           # Markdown rendering
remark-gfm >= 4.0              # GitHub Flavored Markdown
```

## File Structure (New/Modified)

```
backend/
├── services/
│   ├── chat_service.py         # REPLACE: LangGraph agent
│   ├── skill_vault.py          # NEW: Encryption engine
│   ├── license_service.py      # NEW: License management
│   └── execution_service.py    # NEW: Skill execution
├── routers/
│   ├── skills.py               # NEW: Skill upload/execute/license
│   └── licenses.py             # NEW: License verification
├── agents/
│   ├── __init__.py
│   ├── shopping_agent.py       # NEW: LangGraph shopping agent
│   ├── nodes.py                # NEW: Agent node functions
│   └── state.py                # NEW: Agent state definition
├── database.py                 # MODIFY: Add new tables
└── models.py                   # MODIFY: Add new models

frontend/
├── src/
│   ├── components/
│   │   ├── ChatPanel.jsx       # MODIFY: Markdown rendering
│   │   └── SkillUploader.jsx   # NEW: Upload form
│   ├── pages/
│   │   └── PublishPage.jsx     # MODIFY: Support skill upload
│   └── services/
│       └── api.js              # MODIFY: Add skill endpoints
```
