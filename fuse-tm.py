import fuse # for fuse_python_api
from fuse import Fuse

import argparse
import errno
import os
import stat
import sys
import syslog

fuse.fuse_python_api = (0, 2)
fuse.feature_assert('stateful_files')

class TimeMachineFS(Fuse):
    """
    A FUSE interface to interface with a time machine backup.
    """
    def check_options(self):
        """
        I check to make sure that the self.hfs_path attribute points to
        a mounted filesystem that looks like a time machine
        implementation, and that the self.hostname exists.
        """
        # check that self.hfs_path exists...
        try:
            dirents = os.listdir(self.hfs_path)
        except OSError: # doesn't exist, not a directory, etc
            return False

        # ...and that it contains the private directory that we're
        # looking for.
        self.private_dir = None
        for de in dirents:
            if de.startswith(".HFS+ Private Directory Data"):
                self.private_dir = os.path.join(self.hfs_path, de)
                break

        if self.private_dir is None:
            return False

        # Now check that self.hostname is an actual hostname in the mountpoint and
        # has a Latest dir to restore
        path_to_hd = os.path.join(self.hfs_path, "Backups.backupdb", self.hostname, "Latest")
        try:
            os.stat(path_to_hd)
        except OSError:
            return False

        self.basedir = path_to_hd

        return True

    # FUSE API methods
    def getattr(self, path):
        """
        Return stats for path by translating it to a real path and then
        running stat on it normally.
        """
        syslog.syslog("handling getattr on %s" % path)
        return self.run_operation_on_real_path(path, os.stat)

    def readdir(self, path, offset):
        syslog.syslog("handling readdir on %s" % path)
        entries = self.run_operation_on_real_path(path, os.listdir)
        syslog.syslog("got entries %s for %s" % (entries, path))
        if entries is not None:
            for e in entries:
                yield fuse.Direntry(e)

    def statfs ( self ):
        syslog.syslog('handling statfs')
        return self.run_operation_on_real_path(path, os.statvfs)

    def access(self, path, mode):
        res = self.run_operation_on_real_path(path, lambda rp: os.access(rp, mode))
        if res:
            return 0
        return 1

    def readlink ( self, path ):
        syslog.syslog("reading link at %s" % path)
        target = self.run_operation_on_real_path(path, os.readlink)
        return self.get_real_path(target)

    class TimeMachineFile(object):
        def __init__(self, path, flags):
            self.realpath = self.fuse_object.get_real_path(path)
            # ignore flags and mode, we're read-only
            self.fo = open(self.realpath, "r")

        def read(self, length, offset):
            self.fo.seek(offset)
            return self.fo.read(length)

        def release(self, flags):
            self.fo.close()

        def fgetattr(self):
            return os.stat(self.realpath)

        # write capabilities aren't implemented.

    def main(self, *a, **kw):
        self.file_class = self.TimeMachineFile
        self.file_class.fuse_object = self

        # populate options
        if not hasattr(self, "hfs_path"):
            self.parser.error("error: HFS path not specified")

        if not hasattr(self, "hostname"):
            self.parser.error("error: hostname not specified")

        if not self.check_options():
            self.parser.error("error: bad options")

        return Fuse.main(self, *a, **kw)

    # The following operations aren't supported.
    def rename ( self, oldPath, newPath ):
        syslog.syslog("rename")
        return -errno.ENOSYS

    def rmdir ( self, path ):
        syslog.syslog("rmdir")
        return -errno.ENOSYS

    def mythread(self):
        syslog.syslog("mythread")
        return -errno.ENOSYS

    def chmod (self, path, mode):
        syslog.syslog("chmod")
        return -errno.ENOSYS

    def chown(self, path, uid, gid):
        syslog.syslog("chown")
        return -errno.ENOSYS

    def fsync(self, path, isFsyncFile):
        syslog.syslog("fsync")
        return -errno.ENOSYS

    def link(self, targetPath, linkPath):
        syslog.syslog("link")
        return -errno.ENOSYS

    def mkdir ( self, path, mode ):
        syslog.syslog("mkdir")
        return -errno.ENOSYS

    def mknod ( self, path, mode, dev ):
        syslog.syslog("mknod")
        return -errno.ENOSYS

    def symlink ( self, targetPath, linkPath ):
        syslog.syslog("symlink")
        return -errno.ENOSYS

    def truncate ( self, path, size ):
        syslog.syslog("truncate")
        return -errno.ENOSYS

    def unlink ( self, path ):
        syslog.syslog("unlink")
        return -errno.ENOSYS

    def utime ( self, path, times ):
        syslog.syslog("utime")
        return -errno.ENOSYS

    def write ( self, path, buf, offset ):
        syslog.syslog("write")
        return -errno.ENOSYS

    # Utility methods
    def split_path(self, path):
        """
        Repeatedly call os.path.split to get a list of path components.
        """
        comps = []
        while True:
            head, tail = os.path.split(path)
            if not tail: break
            comps.append(tail)
            path = head
        comps.reverse()
        return comps

    def get_real_path(self, path):
        """
        I translate a conceptual path (e.g.,
        /Users/kacarstensen/Documents/foo/bar/baz into the actual path
        (which may be something like
        /mountpoint/.HFS_private_whatever/dir_5323123/), and return that
        to my caller.
        """
        # leading /s confuse os.path.join
        conceptual_path = ""
        if path.startswith("/"):
            path = path[1:]
            conceptual_path += "/"
        comps = self.split_path(path)
        # Check each component for validity.
        path = self.basedir
        for comp in comps:
            candidate = os.path.join(path, comp)

            if os.path.islink(candidate):
                target = os.readlink(candidate)
                # Does it have a leading /? Then it's an absolute path and we
                # don't have to deal with it.
                if not target.startswith(os.path.pathsep):
                    target = os.path.join(conceptual_path, target)
                candidate = self.get_real_path(target)
                conceptual_path = target
            else:
                conceptual_path = os.path.join(conceptual_path, comp)
            # the candidate can be a directory, in which case we keep
            # going...
            if os.path.isdir(candidate):
                path = candidate
                continue
            # otherwise, it's a file, and we need to stat it to learn
            # more about it.
            st_info = os.stat(candidate)

            # if the size is greater than 0, then it's a file.
            if st_info.st_size > 0 or st_info.st_nlink < 100:
                path = candidate
                continue

            # otherwise, it might be a directory disguised as a file.
            new_path = os.path.join(self.private_dir, "dir_%s" % st_info.st_nlink)
            assert os.path.isdir(new_path)
            path = new_path

        return path

    def run_operation_on_real_path(self, path, op):
        """
        I translate my path argument into an actual path, then run the
        given callback on that path. If the operation completes and
        returns something, I return that to my caller. If the operation
        raises an exception, I return None to my caller.
        """
        syslog.syslog("asked to run an operation on %s" % path)
        realpath = self.get_real_path(path)
        syslog.syslog("this translates to real path %s" % realpath)
        result = None
        try:
            result = op(realpath)
        except OSError, e:
            syslog.syslog('got error %s' % e)
            pass
        finally:
            return result


if __name__=="__main__":
    fs = TimeMachineFS(version="%prog " + fuse.__version__,
                       usage="read-only FUSE interface to a time machine drive")
    fs.debug = True
    fs.parser.add_option("--hfs-path", help="Path to mounted HFS+ filesystem",
                         action='store', dest='hfs_path', default=None, nargs=1)
    fs.parser.add_option("--hostname", help="Hostname of the system to be recovered",
                         action='store', dest='hostname', default=None, nargs=1)

    # causes parsed options to be stored as attributes in fs, e.g., fs.hostname, fs.hfs_path
    fs.parse(values=fs, errex=1)
    fs.main()
