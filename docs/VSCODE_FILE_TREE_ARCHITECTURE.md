# VS Code File Tree (Explorer) — Vị trí & Luồng hoạt động

Tài liệu này mô tả **ở đâu** và **cách hoạt động** toàn bộ file tree (Explorer) trong source code VS Code tại `/home/ducminh/vscode`.

---

## 1. Vị trí các file chính

| Thư mục / File | Mục đích |
|----------------|----------|
| **`src/vs/workbench/contrib/files/`** | Toàn bộ contribution "Files" (Explorer, file actions, commands) |
| **`common/explorerModel.ts`** | **Model**: `ExplorerModel`, `ExplorerItem` — cây dữ liệu, roots, children, merge với disk |
| **`common/explorerFileNestingTrie.ts`** | File nesting (nhóm file theo pattern, VD `index.ts` + `index.test.ts`) |
| **`common/files.ts`** | Constants, context keys, interfaces (`IExplorerService`, `IExplorerView`) |
| **`browser/explorerService.ts`** | **Service**: đăng ký view, xử lý `onDidFilesChange` / `onDidRunOperation`, refresh, select |
| **`browser/views/explorerView.ts`** | **View**: UI tree, `WorkbenchCompressibleAsyncDataTree`, refresh, setTreeInput, selectResource |
| **`browser/views/explorerViewer.ts`** | **DataSource + Renderer**: `ExplorerDataSource`, `ExplorerDelegate`, `FilesRenderer`, filter, sort, drag-drop |
| **`browser/explorerViewlet.ts`** | **Viewlet**: container chứa Explorer view + Open Editors + Empty view, đăng ký view descriptors |

---

## 2. Luồng dữ liệu (end-to-end)

