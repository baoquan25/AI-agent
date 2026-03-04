# So sánh Daytona Sandbox vs VS Code (Backend cho Remote IDE)

Phạm vi so sánh: **phần backend** mà một IDE (VS Code, OpenVS Code, Theia) cần để làm việc với workspace từ xa: file system, file events, terminal, cache. **Không** so sánh UI, extension host, hay toàn bộ sản phẩm VS Code.

---

## 1. Tổng quan điểm (ước lượng)

| Phạm vi so sánh | Độ giống (ước lượng) | Ghi chú |
|-----------------|----------------------|--------|
| **Backend cho Remote IDE** (file + terminal + events + cache) | **~88%** | Cơ chế đã bám sát VS Code; thiếu LSP/DAP trong repo này |
| **Toàn bộ VS Code** (bao gồm UI, extensions, editor, debug, settings…) | **~15%** | Sandbox chỉ là một lớp backend, không có UI/workbench |

Phần dưới dùng **Backend cho Remote IDE** để chấm điểm chi tiết.

---

## 2. Chấm điểm theo từng khối (trọng số)

### 2.1 File System API & operations — **25%** trọng số → **95%**

| Tiêu chí | VS Code (remote) | Daytona Sandbox | Điểm |
|----------|------------------|-----------------|------|
| List / tree | FileSystemProvider.list / resolve (recursive) | GET /fs/list, GET /fs/tree (max_depth) | ✅ |
| Read file | Provider.readFile / stream | GET /fs/file/content (ETag, 304) | ✅ |
| Write file | Provider.writeFile | PUT /fs/file/content | ✅ |
| Create file/folder | createFile, createFolder | POST /fs/file, POST /fs/folder | ✅ |
| Delete | delete | DELETE /fs/path (recursive) | ✅ |
| Rename / move | rename, move | POST /fs/rename | ✅ |
| Search by name | — (extensions) | POST /fs/search | ✅ |
| Find in files | — (search service) | POST /fs/find | ✅ |
| Replace in files | — | POST /fs/replace | ✅ |
| Permissions | chmod (một số provider) | POST /fs/permissions | ✅ |
| Path validation | normalize, traversal guard | normalize_path, reject .. | ✅ |

**Kết luận**: API filesystem đủ và tương đương với những gì VS Code remote dùng. **95%**.

---

### 2.2 File change events (watch + push) — **25%** trọng số → **95%**

| Tiêu chí | VS Code | Daytona Sandbox | Điểm |
|----------|---------|-----------------|------|
| Nguồn event | inotify → ParcelWatcher / NodeJSWatcher | watchdog (inotify) | ✅ |
| Batching window | FILE_CHANGES_HANDLER_DELAY 75 ms | FILE_CHANGES_HANDLER_DELAY 75 ms | ✅ |
| Event coalescing | EventCoalescer (ADDED+DELETED→drop, …) | EventCoalescer port 1:1 | ✅ |
| Throttled delivery | ThrottledWorker 500/chunk, 200 ms, 30k cap | 500/chunk, 200 ms, 30k cap | ✅ |
| Transport | IPC (MessagePort) | WebSocket /fs/watch | ✅ (khác kênh, cùng mô hình push) |
| Event ngay sau API | onDidRunOperation + refresh view | _emit_change() sau write/create/delete/rename | ✅ |
| Watcher restart | MAX_RESTARTS=5, 800 ms | MAX_RESTARTS=5, RESTART_DELAY=0.8 s | ✅ |
| Child DELETE pruning | Có | Có (_is_parent) | ✅ |

**Kết luận**: Cơ chế event-driven và tham số giống VS Code. **95%**.

---

### 2.3 Terminal / PTY — **15%** trọng số → **90%**

| Tiêu chí | VS Code | Daytona Sandbox | Điểm |
|----------|---------|-----------------|------|
| PTY trong sandbox | createPtySession (remote) | sandbox.process.create_pty_session | ✅ |
| Kênh I/O | WebSocket / IPC | WebSocket /terminal/pty | ✅ |
| Resize | pty.resize(cols, rows) | JSON { type: "resize", cols, rows } | ✅ |
| SIGINT (Ctrl+C) | sendInput("\x03") | JSON { type: "ctrl+c" } → \x03 | ✅ |
| Binary vs text | Có xử lý | Gửi text; binary có thể mở rộng | ~ |

**Kết luận**: PTY + WebSocket đúng mô hình, thiếu nhỏ (binary, một số tùy chọn). **90%**.

---

