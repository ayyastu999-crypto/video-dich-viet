"""
Douyin Video Translation Pipeline - Web UI (Gradio)

Main application entry point. Provides:
- Tab 1: Pipeline (submit URLs, select languages, run pipeline)
- Tab 2: Dashboard (monitor all jobs, view progress)
- Tab 3: SRT Editor (view/edit subtitles before final render)
- Tab 4: Voice Settings (TTS provider + voice selection)
- Tab 5: Settings (captions, audio, upload, scheduler)

Primary language: Vietnamese
Theme: Dark (Premium glassmorphism)
"""
import time
import yaml
import gradio as gr
from pathlib import Path

from src.web.state import (
    AppState, JobStatus, StepName, STEP_LABELS_VI, PIPELINE_STEPS,
)
from src.web.worker import PipelineWorker
from src.web.theme import CUSTOM_CSS
from src.config import load_config

# ---- Constants ---------------------------------------------------------------

LANGUAGES = {
    "vi": "Tiếng Việt",
    "en": "English",
    "ja": "Tiếng Nhật",
    "ko": "Tiếng Hàn",
    "th": "Tiếng Thái",
    "id": "Tiếng Indonesia",
}

VOICE_GENDERS = {"female": "Nữ", "male": "Nam"}

CONFIG_PATH = "config/default.yaml"

# ---- Step icons (Unicode) for the progress tracker --------------------------

STEP_ICONS = {
    StepName.DOWNLOAD: "↧",       # down arrow
    StepName.STT: "🎤",          # microphone
    StepName.TRANSLATE: "🌐",    # globe
    StepName.TTS: "🗣",          # speaking head
    StepName.CAPTION_DETECT: "🔍", # magnifier
    StepName.CAPTION_BLUR: "❌",  # x
    StepName.CAPTION_WRITE: "✎",  # pencil
    StepName.AUDIO_SEPARATE: "🎶", # notes
    StepName.AUDIO_MIX: "🎧",    # headphone
    StepName.COMPOSE: "🎬",      # clapper
    StepName.UPLOAD: "☁",         # cloud
}

# ---- Globals -----------------------------------------------------------------

state = AppState()
worker = PipelineWorker(CONFIG_PATH)
worker.start()


# ==============================================================================
#  HELPER FUNCTIONS
# ==============================================================================

def _load_voices():
    """Load voices.yaml."""
    path = Path("config/voices.yaml")
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def _load_config():
    return load_config(CONFIG_PATH)


def _save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def _elapsed_for_step(sp):
    """Format elapsed time for a single step."""
    if sp.started_at is None:
        return ""
    end = sp.finished_at or time.time()
    secs = int(end - sp.started_at)
    if secs < 60:
        return f"{secs}s"
    mins, secs = divmod(secs, 60)
    return f"{mins}m{secs:02d}s"


def _build_progress_html(job):
    """Generate premium HTML for the step-by-step progress tracker."""
    if job is None:
        return """
        <div class="empty-state">
            <div class="empty-icon">🎬</div>
            <div class="empty-title">Chưa có tác vụ nào</div>
            <div class="empty-desc">Dan URL video Douyin vao o ben trai va nhan "Bắt đầu dịch" de bat dau.</div>
        </div>
        """

    status_icons = {
        JobStatus.QUEUED: "○",
        JobStatus.RUNNING: '<span class="spin-icon">⚙</span>',
        JobStatus.COMPLETED: "✓",
        JobStatus.FAILED: "✗",
    }

    rows = []
    for i, step_name in enumerate(PIPELINE_STEPS):
        sp = job.steps[step_name]
        status_cls = sp.status.value
        icon = status_icons.get(sp.status, "?")
        label = STEP_LABELS_VI.get(step_name, step_name.value)
        step_emoji = STEP_ICONS.get(step_name, "")
        msg = sp.message or ""
        elapsed = _elapsed_for_step(sp)
        row_cls = f"step-{status_cls}" if status_cls != "queued" else ""

        rows.append(f"""
        <div class="step-row {row_cls}">
            <div class="step-icon {status_cls}">{icon}</div>
            <div class="step-label {status_cls}">
                <span style="margin-right: 4px; opacity: 0.5;">{step_emoji}</span>
                {label}
            </div>
            <div class="step-status">{msg}</div>
            <div class="step-time">{elapsed}</div>
        </div>
        """)

    progress = job.overall_progress
    status_cls = job.status.value if job.status else "queued"

    status_labels = {
        "queued": "Chờ xử lý",
        "running": "Đang chạy",
        "completed": "Hoàn tất",
        "failed": "Lỗi",
    }

    # SVG circular progress
    radius = 34
    circumference = 2 * 3.14159 * radius
    offset = circumference * (1 - progress / 100)

    # Determine gradient color based on status
    grad_color1 = "#6366f1"
    grad_color2 = "#22d3ee"
    if status_cls == "completed":
        grad_color1 = "#10b981"
        grad_color2 = "#34d399"
    elif status_cls == "failed":
        grad_color1 = "#ef4444"
        grad_color2 = "#f87171"

    return f"""
    <div class="glass-card-static" style="padding: 20px;">
        <div class="job-card-header" style="margin-bottom: 16px;">
            <div class="job-card-title" style="font-size: 15px;">
                <span style="color: var(--text-muted);">#{job.job_id}</span>
                &nbsp;&middot;&nbsp;
                <span style="color: var(--primary-light);">{job.target_lang.upper()}</span>
            </div>
            <div class="job-card-badge {f"badge-{status_cls}"}">
                <span class="badge-dot"></span>
                {status_labels.get(status_cls, status_cls)}
            </div>
        </div>

        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 16px;
                    word-break: break-all; font-family: var(--font-mono);
                    padding: 8px 12px; background: rgba(255,255,255,0.02);
                    border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
            {job.url[:80]}{'...' if len(job.url) > 80 else ''}
        </div>

        <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 20px;">
            <div class="circular-progress">
                <svg viewBox="0 0 80 80">
                    <defs>
                        <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stop-color="{grad_color1}"/>
                            <stop offset="100%" stop-color="{grad_color2}"/>
                        </linearGradient>
                    </defs>
                    <circle class="track" cx="40" cy="40" r="{radius}"/>
                    <circle class="fill" cx="40" cy="40" r="{radius}"
                            stroke-dasharray="{circumference}"
                            stroke-dashoffset="{offset}"/>
                </svg>
                <div class="percentage">{progress:.0f}%</div>
            </div>
            <div style="flex: 1;">
                <div class="progress-bar-track">
                    <div class="progress-bar-fill {status_cls}" style="width: {progress:.0f}%"></div>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 8px;">
                    <span style="font-size: 12px; color: var(--text-muted); font-family: var(--font-mono);">
                        {job.elapsed_str}
                    </span>
                    <span style="font-size: 12px; color: var(--text-muted);">
                        {progress:.0f}% hoan thanh
                    </span>
                </div>
            </div>
        </div>

        <div class="pipeline-progress">
            {''.join(rows)}
        </div>
    </div>
    """


