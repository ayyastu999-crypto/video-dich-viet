import os
from pathlib import Path

from src.steps.base import BaseStep
from src.utils.srt import parse_srt, write_srt


LANG_NAMES = {
    "vi": "Vietnamese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "th": "Thai",
    "id": "Indonesian",
    "zh": "Chinese",
}


class Translator(BaseStep):
    def run(self, srt_path: Path, target_lang: str) -> dict:
        segments = parse_srt(str(srt_path))
        if not segments:
            raise ValueError(f"No segments found in {srt_path}")

        trans_cfg = self.config["translation"]
        provider = trans_cfg.get("provider", "gemini")
        batch_size = trans_cfg.get("batch_size", 15)
        lang_name = LANG_NAMES.get(target_lang, target_lang)

        if provider == "gemini":
            client = self._init_gemini(trans_cfg)
        else:
            client = self._init_openai(trans_cfg)

        translated_segments = []
        for batch_start in range(0, len(segments), batch_size):
            batch = segments[batch_start:batch_start + batch_size]
            texts = [seg["text"] for seg in batch]

            self.log(f"Translating batch {batch_start // batch_size + 1} "
                     f"({len(texts)} segments) -> {lang_name}")

            translated_texts = self._translate_batch(
                client, provider, trans_cfg, texts, lang_name
            )

            if len(translated_texts) != len(batch):
                self.log(f"Warning: got {len(translated_texts)} translations "
                         f"for {len(batch)} segments. Retrying...")
                translated_texts = self._translate_batch(
                    client, provider, trans_cfg, texts, lang_name, strict=True
                )

            for seg, trans_text in zip(batch, translated_texts):
                translated_segments.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": trans_text.strip(),
                })

        srt_dir = self.ensure_dir("srt")
        out_path = srt_dir / f"{srt_path.stem.replace('_original', '')}_{target_lang}.srt"
        write_srt(translated_segments, str(out_path))

        self.log(f"Translated {len(translated_segments)} segments -> {out_path.name}")
        return {"translated_srt": out_path}

    def _init_gemini(self, cfg):
        from google import genai
        return genai.Client(api_key=cfg.get("api_key", ""))

    def _init_openai(self, cfg=None):
        """Client tuong thich OpenAI. DeepSeek dung chung giao thuc, chi khac base_url."""
        from openai import OpenAI

        cfg = cfg or {}
        if cfg.get("provider") == "deepseek":
            return OpenAI(
                api_key=cfg.get("api_key") or os.getenv("DEEPSEEK_API_KEY", ""),
                base_url=cfg.get("base_url", "https://api.deepseek.com"),
            )
        return OpenAI(api_key=cfg.get("api_key") or os.getenv("OPENAI_API_KEY", "") or None)

    def _build_prompt(self, texts, lang_name, strict=False):
        numbered = "\n".join(f"{i+1}: {t}" for i, t in enumerate(texts))
        strict_note = (
            f"\nIMPORTANT: Return EXACTLY {len(texts)} lines. "
            "Each line prefixed with its number."
        ) if strict else ""

        return (
            f"Translate these subtitle lines from Chinese to {lang_name}.\n"
            f"Rules:\n"
            f"- Keep translations concise (subtitle-friendly, max 2 lines)\n"
            f"- Return EXACTLY {len(texts)} lines, numbered like input\n"
            f"- Preserve meaning, tone, and register\n"
            f"- Do NOT add explanations{strict_note}\n\n"
            f"Lines:\n{numbered}"
        )

    def _call_api(self, client, provider, cfg, prompt, attempts: int = 4) -> str:
        """Goi API dich, co thu lai.

        Gemini thinh thoang tra 403/429/503 tam thoi. Khong thu lai thi mot
        loi thoang qua se giet ca luot chay da ton vai phut o buoc truoc.
        """
        import time

        delay = 5
        last_error = None
        for i in range(attempts):
            try:
                if provider == "gemini":
                    response = client.models.generate_content(
                        model=cfg.get("model", "gemini-2.5-flash"),
                        contents=prompt,
                    )
                    return response.text.strip()
                default_model = ("deepseek-chat" if provider == "deepseek"
                                 else "gpt-4o-mini")
                response = client.chat.completions.create(
                    model=cfg.get("model") or default_model,
                    messages=[
                        {"role": "system", "content": "You are a professional subtitle translator."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=cfg.get("temperature", 0.3),
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                last_error = e
                if i == attempts - 1:
                    break
                msg = str(e).replace(chr(10), " ")[:160]
                self.log(f"Loi API ({type(e).__name__}) thu lai sau {delay}s "
                         f"[{i + 1}/{attempts - 1}]: {msg}")
                time.sleep(delay)
                delay *= 2
        raise last_error

    def _translate_batch(self, client, provider, cfg, texts, lang_name, strict=False):
        prompt = self._build_prompt(texts, lang_name, strict)
        raw = self._call_api(client, provider, cfg, prompt)

        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> list[str]:
        lines = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Remove number prefix like "1: " or "1. "
            if line and line[0].isdigit():
                for sep in [": ", ". ", ") "]:
                    idx = line.find(sep)
                    if idx != -1 and idx < 5:
                        line = line[idx + len(sep):]
                        break
            lines.append(line)
        return lines
