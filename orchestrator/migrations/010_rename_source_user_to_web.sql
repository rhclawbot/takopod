-- Rename source 'user' to 'web' for clarity (distinguishes web UI from slack, etc.)
UPDATE messages SET source = 'web' WHERE source = 'user';
