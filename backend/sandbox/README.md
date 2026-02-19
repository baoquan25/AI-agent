# Sandbox API — Port 8000

Handles code execution, file system operations, and terminal access inside Daytona sandboxes.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/run` | Execute code in sandbox |
| GET | `/fs/tree` | Get file tree |
| GET | `/fs/list` | List directory |
| GET | `/fs/file/content` | Read file |
| PUT | `/fs/file/content` | Write file |
| POST | `/fs/file` | Create file |
| POST | `/fs/folder` | Create folder |
| DELETE | `/fs/path` | Delete file/folder |
| POST | `/fs/rename` | Rename/move file |
| POST | `/fs/search` | Search files |
| POST | `/fs/init` | Initialize workspace |
| DELETE | `/fs/cleanup` | Cleanup workspace |
| WebSocket | `/terminal/pty` | PTY terminal session |

## Run

```bash
pip install -r backend/requirements.txt
cd backend/sandbox
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Environment Variables

Copy `.env` from the root backend folder or set:

```
DAYTONA_API_KEY=
DAYTONA_API_URL=
SNAPSHOT_NAME=sandbox-daytona
AUTO_STOP_INTERVAL=7200
LANGUAGE=python
FILE_CACHE_MAX_SIZE=1000
FILE_CACHE_TTL_SECONDS=300
```