```
Workspace folders (IWorkspaceContextService)
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  ExplorerModel (explorerModel.ts)                                │
│  - _roots: ExplorerItem[]  (mỗi folder workspace = 1 root)      │
│  - onDidChangeRoots khi workspace folders thay đổi               │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  ExplorerItem (explorerModel.ts)                                 │
│  - resource, name, isDirectory, children: Map<string, ExplorerItem>  │
│  - fetchChildren(sortOrder): gọi fileService.resolve() → lazy load   │
│  - forgetChildren(): clear cache để refresh từ disk              │
│  - mergeLocalWithDisk(disk, local): gộp stat từ disk vào model    │
│  - addChild, removeChild, move, rename                            │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  ExplorerService (explorerService.ts)                            │
│  - model: ExplorerModel                                          │
│  - view: IExplorerView (ExplorerView)                            │
│  - onDidRunOperation → cập nhật model (addChild/removeChild/move) │
│    và gọi view.refresh() NGAY LẬP TỨC (không delay)              │
│  - onDidFilesChange → push event, schedule refresh 500ms         │
│    (EXPLORER_FILE_CHANGES_REACT_DELAY) → refresh() nếu cần       │
│  - refresh(): roots.forEach(r => r.forgetChildren()); view.refresh() │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  ExplorerView (explorerView.ts)                                  │
│  - tree: WorkbenchCompressibleAsyncDataTree<ExplorerItem, ...>   │
│  - setTreeInput(): tree.setInput(roots, viewState)               │
│  - refresh(item?): tree.updateChildren(item || input, recursive) │
│  - DataSource = ExplorerDataSource (explorerViewer.ts)           │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  ExplorerDataSource (explorerViewer.ts)                          │
│  - getChildren(element): element.fetchChildren(sortOrder)        │
│    → ExplorerItem.fetchChildren() gọi fileService.resolve()      │
│  - hasChildren(element): element.hasChildren(filter)             │
│  - getParent(element): element.parent                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Chi tiết từng lớp

### 3.1 ExplorerModel (`common/explorerModel.ts`)

- **ExplorerModel**: giữ `_roots: ExplorerItem[]`. Mỗi workspace folder = một `ExplorerItem` root. Khi `onDidChangeWorkspaceFolders` → set lại roots và fire `onDidChangeRoots`.
- **ExplorerItem**:
  - Thuộc tính: `resource`, `_name`, `_isDirectory`, `_isDirectoryResolved`, `children: Map<string, ExplorerItem>`, `parent`, `nestedParent`, `nestedChildren` (cho file nesting).
  - **fetchChildren(sortOrder)**:
    - Nếu chưa resolve: `fileService.resolve(this.resource, { resolveSingleChildDescendants, resolveMetadata })` → `ExplorerItem.create(..., stat, this)` → `mergeLocalWithDisk(resolved, this)`.
    - Trả về danh sách con (có thể qua file nesting).
  - **forgetChildren()**: `children.clear()`, `_isDirectoryResolved = false` → lần expand tiếp theo sẽ gọi lại `fileService.resolve`.
  - **mergeLocalWithDisk(disk, local)**: copy thuộc tính từ stat disk vào item local, merge children theo resource.
  - **create(fileService, ..., raw: IFileStat, parent, resolveTo?)**: tạo ExplorerItem từ IFileStat, đệ quy add child nếu `raw.children` có.

### 3.2 ExplorerService (`browser/explorerService.ts`)

- **EXPLORER_FILE_CHANGES_REACT_DELAY = 500** ms.
- **onDidRunOperation** (CREATE/COPY/MOVE/DELETE):
  - **CREATE/COPY**: tìm parent trong model, resolve nếu chưa, `parent.addChild(ExplorerItem.create(..., addedElement, ...))`, `view.refresh(shouldDeepRefresh, p)`.
  - **MOVE**: cùng parent → rename; khác parent → move trong model, refresh old/new parent.
  - **DELETE**: `parent.removeChild(modelElement)`, `view.refresh(..., parent)`.
- **onDidFilesChange**:
  - Push event vào `fileChangeEvents`, schedule `onFileChangesScheduler` (500ms).
  - Trong scheduler: lọc DELETED (và UPDATED nếu sort by modified), kiểm tra `doesFileEventAffect`, với ADDED kiểm tra parent đã resolve và chưa có child → nếu cần thì `refresh(false)`.

### 3.3 ExplorerView (`browser/views/explorerView.ts`)

- **tree**: `WorkbenchCompressibleAsyncDataTree<ExplorerItem | ExplorerItem[], ExplorerItem, FuzzyScore>`.
- **setTreeInput()**: input = roots (hoặc roots[0] nếu single folder), lấy viewState từ storage hoặc tree hiện tại → `tree.setInput(input, viewState)`.
- **refresh(recursive, item?, cancelEditing)**: `tree.updateChildren(toRefresh, recursive, !!item)`.
- **selectResource(resource, reveal)**: expand dọc đường từ root tới resource, rồi `tree.setFocus` / `setSelection` / `reveal`.

### 3.4 ExplorerDataSource (`browser/views/explorerViewer.ts`)

- **getChildren(element)**:
  - Nếu `element` là mảng (roots) → trả về luôn.
  - Gọi `element.fetchChildren(sortOrder)` → Promise trả về `ExplorerItem[]` (từ disk qua `fileService.resolve` hoặc từ cache nested).
- **hasChildren(element)**: `element.hasChildren(filter)` (có tính filter).
- **getParent(element)**: `element.parent`.

### 3.5 ExplorerViewlet (`browser/explorerViewlet.ts`)

- Đăng ký view container và các view: Open Editors, **Explorer (FILE EXPLORER)**, Empty view.
- View ID file explorer: **`VIEW_ID`** (từ `common/files.ts`).

---

## 4. Nơi “tree” thực sự được tạo và render

- **Tree widget**: `WorkbenchCompressibleAsyncDataTree` được tạo trong **`ExplorerView.createTree()`** (`explorerView.ts` khoảng dòng 318–374).
- **Input**: `ExplorerDataSource` (từ `explorerViewer.ts`).
- **Input data**: `explorerService.roots` (ExplorerItem[]). Set lần đầu và khi workspace đổi qua **`setTreeInput()`** (gọi từ `onDidChangeBodyVisibility`, `explorerService.model.onDidChangeRoots`, `explorerService.refresh` khi đổi provider, v.v.).
- **Mỗi node con**: khi user expand một folder, tree gọi `ExplorerDataSource.getChildren(element)` → `element.fetchChildren(sortOrder)` → `fileService.resolve(element.resource, ...)` → trả về `ExplorerItem[]` → tree render từng item qua **FilesRenderer** (cùng file `explorerViewer.ts`).

---

## 5. Tóm tắt đường dẫn đọc code

1. **Model & item**: `src/vs/workbench/contrib/files/common/explorerModel.ts` (ExplorerModel, ExplorerItem, fetchChildren, mergeLocalWithDisk, forgetChildren).
2. **Service (event → refresh/update model)**: `src/vs/workbench/contrib/files/browser/explorerService.ts` (onDidRunOperation, onDidFilesChange, refresh, 500ms delay).
3. **View (tree UI)**: `src/vs/workbench/contrib/files/browser/views/explorerView.ts` (createTree, setTreeInput, refresh, selectResource).
4. **DataSource & renderer**: `src/vs/workbench/contrib/files/browser/views/explorerViewer.ts` (ExplorerDataSource.getChildren → fetchChildren, FilesRenderer, filter, sort, dnd).
5. **Viewlet (container)**: `src/vs/workbench/contrib/files/browser/explorerViewlet.ts` (đăng ký Explorer view).

---

## 6. So sánh nhanh với Daytona Sandbox

| Khía cạnh | VS Code | Daytona Sandbox |
|-----------|---------|------------------|
| Nguồn dữ liệu tree | `fileService.resolve(uri)` (từ FileSystemProvider) | `GET /fs/tree`, `GET /fs/list` (REST) |
| Cập nhật khi có thay đổi | `onDidFilesChange` (event) + `onDidRunOperation` (event) → refresh/update model | `WS /fs/watch` (fileChange) → client refresh tree hoặc patch node |
| Lazy children | Có: expand mới gọi `fetchChildren` → resolve | Client có thể lazy: expand → GET /fs/list?path=... |
| Delay refresh từ watcher | 500 ms (EXPLORER_FILE_CHANGES_REACT_DELAY) | Client tự quyết định (có thể 0 ms khi dùng WS event) |

File tree trong VS Code nằm trọn trong **`src/vs/workbench/contrib/files/`**, với ba lớp chính: **Model** (explorerModel.ts), **Service** (explorerService.ts), **View + DataSource/Renderer** (explorerView.ts, explorerViewer.ts).
