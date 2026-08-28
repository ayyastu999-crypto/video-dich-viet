# Douyin Dịch Video Pipeline

Tự động tải, dịch, lồng tiếng video Douyin sang tiếng Việt và các ngôn ngữ khác.

## Tính năng

- **Tải video Douyin** tự động (Playwright, vượt captcha)
- **Nhận dạng giọng nói** AI (faster-whisper GPU)
- **Dịch phụ đề** đa ngôn ngữ (Gemini 2.5 Flash)
- **Lồng tiếng** tự nhiên (edge-tts) hoặc clone giọng gốc (F5-TTS)
- **Phát hiện & xóa** phụ đề cũ (EasyOCR + FFmpeg blur)
- **Chèn phụ đề mới** tự động scale font theo kích thước video
- **Tách nhạc nền** thông minh (Demucs)
- **Tải cả kênh** hoặc tìm theo từ khóa
- **Xử lý hàng loạt** + hẹn giờ tự động
- **Upload** TikTok / YouTube

## Yêu cầu hệ thống

- **Windows 10/11**
- **Python 3.11+**
- **FFmpeg** (bản full, có trong PATH)
- **GPU NVIDIA** + CUDA 12.8 (khuyến nghị RTX 4060 Ti trở lên)
- **RAM**: 16GB+
- **Disk**: 10GB+ (cho models)

## Cài đặt lần đầu

### 1. Cài Python 3.11+
Tải từ https://python.org

### 2. Cài FFmpeg
```
choco install ffmpeg-full
# hoặc scoop install ffmpeg
```

### 3. Cài dependencies
```bash
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
playwright install chromium
```

### 4. Tải models AI
Models Kokoro sẽ tự tải khi dùng. Hoặc tải trước:
```bash
# kokoro-v1.0.onnx (310MB) và voices-v1.0.bin (27MB)
# Đặt vào thư mục models/
```

### 5. Setup cookies Douyin
```bash
# Cài extension "Get cookies.txt LOCALLY" trong Chrome
# Truy cập douyin.com → Export cookies → Lưu cookies.txt vào thư mục gốc
```

### 6. Gemini API Key

Key nằm trong file `.env` ở gốc project (đã được `.gitignore` bỏ qua):

```
GEMINI_API_KEY=...
```

**Không đặt key vào `config/default.yaml`** — file đó không được gitignore.
Nếu `translation.api_key` để trống, hệ thống tự lấy từ biến môi trường tương ứng
với provider đang dùng (`GEMINI_API_KEY` / `OPENAI_API_KEY` / `DEEPSEEK_API_KEY`).

## Cách sử dụng

### Mở Web UI (khuyến nghị)
Double-click **`Douyin Dich Video.bat`** hoặc shortcut trên Desktop
→ Mở trình duyệt tại http://localhost:7860

### Web UI mới — dịch video có sẵn trên máy

```bash
.venv/Scripts/python.exe -m uvicorn webui.server:app --port 5177
```
→ Mở http://localhost:5177 — kéo thả video vào, hoặc dán đường dẫn file.

Giao diện tự dò engine nào dùng được (Whisper GPU, Gemini, DeepSeek) và khoá
những cái chưa sẵn sàng. Tiến trình chạy hiện real-time qua SSE.

### Command Line

**Dịch video có sẵn trên máy (bỏ qua bước tải):**
```bash
python scripts/run.py --file "C:/Users/PC/Desktop/video.mp4" --lang vi
```

**Cả thư mục video:**
```bash
python scripts/run.py --folder "D:/videos-can-dich" --lang vi
```

**Dịch 1 video:**
```bash
python scripts/run.py --url "https://www.douyin.com/video/xxx" --lang vi
```

**Nhiều ngôn ngữ:**
```bash
python scripts/run.py --url "https://..." --lang vi,en,ja
```

**Dùng voice clone (nhân bản giọng gốc):**
```bash
python scripts/run.py --url "https://..." --lang vi --voice-clone
```

**Tải cả kênh + dịch:**
```bash
python scripts/scrape_channel.py "https://www.douyin.com/user/xxx" --translate --lang vi --max 20
```

