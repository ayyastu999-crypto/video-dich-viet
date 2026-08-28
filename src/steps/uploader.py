import time
from pathlib import Path

from src.steps.base import BaseStep


class Uploader(BaseStep):
    PLATFORMS = {}

    @classmethod
    def register(cls, name):
        def decorator(klass):
            cls.PLATFORMS[name] = klass
            return klass
        return decorator

    def run(self, final_video: Path, metadata: dict) -> dict:
        platforms = self.config.get("upload", {}).get("platforms", [])
        delay = self.config.get("upload", {}).get("delay_between", 30)
        results = {}

        for platform in platforms:
            uploader_cls = self.PLATFORMS.get(platform)
            if not uploader_cls:
                self.log(f"Unknown platform: {platform}")
                continue

            try:
                self.log(f"Uploading to {platform}...")
                result = uploader_cls(self.config, self.work_dir).upload(
                    final_video, metadata
                )
                results[platform] = {"status": "success", **result}
            except Exception as e:
                self.log(f"Upload to {platform} failed: {e}")
                results[platform] = {"status": "error", "error": str(e)}

            if delay > 0:
                time.sleep(delay)

        return {"upload_results": results}

    def upload(self, video: Path, metadata: dict) -> dict:
        raise NotImplementedError


@Uploader.register("tiktok")
class TikTokUploader(Uploader):
    def upload(self, video: Path, metadata: dict) -> dict:
        from tiktok_uploader.upload import upload_video

        cookies = self.config.get("upload", {}).get("tiktok", {}).get(
            "cookies", "cookies_tiktok.txt"
        )
        tags = self.config.get("upload", {}).get("tiktok", {}).get(
            "default_tags", ""
        )
        description = metadata.get("description", "") + " " + tags

        upload_video(str(video), description=description.strip(), cookies=cookies)
        return {"platform": "tiktok"}


@Uploader.register("youtube")
class YouTubeUploader(Uploader):
    def upload(self, video: Path, metadata: dict) -> dict:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials

        yt_cfg = self.config.get("upload", {}).get("youtube", {})
        creds_file = yt_cfg.get("credentials", "config/youtube_creds.json")
        privacy = yt_cfg.get("default_privacy", "private")

        creds = Credentials.from_authorized_user_file(creds_file)
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": metadata.get("title", "Translated Video"),
                "description": metadata.get("description", ""),
                "tags": metadata.get("tags", []),
                "categoryId": yt_cfg.get("default_category", "22"),
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(str(video), mimetype="video/mp4"),
        )
        response = request.execute()
        return {"platform": "youtube", "video_id": response["id"]}
