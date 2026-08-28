# DevOps — Douyin Dịch Video Pipeline

Tài liệu hướng dẫn vận hành cho Windows. Tất cả script nằm trong `scripts/`.

---

## 1. Tổng quan các script

| Script | Mục đích | Loại |
|---|---|---|
| `scripts/install-all.ps1` | Cài đặt 1 lần (Python deps, Torch CUDA, Playwright, Kokoro, FFmpeg check) | PowerShell |
| `scripts/deploy.ps1` | Cập nhật mã + restart Web UI + smoke test | PowerShell |
| `scripts/supervisor.py` | Auto-restart Web UI khi sập, dọn port, xoay log | Python |
| `scripts/monitor.py` | TUI theo dõi GPU/CPU/RAM/queue/lỗi (hoặc xuất JSON) | Python |
| `scripts/backup.py` | Sao lưu tăng dần `workspace/output` + giữ N ngày | Python |

---

## 2. Cài đặt lần đầu

Mở **PowerShell** trong thư mục dự án:

```powershell
cd "D:\2023\Tải douyin hàng loạt"
powershell -ExecutionPolicy Bypass -File scripts\install-all.ps1
```

Tham số tuỳ chọn:

```powershell
# Bỏ qua PyTorch (đã cài sẵn)
powershell -ExecutionPolicy Bypass -File scripts\install-all.ps1 -SkipTorch

# Đổi phiên bản CUDA
powershell -ExecutionPolicy Bypass -File scripts\install-all.ps1 -CudaVersion cu121
```

Cuối script in **báo cáo sức khoẻ**: số mục OK / cảnh báo / lỗi.

> Nếu thấy `[X] FFmpeg` — đặt `ffmpeg.exe` vào `workspace\ffmpeg-shared\bin\` hoặc thêm vào PATH.

---

## 3. Khởi chạy Web UI có giám sát

### Cách thường (1 lần, không tự restart)

```powershell
python scripts\run_web.py
```

### Cách production (auto-restart, khuyến nghị)

```powershell
python scripts\supervisor.py --port 7860
```

Tính năng:

- Kiểm tra `localhost:7860` mỗi 30 giây.
- Nếu process chết hoặc port không phản hồi → tự khởi động lại.
- Tự dọn các process Python cũ chiếm port.
- Log Web UI ghi vào `workspace\logs\web_ui.log` (xoay vòng 10MB × 5 file).
- Log supervisor ghi vào `workspace\logs\supervisor.log`.
- Nhấn **Ctrl+C** để dừng mềm (tắt cả Web UI lẫn supervisor).

Tham số:

```powershell
python scripts\supervisor.py --port 7860 --check-interval 30 --startup-grace 45 --max-restarts 0
```

---

## 4. Theo dõi hệ thống

### TUI thời gian thực

```powershell
python scripts\monitor.py
python scripts\monitor.py --interval 5
```

Hiển thị:

- Trạng thái Web UI (ONLINE/OFFLINE)
- Số job pipeline đang chạy
- Số lỗi 60 phút qua (đếm `ERROR`/`Traceback` trong `workspace\logs\`)
- CPU / RAM / Disk
- GPU util / VRAM / nhiệt độ (qua `nvidia-smi`)
- Hàng đợi: số URL trong `workspace\urls.txt`, số video đã tải, số video hoàn tất

### Xuất JSON cho dashboard

```powershell
# 1 lần
python scripts\monitor.py --json D:\dashboard\stats.json

# Liên tục cập nhật mỗi 2 giây
python scripts\monitor.py --json D:\dashboard\stats.json --watch --interval 2
```

---

## 5. Sao lưu

### Sao lưu thủ công

```powershell
python scripts\backup.py --dest D:\Backup\Douyin
```

### Sao lưu nén, giữ 14 ngày

```powershell
python scripts\backup.py --dest E:\backups --retention-days 14 --compress
```

### Xem thử trước khi chạy

```powershell
python scripts\backup.py --dest E:\backups --dry-run
```

### Lập lịch tự động (Windows Task Scheduler)

1. Mở **Task Scheduler** → **Create Basic Task**.
2. Trigger: **Daily**, ví dụ 02:00.
3. Action: **Start a program**
   - Program: `python`
   - Arguments: `scripts\backup.py --dest D:\Backup\Douyin --retention-days 7 --compress`
   - Start in: `D:\2023\Tải douyin hàng loạt`

### Khôi phục

```powershell
# Snapshot thư mục
Copy-Item -Recurse "D:\Backup\Douyin\backup-20260414-020000\*" "D:\2023\Tải douyin hàng loạt\workspace\output\"

