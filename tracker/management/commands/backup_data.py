from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
import zipfile

from django.conf import settings
from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = 'Create a portable compressed backup of database fixtures and uploaded media.'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', default=os.environ.get('BACKUP_DIR', str(settings.BASE_DIR / 'backups')))
        parser.add_argument('--retention-days', type=int, default=int(os.environ.get('BACKUP_RETENTION_DAYS', '30')))

    def handle(self, *args, **options):
        output_dir = Path(options['output_dir']).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            output_dir.chmod(0o700)
        except OSError:
            pass
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        destination = output_dir / f'spendwise-backup-{timestamp}.zip'
        temporary = destination.with_suffix('.zip.tmp')

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                fixture_path = Path(temp_dir) / 'database.json'
                with fixture_path.open('w', encoding='utf-8') as fixture:
                    call_command(
                        'dumpdata', exclude=['contenttypes', 'auth.permission', 'admin.logentry', 'sessions'],
                        use_natural_foreign_keys=True, use_natural_primary_keys=True, indent=2, stdout=fixture,
                    )
                with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                    archive.write(fixture_path, 'database.json')
                    media_root = Path(settings.MEDIA_ROOT)
                    if media_root.exists():
                        for media_file in media_root.rglob('*'):
                            if media_file.is_file() and not media_file.is_symlink():
                                archive.write(media_file, Path('media') / media_file.relative_to(media_root))
            os.replace(temporary, destination)
            try:
                destination.chmod(0o600)
            except OSError:
                pass
        finally:
            temporary.unlink(missing_ok=True)

        retention_days = options['retention_days']
        if retention_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            for old_backup in output_dir.glob('spendwise-backup-*.zip'):
                if old_backup != destination and datetime.fromtimestamp(old_backup.stat().st_mtime, timezone.utc) < cutoff:
                    old_backup.unlink()
        self.stdout.write(self.style.SUCCESS(f'Backup created: {destination}'))
        self.stdout.write('Store a copy outside this server and protect it as sensitive financial data.')
