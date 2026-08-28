"""Full pipeline test for video 7126425581691931935"""
import sys
import io
import asyncio
import subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

work_dir = Path("workspace")
video_id = "7126425581691931935"

print("=== FULL PIPELINE TEST ===\n")

# Step 1: Download (already done)
video_path = work_dir / "downloads" / f"{video_id}.mp4"
print(f"[1] Video: {video_path} ({video_path.stat().st_size / 1024 / 1024:.1f} MB)")

# Step 2: STT (already done)
srt_path = work_dir / "srt" / f"{video_id}_original.srt"
print(f"[2] SRT: {srt_path} (exists: {srt_path.exists()})")

# Step 3: Translate (already done)
translated_srt = work_dir / "srt" / f"{video_id}_vi.srt"
print(f"[3] Translated: {translated_srt} (exists: {translated_srt.exists()})")

# Step 4: TTS
print("[4] Generating full TTS...")
import edge_tts

segments = []
with open(translated_srt, encoding="utf-8") as f:
    blocks = f.read().strip().split("\n\n")
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            segments.append({"ts": lines[1], "text": lines[2]})

tts_dir = work_dir / "tts"
tts_dir.mkdir(exist_ok=True)


async def gen_all_tts():
    ok = 0
    for i, seg in enumerate(segments):
        out = tts_dir / f"{i:04d}.mp3"
        if out.exists() and out.stat().st_size > 0:
            ok += 1
            continue
        text = seg["text"].strip()
        if len(text) < 2:
            text = "..."  # edge-tts needs some text
        try:
            communicate = edge_tts.Communicate(text, "vi-VN-HoaiMyNeural")
            await communicate.save(str(out))
            ok += 1
        except Exception as e:
            print(f"    TTS failed for segment {i}: {e}")
            # Generate silence as fallback
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i",
                 "anullsrc=r=44100:cl=stereo", "-t", "1",
                 "-c:a", "libmp3lame", str(out)],
                capture_output=True,
            )
            ok += 1
    print(f"    Generated {ok}/{len(segments)} TTS segments")


asyncio.run(gen_all_tts())

# Concat TTS
valid_tts = []
for i in range(len(segments)):
    p = tts_dir / f"{i:04d}.mp3"
    if p.exists() and p.stat().st_size > 0:
        valid_tts.append(p)

concat_list = tts_dir / "concat.txt"
with open(concat_list, "w", encoding="utf-8") as f:
    for p in valid_tts:
        safe = str(p.resolve()).replace("\\", "/")
        f.write(f"file '{safe}'\n")

tts_full = tts_dir / "tts_full.wav"
subprocess.run(
    ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
     "-i", str(concat_list), "-c:a", "pcm_s16le", str(tts_full)],
    capture_output=True,
)
print(f"    Full TTS: {tts_full} (exists: {tts_full.exists()})")

# Step 5-6: Skip caption detect/blur
print("[5-6] Skipping caption detect/blur (PaddleOCR not installed)")

# Step 7: Burn subtitles
print("[7] Burning translated subtitles...")
output_dir = work_dir / "output"
output_dir.mkdir(exist_ok=True)

srt_safe = str(translated_srt).replace("\\", "/").replace(":", "\\:")
captioned = output_dir / "captioned.mp4"
r = subprocess.run(
    ["ffmpeg", "-y", "-i", str(video_path),
     "-vf", f"subtitles='{srt_safe}':force_style='FontName=Arial,FontSize=20,"
            f"PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,"
            f"Shadow=1,MarginV=30,Alignment=2'",
     "-c:a", "copy", "-preset", "fast", str(captioned)],
    capture_output=True, text=True,
)
if captioned.exists():
    print(f"    Captioned: {captioned} ({captioned.stat().st_size / 1024 / 1024:.1f} MB)")
else:
    print(f"    Burn subtitle failed: {r.stderr[-300:]}")
    captioned = None

# Step 8: Audio separation
print("[8] Separating audio with Demucs (htdemucs)...")
sep_dir = work_dir / "separated"
sep_dir.mkdir(exist_ok=True)

instrumental = sep_dir / "htdemucs" / video_id / "no_vocals.wav"
if not instrumental.exists():
    try:
        # Extract audio as WAV first (demucs has issues with MP4 save)
        audio_wav = sep_dir / f"{video_id}.wav"
        if not audio_wav.exists():
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(video_path),
                 "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                 str(audio_wav)],
                capture_output=True,
            )
        import demucs.separate
        demucs.separate.main([
            "--two-stems", "vocals",
            "-n", "htdemucs",
            "-o", str(sep_dir),
            str(audio_wav),
        ])
        # Demucs uses filename as stem
        alt_instrumental = sep_dir / "htdemucs" / video_id / "no_vocals.wav"
        if not alt_instrumental.exists():
            # Check if named differently
            for f in (sep_dir / "htdemucs").rglob("no_vocals.wav"):
                instrumental = f
                break
    except Exception as e:
        print(f"    Demucs failed: {e}")
        instrumental = None

if instrumental and instrumental.exists():
    print(f"    Instrumental: {instrumental.exists()}")
else:
    print("    No instrumental track")

# Step 9: Mix audio
mixed = output_dir / "mixed_audio.wav"
if instrumental and instrumental.exists():
    print("[9] Mixing TTS + instrumental...")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(tts_full), "-i", str(instrumental),
         "-filter_complex",
         "[1:a]volume=0.3[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2",
         "-ac", "2", str(mixed)],
        capture_output=True,
    )
    print(f"    Mixed: {mixed.exists()}")
else:
    mixed = tts_full
    print("[9] Using TTS only (no instrumental)")

# Step 10: Final compose
print("[10] Composing final video...")
final = output_dir / f"final_{video_id}_vi.mp4"
src_video = captioned if captioned and captioned.exists() else video_path

r = subprocess.run(
    ["ffmpeg", "-y",
     "-i", str(src_video), "-i", str(mixed),
     "-map", "0:v", "-map", "1:a",
     "-c:v", "libx264", "-preset", "fast", "-crf", "20",
     "-c:a", "aac", "-b:a", "192k",
     "-movflags", "+faststart", "-pix_fmt", "yuv420p",
     "-shortest",
     str(final)],
    capture_output=True, text=True,
)

if final.exists():
    size = final.stat().st_size / 1024 / 1024
    print(f"    FINAL: {final} ({size:.1f} MB)")
else:
    print(f"    FAILED: {r.stderr[-500:]}")

print("\n=== PIPELINE TEST COMPLETE ===")
