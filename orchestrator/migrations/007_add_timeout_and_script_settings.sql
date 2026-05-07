-- Global default timeout settings
INSERT OR IGNORE INTO settings (key, value) VALUES ('idle_timeout_seconds', '300');
INSERT OR IGNORE INTO settings (key, value) VALUES ('inflight_hard_timeout', '600');

-- Per-agent timeout overrides (same pattern as container_memory/container_cpus)
ALTER TABLE agents ADD COLUMN idle_timeout_seconds INTEGER NOT NULL DEFAULT 300;
ALTER TABLE agents ADD COLUMN inflight_hard_timeout INTEGER NOT NULL DEFAULT 600;

-- Script tasks support
ALTER TABLE agentic_tasks ADD COLUMN script TEXT;
ALTER TABLE agentic_tasks ADD COLUMN source_skill_id TEXT;