def _build_dashboard_html():
    """Generate full dashboard view with stats and job list."""
    jobs = state.get_all_jobs()

    total = len(jobs)
    running = sum(1 for j in jobs if j.status == JobStatus.RUNNING)
    completed = sum(1 for j in jobs if j.status == JobStatus.COMPLETED)
    failed = sum(1 for j in jobs if j.status == JobStatus.FAILED)

    stats = f"""
    <div class="stats-row">
        <div class="stat-card">
            <span class="stat-bg-icon">📊</span>
            <div class="stat-value">{total}</div>
            <div class="stat-label">Tổng cộng</div>
        </div>
        <div class="stat-card accent">
            <span class="stat-bg-icon">⚙</span>
            <div class="stat-value">{running}</div>
            <div class="stat-label">Đang chạy</div>
        </div>
        <div class="stat-card success">
            <span class="stat-bg-icon">✓</span>
            <div class="stat-value">{completed}</div>
            <div class="stat-label">Hoàn tất</div>
        </div>
        <div class="stat-card error">
            <span class="stat-bg-icon">⚠</span>
            <div class="stat-value">{failed}</div>
            <div class="stat-label">Lỗi</div>
        </div>
    </div>
    """

    if not jobs:
        return stats + """
        <div class="empty-state">
            <div class="empty-icon">📺</div>
            <div class="empty-title">Chưa có tác vụ nào</div>
            <div class="empty-desc">
                Dan URL vao tab <b style="color: var(--primary-light);">Pipeline</b> de bat dau dich video.
                Cac tác vụ se hien thi tai day.
            </div>
        </div>
        """

    job_cards = []
    for i, job in enumerate(jobs):
        progress = job.overall_progress
        status_cls = job.status.value
        badge_cls = f"badge-{status_cls}"

        status_labels = {
            "queued": "Cho",
            "running": "Đang chạy",
            "completed": "Xong",
            "failed": "Lỗi",
        }

        current = ""
        if job.status == JobStatus.RUNNING and job.current_step:
            step_label = STEP_LABELS_VI.get(job.current_step, '')
            current = f"""
            <span style="color: var(--accent); font-size: 12px; font-weight: 500;">
                &middot; {step_label}
            </span>
            """

        error_line = ""
        if job.error:
            error_line = f"""
            <div class="error-box">
                <span class="error-icon">⚠</span>
                <span>{job.error[:150]}</span>
            </div>
            """

        job_cards.append(f"""
        <div class="job-card {status_cls}" style="animation-delay: {i * 50}ms;">
            <div class="job-card-header">
                <div class="job-card-title">
                    <span style="color: var(--text-muted);">#{job.job_id}</span>
                    &nbsp;&middot;&nbsp;
                    <span style="color: var(--primary-light);">{job.target_lang.upper()}</span>
                    {current}
                </div>
                <div class="job-card-badge {badge_cls}">
                    <span class="badge-dot"></span>
                    {status_labels.get(status_cls, status_cls)}
                </div>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); word-break: break-all;
                        font-family: var(--font-mono); opacity: 0.7;">
                {job.url[:70]}{'...' if len(job.url) > 70 else ''}
            </div>
            <div class="progress-bar-track">
                <div class="progress-bar-fill {status_cls}" style="width: {progress:.0f}%"></div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 8px;">
                <span style="font-size: 12px; color: var(--text-muted); font-family: var(--font-mono);">
                    {job.elapsed_str}
                </span>
                <span style="font-size: 12px; color: var(--text-muted);">
                    {progress:.0f}%
                </span>
            </div>
            {error_line}
        </div>
        """)

    return stats + "".join(job_cards)


def _ass_color_to_css(ass_color: str) -> str:
    """Convert ASS color format (&HBBGGRR or &HFFFFFF) to CSS hex (#RRGGBB)."""
    c = ass_color.strip().lstrip("&H").lstrip("&h").rstrip("&")
    if len(c) == 6:
        return f"#{c[4:6]}{c[2:4]}{c[0:2]}"
    return "#FFFFFF"


def _build_caption_preview(font, size, color, outline, margin_v, alignment):
    """Build a live HTML preview of the subtitle style."""
    try:
        size = int(size) if size else 24
    except (ValueError, TypeError):
        size = 24
    try:
        outline = int(outline) if outline else 2
    except (ValueError, TypeError):
        outline = 2
    try:
        margin_v = int(margin_v) if margin_v else 30
    except (ValueError, TypeError):
        margin_v = 30

    css_color = _ass_color_to_css(str(color)) if color else "#FFFFFF"
    font = font or "Arial"

    align_val = alignment
    if isinstance(alignment, (list, tuple)):
        align_val = alignment[0] if alignment else 2
    try:
        align_val = int(align_val)
    except (ValueError, TypeError):
        align_val = 2

    align_map = {
        1: ("flex-start", "flex-end"),
        2: ("center", "flex-end"),
        3: ("flex-end", "flex-end"),
        8: ("center", "flex-start"),
    }
    h_align, v_align = align_map.get(align_val, ("center", "flex-end"))

    pos_labels = {1: "Trái dưới", 2: "Giữa dưới", 3: "Phải dưới", 8: "Giữa trên"}
    pos_label = pos_labels.get(align_val, "")

    preview_size = max(12, min(size, 48))

    shadow = f"0 0 {outline}px #000, " * 4 if outline > 0 else ""
    shadow = shadow.rstrip(", ")

    # Margin scaled to preview size (preview is 360px high, video is 1920px)
    # Preview MarginV in pixels = user's MarginV * (360 / 1920) = margin_v * 0.1875
    preview_margin = max(6, int(margin_v * 0.19))

    return f"""
    <div style="display: flex; justify-content: center; padding: 20px 0;">
        <div style="position: relative; width: 270px; height: 480px;
                    border-radius: 16px; overflow: hidden;
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                    box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.06);
                    display: flex; align-items: {v_align}; justify-content: {h_align};">
            <!-- Fake video content background -->
            <div style="position: absolute; inset: 0; opacity: 0.35;
                        background:
                            radial-gradient(circle at 30% 30%, rgba(99,102,241,0.3) 0%, transparent 50%),
                            radial-gradient(circle at 70% 60%, rgba(236,72,153,0.2) 0%, transparent 50%),
                            linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.4) 80%);"></div>
            <!-- Fake UI elements -->
            <div style="position: absolute; top: 12px; left: 12px; right: 12px;
                        display: flex; justify-content: space-between; align-items: center;
                        color: rgba(255,255,255,0.5); font-size: 10px;">
                <span>● TikTok/Douyin</span>
                <span>9:16</span>
            </div>
            <!-- Metadata label -->
            <div style="position: absolute; top: 36px; right: 12px;
                        font-size: 9px; color: rgba(255,255,255,0.4);
                        font-family: 'JetBrains Mono', monospace; text-align: right;">
                {pos_label}<br>
                margin: {margin_v}px<br>
                {font} {size}px
            </div>
            <!-- Subtitle preview -->
            <div style="font-family: '{font}', sans-serif;
                        font-size: {preview_size}px;
                        color: {css_color}; text-shadow: {shadow};
                        padding: 4px 16px;
                        margin: {preview_margin}px 12px;
                        line-height: 1.3; text-align: center;
                        position: relative; z-index: 1;
                        max-width: 90%; word-wrap: break-word;
                        font-weight: 600;">
            Xin chào, đây là phụ đề mẫu
            </div>
        </div>
    </div>
    """


