import sys
import time

from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

import fffs

def extract_prefix(path):
    assert path[0] == '/'
    i = path.find('/', 1)
    if i < 0:
        return (path[1:], None)
    else:
        return (path[1:i], path[i+1:])

class FuseAdapter(LoggingMixIn, Operations):
    def __init__(self):
        self.store = fffs.Store()
        self.fs = fffs.Filesystem(self.store)

        file1 = self.store.new_file("xxxxxx")
        dir1 = self.store.new_dir([fffs.DirEntry("file1", fffs.FILE_TYPE, file1.id)])
        image1 = self.store.new_image(dir1, False)

        self.now = time.time()
        now = self.now
        self.images = {"image1": image1.id}
        self.dir_attrs = dict(st_mode=(S_IFDIR | 0755), st_ctime=now,
                               st_mtime=now, st_atime=now, st_nlink=2)
        self.file_attrs = dict(st_mode=(S_IFREG | 0755), st_nlink=1,
                                st_size=0, st_ctime=now, st_mtime=now,
                                st_atime=now)

    def readdir(self, path, fh):
        names = ['.', '..']
        if path == "/":
            names.extend(self.images.keys())
        else:
            prefix, rest = extract_prefix(path)
            if not (prefix in self.images):
                raise FuseOSError(ENOENT)

            image_id = self.images[prefix]
            image = self.store.get_image(image_id)
            if rest == None:
                rest = '.'
            dir = self.fs.get_dir(image, rest)
            for entry in dir.entries:
                names.append(entry.name)

        return names

    def getattr(self, path, fh=None):
        if path == "/":
            return dict(self.dir_attrs)

        prefix, rest = extract_prefix(path)
        if not (prefix in self.images):
            raise FuseOSError(ENOENT)

        if rest == None:
            return dict(self.dir_attrs)
        else:
            image = self.store.get_image(self.images[prefix])
            entry = self.fs.get_entry(image, rest)
            if entry == None:
                raise FuseOSError(ENOENT)
            else:
                if entry.type == fffs.DIR_TYPE:
                    return self.dir_attrs
                else:
                    return self.file_attrs

    def mkdir(self, path, mode):
        prefix, rest = extract_prefix(path)
        if not (prefix in self.images):
            raise FuseOSError(ENOENT)

        if rest == None:
            raise FuseOSError(ENOENT) # TODO: should be, already exists or something

        image = self.store.get_image(self.images[prefix])
        new_image = self.fs.make_dir(image, rest)
        self.images[prefix] = new_image.id

    def getxattr(self, path, name, position=0):
        return ''       # Should return ENOATTR

    def listxattr(self, path):
        return []

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG)
    if len(sys.argv) != 2:
        print('usage: %s <mountpoint>' % sys.argv[0])
        exit(1)

    logging.getLogger().setLevel(logging.DEBUG)
    fuse = FUSE(FuseAdapter(), sys.argv[1], foreground=True)
