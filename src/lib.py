"""Artnotizen organizes all dated files in a given directory in year/month/day
folders, compiles are markdown files to HTML, and constructs an easy to navigate
single-page index in index.html."""
from collections import OrderedDict
from datetime import datetime
import os
import pipes
import re
import shlex
import subprocess
import sys
import time
import urllib
import urlparse
from jinja2 import Environment, PackageLoader, FileSystemLoader

_GENFILES_REGEXP = re.compile(r"(index\.html$)|(lib/.*)$")
_DATE_REGEXP = re.compile(r"^(\d{4})(\d{2})?(\d{2})?.*")
_DATE_PATH_REGEXP = re.compile(r"(\d{4})/(\d{2})?/?(\d{2})?/?.*")
_LIBRARY_URLS = [
    "http://ajax.googleapis.com/ajax/libs/jquery/1.10.2/jquery.min.js",
    "http://ajax.googleapis.com/ajax/libs/jqueryui/1.10.3/jquery-ui.min.js",
]

def is_hidden(path):
    """Check whether given path is hidden.

    Only works for POSIX, checks for basename starting with '.'.

    Args:
        path: path to check for hidden status, absolute or relative

    Returns:
        Boolean hidden status
    """
    return os.path.basename(os.path.abspath(path))[0] == "."

def listfiles(path, hidden=False):
    """Recursively list all files below a given path. Mimics find -type f.

    Args:
        path: path to search for files

    Returns:
        Flat list of files relative to path
    """
    all_files = []
    for root, dirnames, files in os.walk(path, topdown=True):
        if not hidden:
            if is_hidden(root):
                # dirnames must be modified in-place to affect subsequent
                # iterations
                dirnames[:] = []
                continue
            files = [f for f in files if not is_hidden(f)]
        all_files.extend([os.path.join(root, f) for f in files])
    return all_files

def organize_notes(directory):
    """Organize notes into year/month/day folders in the given directory.
    Filenames are preserved, and only files matching ^\\d{4}(\\d{2})?(\\d{2})?.*
    are affected.

    Args:
        directory: string to current working directory

    Returns:
        A list of all matching dated notes and a list of other files
    """
    all_files = listfiles(directory)
    notes = [f for f in all_files
             if _DATE_REGEXP.match(os.path.basename(f))]
    others = [os.path.join(directory, f )for f in all_files
              if not f in notes and not _GENFILES_REGEXP.match(f)]
    out = []
    for note in notes:
        year, month, day = _DATE_REGEXP.match(os.path.basename(note)).groups("")
        note_dir = os.path.join(directory, year, month, day)
        dst = os.path.join(note_dir, os.path.basename(note))
        if note != dst:
            # Handles directory creation and file move
            os.renames(note, dst)
        out.append(dst)
    return out, others

def wait_for_all(running, delay, callback=None):
    """Poll all processes in running at interval delay until all are complete.

    WARNING: This function modifies running in-place. Any further processing of
    its processes should be handled using the callback argument.

    Args:
        running: dictionary with subprocess.Popen values.
        delay: polling interval in seconds.
        callback: optional function of (key, proc) to be called on the
            completion of proc if proc has a return code of 0.

    Returns:
        None on completion of all processes.
    """
    while running:
        for key, proc in running.iteritems():
            retcode = proc.poll()
            if retcode is not None:
                if retcode != 0:
                    print >> sys.stderr, "{} returned with value {}".format(
                        key, retcode)
                elif callback is not None:
                    callback(key, proc)
                del running[key]
                break
        else:
            time.sleep(delay)
            continue

def compile_markdown(files, markdown_ext, markdown_cmd, delay=0.1):
    """Select and compile markdown files from files to HTML.

    Args:
        files: list of files to filter and compile
        ext: file extension for markdown files
        cmd: command to compile markdown to html. Must write to stdout.
        delay: polling delay for launched compilation processes.

    Returns:
        A list of the same length as files with the markdown filenames replaced
        by the corresponding html files.
    """
    md_files = [f for f in files if os.path.splitext(f)[1] == markdown_ext]
    out = files[:]
    cmd_args = shlex.split(markdown_cmd)
    running = {}
    for mkd in md_files:
        html_filename = os.path.splitext(mkd)[0] + ".html"
        with open(html_filename, "wb") as outfile:
            args = cmd_args + [pipes.quote(mkd)]
            running[" ".join(args)] = subprocess.Popen(args, stdout=outfile)
        out[out.index(mkd)] = html_filename
    # Poll compilation processes until all complete
    wait_for_all(running, delay)
    return out

