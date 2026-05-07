-- Track where a message originated (user input, scheduled task, etc.)
ALTER TABLE messages ADD COLUMN source TEXT NOT NULL DEFAULT 'user';
CREATE INDEX IF NOT EXISTS idx_messages_agent_source ON messages(agent_id, source, created_at);

-- Retry tracking for agentic tasks
ALTER TABLE agentic_tasks ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0;

-- Rename statuses: active -> enabled, paused -> disabled
UPDATE agentic_tasks SET status = 'enabled' WHERE status = 'active';
UPDATE agentic_tasks SET status = 'disabled' WHERE status = 'paused';
