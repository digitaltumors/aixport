import os
import zipfile
from typing import List


class ROCrateZipper:
    """
    Utility for creating and inspecting ZIP archives built from RO-Crate
    directory trees.
    """

    def __init__(self, directory_path: str, zip_path: str):
        """
        Initialize with the directory to zip and the output zip file path.

        :param directory_path: Path to the directory to compress.
        :param zip_path: Path where the ZIP archive will be written.
        """
        self._directory_path = os.path.abspath(directory_path)
        self._zip_path = os.path.abspath(zip_path)

    @property
    def directory_path(self) -> str:
        """
        Returns the directory path to be zipped.
        """
        return self._directory_path

    @property
    def zip_path(self) -> str:
        """
        Returns the target ZIP archive path.
        """
        return self._zip_path

    def zip_directory(self) -> None:
        """
        Zips the entire directory (including subdirectories) into a .zip file.
        """
        if not os.path.isdir(self._directory_path):
            raise FileNotFoundError(f'Directory does not exist: {self._directory_path}')

        zip_dir = os.path.dirname(self._zip_path)
        if zip_dir and not os.path.isdir(zip_dir):
            os.makedirs(zip_dir, mode=0o755, exist_ok=True)

        with zipfile.ZipFile(self._zip_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for root, dirs, files in os.walk(self._directory_path):
                rel_root = os.path.relpath(root, self._directory_path)
                if rel_root == '.':
                    rel_root = ''

                # Add files preserving relative path
                for filename in files:
                    file_path = os.path.join(root, filename)
                    arcname = os.path.join(rel_root, filename) if rel_root else filename
                    archive.write(file_path, arcname=arcname)

                # Ensure empty directories are represented in the archive
                if not files and not dirs and rel_root:
                    zinfo = zipfile.ZipInfo(rel_root.rstrip('/') + '/')
                    archive.writestr(zinfo, '')

    def _ensure_archive_exists(self) -> None:
        """
        Raises FileNotFoundError if archive has not been created yet.
        """
        if not os.path.isfile(self._zip_path):
            raise FileNotFoundError(f'ZIP archive not found: {self._zip_path}')

    def list_contents(self) -> List[str]:
        """
        Returns a list of all file names and paths inside the zip archive.
        """
        self._ensure_archive_exists()
        with zipfile.ZipFile(self._zip_path, 'r') as archive:
            return archive.namelist()

    def read_file(self, file_name: str) -> bytes:
        """
        Reads and returns the binary contents of a file inside the zip archive.
        Raises a FileNotFoundError if the file does not exist in the zip.
        """
        self._ensure_archive_exists()
        try:
            with zipfile.ZipFile(self._zip_path, 'r') as archive:
                with archive.open(file_name, 'r') as handle:
                    return handle.read()
        except KeyError as exc:
            raise FileNotFoundError(f'"{file_name}" not found in archive') from exc

    def extract_file(self, file_name: str, dest_path: str) -> None:
        """
        Extracts a specific file from the zip archive to the given destination.
        """
        self._ensure_archive_exists()
        os.makedirs(dest_path, mode=0o755, exist_ok=True)
        try:
            with zipfile.ZipFile(self._zip_path, 'r') as archive:
                archive.extract(member=file_name, path=dest_path)
        except KeyError as exc:
            raise FileNotFoundError(f'"{file_name}" not found in archive') from exc
