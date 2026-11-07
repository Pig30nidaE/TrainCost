"""Race-resistant report output for untrusted checkout paths.

Parent directories are traversed through no-follow directory descriptors. Files
are staged alongside their destination and replaced without following a leaf.
"""

from __future__ import annotations

from contextlib import ExitStack
import os
from pathlib import Path
import secrets
import stat
import sys
import unicodedata

from .safety import ConfigError, looks_sensitive


class OutputPathError(ConfigError):
    """A report destination is unsafe or could not be written."""


_ERROR = "Unsafe or unwritable report output path."


def _output_path(value: str | Path) -> str:
    try:
        text = os.fsdecode(os.fspath(value))
        if (not text.strip() or any(char in text for char in "\r\n\0")
                or looks_sensitive(text) or ".." in text.split(os.sep)):
            raise ValueError
        absolute = os.path.abspath(text)
        # macOS exposes these system directories through fixed root aliases.
        if sys.platform == "darwin":
            for alias in ("/tmp", "/var"):
                target = "/private" + alias
                if (absolute == alias or absolute.startswith(alias + "/")) and os.path.realpath(alias) == target:
                    absolute = target + absolute[len(alias):]
                    break
        if absolute == os.path.sep:
            raise ValueError
        return absolute
    except (TypeError, ValueError, OSError):
        raise OutputPathError(_ERROR) from None


def _protected(paths):
    names, identities = set(), set()
    for path in paths:
        resolved = os.path.realpath(os.fsdecode(os.fspath(path)))
        names.add(resolved)
        try:
            entry = os.stat(resolved)
        except FileNotFoundError:
            continue
        identities.add((entry.st_dev, entry.st_ino))
    return names, identities


def _path_key(path: str) -> str:
    # macOS filesystems commonly fold case and normalize Unicode names.
    return unicodedata.normalize("NFD", path).casefold() if sys.platform == "darwin" else path


def _parent(path: str, stack: ExitStack, *, create: bool) -> tuple[int | None, str]:
    if not all(hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW")):
        raise OutputPathError(_ERROR)
    pieces = path.split(os.sep)[1:]
    leaf = pieces.pop()
    if not leaf or leaf in {".", ".."}:
        raise OutputPathError(_ERROR)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(os.sep, flags)
    stack.callback(os.close, fd)
    for part in pieces:
        if not part or part in {".", ".."}:
            raise OutputPathError(_ERROR)
        try:
            child = os.open(part, flags, dir_fd=fd)
        except FileNotFoundError:
            if not create:
                return None, leaf
            try:
                os.mkdir(part, 0o777, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, flags, dir_fd=fd)
        fd = child
        stack.callback(os.close, child)
    return fd, leaf


def _check(paths: tuple[str, str], protected_paths, stack: ExitStack, *, create: bool):
    names, identities = _protected(protected_paths)
    if _path_key(paths[0]) == _path_key(paths[1]) or any(_path_key(path) in {_path_key(name) for name in names} for path in paths):
        raise OutputPathError(_ERROR)
    entries = []
    parents = []
    for path in paths:
        fd, leaf = _parent(path, stack, create=create)
        parents.append((fd, leaf))
        if fd is None:
            continue
        if len(parents) == 2 and parents[0][0] is not None:
            first_fd, first_leaf = parents[0]
            first_dir, second_dir = os.fstat(first_fd), os.fstat(fd)
            if ((first_dir.st_dev, first_dir.st_ino) == (second_dir.st_dev, second_dir.st_ino)
                    and _path_key(first_leaf) == _path_key(leaf)):
                raise OutputPathError(_ERROR)
        try:
            entry = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(entry.st_mode) or entry.st_nlink != 1:
            raise OutputPathError(_ERROR)
        identity = (entry.st_dev, entry.st_ino)
        if identity in identities or identity in entries:
            raise OutputPathError(_ERROR)
        entries.append(identity)
    return parents


def validate_report_paths(report_path, json_path, *, protected_paths=(), workspace_root=None):
    """Validate destinations without writing files or creating directories.

    All parent symlinks are rejected, including outside the checkout, except the
    standard macOS /tmp and /var aliases. Explicit external paths are supported.
    """
    del workspace_root  # The same conservative boundary applies inside and outside the checkout.
    try:
        paths = (_output_path(report_path), _output_path(json_path))
        with ExitStack() as stack:
            _check(paths, protected_paths, stack, create=False)
    except OutputPathError:
        raise
    except (OSError, ValueError, TypeError, RuntimeError):
        raise OutputPathError(_ERROR) from None


def write_report_files(report_path, json_path, report_text, json_text, *, protected_paths=(), workspace_root=None):
    """Preflight both outputs, then atomically replace each staged report."""
    del workspace_root
    try:
        paths = (_output_path(report_path), _output_path(json_path))
        # Materialize once because callers may provide a generator.
        protected_paths = tuple(protected_paths)
        with ExitStack() as stack:
            _check(paths, protected_paths, stack, create=False)
            parents = _check(paths, protected_paths, stack, create=True)
            staged = []
            for (fd, leaf), text in zip(parents, (report_text, json_text)):
                if not isinstance(text, str):
                    raise OutputPathError(_ERROR)
                temp = ".traincost-" + secrets.token_hex(16)
                temp_fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                stack.callback(_remove_temp, fd, temp)
                with os.fdopen(temp_fd, "w", encoding="utf-8") as stream:
                    stream.write(text)
                staged.append((fd, temp, leaf))
            for fd, temp, leaf in staged:
                os.replace(temp, leaf, src_dir_fd=fd, dst_dir_fd=fd)
    except OutputPathError:
        raise
    except (OSError, ValueError, TypeError, RuntimeError, UnicodeError):
        raise OutputPathError(_ERROR) from None


def _remove_temp(fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=fd)
    except FileNotFoundError:
        pass