def _build_srt_display(srt_path: str) -> str:
    """Read SRT file and return as editable text."""
    if not srt_path or not Path(srt_path).exists():
        return ""
    return Path(srt_path).read_text(encoding="utf-8")


# ==============================================================================
#  EVENT HANDLERS
# ==============================================================================

def submit_urls(urls_text: str, languages: list[str]):
    """Parse URLs and create jobs for each URL x language combination."""
    if not urls_text.strip():
        return "Vui lòng nhập ít nhất 1 URL.", _build_dashboard_html(), ""

    if not languages:
        return "Vui lòng chọn ít nhất 1 ngôn ngữ.", _build_dashboard_html(), ""

    urls = []
    for line in urls_text.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line.split("\t")[0].strip())

    if not urls:
        return "Không tìm thấy URL hợp lệ.", _build_dashboard_html(), ""

    created_ids = []
    for url in urls:
        for lang in languages:
            job = state.create_job(url, lang)
            worker.enqueue(job.job_id)
            created_ids.append(job.job_id)

    count = len(created_ids)
    msg = f"Đã tạo {count} tác vụ ({len(urls)} video x {len(languages)} ngôn ngữ)."

    first_job = state.get_job(created_ids[0])
    progress_html = _build_progress_html(first_job)

    return msg, _build_dashboard_html(), progress_html


def submit_batch(input_mode: str, urls_text: str, channel_url: str,
                 keyword: str, max_n: int, sort_by: str,
                 languages: list[str]):
    """Handle all 3 input modes: urls | channel | keyword."""
    if not languages:
        return "Vui lòng chọn ít nhất 1 ngôn ngữ.", _build_dashboard_html(), ""

    urls = []

    if input_mode == "urls":
        if not urls_text.strip():
            return "Vui lòng nhập ít nhất 1 URL.", _build_dashboard_html(), ""
        for line in urls_text.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line.split("\t")[0].strip())

    elif input_mode == "channel":
        if not channel_url.strip():
            return "Vui lòng nhập URL kênh.", _build_dashboard_html(), ""
        try:
            from src.steps.channel_scraper import ChannelScraper
            scraper = ChannelScraper(worker.config, worker.work_dir)
            result = scraper.run(
                profile_url=channel_url.strip(),
                max_videos=int(max_n) if max_n else 0,
            )
            urls = result["video_urls"]
            if not urls:
                return "Không tìm thấy video. Kênh có thể cần cookies mới.", _build_dashboard_html(), ""
        except Exception as e:
            return f"Lỗi scrape kênh: {e}", _build_dashboard_html(), ""

    elif input_mode == "keyword":
        if not keyword.strip():
            return "Vui lòng nhập từ khóa.", _build_dashboard_html(), ""
        try:
            from src.steps.keyword_search import KeywordSearch
            searcher = KeywordSearch(worker.config, worker.work_dir)
            result = searcher.run(
                keyword=keyword.strip(),
                max_results=int(max_n) if max_n else 10,
                sort=sort_by or "popular",
            )
            urls = [v["url"] for v in result["videos"]]
            if not urls:
                return "Không tìm thấy video.", _build_dashboard_html(), ""
        except Exception as e:
            return f"Lỗi tìm kiếm: {e}", _build_dashboard_html(), ""

    if not urls:
        return "Không có URL để xử lý.", _build_dashboard_html(), ""

    created_ids = []
    for url in urls:
        for lang in languages:
            job = state.create_job(url, lang)
            worker.enqueue(job.job_id)
            created_ids.append(job.job_id)

    count = len(created_ids)
    mode_desc = {"urls": "URL", "channel": "từ kênh", "keyword": f'từ khóa "{keyword}"'}
    msg = f"Đã tạo {count} tác vụ ({len(urls)} video {mode_desc.get(input_mode, '')} × {len(languages)} ngôn ngữ)."

    first_job = state.get_job(created_ids[0])
    progress_html = _build_progress_html(first_job)

    return msg, _build_dashboard_html(), progress_html


def refresh_dashboard():
    """Refresh the dashboard display."""
    return _build_dashboard_html()


def refresh_progress(job_id_text: str):
    """Refresh progress for a specific job."""
    job_id = job_id_text.strip()
    if not job_id:
        jobs = state.get_all_jobs()
        if jobs:
            job = jobs[0]
        else:
            return _build_progress_html(None), "", ""
    else:
        job = state.get_job(job_id)

    if not job:
        return _build_progress_html(None), "", ""

    progress_html = _build_progress_html(job)
    srt_original = _build_srt_display(job.srt_original) if job.srt_original else ""
    srt_translated = _build_srt_display(job.srt_translated) if job.srt_translated else ""
    return progress_html, srt_original, srt_translated


def refresh_job_list():
    """Get list of job IDs for dropdown."""
    jobs = state.get_all_jobs()
    if not jobs:
        return gr.update(choices=[], value="")
    choices = [f"{j.job_id} ({j.target_lang.upper()})" for j in jobs]
    return gr.update(choices=choices, value=choices[0] if choices else "")


