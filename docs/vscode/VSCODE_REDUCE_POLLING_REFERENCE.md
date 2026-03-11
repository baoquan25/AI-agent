# Tài liệu tham chiếu VS Code: Cách giảm / loại bỏ polling

Tài liệu này tổng hợp từ **mã nguồn VS Code** (`/home/ducminh/vscode`) — cách VS Code tránh polling và chỉ dùng polling khi bắt buộc (ví dụ WSL1).

---

## 1. Nguyên tắc chung: Event-driven, không poll

VS Code **không** dùng polling để theo dõi thay đổi file trong trường hợp thông thường. Thay vào đó:

- **File tree / list**: Cập nhật qua **sự kiện từ watcher** (`onDidChangeFile`), không gọi lại API tree/list theo chu kỳ.
- **Nội dung file**: Đọc khi mở / khi lưu; dùng **ETag / conditional request** khi cần re-read; không định kỳ gọi "get content" để kiểm tra thay đổi.
- **Terminal**: Output qua **stream (PTY / WebSocket)**, không có endpoint "get output" gọi định kỳ.

---

## 2. File watcher: Native events, không poll (trừ WSL1)

### 2.1 Backend mặc định: native, không polling

- **Recursive watcher**: Dùng **@parcel/watcher** với backend:
  - Linux: `inotify`
  - macOS: `fs-events`
  - Windows: `windows`
- **Non-recursive**: Node.js `fs.watch` (hoặc tương đương).
- Luồng: native event → **batch 75ms** → **coalesce** → **throttle** → emit cho client. **Không** có vòng lặp setInterval/setTimeout để quét file.

**Tham chiếu mã:**

- `src/vs/platform/files/node/watcher/parcel/parcelWatcher.ts`: `parcelWatcher.subscribe()` — nhận event từ Parcel, không poll.
- `src/vs/platform/files/common/watcher.ts`: `IRecursiveWatchRequest.pollingInterval` — **chỉ** dùng khi bật polling (xem 2.2).

### 2.2 Khi nào VS Code dùng polling?

Polling **chỉ** được dùng trong trường hợp đặc biệt (ví dụ **WSL1**), và được đánh dấu **@deprecated** trong code:

- **Chỗ cấu hình**: `diskFileSystemProvider.ts` — `options?.watcher?.recursive?.usePolling` và `pollingInterval`.
- **Chỗ thực thi**: `parcelWatcher.ts` — `startPolling()` chỉ chạy khi `request.pollingInterval` được set.
- **Mặc định**: `usePolling === true` → `pollingInterval = 5000` ms (5 giây).

**Cách “giảm polling” trong VS Code:**

- **Tắt hẳn**: Không set `usePolling` (hoặc set `false`) → không có polling, chỉ dùng native watcher.
- **Nếu bắt buộc phải poll** (vd. WSL1): Tăng `pollingInterval` (vd. 5000 → 10000) để giảm tần suất poll; đồng thời thu hẹp `usePolling` thành mảng đường dẫn thay vì `true` để chỉ poll những path cần thiết.

**Tham chiếu:**

- `src/vs/platform/files/common/diskFileSystemProvider.ts` (khoảng dòng 116–123).
- `src/vs/platform/files/common/watcher.ts`: interface `IRecursiveWatcherOptions` — `usePolling`, `pollingInterval` (deprecated).
- `src/vs/platform/files/node/watcher/parcel/parcelWatcher.ts`: `startPolling()`, `FILE_CHANGES_HANDLER_DELAY = 75`.

---

## 3. Coalescing (gộp event) — giảm spam và “ảo giác” cần poll

Để tránh client phải xử lý quá nhiều event trùng lặp hoặc nối tiếp nhanh (và tránh cảm giác “phải poll để có state đúng”), VS Code **coalesce** event trước khi emit:

- **ADDED + DELETED** (cùng path, trong cùng đợt): **bỏ** (coalescer xóa event).
- **DELETED + ADDED** (cùng path): gộp thành **UPDATED**.
- **ADDED + UPDATED**: giữ **ADDED**.
- **DELETE của con**: nếu cha đã bị DELETE thì bỏ DELETE của con (prune).

**Tham chiếu:** `src/vs/platform/files/common/watcher.ts` — class `EventCoalescer`, hàm `coalesceEvents()`.

---

## 4. Throttling (giới hạn tốc độ emit) — tránh quá tải

Sau coalesce, event được đưa qua **ThrottledWorker** để không emit ồ ạt:

- **Parcel (recursive):**
  - `maxWorkChunkSize: 500` — tối đa 500 thay đổi mỗi lần xử lý.
  - `throttleDelay: 200` ms — nghỉ 200 ms trước khi xử lý chunk tiếp theo.
  - `maxBufferedWork: 30000` — không buffer quá 30k event.
