"""Full pipeline test v2 - with proper TTS timing sync"""
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
output_dir = work_dir / "output"
output_dir.mkdir(exist_ok=True)


def get_duration(filepath):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(filepath)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except:
        return 0.0


def parse_srt_timestamps(srt_path):
    """Parse SRT into list of {start_sec, end_sec, text}."""
    segments = []
    with open(srt_path, encoding="utf-8") as f:
        blocks = f.read().strip().split("\n\n")
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue
            ts = lines[1]
            start_str, end_str = ts.split(" --> ")
            segments.append({
                "start": ts_to_sec(start_str.strip()),
                "end": ts_to_sec(end_str.strip()),
                "text": lines[2],
            })
    return segments


def ts_to_sec(ts):
    """HH:MM:SS,mmm -> seconds"""
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])


print("=== PIPELINE TEST v2 - TIMING SYNC ===\n")

video_path = work_dir / "downloads" / f"{video_id}.mp4"
translated_srt = work_dir / "srt" / f"{video_id}_vi.srt"
video_duration = get_duration(str(video_path))
print(f"Video: {video_path.name} ({video_duration:.1f}s)")

segments = parse_srt_timestamps(str(translated_srt))
print(f"Segments: {len(segments)}")

# Step 4: TTS with timing
print("\n[4] Generating TTS with timing sync...")
import edge_tts

tts_dir = work_dir / "tts_v2"
tts_dir.mkdir(exist_ok=True)


async def gen_tts_synced():
    for i, seg in enumerate(segments):
        raw_file = tts_dir / f"{i:04d}_raw.mp3"
        final_file = tts_dir / f"{i:04d}.mp3"

        # Generate TTS
        if not raw_file.exists() or raw_file.stat().st_size == 0:
            text = seg["text"].strip()
            if len(text) < 2:
                text = "..."
            try:
                comm = edge_tts.Communicate(text, "vi-VN-HoaiMyNeural")
                await comm.save(str(raw_file))
            except Exception as e:
                print(f"    [{i}] TTS failed: {e}")
                # Generate 0.5s silence as placeholder
                subprocess.run(
                    ["ffmpeg", "-y", "-f", "lavfi", "-i",
                     "anullsrc=r=44100:cl=stereo", "-t", "0.5",
                     "-c:a", "libmp3lame", str(raw_file)],
                    capture_output=True,
                )

        # Adjust speed to match subtitle duration
        target_duration = seg["end"] - seg["start"]
        tts_duration = get_duration(str(raw_file))

        if tts_duration <= 0 or target_duration <= 0:
            # Just copy
            if not final_file.exists():
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(raw_file), str(final_file)],
                    capture_output=True,
                )
            continue

        ratio = tts_duration / target_duration

        if ratio > 1.1:
            # TTS too slow -> speed up
            speed = min(ratio, 2.5)
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(raw_file),
                 "-filter:a", f"atempo={min(speed, 2.0)}" +
                 (f",atempo={speed / 2.0}" if speed > 2.0 else ""),
                 str(final_file)],
                capture_output=True,
            )
            actual = get_duration(str(final_file))
            print(f"    [{i}] {seg['text'][:20]}... speed {speed:.1f}x ({tts_duration:.1f}s -> {actual:.1f}s / target {target_duration:.1f}s)")
        elif ratio < 0.7:
            # TTS too fast -> pad silence at end
            pad = target_duration - tts_duration
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(raw_file),
                 "-af", f"apad=pad_dur={pad}",
                 "-t", str(target_duration),
                 str(final_file)],
                capture_output=True,
            )
        else:
            # Close enough, just copy
            if not final_file.exists():
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(raw_file), str(final_file)],
                    capture_output=True,
                )

    print(f"    Done: {len(segments)} segments adjusted")


asyncio.run(gen_tts_synced())

# Build full audio track with silence gaps at correct positions
print("\n[4b] Building synced audio track...")
# Use ffmpeg to create a full-length silent track, then overlay each segment at its timestamp
silence_track = tts_dir / "silence_base.wav"
subprocess.run(
    ["ffmpeg", "-y", "-f", "lavfi", "-i",
     f"anullsrc=r=44100:cl=stereo",
     "-t", str(video_duration),
     "-c:a", "pcm_s16le", str(silence_track)],
    capture_output=True,
)

# Build complex filter to overlay all segments at correct timestamps
filter_parts = []
inputs = ["-i", str(silence_track)]
for i, seg in enumerate(segments):
    final_file = tts_dir / f"{i:04d}.mp3"
    if final_file.exists() and final_file.stat().st_size > 0:
        inputs.extend(["-i", str(final_file)])

# Build amerge filter chain
# [0] is silence base, [1],[2],... are TTS segments
active_inputs = []
input_idx = 1
for i, seg in enumerate(segments):
    final_file = tts_dir / f"{i:04d}.mp3"
    if final_file.exists() and final_file.stat().st_size > 0:
        delay_ms = int(seg["start"] * 1000)
        filter_parts.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms}[d{i}]")
        active_inputs.append(f"[d{i}]")
        input_idx += 1

# Mix all together
if active_inputs:
    all_inputs = "[0:a]" + "".join(active_inputs)
    n = len(active_inputs) + 1
    filter_parts.append(f"{all_inputs}amix=inputs={n}:duration=first:normalize=0[out]")
    filter_str = ";".join(filter_parts)

    tts_synced = tts_dir / "tts_synced.wav"
    cmd = (
        ["ffmpeg", "-y"] + inputs +
        ["-filter_complex", filter_str,
         "-map", "[out]",
         "-c:a", "pcm_s16le",
         "-t", str(video_duration),
         str(tts_synced)]
    )
    r = subprocess.run(cmd, capture_output=True, text=True)
    if tts_synced.exists():
        print(f"    Synced TTS: {tts_synced} ({get_duration(str(tts_synced)):.1f}s)")
    else:
        print(f"    FAILED: {r.stderr[-300:]}")
        tts_synced = None
else:
    tts_synced = None
    print("    No valid TTS segments")

# Step 7: Burn subtitles (reuse existing)
captioned = output_dir / "captioned.mp4"
print(f"\n[7] Captioned video: {captioned} (exists: {captioned.exists()})")

# Step 10: Final compose with synced audio
print("\n[10] Composing final video with synced TTS...")
final = output_dir / f"final_{video_id}_vi_v2.mp4"
audio_src = tts_synced if tts_synced and tts_synced.exists() else None

if audio_src and captioned.exists():
    r = subprocess.run(
        ["ffmpeg", "-y",
         "-i", str(captioned), "-i", str(audio_src),
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
        dur = get_duration(str(final))
        print(f"    FINAL: {final} ({size:.1f} MB, {dur:.1f}s)")
    else:
        print(f"    FAILED: {r.stderr[-500:]}")
else:
    print("    Missing audio or video source")

print("\n=== DONE ===")
