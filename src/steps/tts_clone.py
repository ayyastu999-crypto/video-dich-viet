"""Voice cloning TTS using F5-TTS.

Clone the original speaker's voice from the video, then generate
translated speech that sounds like the original speaker.
"""
import asyncio
import subprocess
from pathlib import Path

from src.steps.base import BaseStep
from src.utils.srt import parse_srt
from src.utils.ffmpeg import get_duration, run_ffmpeg


class TTSCloneGenerator(BaseStep):
    """Generate dubbed audio using voice cloning (F5-TTS).

    Flow:
    1. Extract reference audio from original video (vocal track from Demucs)
    2. Use F5-TTS to clone voice and generate translated speech
    3. Adjust timing to match subtitle timestamps
    4. Build synced audio track
    """

    def __init__(self, config, work_dir):
        super().__init__(config, work_dir)
        self._model = None

    def _get_model(self):
        if self._model is None:
            self._patch_torchaudio()
            from f5_tts.api import F5TTS
            self._model = F5TTS(model="F5TTS_v1_Base", device="cuda")
        return self._model

    @staticmethod
    def _patch_torchaudio():
        """Replace torchaudio load/save with soundfile (torchcodec broken on Windows)."""
        import torch
        import numpy as np
        import soundfile as sf
        import torchaudio

        def sf_load(filepath, *args, **kwargs):
            data, sr = sf.read(str(filepath), dtype="float32")
            tensor = torch.from_numpy(np.array(data))
            if tensor.dim() == 1:
                tensor = tensor.unsqueeze(0)
            else:
                tensor = tensor.T
            return tensor, sr

        def sf_save(filepath, src, sample_rate, *args, **kwargs):
            data = src.cpu().numpy()
            if data.ndim == 2:
                data = data.T
            sf.write(str(filepath), data, sample_rate)

        # Override at module level - catches all internal calls
        torchaudio.load = sf_load
        torchaudio.save = sf_save
        # Also patch the internal references F5-TTS may use
        torchaudio.load_with_torchcodec = sf_load
        torchaudio.save_with_torchcodec = sf_save
        # Patch the _torchcodec module if it exists
        if hasattr(torchaudio, '_torchcodec'):
            torchaudio._torchcodec.load_with_torchcodec = sf_load
            torchaudio._torchcodec.save_with_torchcodec = sf_save

    def run(self, translated_srt: Path, original_srt: Path,
            vocals_path: Path, target_lang: str) -> dict:
        """Generate voice-cloned TTS audio.

        Args:
            translated_srt: Path to translated SRT file
            original_srt: Path to original Chinese SRT file
            vocals_path: Path to extracted vocals WAV (from Demucs)
            target_lang: Target language code
        """
        tts_dir = self.ensure_dir("tts_clone")
        translated_segments = parse_srt(str(translated_srt))
        original_segments = parse_srt(str(original_srt))

        if not translated_segments:
            raise ValueError(f"No segments in {translated_srt}")

        self.log(f"Voice cloning TTS: {len(translated_segments)} segments")

        # Step 1: Extract ONE long reference clip (best 10-15s)
        ref_clip, ref_text = self._extract_best_reference(
            vocals_path, original_segments, tts_dir
        )

        # Step 2: Generate cloned speech for each segment
        model = self._get_model()
        video_duration = max(s["end"] for s in translated_segments) + 1.0
        max_speed = self.config["tts"].get("max_speed", 2.5)

        for i, (trans_seg, orig_seg) in enumerate(
            zip(translated_segments, original_segments)
        ):
            final_file = tts_dir / f"{i:04d}.wav"
            if final_file.exists() and final_file.stat().st_size > 100:
                continue

            if not ref_clip or not ref_clip.exists():
                self._fallback_edge_tts(
                    trans_seg["text"], target_lang, str(final_file)
                )
                continue

            raw_file = tts_dir / f"{i:04d}_raw.wav"
            try:
                # F5-TTS voice clone - same reference for ALL segments
                wav, sr, _ = model.infer(
                    ref_file=str(ref_clip),
                    ref_text=ref_text,
                    gen_text=trans_seg["text"],
                    file_wave=str(raw_file),
                    nfe_step=48,  # higher = better quality
                    cfg_strength=2.5,
                    seed=-1,
                )

                # Adjust speed to match timing
                target_dur = trans_seg["end"] - trans_seg["start"]
                tts_dur = get_duration(str(raw_file))

                if tts_dur > 0 and target_dur > 0:
                    ratio = tts_dur / target_dur
                    if ratio > 1.1:
                        speed = min(ratio, max_speed)
                        self._adjust_speed(str(raw_file), str(final_file), speed)
                    else:
                        self._copy(str(raw_file), str(final_file))
                else:
                    self._copy(str(raw_file), str(final_file))

            except Exception as e:
                self.log(f"  [{i}] Clone failed: {e}, fallback to edge-tts")
                self._fallback_edge_tts(
                    trans_seg["text"], target_lang, str(final_file)
                )

        # Step 3: Build synced audio track
        self.log("Building synced audio track...")
        synced_audio = tts_dir / "tts_clone_synced.wav"
        self._build_synced_track(translated_segments, tts_dir, synced_audio, video_duration)

        self.log(f"Voice clone TTS complete: {synced_audio.name}")
        return {"tts_audio": synced_audio}

    def _extract_best_reference(self, vocals_path, segments, output_dir):
        """Extract the best 10-15s reference clip from vocals.

        Picks the longest consecutive segments with clear speech.
        Returns (clip_path, ref_text).
        """
        ref_path = output_dir / "reference.wav"
        if ref_path.exists() and ref_path.stat().st_size > 1000:
            # Load cached ref text
            ref_text_file = output_dir / "reference_text.txt"
            ref_text = ref_text_file.read_text(encoding="utf-8") if ref_text_file.exists() else ""
            self.log(f"  Using cached reference: {ref_path.name}")
            return ref_path, ref_text

        # Find best 10-15s window with longest speech
        target_duration = 12.0
        best_start = 0
        best_end = 0
        best_text = ""
        best_speech_time = 0

        for i, seg in enumerate(segments):
            # Accumulate from this segment
            total_speech = 0
            texts = []
            for j in range(i, len(segments)):
                window_dur = segments[j]["end"] - seg["start"]
                if window_dur > target_duration + 3:
                    break
                speech_dur = segments[j]["end"] - segments[j]["start"]
                total_speech += speech_dur
                texts.append(segments[j]["text"])

                if total_speech > best_speech_time and window_dur >= 5:
                    best_speech_time = total_speech
                    best_start = seg["start"]
                    best_end = segments[j]["end"]
                    best_text = " ".join(texts)

        if best_end <= best_start:
            self.log("  No suitable reference found")
            return None, ""

        duration = min(best_end - best_start, 15.0)
        self.log(f"  Reference: {best_start:.1f}s - {best_start + duration:.1f}s ({duration:.1f}s)")

        try:
            run_ffmpeg([
                "-i", str(vocals_path),
                "-ss", str(best_start),
                "-t", str(duration),
                "-c:a", "pcm_s16le",
                "-ar", "24000",
                "-ac", "1",
                str(ref_path),
            ])
            # Save ref text
            (output_dir / "reference_text.txt").write_text(best_text, encoding="utf-8")
        except Exception as e:
            self.log(f"  Reference extraction failed: {e}")
            return None, ""

        return ref_path, best_text

    def _fallback_edge_tts(self, text, lang, output_path):
        """Fallback to edge-tts when voice cloning fails."""
        import edge_tts
        voice = self.config["tts"]["voices"].get(lang, "vi-VN-HoaiMyNeural")
        try:
            asyncio.run(self._edge_tts_save(text, voice, output_path))
        except Exception:
            # Generate silence
            run_ffmpeg([
                "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                "-t", "0.5", "-c:a", "pcm_s16le", output_path,
            ])

    async def _edge_tts_save(self, text, voice, path):
        import edge_tts
        comm = edge_tts.Communicate(text, voice)
        await comm.save(path)

    def _build_synced_track(self, segments, tts_dir, output_path, total_duration):
        """Same as TTSGenerator - place each clip at correct timestamp."""
        silence = tts_dir / "silence_base.wav"
        run_ffmpeg([
            "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", str(total_duration), "-c:a", "pcm_s16le", str(silence),
        ])

        inputs = ["-i", str(silence)]
        filter_parts = []
        input_idx = 1

        for i, seg in enumerate(segments):
            f = tts_dir / f"{i:04d}.wav"
            if not f.exists() or f.stat().st_size < 100:
                continue
            inputs.extend(["-i", str(f)])
            delay_ms = int(seg["start"] * 1000)
            filter_parts.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms}[d{i}]")
            input_idx += 1

        if not filter_parts:
            self._copy(str(silence), str(output_path))
            return

        mix_inputs = "[0:a]" + "".join(
            f"[d{i}]" for i, seg in enumerate(segments)
            if (tts_dir / f"{i:04d}.wav").exists()
            and (tts_dir / f"{i:04d}.wav").stat().st_size >= 100
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
        filters = []
        remaining = speed
        while remaining > 2.0:
            filters.append("atempo=2.0")
            remaining /= 2.0
        filters.append(f"atempo={remaining:.4f}")
        run_ffmpeg(["-i", input_path, "-filter:a", ",".join(filters), output_path])

    def _copy(self, src, dst):
        run_ffmpeg(["-i", src, dst])