class _Note(object):
    """_Note stores information regarding a particular note.

    Attributes:
        name: String name of the note, often a filename
        path: String path to the note relative to index.html
    """
    def __init__(self, path, name):
        self.name = name
        self.path = path

class _Group(object):
    """_Group stores groups of notes, possibly with child groups.

    Attributes:
        key: A key for sorting
        identifier: Separate identifier for HTML elements
        notes: A list of _Note's
        children: A dictionary of child _Group's
    """
    def __init__(self, key="", identifier=None, notes=None, children=None):
        self.key = key
        if identifier is None:
            identifier = key
        if notes is None:
            notes = []
        if children is None:
            children = {}
        self.identifier = identifier
        self.notes = notes
        self.children = children

    def sort(self):
        """Sort children by key and notes by name.
        Converts children to an OrderedDict."""
        self.children = OrderedDict(sorted(self.children.items(),
                                           key=lambda t: t[1].key))
        self.notes.sort(key=lambda x: x.name)

def index_data(notes, directory, depth):
    """Extract index data from list of paths to note files.
    """
    groups = {"Other notes": _Group("zzzz", "other")}
    for note in notes:
        info = _Note(name=os.path.basename(note),
                     path=os.path.relpath(note, directory))
        match = _DATE_PATH_REGEXP.search(note)
        if not match:
            groups["Other notes"].notes.append(info)
            continue
        year, month, day = match.groups()
        date = datetime.strptime(year + month + day, "%Y%m%d")
        if year not in groups:
            groups[year] = _Group(year)
        if depth == "year" or month == "" or (
            day == "" and depth == "week"):
            groups[year].notes.append(info)
            continue
        if depth == "month":
            nice_month = date.strftime("%B")
            if nice_month not in groups[year].children:
                groups[year].children[nice_month] = _Group(month, year + month)
            groups[year].children[nice_month].notes.append(info)
            continue
        if depth == "week":
            week = str(date.isocalendar()[1])
            if week not in groups[year].children:
                groups[year].children[week] = _Group(int(week), year + week)
            groups[year].children[week].notes.append(info)
            continue
    groups = OrderedDict(sorted(groups.items(), key=lambda t: t[1].key,
                                reverse=True))
    for key in groups:
        groups[key].sort()
    return groups

def download_libraries(library_urls, directory):
    """Download libraries from CDN as needed

    Downloads libraries provided in library_urls to {directory}/lib. Does not
    overwrite existing libraries with the same filenames.

    Returns a list of library paths relative to directory.
    """
    lib_dir = os.path.join(directory, "lib")
    if not os.path.exists(lib_dir):
        os.makedirs(lib_dir)
    libraries = []
    for url in library_urls:
        filename = os.path.basename(urlparse.urlparse(url)[2])
        out = os.path.join(lib_dir, filename)
        libraries.append(out)
        if not os.path.exists(out):
            urllib.urlretrieve(url, out)
    return libraries

def build_index(notes, others, directory, template_path, depth):
    """Build HTML index of notes.

    Notes in year/[month/[day/]] folders are placed under appropriate headings.
    Other notes are organized in lexicographic order.
    """
    if os.path.exists(template_path):
        env = Environment(loader=FileSystemLoader(template_path))
    else:
        env = Environment(loader=PackageLoader("artnotizen"))
    libraries = download_libraries(_LIBRARY_URLS, directory)
    env.globals = {
        "notes": index_data(set(notes + others), directory, depth),
        "libraries": libraries,
    }
    template = env.get_template("index.html")
    with open(os.path.join(directory, "index.html"), "wb") as indexfile:
        print >> indexfile, template.render()
