#!/usr/bin/env python3
"""
heal.py — CLI cho hệ thống tự phục hồi pipeline Douyin.

Sử dụng:
    python scripts/heal.py scan                      # Quét và báo cáo lỗi
    python scripts/heal.py heal                      # Tự sửa toàn bộ
    python scripts/heal.py heal --video <id>         # Sửa 1 video
    python scripts/heal.py heal --video <id> --force-step translate
    python scripts/heal.py resume                    # Tiếp tục các video đang dở
    python scripts/heal.py validate <file.mp4>       # Kiểm tra 1 file media
    python scripts/heal.py validate-srt <file.srt>   # Kiểm tra 1 SRT
    python scripts/heal.py loop --interval 300       # Chạy nền quét định kỳ

Tuỳ chọn chung:
    --config <yaml>         (mặc định: config/default.yaml)
    --workspace <path>      (mặc định: workspace)
    --lang <code>           (mặc định: vi)
    --json                  In báo cáo JSON thay vì text màu

Mã thoát:
    0 = thành công, không có lỗi nghiêm trọng
    1 = có lỗi / phục hồi không hoàn tất / reconciliation lệch
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Đảm bảo import được src.* khi gọi trực tiếp từ scripts/
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.remediation._common import C, colour, head, ok, warn, err, info  # noqa: E402
from src.remediation.healer import PipelineHealer  # noqa: E402
from src.remediation.media_validator import MediaValidator  # noqa: E402
from src.remediation.srt_validator import SrtValidator  # noqa: E402


def _load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(warn(f"Không tìm thấy config '{path}', dùng config rỗng"))
        return {}
    try:
        from src.config import load_config
        return load_config(path)
    except Exception as e:
        print(err(f"Lỗi load config: {e}"))
        return {}


def _print_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------
def cmd_scan(args) -> int:
    cfg = _load_config(args.config)
    healer = PipelineHealer(cfg, args.workspace, args.lang)
    rep = healer.scan()
    if args.json:
        _print_json(rep.to_dict())
    else:
        print(healer.get_status_report())
    # Exit 0 nếu không có vấn đề nghiêm trọng
    has_issues = (rep.stuck > 0
                  or rep.translation_issues
                  or any(v >= 1 for v in rep.media_issues.values()))
    return 1 if has_issues else 0


def cmd_heal(args) -> int:
    cfg = _load_config(args.config)
    healer = PipelineHealer(cfg, args.workspace, args.lang)

    if args.video:
        result = healer.heal_video(args.video, force_step=args.force_step)
        if args.json:
            _print_json(result.to_dict())
        else:
            status = result.final_status
            label = ok if status == "success" else (warn if status == "partial" else err)
            print(label(f"Video {args.video}: {status}"))
            for a in result.attempts:
                tag = ok("OK") if a.success else err("FAIL")
                print(f"  - {a.step:18s} {tag}  {a.error or ''}")
            if result.quarantined:
                print(warn(f"Đã cách ly: {result.quarantine_reason}"))
        return 0 if result.final_status == "success" else 1

    rep = healer.heal_all()
    if args.json:
        _print_json(rep.to_dict())
    else:
        print(healer.get_status_report())
    return 0 if rep.reconciliation_ok and rep.quarantined_count == 0 else 1


def cmd_resume(args) -> int:
    cfg = _load_config(args.config)
    healer = PipelineHealer(cfg, args.workspace, args.lang)
    ws = healer.inspector.scan()

    targets = ws.resumable_ids + ws.stuck_ids
    if not targets:
        print(ok("Không có video nào cần tiếp tục"))
        return 0

    print(info(f"Sẽ tiếp tục {len(targets)} video..."))
    failed = 0
    for vid in targets:
        print(head(f"\n--- {vid} ---"))
        result = healer.heal_video(vid)
        status = result.final_status
        if status == "success":
            print(ok(f"Hoàn tất: {vid}"))
        elif status == "partial":
            print(warn(f"Một phần: {vid}"))
            failed += 1
        else:
            print(err(f"Thất bại: {vid}"))
            failed += 1
        for a in result.attempts:
            tag = ok("OK") if a.success else err("FAIL")
            print(f"  - {a.step:18s} {tag}  {a.error or ''}")

    if args.json:
        # In lại snapshot mới sau khi resume
        post = healer.scan()
        _print_json(post.to_dict())

    return 0 if failed == 0 else 1


def cmd_validate(args) -> int:
    """Validate 1 file media (mp4/wav)."""
    v = MediaValidator(args.workspace)
    rep = v.validate(args.file, check_silence=not args.no_silence)
    if args.json:
        _print_json(rep.to_dict())
        return 0 if rep.safe_to_process else 1

    print(head(f"\n=== KIỂM TRA: {args.file} ===\n"))
    print(f"  Tồn tại:       {rep.exists}")
    print(f"  Kích thước:    {rep.size:,} bytes")
    print(f"  Thời lượng:    {rep.duration:.2f}s")
    print(f"  Có video:      {rep.has_video} ({rep.video_codec or '-'} {rep.width or '?'}x{rep.height or '?'})")
    print(f"  Có audio:      {rep.has_audio} ({rep.audio_codec or '-'} {rep.sample_rate or '?'} Hz)")
    if rep.mean_volume_db is not None:
        print(f"  Âm lượng TB:   {rep.mean_volume_db:.1f} dB ({'CÂM' if rep.is_silent else 'OK'})")
    print()
    if rep.issues:
        print(head("Vấn đề phát hiện:"))
        for i in rep.issues:
            label = err if i.severity in ("error", "fatal") else warn
            print(label(f"  [{i.severity:5s}] {i.code}: {i.message}"))
    else:
        print(ok("Không phát hiện vấn đề"))
    print()
    print(ok("AN TOÀN xử lý") if rep.safe_to_process else err("KHÔNG nên xử lý"))
    return 0 if rep.safe_to_process else 1


def cmd_validate_srt(args) -> int:
    v = SrtValidator(args.workspace, auto_fix=args.fix)
    rep = v.validate(args.file)
    if args.json:
        _print_json(rep.to_dict())
        return 0 if rep.is_recoverable and not rep.has_errors() else 1

    print(head(f"\n=== KIỂM TRA SRT: {args.file} ===\n"))
    print(f"  Số segment:    {rep.segment_count}")
    print(f"  Có thể phục hồi: {rep.is_recoverable}")
    if rep.fixed_path:
        print(ok(f"  Đã ghi bản đã sửa: {rep.fixed_path}"))
    print()
    if rep.issues:
        for i in rep.issues:
            label = err if i.severity in ("error", "fatal") else warn
            tag = " [đã sửa]" if i.fixed else ""
            print(label(f"  [{i.severity:5s}] {i.code}{tag}: {i.message}"))
    else:
        print(ok("Không phát hiện vấn đề"))
    return 0 if rep.is_recoverable and not rep.has_errors() else 1


def cmd_loop(args) -> int:
    cfg = _load_config(args.config)
    healer = PipelineHealer(cfg, args.workspace, args.lang)
    print(info(f"Bắt đầu loop quét mỗi {args.interval}s (Ctrl+C để dừng)..."))
    healer.start_loop(interval=args.interval, auto_heal=args.auto_heal)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        print(info("Đang dừng loop..."))
        healer.stop_loop()
    return 0


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="heal.py",
        description="Hệ thống tự phục hồi pipeline dịch video Douyin",
    )
    p.add_argument("--config", default="config/default.yaml",
                   help="Đường dẫn file YAML config")
    p.add_argument("--workspace", default="workspace",
                   help="Thư mục workspace")
    p.add_argument("--lang", default="vi", help="Mã ngôn ngữ đích (vi/en/...)")
    p.add_argument("--json", action="store_true", help="In JSON thay vì text")

    sub = p.add_subparsers(dest="command", required=True)

    s_scan = sub.add_parser("scan", help="Quét và báo cáo (không sửa)")
    s_scan.set_defaults(func=cmd_scan)

    s_heal = sub.add_parser("heal", help="Tự sửa toàn bộ vấn đề")
    s_heal.add_argument("--video", help="Chỉ sửa 1 video_id cụ thể")
    s_heal.add_argument("--force-step", help="Bắt buộc chạy lại từ bước này")
    s_heal.set_defaults(func=cmd_heal)

    s_resume = sub.add_parser("resume", help="Tiếp tục các video dang dở/treo")
    s_resume.set_defaults(func=cmd_resume)

    s_val = sub.add_parser("validate", help="Kiểm tra 1 file media (mp4/wav)")
    s_val.add_argument("file", help="Đường dẫn file")
    s_val.add_argument("--no-silence", action="store_true",
                       help="Bỏ qua kiểm tra âm lượng")
    s_val.set_defaults(func=cmd_validate)

    s_vs = sub.add_parser("validate-srt", help="Kiểm tra 1 file SRT")
    s_vs.add_argument("file", help="Đường dẫn file SRT")
    s_vs.add_argument("--fix", action="store_true", help="Auto-fix nếu có thể")
    s_vs.set_defaults(func=cmd_validate_srt)

    s_loop = sub.add_parser("loop", help="Chạy nền quét định kỳ")
    s_loop.add_argument("--interval", type=int, default=300,
                        help="Chu kỳ quét (giây), mặc định 300")
    s_loop.add_argument("--auto-heal", action="store_true",
                        help="Tự sửa luôn thay vì chỉ scan")
    s_loop.set_defaults(func=cmd_loop)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print()
        print(warn("Bị huỷ bởi người dùng"))
        return 1
    except Exception as e:
        print(err(f"Lỗi không xử lý được: {e}"))
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
