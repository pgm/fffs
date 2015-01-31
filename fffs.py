__author__ = 'pmontgom'

# TODO: Add reference counting
# TODO: Add checks for failure conditions:
#   cannot unlink missing file
#   when making dir, all parent dirs must exist
#   when creating a dir, all parent dirs must exist
#   when renaming dir, source must exist and dest must not exist

class Dir:
    def __init__(self, id, entries):
        assert isinstance(id, int)
        self.id = id
        self.entries = entries

    def get_entry(self, name):
        m = [x for x in self.entries if x.name == name]
        if len(m) == 0:
            return None
        elif len(m) > 1:
            raise Exception("Found multiple entries with the name %r" % name)
        assert len(m) == 1
        return m[0]

class File:
    def __init__(self, id, path):
        assert isinstance(id, int)
        self.id = id
        self.path = path

class DirEntry:
    def __init__(self, name, type, id):
        assert isinstance(id, int)
        self.name = name
        self.type = type
        self.id = id

class Image:
    def __init__(self, id, dir, is_frozen):
        assert isinstance(id, int)
        assert isinstance(dir, Dir)
        self.id = id
        self.dir = dir
        self.is_frozen = is_frozen

class Store:
    def __init__(self):
        self.dirs = {}
        self.files = {}
        self.images = {}
        self.next_id = 1
    def get_dir(self, id):
        return self.dirs[id]
    def get_file(self, id):
        return self.files[id]
    def get_image(self, id):
        return self.images[id]
    def store_dir(self, dir):
        self.dirs[dir.id] = dir
    def store_file(self, file):
        self.files[file.id] = file
    def store_image(self, image):
        self.images[image.id] = image
    def new_id(self):
        n = self.next_id
        self.next_id += 1
        return n
    def new_image(self, dir, is_frozen):
        assert dir != None
        f = Image(self.new_id(), dir, is_frozen)
        self.store_image(f)
        return f
    def new_dir(self, entries):
        f = Dir(self.new_id(), entries)
        self.store_dir(f)
        return f
    def new_file(self, path):
        assert path != None
        f = File(self.new_id(), path)
        self.store_file(f)
        return f

DIR_TYPE = "D"
FILE_TYPE = "F"

