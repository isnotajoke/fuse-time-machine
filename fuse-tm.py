from fuse import Fuse

import errno
import os
import stat

class TimeMachine(Fuse):
    """
    A FUSE interface to interface with a time machine backup.
    """
    def __init__(self, *args, **kwargs):
        Fuse.__init__(self, *args, **kw)
        # keep track of open file descriptors so we can close them
        # later.
        # path => (flags, fd)
        self.fds = {}
        return

    # FUSE API methods
    def getattr(self, path):
        """
        Return stats for path by translating it to a real path and then
        running stat on it normally.
        """
        return self.run_operation_on_real_path(path, os.stat)

    def getdir(self, path):
        """
        return: [[('file1', 0), ('file2', 0), ... ]]
        """
        entries = self.run_operation_on_real_path(path, os.listdir)
        if entries is not None:
            # per docs, the listdir call doesn't append the '.' or '..'
            # entries, so we have to add them ourselves.
            entries.append(".")
            entries.append("..")
        return entries

    def statfs ( self ):
        return self.run_operation_on_real_path(path, os.statvfs)

    def open (self, path, flags):
        # Ignore flags; we're read-only, and we return an error if they
        # try to write to us.
        fd = self.run_operation_on_real_path(path, lambda realpath: os.open(path, os.O_RDONLY))
        self.fds.setdefault(path, {})[flags] = fd
        return fd

    def read ( self, path, length, offset ):
        f = self.run_operation_on_real_path(path, lambda realpath: open(path, "rb"))
        f.seek(offset)
        data = f.read(length)
        f.close()
        return data

    def readlink ( self, path ):
        return self.run_operation_on_real_path(path, os.readlink)

    def release(self, path, flags):
        fd = self.fds[path][flags]
        os.close(fd)
        del(self.fds[path][flags])

    # The following operations aren't supported.
    def rename ( self, oldPath, newPath ):
        return -errno.ENOSYS

    def rmdir ( self, path ):
        return -errno.ENOSYS

    def mythread(self):
        return -errno.ENOSYS

    def chmod (self, path, mode):
        return -errno.ENOSYS

    def chown(self, path, uid, gid):
        return -errno.ENOSYS

    def fsync(self, path, isFsyncFile):
        return -errno.ENOSYS

    def link(self, targetPath, linkPath):
        return -errno.ENOSYS

    def mkdir ( self, path, mode ):
        return -errno.ENOSYS

    def mknod ( self, path, mode, dev ):
        return -errno.ENOSYS

    def symlink ( self, targetPath, linkPath ):
        return -errno.ENOSYS

    def truncate ( self, path, size ):
        return -errno.ENOSYS

    def unlink ( self, path ):
        return -errno.ENOSYS

    def utime ( self, path, times ):
        return -errno.ENOSYS

    def write ( self, path, buf, offset ):
        return -errno.ENOSYS

    # Utility methods
    def get_real_path(self, path):
        """
        I translate a conceptual path (e.g.,
        /Users/kacarstensen/Documents/foo/bar/baz into the actual path
        (which may be something like
        /mountpoint/.HFS_private_whatever/dir_5323123/), and return that
        to my caller.
        """
        return path

    def run_operation_on_real_path(self, path, op):
        """
        I translate my path argument into an actual path, then run the
        given callback on that path. If the operation completes and
        returns something, I return that to my caller. If the operation
        raises an exception, I return None to my caller.
        """
        realpath = self.get_real_path(path)
        result = None
        try:
            result = op(path)
        except OSError:
            pass
        finally:
            return result
