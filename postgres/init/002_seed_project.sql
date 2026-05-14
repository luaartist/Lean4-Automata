-- Seed the default project so the watcher can index files immediately.
-- watch_root inside the container is /lean-src (mapped via docker-compose.override.yml).
INSERT INTO projects (id, name, root_path, lean_version)
VALUES (1, 'torchlean4physics', '/lean-src', '4.x')
ON CONFLICT DO NOTHING;
