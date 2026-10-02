from whitenoise.storage import CompressedManifestStaticFilesStorage

class LenientCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False

    def post_process(self, paths, dry_run=False, **options):
        # Exclude Tailwind source file input.css from Django post-processing (it contains @import "tailwindcss")
        filtered_paths = {k: v for k, v in paths.items() if not k.replace('\\', '/').endswith('css/input.css')}
        return super().post_process(filtered_paths, dry_run=dry_run, **options)