**Tìm video theo từ khóa + dịch:**
```bash
python scripts/search_douyin.py "美食教程" --max 10 --translate --lang vi
```

**Batch từ file URL:**
```bash
python scripts/run.py --batch workspace/urls.txt --lang vi
```

**Hẹn giờ tự động:**
```bash
python scripts/run.py --schedule "0 8 * * *" --batch workspace/urls.txt --lang vi
```

## Bật/tắt các bước nặng

Trong `config/default.yaml`, mục `pipeline:`:

| Công tắc | Mặc định | Cần khi nào |
|---|---|---|
| `separate_audio` | `false` | Tách nhạc nền bằng Demucs. Cần `torch` (~2.5GB). Bật khi muốn giữ nhạc nền mà thay giọng. |
| `blur_old_captions` | `false` | Dò + blur phụ đề cháy sẵn bằng PaddleOCR. Chỉ cần với video nguồn đã có phụ đề. |
| `make_voice` | `true` | Tắt khi chỉ cần phụ đề, không cần lồng tiếng — chạy nhanh hơn nhiều. |
| `export_script` | `true` | Xuất kịch bản ra `.txt` (văn xuôi + song ngữ) để copy đi viết lại content. |

Tắt cả `separate_audio` và `blur_old_captions` thì không cần cài `torch`,
`demucs`, `paddleocr`, `opencv` — bộ cài gọn hơn rất nhiều.

## Cấu trúc project

```
├── Douyin Dich Video.bat   # Shortcut mở app
├── landing.html             # Trang giới thiệu
├── config/
│   ├── default.yaml         # Cấu hình chính
│   └── voices.yaml          # Voice mapping
├── src/
│   ├── pipeline.py          # Orchestrator
│   ├── steps/               # 15 bước xử lý
│   ├── utils/               # SRT, FFmpeg helpers
│   └── web/                 # Gradio UI
├── scripts/
│   ├── run.py               # CLI chính
│   ├── run_web.py           # Web UI launcher
│   ├── scrape_channel.py    # Scrape kênh Douyin
│   └── search_douyin.py     # Tìm theo từ khóa
├── models/                  # AI models (Kokoro, etc)
├── workspace/
│   ├── downloads/           # Video đã tải
│   ├── srt/                 # Phụ đề gốc + dịch
│   ├── tts/                 # Audio TTS
│   ├── separated/           # Vocal/instrumental
│   └── output/              # Video thành phẩm
└── requirements.txt
```

## Hiệu năng

Trên RTX 4060 Ti 16GB:
- Video 60s: **~1.5-2.5 phút/video**
- Chi phí: **~$0.001/video** (chỉ Gemini API)
- Batch 10 video: **~20-25 phút**

## Tech stack

| Component | Tool |
|-----------|------|
| Download | Playwright + yt-dlp |
| STT | faster-whisper large-v3 (GPU) |
| Dịch | Gemini 2.5 Flash |
| TTS | edge-tts / F5-TTS (voice clone) |
| OCR | EasyOCR (GPU) |
| Audio sep | Demucs htdemucs |
| Video | FFmpeg + OpenCV |
| UI | Gradio 6 |

## Troubleshooting

### "Fresh cookies needed" khi download
→ Export lại `cookies.txt` từ Chrome (đã đăng nhập Douyin)

### "CUDA not available"
→ Cài PyTorch CUDA: `pip install torch --index-url https://download.pytorch.org/whl/cu128`

### Port 7860 bị chiếm
→ Bat file tự động kill process cũ, hoặc chạy thủ công:
```bash
netstat -ano | findstr 7860
taskkill /F /PID <pid>
```

### Font phụ đề quá to/nhỏ
→ Pipeline tự scale theo chiều rộng video (2.5% of width). Có thể chỉnh trong tab Cài đặt.

### Video không có lời nói
→ Whisper trả về 0 segments, pipeline dừng. Chọn video khác có dialogue.

## License

Personal/Educational use only. Tuân thủ Douyin Terms of Service khi sử dụng.
