from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Import bộ câu hỏi GT1 đã chuyển đổi từ đề giấy dưới dạng draft; không tự động duyệt."

    def add_arguments(self, parser):
        parser.add_argument("--path", default="data/question_bank/gt1_online_drafts.json")
        parser.add_argument("--course", default="GT1")
        parser.add_argument("--username", default="demo-teacher")

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Lệnh cũ được chuyển sang importer paper-to-online an toàn."))
        call_command(
            "import_paper_question_drafts",
            path=options["path"], course=options["course"], username=options["username"],
        )
