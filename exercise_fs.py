import os
import os.path
import subprocess
import shutil
import time

def exercise_basic_operations(base_dir):
    ffuse_log = open("ffuse.log", "w")
    p = subprocess.Popen(["python","ffuse.py", base_dir], stderr=subprocess.STDOUT, stdout=ffuse_log)
    # fix this: need to wait a little for the mount to come online before we run our test
    time.sleep(2)
    assert p.poll() == None
    try:
        print "making image"
        os.mkdir(base_dir+"/a")
        
        print "checking .fffs dir"
        assert "id" in os.listdir(base_dir+"/a/.fffs")
        
        with open(base_dir+"/a/.fffs/id", "r") as fd:
          version = fd.read()

        print "checking listdir of images"
        assert "a" in os.listdir(base_dir)

        print "writing a file"
        with open(base_dir+"/a/f", "w") as fd:
          fd.write("data")

        print "checking listdir within image"
        assert "f" in os.listdir(base_dir+"/a")

        print "verifying file size"
        assert os.path.getsize(base_dir+"/a/f") == 4

        print "verifying file content"
        with open(base_dir+"/a/f", "r") as fd:
          assert "data" == fd.read()
    finally:
        p.terminate()
        print "Waiting for mount to terminate"
        p.wait()
        ffuse_log.close()

if __name__ == "__main__":
    base_dir = "x_mm_test"
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)

    os.mkdir(base_dir)
    exercise_basic_operations(base_dir)