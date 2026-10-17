from pathlib import Path, PurePosixPath
import tempfile
import zipfile

from django.conf import settings
from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = 'Restore a backup produced by backup_data (requires an explicit confirmation flag).'

    def add_arguments(self, parser):
        parser.add_argument('backup_file')
        parser.add_argument('--confirm', action='store_true', help='Confirm that database records may be changed.')
        parser.add_argument('--replace', action='store_true', help='Flush current database records before restoring.')

    def handle(self, *args, **options):
        if not options['confirm']:
            raise self.CommandError('Pass --confirm after reviewing the backup file and target database.')
        backup_path = Path(options['backup_file']).expanduser().resolve()
        if not backup_path.is_file():
            raise self.CommandError(f'Backup file does not exist: {backup_path}')
        try:
            archive = zipfile.ZipFile(backup_path)
            if 'database.json' not in archive.namelist():
                raise self.CommandError('The archive does not contain database.json.')
            media_root = Path(settings.MEDIA_ROOT).resolve()
            for member in archive.infolist():
                relative = PurePosixPath(member.filename)
                if member.filename.startswith('media/') and not relative.is_absolute() and '..' not in relative.parts:
                    target = (media_root / Path(*relative.parts[1:])).resolve()
                    if target != media_root and media_root not in target.parents:
                        raise self.CommandError('The archive contains an unsafe media path.')
            with tempfile.TemporaryDirectory() as temp_dir:
                fixture = Path(temp_dir) / 'database.json'
                fixture.write_bytes(archive.read('database.json'))
                if options['replace']:
                    # Preserve a rollback point immediately before destructive replacement.
                    call_command('backup_data')
                    call_command('flush', interactive=False, verbosity=0)
                call_command('loaddata', str(fixture))
            media_root.mkdir(parents=True, exist_ok=True)
            for member in archive.infolist():
                relative = PurePosixPath(member.filename)
                if member.filename.startswith('media/') and not relative.is_absolute() and '..' not in relative.parts:
                    target = (media_root / Path(*relative.parts[1:])).resolve()
                    if media_root != target and media_root in target.parents:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(member) as source, target.open('wb') as destination:
                            while chunk := source.read(1024 * 1024):
                                destination.write(chunk)
        except (OSError, zipfile.BadZipFile) as error:
            raise self.CommandError(f'Could not read or restore the backup: {error}') from error
        finally:
            if 'archive' in locals():
                archive.close()
        self.stdout.write(self.style.SUCCESS('Backup restore completed.'))