def save_srt_edits(job_id_text: str, srt_content: str):
    """Save edited SRT content back to file."""
    job_id = job_id_text.strip().split(" ")[0] if job_id_text else ""
    job = state.get_job(job_id)
    if not job or not job.srt_translated:
        return "Không tìm thấy file SRT để lưu."
    Path(job.srt_translated).write_text(srt_content, encoding="utf-8")
    return f"Đã lưu {job.srt_translated}"


def save_settings(
    caption_auto,
    caption_font, caption_size, caption_color, caption_outline,
    caption_margin_v, caption_alignment,
    bg_volume, audio_bitrate,
    upload_tiktok, upload_youtube,
    tiktok_tags, youtube_privacy,
    scheduler_enabled, scheduler_cron, scheduler_url_file,
):
    """Save all settings to config/default.yaml."""
    config = _load_config()

    config["caption"]["style"]["auto_position"] = bool(caption_auto)
    config["caption"]["style"]["font"] = caption_font
    config["caption"]["style"]["size"] = int(caption_size)
    config["caption"]["style"]["color"] = caption_color
    config["caption"]["style"]["outline"] = int(caption_outline)
    config["caption"]["style"]["margin_v"] = int(caption_margin_v)
    config["caption"]["style"]["alignment"] = int(caption_alignment)

    config["audio"]["bg_volume"] = float(bg_volume)
    config["output"]["audio_bitrate"] = audio_bitrate

    platforms = []
    if upload_tiktok:
        platforms.append("tiktok")
    if upload_youtube:
        platforms.append("youtube")
    config["upload"]["platforms"] = platforms
    config["upload"]["tiktok"]["default_tags"] = tiktok_tags
    config["upload"]["youtube"]["default_privacy"] = youtube_privacy

    config["scheduler"]["enabled"] = scheduler_enabled
    config["scheduler"]["cron"] = scheduler_cron
    config["scheduler"]["url_file"] = scheduler_url_file

    _save_config(config)
    return "Đã lưu cấu hình thành công!"


def load_settings():
    """Load current settings for the form."""
    config = _load_config()
    cap = config.get("caption", {}).get("style", {})
    audio = config.get("audio", {})
    output = config.get("output", {})
    upload = config.get("upload", {})
    sched = config.get("scheduler", {})

    platforms = upload.get("platforms", [])

    return (
        cap.get("font", "Arial"),
        cap.get("size", 24),
        cap.get("color", "&HFFFFFF"),
        cap.get("outline", 2),
        cap.get("margin_v", 30),
        cap.get("alignment", 2),
        audio.get("bg_volume", 0.3),
        output.get("audio_bitrate", "192k"),
        "tiktok" in platforms,
        "youtube" in platforms,
        upload.get("tiktok", {}).get("default_tags", ""),
        upload.get("youtube", {}).get("default_privacy", "private"),
        sched.get("enabled", False),
        sched.get("cron", "0 8 * * *"),
        sched.get("url_file", "workspace/urls.txt"),
    )


def get_video_for_preview(job_id_text: str, video_type: str):
    """Return video file path for preview."""
    job_id = job_id_text.strip().split(" ")[0] if job_id_text else ""
    job = state.get_job(job_id)
    if not job:
        return None

    if video_type == "original" and job.video_path:
        p = Path(job.video_path)
        return str(p) if p.exists() else None
    elif video_type == "final" and job.final_video:
        p = Path(job.final_video)
        return str(p) if p.exists() else None
    return None


# ==============================================================================
#  BUILD THE UI
# ==============================================================================

