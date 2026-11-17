import logging
import shutil
from pathlib import Path

from .base import ObjectStorage
from .models import StoredObject, AccessMode
from .errors import StorageError, StorageNotFoundError

logger = logging.getLogger("analytics_service.services.storage.local")


class LocalStorage(ObjectStorage):
    """
    Filesystem adapter for local development: no cloud account needed.

    Each "bucket" is a directory under ``root``:
      AccessMode.PUBLIC  → <root>/<STORAGE_PUBLIC_BUCKET>/<key>
      AccessMode.PRIVATE → <root>/<STORAGE_PRIVATE_BUCKET>/<key>

    Not for production: nothing is served over HTTP, and the files live only on
    this machine, so the web server, consumer and worker must share the disk.
    """

    def __init__(self, root: str, public_bucket: str, private_bucket: str):
        self.root = Path(root).resolve()
        self.public_bucket = public_bucket
        self.private_bucket = private_bucket

    def _path(self, object_key: str, access_mode: AccessMode) -> Path:
        base = (self.root / self._bucket_for(access_mode)).resolve()
        path = (base / object_key).resolve()
        if not path.is_relative_to(base):
            raise StorageError(f"Object key escapes the storage root: {object_key!r}")
        return path

    def _stored(self, object_key: str, access_mode: AccessMode, content_type: str | None) -> StoredObject:
        return StoredObject(
            provider="local",
            bucket=self._bucket_for(access_mode),
            key=object_key,
            access_mode=access_mode,
            content_type=content_type,
        )

    def upload_file(self, local_file_path, object_key, content_type=None, access_mode=AccessMode.PRIVATE):
        dest = self._path(object_key, access_mode)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_file_path, dest)
        logger.info(f"Stored file locally at {dest}")
        return self._stored(object_key, access_mode, content_type)

    def upload_bytes(self, data, object_key, content_type=None, access_mode=AccessMode.PRIVATE):
        dest = self._path(object_key, access_mode)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        logger.info(f"Stored {len(data)} bytes locally at {dest}")
        return self._stored(object_key, access_mode, content_type)

    def download_bytes(self, object_key, access_mode=AccessMode.PRIVATE):
        path = self._path(object_key, access_mode)
        if not path.is_file():
            raise StorageNotFoundError(f"Local object not found: {path}")
        return path.read_bytes()

    def delete_object(self, object_key, access_mode=AccessMode.PRIVATE):
        path = self._path(object_key, access_mode)
        if not path.is_file():
            raise StorageNotFoundError(f"Local object not found: {path}")
        path.unlink()

    def generate_access_url(self, object_key, expires_in_seconds, access_mode=AccessMode.PRIVATE):
        # No signing locally; a file:// URL is enough to open the object on this machine.
        return self._path(object_key, access_mode).as_uri()
