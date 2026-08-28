import asyncio
import subprocess
from pathlib import Path

from src.steps.base import BaseStep
from src.utils.srt import parse_srt
from src.utils.ffmpeg import get_duration, run_ffmpeg


class TTSGenerator(BaseStep):
    def _get_provider(self) -> str:
        """Return the configured TTS provider name."""
        return self.config["tts"].get("provider", "edge-tts")

    def _init_kokoro(self):
        """Lazily initialise kokoro-onnx and cache the instance."""
        if not hasattr(self, "_kokoro"):
            import kokoro_onnx
            model_path = self.config["tts"].get("kokoro_model", "models/kokoro-v1.0.onnx")
            voices_path = self.config["tts"].get("kokoro_voices", "models/voices-v1.0.bin")
            self._kokoro = kokoro_onnx.Kokoro(model_path, voices_path)
        return self._kokoro

    async def _generate_segment_edge(self, text: str, voice: str, output_path: Path) -> bool:
        """Generate a single TTS segment with edge-tts. Returns True on success."""
        import edge_tts

        for attempt in range(3):
            try:
                comm = edge_tts.Communicate(text, voice)
                await comm.save(str(output_path))
                if output_path.exists() and output_path.stat().st_size > 100:
                    return True
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(1)
        return False

    def _generate_segment_kokoro(self, text: str, output_path: Path) -> bool:
        """Generate a single TTS segment with Kokoro. Returns True on success."""
        import soundfile as sf

        try:
            kokoro = self._init_kokoro()
            voice = self.config["tts"].get("kokoro_voice", "af_heart")
            speed = self.config["tts"].get("kokoro_speed", 1.0)
            samples, sr = kokoro.create(text, voice=voice, speed=float(speed))
            sf.write(str(output_path), samples, sr)
            return output_path.exists() and output_path.stat().st_size > 100
        except Exception as e:
            self.log(f"  Kokoro TTS error: {e}")
            return False

    async def run(self, translated_srt: Path, target_lang: str) -> dict:
        provider = self._get_provider()

        segments = parse_srt(str(translated_srt))

        # Resolve voice depending on provider
        if provider == "kokoro":
            kokoro_voice = self.config["tts"].get("kokoro_voice", "af_heart")
            voice_label = f"kokoro/{kokoro_voice}"
        else:
            voice = self.config["tts"]["voices"].get(target_lang)
            if not voice:
                raise ValueError(f"No TTS voice configured for language: {target_lang}")
            voice_label = voice

        # Use per-video TTS directory to avoid mixing segments across videos
        video_key = translated_srt.stem.replace("_vi", "").replace("_en", "") \
            .replace("_ja", "").replace("_ko", "").replace("_th", "").replace("_id", "")
        tts_dir = self.ensure_dir(f"tts/{video_key}_{target_lang}")

        # Clean any stale files from previous runs
        for old in tts_dir.glob("*.mp3"):
            old.unlink()
        for old in tts_dir.glob("*.wav"):
            old.unlink()

        max_speed = self.config["tts"].get("max_speed", 2.5)

        self.log(f"Generating TTS for {len(segments)} segments (provider: {provider}, voice: {voice_label})")

        # Get video duration for building full audio track
        video_duration = max(seg["end"] for seg in segments) + 1.0

        # Phase 1a: Generate raw TTS in PARALLEL (edge-tts) or sequential (kokoro)
        raw_ext = ".wav" if provider == "kokoro" else ".mp3"

        async def gen_one(i, seg):
            raw_file = tts_dir / f"{i:04d}_raw{raw_ext}"
            final_file = tts_dir / f"{i:04d}.mp3"
            if final_file.exists() and final_file.stat().st_size > 100:
                return i, raw_file, final_file, True
            text = seg["text"].strip()
            if len(text) < 2:
                text = "..."
            if provider == "kokoro":
                generated = self._generate_segment_kokoro(text, raw_file)
            else:
                generated = await self._generate_segment_edge(text, voice, raw_file)
            if not generated:
                self._generate_silence_mp3(str(raw_file), 0.5)
                self.log(f"  [{i}] TTS failed, using silence")
            return i, raw_file, final_file, True

        # Batch in chunks of 8 for concurrent edge-tts (avoid rate limit)
        BATCH_SIZE = 8 if provider != "kokoro" else 1
        results = []
        for batch_start in range(0, len(segments), BATCH_SIZE):
            batch = segments[batch_start:batch_start + BATCH_SIZE]
            tasks = [gen_one(batch_start + j, seg) for j, seg in enumerate(batch)]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in batch_results:
                if isinstance(r, Exception):
                    self.log(f"  TTS batch error: {r}")
                else:
                    results.append(r)

        # Phase 1b: Speed-adjust each segment (sequential FFmpeg calls)
        for i, raw_file, final_file, _ in results:
            if final_file.exists() and final_file.stat().st_size > 100 and final_file != raw_file:
                continue
            seg = segments[i]
            target_dur = seg["end"] - seg["start"]
            tts_dur = get_duration(str(raw_file))

            if tts_dur <= 0 or target_dur <= 0:
                self._copy_file(str(raw_file), str(final_file))
                continue

            ratio = tts_dur / target_dur
            if ratio > 1.1:
                speed = min(ratio, max_speed)
                self._adjust_speed(str(raw_file), str(final_file), speed)
            elif ratio < 0.7:
                self._pad_audio(str(raw_file), str(final_file), target_dur)
            else:
                self._copy_file(str(raw_file), str(final_file))

        # Phase 2: Build full synced audio track using adelay
        self.log("Building synced audio track...")
        synced_audio = tts_dir / "tts_synced.wav"
        self._build_synced_track(segments, tts_dir, synced_audio, video_duration)

        self.log(f"TTS complete: {synced_audio.name} ({get_duration(str(synced_audio)):.1f}s)")
        return {"tts_audio": synced_audio}

    def _build_synced_track(self, segments, tts_dir, output_path, total_duration):
        """Place each TTS segment at correct timestamp.

        For videos with many segments (>50), process in chunks to avoid
        FFmpeg command line length limits on Windows.
        """
        CHUNK_SIZE = 40  # Max segments per FFmpeg call

        # Collect valid segment files
        valid = []
        for i, seg in enumerate(segments):
            f = tts_dir / f"{i:04d}.mp3"
            if f.exists() and f.stat().st_size >= 100:
                valid.append((i, seg, f))

        if not valid:
            silence = tts_dir / "silence_base.wav"
            run_ffmpeg([
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(total_duration), "-c:a", "pcm_s16le", str(silence),
            ])
            self._copy_file(str(silence), str(output_path))
            return

        if len(valid) <= CHUNK_SIZE:
            # Small enough for single FFmpeg call
            self._merge_chunk(valid, tts_dir, output_path, total_duration)
        else:
            # Process in chunks, then merge chunks
            chunk_files = []
            for ci in range(0, len(valid), CHUNK_SIZE):
                chunk = valid[ci:ci + CHUNK_SIZE]
                chunk_out = tts_dir / f"chunk_{ci // CHUNK_SIZE}.wav"
                self._merge_chunk(chunk, tts_dir, chunk_out, total_duration)
                chunk_files.append(chunk_out)

            # Merge all chunks by averaging
            if len(chunk_files) == 1:
                self._copy_file(str(chunk_files[0]), str(output_path))
            else:
                inputs = []
                for f in chunk_files:
                    inputs.extend(["-i", str(f)])
                n = len(chunk_files)
                run_ffmpeg(
                    inputs + [
                        "-filter_complex",
                        "".join(f"[{i}:a]" for i in range(n))
                        + f"amix=inputs={n}:duration=first:normalize=0[out]",
                        "-map", "[out]", "-c:a", "pcm_s16le",
                        "-t", str(total_duration), str(output_path),
                    ]
                )

    def _merge_chunk(self, valid_segments, tts_dir, output_path, total_duration):
        """Merge a chunk of segments into a single audio track."""
        silence = tts_dir / "silence_base.wav"
        if not silence.exists():
            run_ffmpeg([
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(total_duration), "-c:a", "pcm_s16le", str(silence),
            ])

        inputs = ["-i", str(silence)]
        filter_parts = []
        input_idx = 1

        for i, seg, f in valid_segments:
            inputs.extend(["-i", str(f)])
            delay_ms = int(seg["start"] * 1000)
            filter_parts.append(
                f"[{input_idx}:a]adelay={delay_ms}|{delay_ms}[d{input_idx}]"
            )
            input_idx += 1

        mix_inputs = "[0:a]" + "".join(
            f"[d{j}]" for j in range(1, input_idx)
        )
        filter_parts.append(
            f"{mix_inputs}amix=inputs={input_idx}:duration=first:normalize=0[out]"
        )

        run_ffmpeg(
            inputs + [
                "-filter_complex", ";".join(filter_parts),
                "-map", "[out]", "-c:a", "pcm_s16le",
                "-t", str(total_duration), str(output_path),
            ]
        )

    def _adjust_speed(self, input_path, output_path, speed):
        """Speed up audio. Chain atempo filters for speed > 2.0."""
        filters = []
        remaining = speed
        while remaining > 2.0:
            filters.append("atempo=2.0")
            remaining /= 2.0
        filters.append(f"atempo={remaining:.4f}")

        run_ffmpeg([
            "-i", input_path,
            "-filter:a", ",".join(filters),
            output_path,
        ])

    def _pad_audio(self, input_path, output_path, target_duration):
        """Pad audio with silence to reach target duration."""
        run_ffmpeg([
            "-i", input_path,
            "-af", f"apad=pad_dur={target_duration}",
            "-t", str(target_duration),
            output_path,
        ])

    def _generate_silence_mp3(self, output_path, duration):
        run_ffmpeg([
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration), "-c:a", "libmp3lame", output_path,
        ])

    def _copy_file(self, src, dst):
        run_ffmpeg(["-i", src, dst])
