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
EMPTY_FILE_ATTRS = dict(st_mode=(S_IFREG | 0755), st_nlink=1,
                        st_size=0, st_ctime=now, st_mtime=now,
                        st_atime=now)

def mk_file_attrs(size):
    return dict(st_mode=(S_IFREG | 0755), st_nlink=1,
                        st_size=size, st_ctime=now, st_mtime=now,
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
    def __init__(self, fs, image_map, store, transient_paths):
        self.fs = fs
        self.image_map = image_map
        self.store = store
        self.transient_paths = transient_paths

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
        names.extend(self.transient_paths.get_files(path, "."))
        return names

    def getattr(self, path, fh=None):
        if path in self.image_map:
            return DIR_ATTRS
        else:
            raise FuseOSError(ENOENT)

import collections
import os.path
import uuid

class TransientPaths:
    def __init__(self, data_dir):
        self.m = collections.defaultdict(lambda: {})
        self.data_dir = data_dir

    def get_files(self, image, path):
        return self.m[(image, path)].keys()

    def is_transient_file(self, image, path):
        parent_dir, filename = os.path.split(path)
        if parent_dir == '':
            parent_dir = '.'
        return filename in self.m[(image, parent_dir)]

    def add(self, image, path):
        parent, filename = os.path.split(path)
        if parent == '':
            parent = "."
        data_file = os.path.join(self.data_dir, str(uuid.uuid4()))
        self.m[(image, parent)][filename] = data_file

        print "transient_paths", self.m
        #raise Exception("fail")

    def get_size(self, image, path):
        parent, filename = os.path.split(path)
        if parent == '':
            parent = "."
        data_file = self.m[(image, parent)][filename]
        if os.path.exists(data_file):
            size = os.path.getsize(data_file)
        else:
            size = 0
        return size

    def write(self, image, path, data, offset, fh):
        parent, filename = os.path.split(path)
        if parent == '':
            parent = "."
        data_file = self.m[(image, parent)][filename]
        if os.path.exists(data_file):
            size = os.path.getsize(data_file)
        else:
            size = 0
        assert size == offset
        with open(data_file, "a") as fd:
            fd.write(data)
        return len(data)

    def rm(self, image, path):
        data_file = self.release(image, path)

    def release(self, image, path):
        parent_dir, filename = os.path.split(path)
        if parent_dir == '':
            parent_dir = '.'
        data_file = self.m[(image, parent_dir)][filename]
        del self.m[(image, parent_dir)][filename]
        return data_file

class FffsControl:
    def __init__(self, fs, images, name):
        self.name = name
        self.images = images
        self.fs = fs

    def readdir(self, path, fh):
        if path == ".fffs":
            names = ['.', '..', 'id']
            return names
        else:
            raise FuseOSError(ENOTDIR)

    def getattr(self, path, fh=None):
        if path == ".fffs":
            return DIR_ATTRS
        elif path in ['.fffs/id']:
            return EMPTY_FILE_ATTRS
        else:
            raise FuseOSError(ENOENT)

    def read(self, path, size, offset, fh):
        if path == ".fffs/id":
            return str(self.images[self.name])[offset:offset+size]
        else:
            raise FuseOSError(ENOENT)

    def open(self, fd, path, flags):
        pass

class ImageMount:
    # handles all operations on path "/image/dir*"
    def __init__(self, fs, image_id, store, images, name, transient_paths):
        self.fs = fs
        self.image_id = image_id
        self.store = store
        self.images = images
        self.name = name
        self.transient_paths = transient_paths

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

    def read(self, path, size, offset, fh):
        return self.fs.read(self.image, path, size, offset)

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
        elif path == '.fffs':
            return DIR_ATTRS
        elif self.transient_paths.is_transient_file(self.name, path):
            size = self.transient_paths.get_size(self.name, path)
            return mk_file_attrs(size)
        else:
            #print "%r not in %r" % (path, self.transient_paths)
            entry = self.fs.get_entry(self.image, path)
            if entry == None:
                raise FuseOSError(ENOENT)
            else:
                if entry.type == fffs.DIR_TYPE:
                    return DIR_ATTRS
                else:
                    file = self.store.get_file(entry.id)
                    return mk_file_attrs(file.size)

    def open(self, fd, path, flags):
        pass

    def create(self, fd, path, flags, fi):
        #self.transient_paths[fd] = path
        #print "Added %r to transient paths: %r" % (path, self.transient_paths)
        self.transient_paths.add(self.name, path)

    def write(self, path, data, offset, fh):
        return self.transient_paths.write(self.name, path, data, offset, fh)

    def truncate(self, path, length, fh):
        pass

    def unlink(self, path):
        if self.transient_paths.is_transient_file(self.name, path):
            self.transient_paths.rm(self.name, path)

    def release(self, path, fh):
        if self.transient_paths.is_transient_file(self.name, path):
            filename = self.transient_paths.release(self.name, path)
            image_id = self.images[self.name]
            image = self.store.get_image(image_id)
            new_image = self.fs.set_file(image, path, filename)
            self.update_image(new_image)


class FuseAdapter(LoggingMixIn, Operations):
    def __init__(self):
        self.store = fffs.Store("datafiles")
        self.fs = fffs.Filesystem(self.store)

        self.now = time.time()
        self.images = {}
        self.root_mount = RootMount(self.images)
        self.transient_paths = TransientPaths(self.store.data_path)
        self.images_mount = ImagesMount(self.fs, self.images, self.store, self.transient_paths)
        self.next_fd = 0

    def get_delegate(self, path):
        if path == "/":
            print "returning", "/", self.root_mount
            return "/", self.root_mount

        prefix, rest = extract_prefix(path)
        if rest == None:
            print "returning", prefix, self.images_mount
            return prefix, self.images_mount
        elif rest.startswith(".fffs"):
            return rest, FffsControl(self.fs, self.images, prefix)
        if prefix in self.images:
            m = ImageMount(self.fs, self.images[prefix], self.store, self.images, prefix, self.transient_paths)
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

    def read(self, path, size, offset, fh):
        vpath, delegate = self.get_delegate(path)
        print "calling read(%r, %r, %r, %r)" % (vpath, size, offset, fh)
        return delegate.read(vpath, size, offset, fh)

    def open(self, path, flags):
        vpath, delegate = self.get_delegate(path)
        # TODO: is fd necessary?
        fd = self.next_fd
        self.next_fd += 1
        delegate.open(fd, vpath, flags)
        return fd

    def truncate(self, path, length, fh=None):
        vpath, delegate = self.get_delegate(path)
        return delegate.truncate(path, length, fh)

    def write(self, path, data, offset, fh):
        vpath, delegate = self.get_delegate(path)
        return delegate.write(vpath, data, offset, fh)

    def create(self, path, mode, fi=None):
        vpath, delegate = self.get_delegate(path)
        # TODO: is fd necessary?
        fd = self.next_fd
        self.next_fd += 1
        delegate.create(fd, vpath, mode, fi)
        return fd

    def unlink(self, path):
        vpath, delegate = self.get_delegate(path)
        delegate.unlink(vpath)

    def release(self, path, fh):
        vpath, delegate = self.get_delegate(path)
        delegate.release(vpath,fh)
        return 0

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
    fuse = FUSE(FuseAdapter(), sys.argv[1], foreground=True, direct_io=True)
