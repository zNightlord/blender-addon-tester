import os
import sys
import shutil
import subprocess
import zipfile
import tarfile
import requests
import re
from glob import glob
from bs4 import BeautifulSoup
from distutils.dir_util import copy_tree

CURRENT_MODULE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))

def getSuffix(blender_version):
    print(sys.platform)
    if "win32" == sys.platform or "win64" == sys.platform or "cygwin" == sys.platform:
        machine = "windows64"
        ext = "zip"
    elif "darwin" == sys.platform:
        machine = "(macOS|OSX)"
        ext = "(dmg|zip)"
    else:
        machine = "linux.*64"
        ext = "tar.+"

    g = re.search(f"\d\.\d\d", blender_version)
    if g:
        rev = g.group(0)
    else:
        raise RuntimeError("Blender version cannot be guessed in the following string: {0}".format(blender_version))
        
    urls = [
        f"https://ftp.nluug.nl/pub/graphics/blender/release/Blender{rev}",
        "https://builder.blender.org/download",
    ]
    blender_zippath = None
    nightly = False
    for url in urls:
        page = requests.get(url)
        data = page.text
        soup = BeautifulSoup(data, features="html.parser")
        
        blender_version_suffix = ""
        versions_found = []
        for link in soup.find_all("a"):
            x = str(link.get("href"))
            #print(x)
            g = re.search(f"blender-(.+)-{machine}.+{ext}", x)
            if g:
                version_found = g.group(1).split("-")[0]
                versions_found.append(version_found)
                if version_found == blender_version:
                    blender_zippath = f"{url}/{g.group(0)}"
                    if url == urls[1]:
                        nightly = True
     
    if None == blender_zippath:
        print(soup)
        raise Exception(f"Unable to find {blender_version} in nightlies, here is what is available {versions_found}")
    
    return blender_zippath, nightly


def getBlender(blender_version, blender_zippath, nightly):
    """ Downloads Blender v'blender_version'//'nightly' if not yet in cache. Returns a decompressed Blender release path.
    """
    remove = False
    cwd = os.getcwd()
    if "BLENDER_CACHE" in os.environ.keys():
        print(f"BLENDER_CACHE environment variable found {os.environ['BLENDER_CACHE']}")
        cache_path = os.path.expanduser(os.environ["BLENDER_CACHE"])
        if not os.path.exists(cache_path):
            print(f"Creating cache directory: {cache_path}")
            os.makedirs(cache_path)
        else:
            print(f"Cache directory already exists: {cache_path}")
    else:
        cache_path = ".."
    os.chdir(cache_path)
    
    cache_dir = os.getcwd()

    ext = ""
    if nightly == True:
        ext = "-nightly"
    dst = os.path.join(cache_dir, f"blender-{blender_version}{ext}")

    if os.path.exists(dst):
        if nightly == True or remove:
            print(f"Removing directory (nightly:{nightly}, remove:{remove}): {dst}")
            shutil.rmtree(dst)
        else:
            print(f"Blender {blender_version} (non-nightly) release found at: {dst}")
            os.chdir(cwd)
            return dst

    blender_zipfile = blender_zippath.split("/")[-1]

    files = glob(blender_zipfile)

    is_osx_archive = False

    if 0 == len(files):
        if not os.path.exists(blender_zipfile):
            r = requests.get(blender_zippath, stream=True)
            print(f"Downloading {blender_zippath}")
            open(blender_zipfile, "wb").write(r.content)

    if blender_zipfile.endswith("zip"):
        z = zipfile.ZipFile(blender_zipfile, "r")
        zfiles = z.namelist()
        zdir = zfiles[0].split("/")[0]

        # Some .zip archives main abnormally contain an OSX release
        # Example case: https://ftp.nluug.nl/pub/graphics/blender/release/Blender2.78/blender-2.78c-OSX_10.6-x86_64.zip
        for zfile in zfiles:
            if re.search(".*OSX.*", zfile):
                is_osx_archive = True
                zdir = os.path.join(zdir, "blender.app/Contents")
        if is_osx_archive:
            print("Detected old-style type of MacOSX release: a .zip archive (instead of .dmg) containing a directory.")
    elif blender_zipfile.endswith("dmg"):
        is_osx_archive = True
        from dmglib import attachedDiskImage
        with attachedDiskImage(blender_zipfile) as mounted_dmg:
            print(f"Mounted {blender_zipfile}")
            print(f'Copying Blender out of mounted space from {mounted_dmg[0]}/Blender.app to {os.path.realpath(".")}...')
            copy_tree(f'{mounted_dmg[0]}/Blender.app', os.path.realpath("."))
        zdir = "./Contents"
    elif blender_zipfile.endswith("tar.bz2"):
        z = tarfile.open(blender_zipfile)
        zfiles = z.getnames()
        zdir = zfiles[0].split("/")[0]
    else:
        print("Error, unknown archive extension: {blender_zipfile}. Will not extract it.}")
        exit(1)

    # Directories for MacOSX have a special structure, doing more checks first
    if is_osx_archive:
        expected_executable_dir = os.path.realpath("./Contents/MacOS")
        executable_path = glob(f"{expected_executable_dir}/*lender")
        if executable_path:
            print("Blender MacOS executable found at:", executable_path)
        else:
            print("Error, Blender MacOS executable not found in directory:", expected_executable_dir)
            exit(1)
 
        zfiles = []
        for root, directories, filenames in os.walk(zdir):
            for filename in filenames:
                zfiles.append(os.path.realpath(os.path.join(root,filename)))

    if not os.path.isdir(zdir):
        print(f"Unpacking {blender_zipfile}")
        z.extractall()
        z.close()
    blender_archive = os.path.realpath(zdir)

    python = None
    for zfile in zfiles:
        if re.search("bin/python.exe", zfile) or re.search("bin/python\d.\dm?", zfile):
            python = os.path.realpath(zfile)
            print(f"Blender's bundled python executable was found: {python}")
            break
    if not python:
        print("ERROR, Blender's bundled python executable could not be found within Blender's files")
        exit(1)

    if "cygwin" == sys.platform:
        print("ERROR, do not run this under cygwin, run it under Linux and Windows cmd!!")
        exit(1)

    if sys.platform.startswith("win"):
        import urllib.request
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", "get-pip.py")
        cmd = f"{python} get-pip.py"
        os.system(cmd)
    else:
        cmd = f"{python} -m ensurepip"
        os.system(cmd)

    cmd = f"{python} -m pip install --upgrade -r {CURRENT_MODULE_DIRECTORY}/blender_requirements.txt -r {CURRENT_MODULE_DIRECTORY}/requirements.txt"
    os.system(cmd)


    shutil.rmtree("tests/__pycache__", ignore_errors=True)

    src = blender_archive
    print(f"Move {src} to {dst}")
    shutil.move(src, dst)
    os.chdir(cwd)

    return dst


def get_blender_from_suffix(blender_version):

    blender_zipfile, nightly = getSuffix(blender_version)

    return getBlender(blender_version, blender_zipfile, nightly)


if __name__ == "__main__":
    if "cygwin" == sys.platform:
        print("ERROR, do not run this under cygwin, run it under Linux and Windows cmd!!")
        exit(1)

    if len(sys.argv) >= 2:
        blender_rev = sys.argv[1]
    else:
        blender_rev = "2.79b"

    if re.search("-", blender_rev):
        blender_rev, _ = blender_rev.split("-")

    get_blender_from_suffix(blender_rev)