# Snapshot ZIP
Expand-Archive -Path "D:\Backup\Douyin\backup-20260414-020000.zip" `
               -DestinationPath "D:\2023\Tải douyin hàng loạt\workspace\output\" -Force
```

---

## 6. Triển khai cập nhật

```powershell
# Cập nhật đầy đủ: git pull → pip → restart → smoke test
powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1

# Chỉ restart, không pull/pip
powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1 -SkipGit -SkipPip

# Đổi port
powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1 -Port 7861
```

Smoke test sẽ thử `GET http://localhost:PORT` tối đa 60 giây. Nếu không phản hồi, script trả mã thoát `1` và hướng dẫn xem `workspace\logs\web_ui.log`.

---

## 7. Vị trí log quan trọng

| File | Nội dung |
|---|---|
| `workspace\logs\web_ui.log` | stdout/stderr của Web UI (Gradio) |
| `workspace\logs\supervisor.log` | Hoạt động của supervisor (restart, kill PID) |
| `workspace\logs\healer.log` | Module heal (sửa video lỗi) |
| `workspace\logs\inspector.log` | Module kiểm tra |
| `workspace\logs\media_validator.log` | Validator media |
| `workspace\logs\srt_validator.log` | Validator phụ đề |
| `workspace\logs\translation_qc.log` | QC bản dịch |
| `workspace\logs\recovery.log` | Khôi phục pipeline |
| `workspace\logs\audit.jsonl` | Audit chi tiết theo job (JSON Lines) |

Tất cả file `.log` đều được monitor đếm lỗi (60 phút gần nhất).

---

## 8. Xử lý sự cố thường gặp

### "Port 7860 đang bận"

```powershell
# Cách 1: dùng supervisor (tự dọn)
python scripts\supervisor.py

# Cách 2: dọn thủ công
Get-NetTCPConnection -LocalPort 7860 -State Listen |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force }
```

### "Web UI sập ngay khi khởi động"

1. Xem `workspace\logs\web_ui.log` (50 dòng cuối):
   ```powershell
   Get-Content workspace\logs\web_ui.log -Tail 50
   ```
2. Lỗi import module → chạy `install-all.ps1` lại.
3. Lỗi CUDA OOM → giảm batch size trong `config\default.yaml`.

### "GPU không được phát hiện"

```powershell
nvidia-smi
python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"
```

Nếu `False` → cài lại Torch:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-all.ps1 -CudaVersion cu124
```

### "Pipeline treo, không tiến triển"

1. Mở `monitor.py` xem GPU util — nếu = 0% nhiều phút → process kẹt.
2. Tìm process kẹt qua tên trong `monitor.py` (mục `active_jobs`).
3. Kill và để supervisor restart.

### "Disk đầy"

- Kiểm tra `workspace\downloads\` (video gốc) và `workspace\separated\` (audio tách).
- Xoá file cũ:
  ```powershell
  Get-ChildItem workspace\downloads -File |
      Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
      Remove-Item
  ```

### "supervisor.log toàn ERROR restart liên tục"

→ Web UI có lỗi cấu hình. Dừng supervisor (`Ctrl+C`), chạy `python scripts\run_web.py` trực tiếp để xem lỗi hiện tại.

---

## 9. Quy trình vận hành đề xuất

**Hằng ngày**

- Mở `monitor.py` ở 1 cửa sổ kiểm tra nhanh.
- Để `supervisor.py` chạy nền (qua Task Scheduler hoặc cửa sổ PowerShell luôn mở).

**Hằng tuần**

- Chạy `backup.py` (hoặc đã lập lịch).
- Xem nhanh `supervisor.log` xem có restart bất thường không.

**Khi có cập nhật mã**

- Chạy `deploy.ps1`.

**Mỗi tháng**

- Dọn `workspace\downloads\`, `workspace\separated\` các job đã hoàn tất.
- Kiểm tra dung lượng đích backup, xoá thủ công nếu cần.

---

## 10. Câu hỏi chưa giải quyết

- Có cần tích hợp gửi cảnh báo (email/Telegram) khi Web UI restart > N lần / giờ không?
- Snapshot backup hiện copy đầy đủ — nếu cần tiết kiệm dung lượng, thêm chế độ hard-link với base snapshot trước (ReFS/NTFS hỗ trợ).
- `count_active_jobs()` trong monitor đang nhận diện qua tên script (`run.py`, `run_web.py`...). Nếu pipeline đổi entrypoint, cần cập nhật danh sách `needles`.
