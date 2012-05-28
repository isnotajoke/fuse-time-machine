import fuse
import os

fuse.fuse_python_api = (0, 2)
fuse.feature_assert('stateful_files')

class TimeMachineFS(fuse.Fuse):
    """
    A fuse.Fuse subclass to interface with a mounted time machine backup.
    """
    # FUSE API methods
    def getattr(self, path):
        return self.run_operation_on_real_path(path, os.lstat)

    def readdir(self, path, offset):
        entries = self.run_operation_on_real_path(path, os.listdir)
        for e in entries:
            yield fuse.Direntry(e)

    def statfs(self):
        return self.run_operation_on_real_path(path, os.statvfs)

    def access(self, path, mode):
        res = self.run_operation_on_real_path(path, lambda rp: os.access(rp, mode))
        # convert True/False return to 0 or 1 as appropriate.
        if res:
            return 0
        return 1

    def readlink(self, path):
        return self.run_operation_on_real_path(path, os.readlink)

    class TimeMachineFile(object):
        def __init__(self, path, flags):
            self.realpath = self.fuse_object.get_real_path(path)
            # ignore flags and mode, we're read-only, and should only ever read
            # things.
            self.fo = open(self.realpath, "r")

        def read(self, length, offset):
            self.fo.seek(offset)
            return self.fo.read(length)

        def release(self, flags):
            self.fo.close()

        def fgetattr(self):
            return os.lstat(self.realpath)

        # write capabilities aren't implemented.

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
        if path.startswith("/"):
            path = path[1:]
        comps = self.split_path(path)
        # Check each component for validity.
        path = self.basedir
        for comp in comps:
            candidate = os.path.join(path, comp)

            # the candidate can be a directory, in which case we keep
            # going...
            if os.path.isdir(candidate):
                path = candidate
                continue
            # otherwise, it's a file, and we need to stat it to learn
            # more about it.
            st_info = os.lstat(candidate)

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
        realpath = self.get_real_path(path)
        result = op(realpath)
        return result

    def check_hfs_path(self):
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

        return True

    def check_hostname(self):
        # Now check that self.hostname is an actual hostname in the mountpoint and
        # has a Latest dir to restore
        path_to_hd = os.path.join(self.hfs_path, "Backups.backupdb", self.hostname, "Latest")
        try:
            os.stat(path_to_hd)
        except OSError:
            return False

        # Note that Latest is a symlink to another directory. Since
        # we're programmed to not follow symlinks, we need to evaluate
        # that before we set it as the basedir.
        target = os.readlink(path_to_hd)
        path_to, latest = os.path.split(path_to_hd)
        path_to_hd = os.path.join(path_to, target)

        self.basedir = path_to_hd

        return True

    def main(self, *a, **kw):
        self.file_class = self.TimeMachineFile
        self.file_class.fuse_object = self

        if not hasattr(self, "hfs_path"):
            self.parser.error("error: HFS path not specified")

        if not self.check_hfs_path():
            self.parser.error("error: invalid HFS path specified")

        if not hasattr(self, "hostname"):
            self.parser.error("error: hostname not specified")

        if not self.check_hostname():
            self.parser.error("error: invalid hostname specified")

        return fuse.Fuse.main(self, *a, **kw)


if __name__=="__main__":
    fs = TimeMachineFS(version="%prog " + fuse.__version__,
                       usage="read-only FUSE interface to a time machine drive")
    fs.parser.add_option("--hfs-path", help="Path to mounted HFS+ filesystem",
                         action='store', dest='hfs_path', default=None, nargs=1)
    fs.parser.add_option("--hostname", help="Hostname of the system to be recovered",
                         action='store', dest='hostname', default=None, nargs=1)

    # causes parsed options to be stored as attributes in fs, e.g., fs.hostname, fs.hfs_path
    fs.parse(values=fs, errex=1)
    fs.main()
