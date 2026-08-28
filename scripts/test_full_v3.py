"""Full pipeline test v3 - with Demucs + PaddleOCR + timing sync"""
import sys, io, subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.utils.ffmpeg import get_duration

config = load_config("config/default.yaml")
work_dir = Path("workspace")
video_id = "7126425581691931935"
video_path = work_dir / "downloads" / f"{video_id}.mp4"
translated_srt = work_dir / "srt" / f"{video_id}_vi.srt"
output_dir = work_dir / "output"
output_dir.mkdir(exist_ok=True)

print("=== FULL PIPELINE v3 ===\n")

# Step 5: PaddleOCR detect caption
print("[5] Detecting captions with PaddleOCR...")
from src.steps.caption_detector import CaptionDetector
detector = CaptionDetector(config, work_dir)
detect_result = detector.run(video_path=video_path)
caption_region = detect_result["caption_region"]
print(f"    Region: {caption_region}")

# Step 6: Blur old caption
print("[6] Blurring old captions...")
from src.steps.caption_blur import CaptionBlur
blur = CaptionBlur(config, work_dir)
blur_result = blur.run(video_path=video_path, caption_region=caption_region)
blurred_video = blur_result["blurred_video"]
print(f"    Blurred: {blurred_video}")

# Step 7: Burn new subtitles on blurred video
print("[7] Burning translated subtitles...")
from src.steps.caption_writer import CaptionWriter
writer = CaptionWriter(config, work_dir)
cap_result = writer.run(video_path=blurred_video, translated_srt=translated_srt)
captioned_video = cap_result["captioned_video"]
print(f"    Captioned: {captioned_video}")

# Step 8: Audio separation with soundfile save
print("[8] Separating audio (Demucs + soundfile)...")
from src.steps.audio_separator import AudioSeparator
separator = AudioSeparator(config, work_dir)
sep_result = separator.run(video_path=video_path)
instrumental = sep_result["instrumental"]
print(f"    Instrumental: {instrumental} (exists: {instrumental.exists()})")

# Step 9: Mix TTS + instrumental
tts_synced = work_dir / "tts_v2" / "tts_synced.wav"
if not tts_synced.exists():
    print("    [!] Run test_pipeline_v2.py first for TTS")
    sys.exit(1)

print("[9] Mixing TTS + instrumental...")
from src.steps.audio_mixer import AudioMixer
mixer = AudioMixer(config, work_dir)
mix_result = mixer.run(tts_audio=tts_synced, instrumental=instrumental)
mixed_audio = mix_result["mixed_audio"]
print(f"    Mixed: {mixed_audio}")

# Step 10: Final compose with logo
print("[10] Composing final video...")
from src.steps.composer import Composer
logo = Path("assets/logo.png")
composer = Composer(config, work_dir)
final_result = composer.run(
    captioned_video=captioned_video,
    mixed_audio=mixed_audio,
    logo=logo if logo.exists() else None,
)
final = final_result["final_video"]
size = final.stat().st_size / 1024 / 1024
dur = get_duration(str(final))
print(f"    FINAL: {final} ({size:.1f} MB, {dur:.1f}s)")

print("\n=== DONE ===")