class Filesystem:
    def __init__(self, store):
        self.store = store
        self.EMPTY_DIR = store.new_dir([])

    def new_id(self):
        return self.store.new_id()

    def clone_dir_with_replacement(self, dir, name, new_value_type, new_value):
        assert isinstance(dir, Dir)
        assert isinstance(new_value, int) or new_value is None

        entries = []
        found_name = False

        for existing_entry in dir.entries:
            if existing_entry.name == name:
                if new_value != None:
                    entries.append(DirEntry(name, new_value_type, new_value))
                found_name = True
            else:
                entries.append(existing_entry)

        if not found_name and new_value != None:
            entries.append(DirEntry(name, new_value_type, new_value))

        return self.store.new_dir(entries)

    def get_dirs(self, parent_dir, vpath_parts):
        parent_dirs = []
        for dir_name in vpath_parts:
            if dir_name != ".":
                de = parent_dir.get_entry(dir_name)
                assert de != None, "get_entry(%r) on %r returned None" % (dir_name, parent_dir)
                assert de.type == DIR_TYPE
                parent_dir = self.store.get_dir(de.id)
            assert parent_dir != None
            parent_dirs.append(parent_dir)
        return parent_dirs

    def split(self, vpath):
        if not vpath.startswith("/"):
            vpath = "./" + vpath
        return vpath.split("/")

    def clone_recursive_clone_with_replacement(self, parent_dir, vpath, new_value_type, new_value):
        vpath_parts = self.split(vpath)
        filename = vpath_parts[-1]

        parent_dirs = self.get_dirs(parent_dir, vpath_parts[:-1])
        assert len(vpath_parts)-1 == len(parent_dirs)

        name = filename
        for i in reversed(range(len(vpath_parts)-1)):
            parent_dir = parent_dirs[i]
            new_parent_dir = self.clone_dir_with_replacement(parent_dir, name, new_value_type, new_value)
            # for the next iteration
            new_value = new_parent_dir.id
            new_value_type = DIR_TYPE
            name = vpath_parts[i]

        return new_parent_dir

    def set_file(self, image, vpath, path):
        "returns new dir object and new file object"
        new_file = self.store.new_file(path)
        new_dir = self.clone_recursive_clone_with_replacement(image.dir, vpath, FILE_TYPE, new_file.id)
        return self.store.new_image(new_dir, False)

    def make_dir(self, image, vpath):
        new_dir = self.clone_recursive_clone_with_replacement(image.dir, vpath, DIR_TYPE, self.EMPTY_DIR.id)
        return self.store.new_image(new_dir, False)

    def rename(self, image, existing_vpath, new_vpath):
        old_file_id = self.get_entry(image, existing_vpath).id
        old_file = self.store.get_file(old_file_id)
        image_1 = self.unlink(image, existing_vpath)
        return self.set_file(image_1, new_vpath, old_file)

    def read(self, image, path, size, offset):
        file = self.get_file(image, path)
        fd = open(file.path, "r")
        fd.seek(offset)
        buffer = fd.read(size)
        fd.close()
        return buffer

    def unlink(self, image, vpath):
        new_dir = self.clone_recursive_clone_with_replacement(image.dir, vpath, None, None)
        return self.store.new_image(new_dir, False)

    def get_entry(self, image, vpath):
        parts = self.split(vpath)
        dirs = self.get_dirs(image.dir, parts[:-1])
        return dirs[-1].get_entry(parts[-1])

    def get_file(self, image, vpath):
        de = self.get_entry(image, vpath)
        assert de.type == FILE_TYPE
        return self.store.get_file(de.id)

    def get_dir(self, image, vpath):
        if vpath == ".":
            return image.dir
        de = self.get_entry(image, vpath)
        assert de.type == DIR_TYPE
        return self.store.get_dir(de.id)

    def entry_exists(self, image, vpath):
        return self.get_entry(image, vpath) != None

# class Writer:
#     def __init__(self, fh, fd, vpath, data_file):
#         self.fd = fd
#         self.vpath = vpath
#         self.data_file = data_file
#
# import errno
# import fuse
#
# def psplit(path):
#     assert path.startswith("/")
#     t = path.find("/")
#     prefix = path[:t]
#     vpath = path[(t+1):]
#     return (prefix, vpath)
#
# class FuseBinding(fuse.Operations):
#     def __init__(self, fs):
#         self.fs = fs
#         self.active_writers_by_fh = {}
#         self.active_writers_by_path = {}
#         self.prefix_to_image = {}
#
#     def mkdir(self, path, mode):
#         prefix, vpath = psplit(path)
#         image = self.prefix_to_image[prefix]
#         new_image = self.fs.make_dir(image, vpath)
#         self.prefix_to_image[prefix] = new_image
#
#     def rmdir(self, path):
#         prefix, vpath = psplit(path)
#         image = self.prefix_to_image[prefix]
#         new_image = self.fs.unlink(image, vpath)
#         self.prefix_to_image[prefix] = new_image
#
#     def readdir(self, path, fh):
#         # get dirs and merge in active_writers
#         yield fuse.Direntry(".")
#         yield fuse.Direntry("..")
#
#     def open(self, path, flags):
#         prefix, vpath = psplit(path)
#         if writing:
#             assert file does not exist
#             w = Writer(new_fh(), fd, vpath, data_file)
#             self.active_writers_by_fh[w.fh] = w
#             self.active_writers_by_path[w.vpath] = w
#
#     def create(self, path, mode, fi=None):
#         return -errno.ENOSYS
#     def read(self, path, length, offset, fh):
#         return -errno.ENOSYS
#     def write(self, path, buf, offset, fh):
#         return -errno.ENOSYS
#
#     def release(self, path, fh):
#         w = self.active_writers_by_fh[fh]
#         self.fs.set_file(image, w.vpath, w.data_file)
#         return -errno.ENOSYS