- **Node.js (non-recursive):** cùng ý tưởng, `maxBufferedWork: 10000`.

**Tham chiếu:**  
`src/vs/platform/files/node/watcher/parcel/parcelWatcher.ts` (khoảng 181–186),  
`src/vs/platform/files/node/watcher/nodejs/nodejsWatcherLib.ts` (khoảng 40–45).

---

## 5. Batch delay 75 ms

Event từ watcher không emit ngay từng cái một; được gom qua **RunOnceWorker** với delay **75 ms** (sau Parcel’s 50 ms) rồi mới coalesce và throttle. Mục đích: gom nhiều thay đổi trong khoảng thời gian ngắn thành một đợt, giảm số lần client phải refresh (và không cần poll).

**Tham chiếu:**  
- `parcelWatcher.ts`: `FILE_CHANGES_HANDLER_DELAY = 75`.  
- `nodejsWatcherLib.ts`: `FILE_CHANGES_HANDLER_DELAY = 75`.

---

## 6. Mutation → event ngay (không chờ poll)

Khi chính VS Code (hoặc extension) ghi / xóa / đổi tên file qua FileSystemProvider, thay đổi đó được phản ánh qua **sự kiện** (ví dụ `onDidRunOperation` / tương đương), không dựa vào watcher poll để “thấy” thay đổi. Tức là: **mutation → emit event ngay**; client không cần poll để biết thao tác vừa xong.

---

## 7. Watcher restart (không dùng poll thay thế)

Khi watcher lỗi, VS Code **restart watcher** (số lần giới hạn, ví dụ `MAX_RESTARTS = 5`, delay ~800 ms), chứ không chuyển sang polling vĩnh viễn. Polling chỉ được bật khi cấu hình `usePolling` (vd. WSL1).

**Tham chiếu:** `src/vs/platform/files/common/watcher.ts` — `AbstractWatcherClient`, `MAX_RESTARTS`, `restart()`.

---

## 8. Client / Extension: dùng watcher, không poll

- **FileService**: đăng ký `provider.onDidChangeFile` và forward event; không có timer poll tree/list.
- **Extension / Workbench**: dùng `fileService.createWatcher()` hoặc `fileService.watch()`; cập nhật UI khi nhận event. Hướng dẫn nội bộ: “When adding file watching, prefer **correlated** file watchers (via fileService.createWatcher) to shared ones.” (`.github/copilot-instructions.md`).

**Tham chiếu:**  
- `src/vs/platform/files/common/fileService.ts`: đăng ký `onDidChangeFile` từ provider.  
- `src/vs/workbench/contrib/files/browser/workspaceWatcher.ts`: `fileService.watch(..., { recursive: true, excludes })`.  
- `src/vs/workbench/api/browser/mainThreadFileSystemEventService.ts`: `createWatcher` cho extension.

---

## 9. Tóm tắt: Làm sao để giảm polling (theo chuẩn VS Code)

| Mục tiêu | Cách làm (theo VS Code) |
|----------|--------------------------|
| **Không poll file tree/list** | Chỉ refresh khi nhận event từ watcher (`onDidChangeFile` / `fileChange`); gọi GET tree/list **một lần** lúc init, sau đó chỉ khi có event hoặc user action. |
| **Không poll nội dung file** | Dùng ETag / If-None-Match; re-read chỉ khi có event “file changed” cho file đó hoặc khi user mở file. |
| **Không poll terminal output** | Dùng stream (PTY / WebSocket); không có API “get output” định kỳ. |
| **Giảm polling khi bắt buộc (vd. WSL1)** | Tăng `pollingInterval`; thu hẹp `usePolling` xuống chỉ những path cần thiết. |
| **Giảm spam / tải** | Coalesce event (ADDED+DELETED bỏ, DELETED+ADDED → UPDATED); throttle (chunk 500, delay 200 ms, buffer tối đa 30k). |
| **Backend** | Ưu tiên native watcher (inotify / fs-events / windows); chỉ bật polling khi môi trường không hỗ trợ (deprecated, ví dụ WSL1). |

---

## 10. Áp dụng cho Daytona Sandbox

Phần này đã được mô tả trong **NO_POLLING_AUDIT.md**: backend sandbox đã cung cấp WS `/fs/watch`, ETag cho file content, và WS `/terminal/pty`. Client chỉ cần:

- Một WebSocket `/fs/watch` + refresh tree/list khi nhận `fileChange`.
- GET content có ETag / If-None-Match; re-read khi có `fileChange` (hoặc khi mở file).
- Terminal chỉ qua WebSocket, không poll.

Khi đó **không cần polling request** nào từ client — hành vi tương đương “gần như không polling” của VS Code.

---

*Tài liệu tổng hợp từ mã nguồn VS Code trong `/home/ducminh/vscode` (watcher, fileService, diskFileSystemProvider, parcelWatcher, nodejsWatcher).*
