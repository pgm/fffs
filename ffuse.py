import sys
import time

from errno import ENOENT, EEXIST, ENOTEMPTY, ENOTDIR
from stat import S_IFDIR, S_IFLNK, S_IFREG
from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

import fffs

# TODO: Next step:  mkdir at top level should create a new image
# add support for rmdir
# then test suite

# then open for reading  (only allow opening for reading)
# then writing (this is the hard part)
# then change Store to be persistent



def extract_prefix(path):
    assert path[0] == '/'
    i = path.find('/', 1)
    if i < 0:
        return (path[1:], None)
    else:
        return (path[1:i], path[i+1:])

now = time.time()
DIR_ATTRS = dict(st_mode=(S_IFDIR | 0755), st_ctime=now,
                       st_mtime=now, st_atime=now, st_nlink=2)
FILE_ATTRS = dict(st_mode=(S_IFREG | 0755), st_nlink=1,
                        st_size=0, st_ctime=now, st_mtime=now,
                        st_atime=now)

class RootMount:
    # handles all operations on the path "/"
    def __init__(self, image_map):
        self.image_map = image_map

    def mkdir(self, path, mode):
        raise FuseOSError(EEXIST)

    def rmdir(self, path):
        raise FuseOSError(ENOTEMPTY)

    def readdir(self, path, fh):
        names = ['.', '..']
        names.extend(self.image_map.keys())
        return names

    def getattr(self, path, fh=None):
        return DIR_ATTRS

class ImagesMount:
    # handles all operations on path "/image"
    def __init__(self, fs, image_map, store):
        self.fs = fs
        self.image_map = image_map
        self.store = store

    def mkdir(self, path, mode):
        if path in self.image_map:
            raise FuseOSError(EEXIST)

        new_dir = self.store.new_dir([])
        new_image = self.store.new_image(new_dir, False)
        self.image_map[path] = new_image.id

    def rmdir(self, path):
        if not (path in self.image_map):
            raise FuseOSError(ENOENT)

        # TODO: should check to see image dir is empty

        del self.image_map[path]

    def readdir(self, path, fh):
        names = ['.', '..']
        image_id = self.image_map[path]
        image = self.store.get_image(image_id)
        dir = image.dir #self.fs.get_dir(image, path)
        for entry in dir.entries:
            names.append(entry.name)
        return names

    def getattr(self, path, fh=None):
        if path in self.image_map:
            return DIR_ATTRS
        else:
            raise FuseOSError(ENOENT)

class ImageMount:
    # handles all operations on path "/image/dir*"
    def __init__(self, fs, image_id, store, images, name):
        self.fs = fs
        self.image_id = image_id
        self.store = store
        self.images = images
        self.name = name

    @property
    def image(self):
        return self.store.get_image(self.image_id)

    def update_image(self, new_image):
        self.images[self.name] = new_image.id

    def mkdir(self, path, mode):
        entry = self.fs.get_entry(self.image, path)
        if entry != None:
            raise FuseOSError(EEXIST)

        new_image = self.fs.make_dir(self.image, path)
        self.update_image(new_image)

    def rmdir(self, path):
        entry = self.fs.get_entry(self.image, path)
        if entry == None:
            raise FuseOSError(ENOENT)

        if entry.type != fffs.DIR_TYPE:
            raise FuseOSError(ENOTDIR)

        dir = self.store.get_dir(entry.id)
        if len(dir.entries) > 0:
            raise FuseOSError(ENOTEMPTY)

        new_image = self.fs.unlink(self.image, path)
        self.update_image(new_image)

    def readdir(self, path, fh):
        names = ['.', '..']
        entry = self.fs.get_entry(self.image, path)
        if entry == None:
            raise FuseOSError(ENOENT)

        if entry.type != fffs.DIR_TYPE:
            raise FuseOSError(ENOTDIR)

        dir = self.store.get_dir(entry.id)
        for entry in dir.entries:
            names.append(entry.name)

        return names

    def getattr(self, path, fh=None):
        if path == ".":
            return DIR_ATTRS
        else:
            entry = self.fs.get_entry(self.image, path)
            if entry == None:
                raise FuseOSError(ENOENT)
            else:
                if entry.type == fffs.DIR_TYPE:
                    return DIR_ATTRS
                else:
                    return FILE_ATTRS


class FuseAdapter(LoggingMixIn, Operations):
    def __init__(self):
        self.store = fffs.Store()
        self.fs = fffs.Filesystem(self.store)

        file1 = self.store.new_file("xxxxxx")
        dir1 = self.store.new_dir([fffs.DirEntry("file1", fffs.FILE_TYPE, file1.id)])
        image1 = self.store.new_image(dir1, False)

        self.now = time.time()
        self.images = {"image1": image1.id}
        self.root_mount = RootMount(self.images)
        self.images_mount = ImagesMount(self.fs, self.images, self.store)

    def get_delegate(self, path):
        if path == "/":
            print "returning", "/", self.root_mount
            return "/", self.root_mount

        prefix, rest = extract_prefix(path)
        if rest == None:
            print "returning", prefix, self.images_mount
            return prefix, self.images_mount

        if prefix in self.images:
            m = ImageMount(self.fs, self.images[prefix], self.store, self.images, prefix)
            print "returning", rest, m
            return rest, m

        raise FuseOSError(ENOENT)

    def readdir(self, path, fh):
        vpath, delegate = self.get_delegate(path)
        return delegate.readdir(vpath, fh)

    def getattr(self, path, fh=None):
        vpath, delegate = self.get_delegate(path)
        return delegate.getattr(vpath, fh)

    def mkdir(self, path, mode):
        vpath, delegate = self.get_delegate(path)
        return delegate.mkdir(vpath, mode)

    def rmdir(self, path):
        vpath, delegate = self.get_delegate(path)
        return delegate.rmdir(vpath)

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
