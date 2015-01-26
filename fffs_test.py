from fffs import *

def test_make_file():
    fs = Filesystem(Store())
    i1 = Image(fs.new_id(), fs.EMPTY_DIR, False)
    i2 = fs.set_file(i1, "file", "/file")
    assert not fs.entry_exists(i1, "file")
    assert fs.entry_exists(i2, "file")

def test_make_dir():
    fs = Filesystem(Store())
    i1 = Image(fs.new_id(), fs.EMPTY_DIR, False)
    i2 = fs.make_dir(i1, "dir")
    assert not fs.entry_exists(i1, "dir")
    assert fs.entry_exists(i2, "dir")

def test_make_nested_dir():
    fs = Filesystem(Store())
    i1 = Image(fs.new_id(), fs.EMPTY_DIR, False)
    i2 = fs.make_dir(i1, "dir1")
    i3 = fs.make_dir(i2, "dir1/dir2")
    assert fs.entry_exists(i3, "dir1")
    assert fs.entry_exists(i3, "dir1/dir2")

def test_overwrite_file():
    fs = Filesystem(Store())
    i1 = Image(fs.new_id(), fs.EMPTY_DIR, False)
    i2 = fs.set_file(i1, "file", "/file1")
    i3 = fs.set_file(i1, "file", "/file2")
    assert fs.get_file(i2, "file").path == "/file1"
    assert fs.get_file(i3, "file").path == "/file2"

def test_unlink():
    fs = Filesystem(Store())
    i1 = Image(fs.new_id(), fs.EMPTY_DIR, False)
    i2 = fs.set_file(i1, "file", "/file")
    i3 = fs.unlink(i2, "file")
    assert fs.entry_exists(i2, "file")
    assert not fs.entry_exists(i3, "file")

def test_rename_in_same_dir():
    fs = Filesystem(Store())
    i1 = Image(fs.new_id(), fs.EMPTY_DIR, False)
    i2 = fs.set_file(i1, "file1", "/file")
    i3 = fs.rename(i2, "file1", "file2")
    assert fs.entry_exists(i3, "file2")
    assert not fs.entry_exists(i3, "file1")

def test_rename_in_different_dir_1():
    fs = Filesystem(Store())
    i1 = Image(fs.new_id(), fs.EMPTY_DIR, False)
    i2 = fs.make_dir(i1, "dir1")
    i3 = fs.set_file(i2, "file1", "/file")
    i4 = fs.rename(i3, "file1", "dir1/file1")
    assert fs.entry_exists(i4, "dir1/file1")
    assert not fs.entry_exists(i4, "file1")

def test_rename_in_different_dir_2():
    fs = Filesystem(Store())
    i1 = Image(fs.new_id(), fs.EMPTY_DIR, False)
    i2 = fs.make_dir(i1, "dir1")
    i3 = fs.set_file(i2, "dir1/file1", "/file")
    i4 = fs.rename(i3, "dir1/file1", "file1")
    assert fs.entry_exists(i4, "file1")
    assert not fs.entry_exists(i4, "dir1/file1")
