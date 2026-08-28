from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger


class PipelineScheduler:
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.scheduler = BlockingScheduler()

    def schedule(self, url_file: str, target_langs: list[str],
                 cron: str = "0 8 * * *"):
        """Schedule batch processing on a cron schedule.

        Args:
            url_file: Path to text file with URLs (1 per line)
            target_langs: List of target language codes
            cron: Crontab expression (default: daily at 8:00 AM)
        """
        trigger = CronTrigger.from_crontab(cron)
        self.scheduler.add_job(
            self.pipeline.run_from_file,
            trigger=trigger,
            args=[url_file, target_langs],
            id="batch_translate",
            replace_existing=True,
        )
        print(f"[Scheduler] Job scheduled: {cron}")
        print(f"[Scheduler] URL file: {url_file}")
        print(f"[Scheduler] Languages: {', '.join(target_langs)}")

    def start(self):
        """Start the scheduler (blocking)."""
        print("[Scheduler] Starting... Press Ctrl+C to stop.")
        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            print("[Scheduler] Stopped.")
