"""
Management command để dọn dẹp lịch sử phân tích ECG của khách vãng lai.

Cách dùng:
    python manage.py cleanup_guest_history
    python manage.py cleanup_guest_history --days 2   # xóa cũ hơn 2 ngày

Có thể lên lịch chạy tự động qua Windows Task Scheduler hoặc cron.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from ecg.models import ECGSignal


class Command(BaseCommand):
    help = "Xóa lịch sử phân tích ECG của khách vãng lai (user=None) cũ hơn N ngày."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="Số ngày để xác định bản ghi cũ (mặc định: 1 ngày).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timezone.timedelta(days=days)

        old_signals = ECGSignal.objects.filter(
            user__isnull=True,
            uploaded_at__lt=cutoff,
        )
        count = old_signals.count()
        old_signals.delete()  # CASCADE tự xóa Prediction liên quan

        self.stdout.write(
            self.style.SUCCESS(
                f"[cleanup_guest_history] Đã xóa {count} bản ghi ECG của khách vãng lai "
                f"cũ hơn {days} ngày."
            )
        )