def create_app():
    """Create and return the Gradio app."""

    with gr.Blocks(
        title="Douyin Dich Video",
        css=CUSTOM_CSS,
        theme=gr.themes.Base(
            primary_hue=gr.themes.colors.indigo,
            secondary_hue=gr.themes.colors.slate,
            neutral_hue=gr.themes.colors.slate,
            font=("Inter", "system-ui", "sans-serif"),
            font_mono=("JetBrains Mono", "Fira Code", "monospace"),
        ).set(
            body_background_fill="#0a0a12",
            body_background_fill_dark="#0a0a12",
            background_fill_primary="#0f0f1a",
            background_fill_primary_dark="#0f0f1a",
            background_fill_secondary="#12121e",
            background_fill_secondary_dark="#12121e",
            border_color_primary="rgba(255,255,255,0.06)",
            border_color_primary_dark="rgba(255,255,255,0.06)",
            block_background_fill="#12121e",
            block_background_fill_dark="#12121e",
            block_border_color="rgba(255,255,255,0.06)",
            block_border_color_dark="rgba(255,255,255,0.06)",
            block_label_background_fill="#0f0f1a",
            block_label_background_fill_dark="#0f0f1a",
            block_label_text_color="#94a3b8",
            block_label_text_color_dark="#94a3b8",
            block_title_text_color="#e2e8f0",
            block_title_text_color_dark="#e2e8f0",
            body_text_color="#e2e8f0",
            body_text_color_dark="#e2e8f0",
            body_text_color_subdued="#94a3b8",
            body_text_color_subdued_dark="#94a3b8",
            button_primary_background_fill="*primary_500",
            button_primary_background_fill_dark="*primary_500",
            button_primary_background_fill_hover="*primary_400",
            button_primary_background_fill_hover_dark="*primary_400",
            button_primary_text_color="white",
            button_primary_text_color_dark="white",
            button_secondary_background_fill="#1a1a2e",
            button_secondary_background_fill_dark="#1a1a2e",
            button_secondary_text_color="#e2e8f0",
            button_secondary_text_color_dark="#e2e8f0",
            input_background_fill="#1a1a2e",
            input_background_fill_dark="#1a1a2e",
            input_border_color="rgba(255,255,255,0.06)",
            input_border_color_dark="rgba(255,255,255,0.06)",
            input_border_color_focus="#6366f1",
            input_border_color_focus_dark="#6366f1",
            shadow_drop="none",
            shadow_drop_lg="none",
            block_radius="16px",
        ),
    ) as app:

        # ---- HEADER ----------------------------------------------------------
        gr.HTML("""
        <div class="app-header">
            <h1>
                <span class="logo-icon">▶</span>
                <span class="header-brand-text">Douyin Dich Video</span>
                <span class="version-tag">v2.0</span>
            </h1>
            <div class="status-badge">
                <span class="status-dot"></span>
                Sẵn sàng
            </div>
        </div>
        """)

        # ---- TABS ------------------------------------------------------------
        with gr.Tabs() as tabs:

            # ==================================================================
            #  TAB 1: PIPELINE (Submit + Progress)
            # ==================================================================
            with gr.Tab("▶  Pipeline", id="pipeline"):
                with gr.Row():

                    # LEFT COLUMN: Input
                    with gr.Column(scale=1):
                        gr.HTML("""
                        <div class="panel-header">
                            <span class="panel-icon primary">🎭</span>
                            Nhập URL Video
                        </div>
                        """)

                        # Mode selector: URL list | Channel | Keyword
                        input_mode = gr.Radio(
                            choices=[
                                ("🎬  URL từng video", "urls"),
                                ("👤  Cả kênh Douyin", "channel"),
                                ("🔍  Tìm theo từ khóa", "keyword"),
                            ],
                            value="urls",
                            label="Chế độ nhập",
                            info="Chọn cách nhập video",
                        )

                        urls_input = gr.Textbox(
                            label="URL Douyin (mỗi dòng 1 URL)",
                            placeholder="https://www.douyin.com/video/...\nhttps://www.douyin.com/video/...",
                            lines=6,
                            max_lines=20,
                        )

                        channel_input = gr.Textbox(
                            label="URL Kênh Douyin",
                            placeholder="https://www.douyin.com/user/MS4wLjAB...",
                            visible=False,
                        )

                        keyword_input = gr.Textbox(
                            label="Từ khóa tìm kiếm",
                            placeholder="Ví dụ: 美食教程, 设计, 穿搭...",
                            visible=False,
                        )

                        with gr.Row(visible=False) as batch_options:
                            max_videos = gr.Number(
                                label="Số video tối đa",
                                value=10,
                                minimum=1,
                                maximum=100,
                                step=1,
                            )
                            sort_by = gr.Dropdown(
                                label="Sắp xếp theo (chỉ cho tìm kiếm)",
                                choices=[
                                    ("Phổ biến nhất", "popular"),
                                    ("Mới nhất", "new"),
                                    ("Liên quan nhất", "default"),
                                ],
                                value="popular",
                            )

                        # Toggle inputs based on mode
                        def _toggle_input_mode(mode):
                            return (
                                gr.update(visible=(mode == "urls")),
                                gr.update(visible=(mode == "channel")),
                                gr.update(visible=(mode == "keyword")),
                                gr.update(visible=(mode in ("channel", "keyword"))),
                            )

                        input_mode.change(
                            fn=_toggle_input_mode,
                            inputs=[input_mode],
                            outputs=[urls_input, channel_input, keyword_input, batch_options],
                        )

                        lang_select = gr.CheckboxGroup(
                            choices=list(LANGUAGES.keys()),
                            value=["vi"],
                            label="Ngôn ngữ dịch",
                            info="Chọn 1 hoặc nhiều ngôn ngữ",
                        )

                        gr.HTML("""
                        <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: -4px; margin-bottom: 16px;">
                            <span style="font-size: 11px; padding: 3px 10px; border-radius: 20px;
                                        background: rgba(99,102,241,0.08); color: var(--primary-light);
                                        border: 1px solid rgba(99,102,241,0.15);">vi = Tiếng Việt</span>
                            <span style="font-size: 11px; padding: 3px 10px; border-radius: 20px;
                                        background: rgba(255,255,255,0.03); color: var(--text-muted);
                                        border: 1px solid var(--border);">en = English</span>
                            <span style="font-size: 11px; padding: 3px 10px; border-radius: 20px;
                                        background: rgba(255,255,255,0.03); color: var(--text-muted);
                                        border: 1px solid var(--border);">ja = Nhat</span>
                            <span style="font-size: 11px; padding: 3px 10px; border-radius: 20px;
                                        background: rgba(255,255,255,0.03); color: var(--text-muted);
                                        border: 1px solid var(--border);">ko = Han</span>
                            <span style="font-size: 11px; padding: 3px 10px; border-radius: 20px;
                                        background: rgba(255,255,255,0.03); color: var(--text-muted);
                                        border: 1px solid var(--border);">th = Thai</span>
                            <span style="font-size: 11px; padding: 3px 10px; border-radius: 20px;
                                        background: rgba(255,255,255,0.03); color: var(--text-muted);
                                        border: 1px solid var(--border);">id = Indonesia</span>
                        </div>
                        """)

                        submit_status = gr.Textbox(
                            label="Trạng thái",
                            interactive=False,
                            lines=1,
                        )

                        with gr.Row():
                            submit_btn = gr.Button(
                                "▶  Bắt đầu dịch",
                                variant="primary",
                                size="lg",
                                elem_classes=["btn-action-lg"],
                            )
                            clear_btn = gr.Button(
                                "Xoa",
                                variant="secondary",
                                size="lg",
                            )

                    # RIGHT COLUMN: Progress
                    with gr.Column(scale=1):
                        gr.HTML("""
                        <div class="panel-header">
                            <span class="panel-icon accent">⚙</span>
                            Tiến trình xử lý
                        </div>
                        """)

                        progress_display = gr.HTML(
                            value=_build_progress_html(None),
                        )

                        with gr.Row():
                            refresh_btn = gr.Button(
                                "↻  Làm mới",
                                variant="secondary",
                                size="sm",
                            )
                            open_folder_btn = gr.Button(
                                "📂  Mở thư mục",
                                variant="secondary",
                                size="sm",
                            )
                            new_video_btn = gr.Button(
                                "➕  Video mới",
                                variant="primary",
                                size="sm",
                            )

                        progress_timer = gr.Timer(value=3)

                # Events
                submit_btn.click(
                    fn=submit_batch,
                    inputs=[input_mode, urls_input, channel_input, keyword_input,
                            max_videos, sort_by, lang_select],
                    outputs=[submit_status, gr.State(), progress_display],
                )

                clear_btn.click(
                    fn=lambda: ("", ["vi"], ""),
                    outputs=[urls_input, lang_select, submit_status],
                )

                # "Video mới" button - scroll to input form and clear
                new_video_btn.click(
                    fn=lambda: ("", ["vi"], ""),
                    outputs=[urls_input, lang_select, submit_status],
                    js="() => { setTimeout(() => { const ta = document.querySelector('textarea[placeholder*=\"douyin\"]'); if (ta) { ta.scrollIntoView({behavior:'smooth', block:'center'}); ta.focus(); } }, 100); return ['', ['vi'], '']; }",
                )

                # "Mở thư mục" - opens workspace/output in Explorer
                def _open_output_folder():
                    import subprocess
                    import platform
                    from pathlib import Path
                    output_dir = Path("workspace/output").resolve()
                    output_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        system = platform.system()
                        if system == "Windows":
                            subprocess.Popen(["explorer", str(output_dir)])
                        elif system == "Darwin":  # macOS
                            subprocess.Popen(["open", str(output_dir)])
                        else:  # Linux
                            subprocess.Popen(["xdg-open", str(output_dir)])
                        return f"Đã mở: {output_dir}"
                    except Exception as e:
                        return f"Lỗi mở thư mục: {e}"

                open_folder_btn.click(
                    fn=_open_output_folder,
                    outputs=[submit_status],
                )

                def _get_latest_job():
                    jobs = state.get_all_jobs()
                    if not jobs:
                        return None
                    running = [j for j in jobs if j.status == JobStatus.RUNNING]
                    return running[0] if running else jobs[0]

                def auto_refresh_progress():
                    jobs = state.get_all_jobs()
                    if jobs:
                        running = [j for j in jobs if j.status == JobStatus.RUNNING]
                        job = running[0] if running else jobs[0]
                        return _build_progress_html(job)
                    return _build_progress_html(None)

                progress_timer.tick(
                    fn=auto_refresh_progress,
                    outputs=[progress_display],
                )

                refresh_btn.click(
                    fn=auto_refresh_progress,
                    outputs=[progress_display],
                )

            # ==================================================================
            #  TAB 2: DASHBOARD
            # ==================================================================
            with gr.Tab("📊  Dashboard", id="dashboard"):

                dashboard_display = gr.HTML(
                    value=_build_dashboard_html(),
                )

                with gr.Row():
                    dash_refresh_btn = gr.Button(
                        "↻  Làm mới Dashboard",
                        variant="secondary",
                        size="sm",
                    )

                dash_timer = gr.Timer(value=5)

                dash_timer.tick(
                    fn=refresh_dashboard,
                    outputs=[dashboard_display],
                )

                dash_refresh_btn.click(
                    fn=refresh_dashboard,
                    outputs=[dashboard_display],
                )

            # ==================================================================
            #  TAB 3: SRT EDITOR
            # ==================================================================
            with gr.Tab("📝  Phụ đề (SRT)", id="srt-editor"):

                gr.HTML("""
                <div class="panel-header" style="margin-bottom: 16px;">
                    <span class="panel-icon primary">📝</span>
                    Trinh chinh sua phu de
                </div>
                """)

                with gr.Row():
                    srt_job_select = gr.Dropdown(
                        label="Chon tác vụ",
                        choices=[],
                        interactive=True,
                    )
                    srt_refresh_btn = gr.Button(
                        "↻  Tải lại danh sach",
                        variant="secondary",
                        size="sm",
                    )

                with gr.Row():
                    srt_original_display = gr.Textbox(
                        label="🇨🇳  Phụ đề gốc (Tieng Trung)",
                        lines=20,
                        max_lines=50,
                        interactive=False,
                        elem_classes=["srt-editor-container"],
                    )

                    srt_translated_edit = gr.Textbox(
                        label="🇻🇳  Phụ đề dịch (có thể chỉnh sửa)",
                        lines=20,
                        max_lines=50,
                        interactive=True,
                        elem_classes=["srt-editor-container"],
                    )

                with gr.Row():
                    save_srt_btn = gr.Button(
                        "💾  Lưu thay đổi",
                        variant="primary",
                    )
                    srt_save_status = gr.Textbox(
                        label="",
                        interactive=False,
                        lines=1,
                    )

                # Video Preview
                gr.HTML("""
                <div class="panel-header" style="margin-top: 24px;">
                    <span class="panel-icon accent">🎬</span>
                    Xem trước Video
                </div>
                """)

                with gr.Row():
                    with gr.Column():
                        gr.HTML("""
                        <div style="font-size: 13px; font-weight: 600; color: var(--text-secondary);
                                    margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
                            <span style="color: var(--text-muted);">🎬</span> Video gốc
                        </div>
                        """)
                        video_original = gr.Video(label="Goc")
                        load_original_btn = gr.Button(
                            "Tải video gốc",
                            size="sm",
                            variant="secondary",
                        )

                    with gr.Column():
                        gr.HTML("""
                        <div style="font-size: 13px; font-weight: 600; color: var(--text-secondary);
                                    margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
                            <span style="color: var(--success);">✓</span> Video đã dịch
                        </div>
                        """)
                        video_final = gr.Video(label="Da dich")
                        load_final_btn = gr.Button(
                            "Tải video đã dịch",
                            size="sm",
                            variant="secondary",
                        )

                # Events for SRT tab
                def _load_srt_for_job(job_id_text):
                    if not job_id_text:
                        return "", ""
                    jid = job_id_text.strip().split(" ")[0]
                    job = state.get_job(jid)
                    if not job:
                        return "", ""
                    orig = _build_srt_display(job.srt_original) if job.srt_original else ""
                    trans = _build_srt_display(job.srt_translated) if job.srt_translated else ""
                    return orig, trans

                srt_job_select.change(
                    fn=_load_srt_for_job,
                    inputs=[srt_job_select],
                    outputs=[srt_original_display, srt_translated_edit],
                )

                srt_refresh_btn.click(
                    fn=refresh_job_list,
                    outputs=[srt_job_select],
                )

                save_srt_btn.click(
                    fn=save_srt_edits,
                    inputs=[srt_job_select, srt_translated_edit],
                    outputs=[srt_save_status],
                )

                load_original_btn.click(
                    fn=lambda jid: get_video_for_preview(jid, "original"),
                    inputs=[srt_job_select],
                    outputs=[video_original],
                )

                load_final_btn.click(
                    fn=lambda jid: get_video_for_preview(jid, "final"),
                    inputs=[srt_job_select],
                    outputs=[video_final],
                )

            # ==================================================================
            #  TAB 4: VOICE SETTINGS
            # ==================================================================
            with gr.Tab("🗣  Giọng đọc (TTS)", id="voices"):
                gr.HTML("""
                <div class="panel-header" style="margin-bottom: 16px;">
                    <span class="panel-icon primary">🗣</span>
                    Cấu hình giọng đọc
                </div>
                """)

                # TTS Provider Selection
                current_config = _load_config()
                current_provider = current_config.get("tts", {}).get("provider", "edge-tts")

                tts_provider = gr.Dropdown(
                    label="Nhà cung cấp TTS",
                    choices=["edge-tts", "voice-clone (F5-TTS)"],
                    value=current_provider if current_provider in ["edge-tts", "voice-clone (F5-TTS)"] else "edge-tts",
                    info="Edge-TTS (giong Viet, mien phi), Voice-Clone (nhan ban giong goc tu video)",
                )

                # Edge-TTS voice group
                with gr.Group(visible=(current_provider != "voice-clone (F5-TTS)")) as edge_voice_group:
                    gr.HTML("""
                    <div class="provider-info">
                        <b>Edge-TTS</b> - Giọng đọc tieng Viet tu Microsoft
                        <span class="tag free">Miễn phí</span>
                        <br><span style="color: var(--text-muted); font-size: 12px;">
                        Chat luong cao, toc do nhanh, khong can GPU.</span>
                    </div>
                    """)

                    current_vi_voice = current_config.get("tts", {}).get("voices", {}).get("vi", "vi-VN-HoaiMyNeural")
                    vi_voice = gr.Dropdown(
                        label="Giọng Việt Nam",
                        choices=[
                            ("HoaiMy - Nu (tu nhien, am ap)", "vi-VN-HoaiMyNeural"),
                            ("NamMinh - Nam (tram, ro rang)", "vi-VN-NamMinhNeural"),
                        ],
                        value=current_vi_voice,
                        info="Chon giong nu hoac nam tieng Viet",
                    )

                    tts_speed = gr.Slider(
                        label="Tốc độ đọc",
                        minimum=0.5,
                        maximum=2.0,
                        step=0.1,
                        value=1.0,
                    )

                    with gr.Row():
                        test_voice_btn = gr.Button(
                            "🎧  Nghe thử giọng",
                            variant="secondary",
                            size="sm",
                        )
                        test_voice_audio = gr.Audio(
                            label="Nghe thử",
                            type="filepath",
                            interactive=False,
                            autoplay=True,
                        )

                # Voice-Clone group
                with gr.Group(visible=(current_provider == "voice-clone (F5-TTS)")) as clone_group:
                    gr.HTML("""
                    <div class="provider-info">
                        <b>Voice-Clone (F5-TTS)</b> - Nhân bản giọng đọc từ video gốc
                        <span class="tag gpu">Cần GPU</span>
                        <br><span style="color: var(--text-muted); font-size: 12px;">
                        Giọng đọc se duoc tu dong trich xuat tu audio goc khi chay pipeline.<br>
                        Yêu cầu GPU (RTX 4060 Ti tro len), chay cham hon Edge-TTS nhung giong tu nhien hon.</span>
                    </div>
                    """)

                # Provider toggle visibility
                def _toggle_tts_provider(provider_val):
                    return (
                        gr.update(visible=(provider_val != "voice-clone (F5-TTS)")),
                        gr.update(visible=(provider_val == "voice-clone (F5-TTS)")),
                    )

                tts_provider.change(
                    fn=_toggle_tts_provider,
                    inputs=[tts_provider],
                    outputs=[edge_voice_group, clone_group],
                )

                # Save provider
                tts_save_btn = gr.Button(
                    "💾  Lưu cấu hình giong doc",
                    variant="primary",
                    size="lg",
                )
                tts_save_msg = gr.HTML(value="")

                def _save_tts_config(provider_val, vi_voice_val):
                    config = _load_config()
                    if provider_val == "voice-clone (F5-TTS)":
                        config["tts"]["provider"] = "voice-clone"
                    else:
                        config["tts"]["provider"] = "edge-tts"
                    config["tts"]["voices"]["vi"] = vi_voice_val
                    _save_config(config)
                    return """
                    <div class="save-success">
                        <span class="check-icon">✓</span>
                        Đã lưu cấu hình giong doc thành công!
                    </div>
                    """

                tts_save_btn.click(
                    fn=_save_tts_config,
                    inputs=[tts_provider, vi_voice],
                    outputs=[tts_save_msg],
                )

                # Test voice handler
                def _test_vi_voice(voice_id, speed_val):
                    try:
                        import edge_tts
                        import asyncio
                        import tempfile

                        test_text = "Xin chao, day la giong doc thu nghiem tieng Viet. Chat luong am thanh rat tu nhien va ro rang."
                        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)

                        async def _gen():
                            comm = edge_tts.Communicate(test_text, voice_id)
                            await comm.save(tmp.name)

                        asyncio.run(_gen())
                        return tmp.name
                    except Exception as e:
                        return None

                test_voice_btn.click(
                    fn=_test_vi_voice,
                    inputs=[vi_voice, tts_speed],
                    outputs=[test_voice_audio],
                )

            # ==================================================================
            #  TAB 5: SETTINGS
            # ==================================================================
            with gr.Tab("⚙  Cài đặt", id="settings"):

                gr.HTML("""
                <div class="panel-header" style="margin-bottom: 16px;">
                    <span class="panel-icon primary">⚙</span>
                    Cấu hình chung
                </div>
                """)

                # Load current values
                (
                    cap_font, cap_size, cap_color, cap_outline,
                    cap_margin, cap_align,
                    bg_vol, audio_br,
                    up_tiktok, up_youtube,
                    tt_tags, yt_privacy,
                    sch_enabled, sch_cron, sch_file,
                ) = load_settings()

                # Caption Style
                with gr.Accordion("✎  Kiểu phụ đề", open=True):
                    current_auto = _load_config().get("caption", {}).get("style", {}).get("auto_position", True)
                    s_cap_auto = gr.Checkbox(
                        label="🤖  Tự động (khớp vị trí & kích thước sub gốc)",
                        value=current_auto,
                        info="Bật = pipeline tự tính. Tắt = dùng cài đặt thủ công bên dưới",
                    )

                    # Preset chooser
                    preset_choice = gr.Dropdown(
                        label="🎨  Preset có sẵn (chọn để auto fill)",
                        choices=[
                            ("— Tùy chỉnh —", "custom"),
                            ("🎬 Cinematic (trắng, viền dày, Arial)", "cinematic"),
                            ("⚪ Minimal (trắng gọn, viền mỏng)", "minimal"),
                            ("🟡 TikTok Style (vàng, nền đen mờ)", "tiktok"),
                            ("📰 News/Tin tức (nền đen, viền vàng)", "news"),
                            ("🌸 Anime/Bubble (hồng pastel, bóng)", "anime"),
                            ("🔥 Bold Impact (đỏ to, viền trắng)", "bold"),
                            ("💎 Elegant (trắng ngà, Georgia)", "elegant"),
                            ("🎮 Gaming (xanh neon, glow)", "gaming"),
                        ],
                        value="custom",
                        info="Chọn preset → các trường dưới tự cập nhật",
                    )

                    with gr.Row():
                        s_cap_font = gr.Textbox(
                            label="Font chữ",
                            value=cap_font,
                        )
                        s_cap_size = gr.Number(
                            label="Cỡ chữ",
                            value=cap_size,
                            minimum=12,
                            maximum=72,
                        )
                        s_cap_color = gr.Textbox(
                            label="Màu chữ (ASS format)",
                            value=cap_color,
                        )

                    with gr.Row():
                        s_cap_outline = gr.Number(
                            label="Độ dày viền",
                            value=cap_outline,
                            minimum=0,
                            maximum=10,
                        )
                        s_cap_margin = gr.Number(
                            label="Khoảng cách dưới (px)",
                            value=cap_margin,
                            minimum=0,
                            maximum=200,
                        )
                        s_cap_align = gr.Dropdown(
                            label="Vị trí",
                            choices=[
                                ("Giữa dưới", 2),
                                ("Trái dưới", 1),
                                ("Phải dưới", 3),
                                ("Giữa trên", 8),
                            ],
                            value=cap_align,
                        )

                    gr.HTML("""
                    <div class="section-title" style="margin-top: 12px;">
                        Xem truoc
                    </div>
                    """)

                    caption_preview = gr.HTML(
                        value=_build_caption_preview(cap_font, cap_size, cap_color, cap_outline, cap_margin, cap_align),
                    )

                    for _comp in [s_cap_font, s_cap_size, s_cap_color, s_cap_outline, s_cap_margin, s_cap_align]:
                        _comp.change(
                            fn=_build_caption_preview,
                            inputs=[s_cap_font, s_cap_size, s_cap_color, s_cap_outline, s_cap_margin, s_cap_align],
                            outputs=[caption_preview],
                        )

                    # Preset handler - apply preset to all fields
                    def _apply_preset(preset_key):
                        presets = {
                            "cinematic": {
                                "font": "Arial", "size": 22, "color": "&HFFFFFF",
                                "outline": 3, "margin_v": 40, "align": 2,
                            },
                            "minimal": {
                                "font": "Arial", "size": 18, "color": "&HFFFFFF",
                                "outline": 1, "margin_v": 30, "align": 2,
                            },
                            "tiktok": {
                                "font": "Arial Black", "size": 24, "color": "&H00F3FF",
                                "outline": 2, "margin_v": 35, "align": 2,
                            },
                            "news": {
                                "font": "Arial", "size": 20, "color": "&H00FFFF",
                                "outline": 3, "margin_v": 25, "align": 2,
                            },
                            "anime": {
                                "font": "Comic Sans MS", "size": 22, "color": "&HC0B4FF",
                                "outline": 2, "margin_v": 40, "align": 2,
                            },
                            "bold": {
                                "font": "Impact", "size": 28, "color": "&H0000FF",
                                "outline": 3, "margin_v": 40, "align": 2,
                            },
                            "elegant": {
                                "font": "Georgia", "size": 20, "color": "&HF0F0FF",
                                "outline": 1, "margin_v": 35, "align": 2,
                            },
                            "gaming": {
                                "font": "Consolas", "size": 22, "color": "&HFFFF00",
                                "outline": 2, "margin_v": 30, "align": 2,
                            },
                        }
                        p = presets.get(preset_key)
                        if not p:
                            # "custom" - don't change anything, return current
                            return (gr.update(), gr.update(), gr.update(),
                                    gr.update(), gr.update(), gr.update())
                        return (p["font"], p["size"], p["color"],
                                p["outline"], p["margin_v"], p["align"])

                    preset_choice.change(
                        fn=_apply_preset,
                        inputs=[preset_choice],
                        outputs=[s_cap_font, s_cap_size, s_cap_color,
                                 s_cap_outline, s_cap_margin, s_cap_align],
                    )

                # Audio
                with gr.Accordion("🎧  Âm thanh", open=False):
                    with gr.Row():
                        s_bg_volume = gr.Slider(
                            label="Âm lượng nhạc nền",
                            minimum=0.0,
                            maximum=1.0,
                            step=0.05,
                            value=bg_vol,
                        )
                        s_audio_bitrate = gr.Dropdown(
                            label="Bitrate",
                            choices=["128k", "192k", "256k", "320k"],
                            value=audio_br,
                        )

                # Upload
                with gr.Accordion("☁  Upload", open=False):
                    with gr.Row():
                        s_upload_tiktok = gr.Checkbox(
                            label="TikTok",
                            value=up_tiktok,
                        )
                        s_upload_youtube = gr.Checkbox(
                            label="YouTube",
                            value=up_youtube,
                        )

                    s_tiktok_tags = gr.Textbox(
                        label="TikTok tags mặc định",
                        value=tt_tags,
                    )

                    s_youtube_privacy = gr.Dropdown(
                        label="YouTube privacy",
                        choices=["private", "unlisted", "public"],
                        value=yt_privacy,
                    )

                # Scheduler
                with gr.Accordion("🕑  Hẹn giờ tự động", open=False):
                    s_scheduler_enabled = gr.Checkbox(
                        label="Bật hẹn giờ",
                        value=sch_enabled,
                    )
                    with gr.Row():
                        s_scheduler_cron = gr.Textbox(
                            label="Cron expression",
                            value=sch_cron,
                            info="Ví dụ: '0 8 * * *' = mỗi ngày lúc 8h sáng",
                        )
                        s_scheduler_file = gr.Textbox(
                            label="File URL",
                            value=sch_file,
                        )

                # Save button
                with gr.Row():
                    save_settings_btn = gr.Button(
                        "💾  Lưu cấu hình",
                        variant="primary",
                        size="lg",
                        elem_classes=["btn-action-lg"],
                    )

                settings_save_msg = gr.HTML(value="")

                save_settings_btn.click(
                    fn=lambda *args: f"""
                    <div class="save-success">
                        <span class="check-icon">✓</span>
                        {save_settings(*args)}
                    </div>
                    """,
                    inputs=[
                        s_cap_auto,
                        s_cap_font, s_cap_size, s_cap_color, s_cap_outline,
                        s_cap_margin, s_cap_align,
                        s_bg_volume, s_audio_bitrate,
                        s_upload_tiktok, s_upload_youtube,
                        s_tiktok_tags, s_youtube_privacy,
                        s_scheduler_enabled, s_scheduler_cron, s_scheduler_file,
                    ],
                    outputs=[settings_save_msg],
                )

    return app


# ==============================================================================
#  MAIN
# ==============================================================================

if __name__ == "__main__":
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
