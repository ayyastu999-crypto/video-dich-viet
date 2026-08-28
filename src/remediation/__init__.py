"""
Hệ thống tự phục hồi (Self-Healing) cho pipeline dịch video Douyin.

Modules:
    - srt_validator: Kiểm tra chất lượng và sửa lỗi file SRT
    - translation_qc: Kiểm tra chất lượng kết quả dịch của Gemini
    - pipeline_inspector: Phát hiện trạng thái pipeline cho từng video
    - recovery: Khôi phục các video bị lỗi/treo
    - media_validator: Tiền-kiểm tra tệp media trước khi xử lý
    - healer: Trình điều phối tổng (PipelineHealer)

Triết lý:
    AI sinh logic sửa - không bao giờ trực tiếp sửa dữ liệu.
    Mọi hành động đều được ghi log có thể truy vết.
    Không bao giờ làm mất dữ liệu ngầm: source == fixed + quarantined.
"""

from src.remediation.srt_validator import SrtValidator, SrtReport
from src.remediation.translation_qc import TranslationQC, TranslationReport
from src.remediation.pipeline_inspector import PipelineInspector, VideoState
from src.remediation.recovery import RecoveryManager, RecoveryResult
from src.remediation.media_validator import MediaValidator, MediaReport
from src.remediation.healer import PipelineHealer, HealReport

__all__ = [
    "SrtValidator", "SrtReport",
    "TranslationQC", "TranslationReport",
    "PipelineInspector", "VideoState",
    "RecoveryManager", "RecoveryResult",
    "MediaValidator", "MediaReport",
    "PipelineHealer", "HealReport",
]
