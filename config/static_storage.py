"""Content-addressed static assets; private uploads use a separate backend."""
from whitenoise.storage import CompressedManifestStaticFilesStorage


class StaticStorage(CompressedManifestStaticFilesStorage):
    # Vendored libraries intentionally omit developer source maps. Keep normal
    # CSS url()/@import rewriting strict, but leave source-map comments alone.
    patterns = tuple(
        (extension, tuple(pattern for pattern in patterns
                          if 'sourceMappingURL' not in (
                              pattern if isinstance(pattern, str) else pattern[0])))
        for extension, patterns in CompressedManifestStaticFilesStorage.patterns
    )