### 2.4 Caching & conflict handling — **15%** trọng số → **88%**

| Tiêu chí | VS Code | Daytona Sandbox | Điểm |
|----------|---------|-----------------|------|
| ETag / 304 | Một số nơi dùng | GET /fs/file/content: ETag, If-None-Match → 304 | ✅ |
| Cache invalidation | Khi write/delete/rename | invalidate_by_path, invalidate_prefix, watcher | ✅ |
| Optimistic locking | Một số API | If-Match + base_mtime (conflict.py) | ✅ |
| 412 on conflict | Có | check_write_conflict → 412 | ✅ |
| LRU + TTL | — | FileCache max_size, ttl_seconds | ✅ |

**Kết luận**: Cache và conflict detection rất gần với cách VS Code làm. **88%**.

---

### 2.5 Code execution — **5%** trọng số → **70%**

| Tiêu chí | VS Code | Daytona Sandbox | Điểm |
|----------|---------|-----------------|------|
| Chạy code trong sandbox | Extension / task / debug | POST /run (Jupyter hoặc direct) | ✅ |
| Jupyter kernel | Extension | JupyterKernelExecutor trong sandbox | ✅ |
| Debug (DAP) | Debug Adapter Protocol | Không có trong repo sandbox | ❌ |

**Kết luận**: Có execute + Jupyter; không có DAP. **70%**.

---

### 2.6 Kiến trúc tổng thể — **15%** trọng số → **90%**

| Tiêu chí | VS Code | Daytona Sandbox | Điểm |
|----------|---------|-----------------|------|
| Event-driven, không polling | onDidFilesChange, onDidRunOperation | WS /fs/watch + _emit_change() | ✅ |
| Watcher → coalesce → push | Có | Có (watchdog → EventCoalescer → WS) | ✅ |
| API mutation fire event ngay | onDidRunOperation | _emit_change() ngay sau mutation | ✅ |
| Per-user / per-workspace | Session, workspace folders | user_id, sandbox per user | ✅ |

**Kết luận**: Kiến trúc backend event-driven bám sát VS Code. **90%**.

---

## 3. Tính điểm tổng (Backend Remote IDE)

| Khối | Trọng số | Điểm | Đóng góp |
|------|----------|------|----------|
| File System API | 25% | 95% | 23.75 |
| File change events | 25% | 95% | 23.75 |
| Terminal / PTY | 15% | 90% | 13.50 |
| Caching & conflict | 15% | 88% | 13.20 |
| Code execution | 5% | 70% | 3.50 |
| Kiến trúc | 15% | 90% | 13.50 |
| **Tổng** | **100%** | | **91.2%** |

Làm tròn: **~91%** so với **backend** mà VS Code remote dùng (file + terminal + events + cache).

---

## 4. Những phần VS Code có mà Daytona Sandbox (repo này) chưa có

- **LSP (Language Server Protocol)**  
  VS Code: extension host + LSP client; server chạy trong/ngoài process.  
  Daytona: docs nói hỗ trợ LSP; trong repo sandbox này không thấy LSP server hay kênh LSP — thường do service khác đảm nhiệm.

- **DAP (Debug Adapter Protocol)**  
  VS Code: debug extension + DAP.  
  Daytona sandbox: không có DAP trong repo.

- **Extension Host / Extensions**  
  VS Code: cả một lớp extension.  
  Daytona: không nằm trong phạm vi sandbox API.

- **UI (workbench, editor, tree view)**  
  VS Code: toàn bộ UI.  
  Daytona: chỉ backend API; UI là ứng dụng gọi API (IDE riêng).

- **Settings, keybindings, workspace trust**  
  Thuộc workbench/process chính VS Code, không so với sandbox.

---

## 5. Kết luận ngắn

- So với **phần backend cho remote IDE** (file, terminal, file events, cache, kiến trúc event-driven):  
  **Daytona Sandbox ~91%** — đã rất sát cơ chế VS Code, không dựa vào polling.

- So với **toàn bộ VS Code** (UI + extensions + editor + debug + settings + …):  
  Sandbox chỉ là một lớp nhỏ → **~15%** nếu đếm theo “số tính năng / khối” của cả sản phẩm.

- Nếu mục tiêu là **“backend để IDE kết nối vào giống cách OpenVS Code/Theia kết nối”**:  
  Dự án của bạn đã đạt **khoảng 9/10**; phần còn thiếu chủ yếu là LSP/DAP (có thể nằm ở service khác) và vài chi tiết nhỏ (binary terminal, v.v.).
