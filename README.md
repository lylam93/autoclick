# Project Context & Requirements: Advanced Background Auto-Clicker

**To AI Assistant (Codex/Cursor/Copilot/Claude/etc.):**
This document contains the core requirements and technical constraints for building an advanced Auto-Clicker application for Windows. Please read carefully before writing any code. Your goal is to generate a complete, working architecture and implement the application based on these specifications.

---

## 1. Tổng quan dự án (Project Overview)
- **Tên phần mềm**: Advanced Background Auto-Clicker.
- **Mục đích**: Chạy auto-click trên các cửa sổ ứng dụng cụ thể (chủ yếu là game trên trình duyệt Chrome, Edge, giả lập Tango, v.v.) trên hệ điều hành Windows.
- **Tính năng cốt lõi**: Đặc biệt ưu tiên khả năng **click chạy ngầm (Background Click)**. Người dùng vẫn có thể dùng chuột làm việc khác trên màn hình vật lý trong khi auto-click đang hoạt động ở một cửa sổ khác.

## 2. Lựa chọn công nghệ (Tech Stack Recommendation)
*AI có thể dùng Python hoặc C# tùy chọn, nhưng cần tuân thủ các thư viện sau để đảm bảo tính năng chạy ngầm và giao diện hiện đại:*
- **Ngôn ngữ ưu tiên**: Python hoặc C# (.NET).
- **Core (Win32 API)**:
  - Bắt buộc dùng `SendMessage` hoặc `PostMessage` của Windows API (chứa `WM_LBUTTONDOWN`, `WM_LBUTTONUP`).
  - **KHÔNG** dùng `mouse_event` hay `pyautogui.click()` vì các hàm này sẽ chiếm quyền điều khiển con trỏ chuột thật của hệ thống.
  - Cần hàm lấy Window Handle (`HWND`) của cửa sổ/tab trình duyệt đích (ví dụ như Chrome_RenderWidgetHostHWND đối với Chrome).
- **Global Hotkeys**: Dùng thư viện `keyboard`, `pynput` (Python) để bắt phím tắt toàn cục dù cửa sổ phần mềm không được focus.
- **UI Framework (Giao diện)**:
  - Nếu dùng Python: Sử dụng `CustomTkinter`, `PyQt6` hoặc `PySide6` để có giao diện hiện đại, thân thiện, bo góc đẹp mắt (Dark mode / Light mode).
  - Nếu dùng C#: Sử dụng `WPF` với mẫu thiết kế Material Design hoặc UI hiện đại.

---

## 3. Các tính năng yêu cầu (Core Features)

### 3.1. Chế độ không chiếm chuột (Background Clicking) - QUAN TRỌNG NHẤT
- Phần mềm phải yêu cầu người dùng chỉ định/chọn một cửa sổ (Window) hoặc một tiến trình (Process) mục tiêu. Có thể dùng tính năng kéo thả (drag-and-drop crosshair) để lấy HWND của cửa sổ, hoặc list danh sách các cửa sổ đang mở để chọn.
- Khi auto-click kích hoạt, tín hiệu chuột phải gửi trực tiếp vào tọa độ `(X, Y)` *tương đối* của cửa sổ đó thông qua Win32 API.
- Chuột vật lý của người dùng không bị di chuyển, không bị ảnh hưởng.

### 3.2. Thu thập và ghi nhớ tọa độ click (Point Recording)
- Hỗ trợ **phím tắt** để người dùng trỏ chuột vào một điểm trên cửa sổ game và lưu lại vị trí đó.
- Cần tính toán tọa độ tương đối (Client Coordinates) của vị trí click so với góc trên bên trái (0,0) của cửa sổ được chọn để đảm bảo click chính xác dù cửa sổ bị di chuyển trên màn hình.
- Có thể lưu danh sách nhiều tọa độ để click theo một kịch bản (nếu cần mở rộng).

### 3.3. Cấu hình chu kỳ và giới hạn (Interval & Constraints)
- **Chu kỳ (Intervals)**: Cho phép setting thời gian giữa các lần click (Delay theo milliseconds hoặc seconds). Có thể hỗ trợ khoảng thời gian ngẫu nhiên (ví dụ click random trong khoảng từ 1000ms đến 1500ms) để tránh bị hệ thống game phát hiện auto.
- **Dừng theo tổng số lượt**: Setting số luợt click tối đa (ví dụ: chạy đúng 100 lượt rồi tự động dừng).
- **Dừng vô thời hạn**: Chạy liên tục cho tới khi bấm phím tắt dừng.

### 3.4. Hệ thống phím tắt linh hoạt (Customizable Hotkeys)
- Gồm các Hotkey cơ bản:
  - `Bắt đầu / Dừng` Auto-click (Start/Stop).
  - `Lấy tọa độ chuột` (Get Position).
- Các phím tắt này phải **có thể cấu hình được** từ UI (người dùng bấm vào ô input và ấn một phím chức năng như F8, F9, Ctrl+Shift+S... để gán lại phím tắt).

### 3.5. Giao diện thân thiện UX/UI (User Interface)
- Thiết kế một Form/Window gọn gàng với các khu vực chức năng rõ ràng:
  1. Khu vực "Target Window": Bắt tên cửa sổ.
  2. Khu vực "Click Settings": Chỉnh Delay, Số lượt click, Random delay.
  3. Khu vực "Hotkeys": Hiển thị và thay đổi phím bắt phím tắt.
  4. Khu vực "Status/Logs": Hiển thị trạng thái (Ready, Running, Stopped, đã click được bao nhiêu lượt, tọa độ đang set là bao nhiêu).

---

## 4. Hướng dẫn lập trình (Implementation Steps cho AI)
1. **Bước 1**: Viết module core xử lý Win32 API (`win32gui`, `win32api`, `ctypes` trên Python). Đảm bảo viết được test function gửi lệnh click giả vào cửa sổ Notepad hoặc Chrome bằng `SendMessage`. *Lưu ý: Đối với Chrome, phải tìm đúng class name là `Chrome_RenderWidgetHostHWND` thuộc child handle thì mới nhận click.*
2. **Bước 2**: Viết module lấy sự kiện phím tắt toàn cục (Global Hooks).
3. **Bước 3**: Viết engine quản lý luồng (Threading/Task) chứa vòng lặp click ngầm. Nó cần kết nối đến nút Start/Stop và cơ chế giới hạn lượt click. Đảm bảo UI không bị "đơ" (freeze) khi vòng lặp đang chạy.
4. **Bước 4**: Xây dựng UI kết nối các modules trên lại với nhau.
5. **Bước 5**: Thêm tính năng lưu cấu hình vào file `config.json` để giữ thiết lập cho lần mở phần mềm sau.

AI: Bắt đầu thiết kế kiến trúc và code từng phần ngay dưới đây dựa theo Requirement này.
