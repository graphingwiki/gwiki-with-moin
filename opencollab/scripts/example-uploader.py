from wiki import CLIWiki
from meta import Meta

import os
import sys
import optparse

from urllib import quote

def main():

    parser = optparse.OptionParser()
    parser.add_option("-o", "--output",
                      dest="output",
                      default=None,
                      metavar="OUTPUT",
                      help="save the file to name OUTPUT in the wiki")
    parser.add_option("-r", "--recursive",
                      action="store_true",
                      dest="recursive",
                      help="recursivly upload files")

    parser.set_usage("%prog [options] WIKIURL PAGENAME FILENAME")

    options, args = parser.parse_args()
    if len(args) != 3:
        parser.error("wiki url, pagename and filename have to be defined")

    url, page, path = args

    wiki = CLIWiki(url)

    if options.recursive:
        for root, dirs, files in os.walk(path):
            for file in files:
                filename = os.path.join(root, file)
                wikiname = quote(filename, safe="")
                sys.stdout.write("Uploading %s as %s\n" % (filename, wikiname)) 
                uploadFile(wiki, page, wikiname, filename)

        sys.exit()

    if options.output is None:
        _, filename = os.path.split(path)
    else:
        filename = options.output

    uploadFile(wiki, page, filename, path)

def uploadFile(wiki, page, filename, path):
    file = open(path, "rb")
    
    sys.stdout.write("\rconnecting & precalculating chunks...")
    sys.stdout.flush()

    for current, total in wiki.putAttachmentChunked(page, filename, file):
        percent = 100.0 * current / float(max(total, 1))
        status = current, total, percent

        sys.stdout.write("\rsent %d/%d bytes (%.02f%%)" % status)
        sys.stdout.flush()

    sys.stdout.write("\ndone\n")
    sys.stdout.flush()

    file.close()

if __name__ == "__main__":
    main()
