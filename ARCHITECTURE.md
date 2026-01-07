# Obsidian Telegram Bot - Queue-Based Architecture

## Overview

This project uses a **two-bot architecture** to separate message reception (cloud) from processing (local):

```
┌─────────────┐
│   Email     │
│  (Zapier)   │
└──────┬──────┘
       │
       ▼
┌─────────────────┐          ┌──────────────────┐
│   Cloud Bot     │          │   PostgreSQL     │
│   (Railway)     │─────────▶│     Queue        │
│                 │  Write   │   (Railway)      │
│ - Receives msgs │          │                  │
│ - Minimal code  │          │ - Stores msgs    │
│ - Always on     │          │ - Preserves      │
└─────────────────┘          │   formatting     │
                             │ - Stores images  │
                             └────────┬─────────┘
                                      │
                                      │ Read
                                      ▼
                             ┌─────────────────┐
                             │  Processing Bot │
                             │    (Laptop)     │
                             │                 │
                             │ - Full pipeline │
                             │ - AI analysis   │
                             │ - OCR           │
                             │ - Obsidian      │
                             └────────┬────────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │ Obsidian Vault  │
                             │    (Local)      │
                             └─────────────────┘
```

## Components

### 1. Cloud Bot (`/cloud-bot`)

**Location:** Railway (cloud)
**Purpose:** Receive and queue messages
**Dependencies:** Minimal (Telegram Bot, PostgreSQL)

**Responsibilities:**
- ✅ Receive Telegram messages (text, photos, documents, voice)
- ✅ Store in PostgreSQL queue with all metadata
- ✅ Preserve formatting (bold, italic, links, mentions)
- ✅ Store photo file IDs and sizes
- ✅ Quick acknowledgment to user
- ❌ NO processing, AI, OCR, or Obsidian access

**Cost:** ~$5/month (Railway Starter)

### 2. Processing Bot (Root directory)

**Location:** Your laptop
**Purpose:** Process queued messages
**Dependencies:** Full (AI, OCR, Obsidian, etc.)

**Responsibilities:**
- ✅ Read pending messages from queue
- ✅ Download files if needed (photos, documents)
- ✅ Run OCR on images
- ✅ Fetch articles from URLs
- ✅ AI analysis (Claude/Ollama)
- ✅ Create Obsidian notes
- ✅ Update message status in queue

**Cost:** Free (runs locally)

### 3. PostgreSQL Queue (Railway)

**Schema:**
- `message_queue` table stores all messages
- Preserves Telegram entities (formatting)
- Stores file IDs for later download
- Tracks processing status

**Fields:**
- `text_content` - Message text
- `entities` - Formatting data (JSON)
- `photo_sizes` - Photo metadata (JSON)
- `file_id` - Telegram file reference
- `status` - `pending`, `processing`, `completed`, `failed`

## Workflow

### Receiving Messages

1. **User sends message** to Telegram bot
2. **Cloud bot receives** via polling
3. **Extracts all data:**
   - Text content
   - Formatting entities
   - File IDs (for photos/documents)
   - Metadata (timestamp, user, etc.)
4. **Inserts to PostgreSQL** queue
5. **Sends acknowledgment** "✓ Queued for processing"

### Processing Messages

1. **Local bot polls queue** (on-demand or scheduled)
2. **Fetches pending messages** from PostgreSQL
3. **Marks as processing**
4. **Downloads files** using Telegram file IDs
5. **Runs full pipeline:**
   - OCR for images
   - Article extraction for URLs
   - AI analysis
   - Obsidian note creation
6. **Updates status:**
   - `completed` on success
   - `failed` on error (with error message)

## Benefits

✅ **Cloud bot is lightweight** - minimal resources, cheap to run 24/7
✅ **Processing bot has Obsidian access** - runs on your laptop
✅ **Run processing on-demand** - when you want, or scheduled
✅ **Messages never lost** - persisted in database
✅ **Easy retry** - just query failed messages
✅ **Scalable** - cloud receives, local processes at own pace
✅ **Email forwarding** - Zapier → Telegram → Queue

## Email Forwarding Setup

**Zapier Flow:**
```
Email Inbox → Zapier Trigger → Telegram API → Cloud Bot → Queue
```

Configure Zapier to:
1. Trigger on new emails
2. Send email content to your Telegram bot
3. Bot queues for processing

## Current Status

✅ Cloud bot implemented (`/cloud-bot`)
✅ Database schema created
✅ Railway deployment ready
⏳ Processing bot needs modification to read from queue

## Next Steps

To complete the architecture:

1. **Deploy cloud bot to Railway:**
   ```bash
   cd cloud-bot
   railway login
   railway init
   railway up
   ```

2. **Add PostgreSQL to Railway project** (one click)

3. **Run database migration** (see `cloud-bot/migrations/001_initial_schema.sql`)

4. **Set environment variables** in Railway:
   - `TELEGRAM_BOT_TOKEN`
   - `ALLOWED_USERS`
   - `DATABASE_URL` (auto-set)

5. **Create `local_main.py`** to:
   - Connect to Railway PostgreSQL
   - Read pending messages
   - Process using existing pipeline
   - Update status

6. **Set up Zapier** for email forwarding (see `cloud-bot/README.md`)

## Files Structure

```
obsidian-telegram/
├── ARCHITECTURE.md         # This file
├── main.py                 # Original bot (now local processor)
├── config.yaml
├── requirements.txt
├── src/                    # Processing logic (AI, OCR, Obsidian)
│   ├── bot/
│   ├── processors/
│   ├── obsidian/
│   └── ai/
│
└── cloud-bot/              # New: Minimal receiver for Railway
    ├── README.md           # Deployment guide
    ├── main.py             # Message receiver
    ├── requirements.txt    # Minimal deps
    ├── pyproject.toml      # For uv
    ├── railway.json        # Railway config
    ├── Procfile
    ├── .env.example
    └── migrations/
        └── 001_initial_schema.sql
```

## Migration from Current Setup

**Before (monolithic):**
```
Telegram → Bot (local/cloud) → Process → Obsidian
```
- Bot must have Obsidian access
- Can't run 24/7 in cloud easily
- No email forwarding

**After (queue-based):**
```
Email/Telegram → Cloud Bot → Queue → Processing Bot → Obsidian
```
- Cloud bot always available
- Processing on local machine
- Email forwarding supported
- Messages never lost
