"""
Tiny commandline tool to get and set config parameters while running
"""

import sys
import time

import xml.dom.minidom
from optparse import OptionParser

from src.database.API import get_config, shutdown
import src.database.Config as Config

class XMLImport:
    def parse_file(self, filename):
        xml = open(filename, "r").read()
        return self.parse_string(xml)
    
    def parse_string(self, string):
        root = xml.dom.minidom.parseString(string)
        
        # Find the "configuration" block
        config = root.getElementsByTagName("configuration")[0]
        return self._parse(config)

    def _parse(self, root, path=""):
        
        retval = []
        my_name = ".".join([path, root.nodeName]).replace(".configuration.", "")
        
        for child in root.childNodes:
            if child.nodeType == root.TEXT_NODE:
                if child.nodeValue.strip():
                    return [(my_name, child.nodeValue)]
            else:
                retval += self._parse(child, my_name)
        return retval


def usage():
    print """Usage:", sys.argv[0]," <command> <parameter> <value>
    Where command is one of:
       reset - Remove 'temporary' data from database to prepare for a new run of the software
       get <parameter> - get a value
       set <parameter> <value> - set a value
       add <parameter> <value> - add a value
       list [parameter] - list children of this parameter
       versions [partial name]- list all known versions (containing partial name)
       import <xml_file> <version> - import XML file as config version
       serialize <root> - Serialize config below a given root (optional) as JSON
       deserialize <root> <filename>  - Deserialize config to a given root

       TIP: Set the default configuration by running
          %s set default_config VERSION_NAME -v default
    """%(sys.argv[0])
    raise SystemExit()


def yn(message):
    """
    Present a yes/no question, return True iff yes
    """
    print message,
    response = raw_input().strip()
    if response.lower() == "y" or response.lower() == "yes":
        return True
    return False

if __name__ == "__main__":

    parser = OptionParser()
    
    parser.add_option("-v", "--version", dest = "version",
                      default = None,
                      help = "Version to operate on")

    parser.add_option("", "--overwrite", dest = "overwrite",
                      action="store_true", default=False,
                      help = "Always overwrite")
    
    (options, args) = parser.parse_args()

    if options.overwrite:
        print "WARNING: Overwrite is set"
    
    cfg = get_config()

    if options.version:
        try:
            cfg.set_version(options.version)
        except Config.NoSuchVersionException:
            if yn("No version '%s', create it?"%options.version):
                cfg.set_version(options.version, create=True)
            else:
                raise SystemExit("Aborted")

    if args:
        command = args[0]
    else:
        usage()
        raise SystemExit()

    try:
        if args[0] == "get":
            if len(args) < 2:
                usage()
            param = cfg.get(args[1])
            if not param:
                print "No such parameter '%s'"%args[1]
                raise SystemExit(1)
            print param.get_full_path()
            print " Value        : %25s"%param.get_value()
            print " Datatype     : %25s"%param.datatype
            print " Version      : %25s"%param.version
            print " Last modified: %25s"%time.ctime(param.last_modified)
            print " Comment      : %25s"%param.comment
            print 

        elif args[0] == "set":
            if len(args) < 3:
                usage()
            cfg.set(args[1], args[2], version=options.version)

        elif args[0] == "add":
            if len(args) < 3:
                usage()
            cfg.add(args[1], args[2], version=options.version)
        elif args[0] == "remove":
            if len(args) != 2:
                usage()
            cfg.remove(args[1], version=options.version)

        elif command == "list":
            if len(args) > 1:
                root = args[1]
            else:
                root = "root"

            def recursive_print(root, indent=""):
                elems = cfg.keys(root)
                for elem in elems:
                    recursive_print(root + "." + elem, indent + "  ")

                if len(elems) == 0:
                    print root, "=", cfg[root]

            recursive_print(root)

        elif command == "reset":
            cfg.reset()

        elif command == "versions":
            if len(args) > 1:
                versions = cfg.list_versions(args[1])
            else:
                versions = cfg.list_versions()
            print "Known versions:"
            for version in versions:
                print "  ", version
            print
        elif command == "delete":
            if len(args) < 2:
                raise SystemExit("What do you want me to delete?")
            if args[1] == "version":
                if not options.version:
                    raise SystemExit("Need a version to delete")
                if yn("Delete configuration version '%s' permanently?"%\
                          options.version):
                    cfg.delete_version(options.version)
                    print "Configuration deleted!"
                else:
                    print "Aborted"
            else:
                print "Dont know how to delete '%s'"%args[1]

        elif command == "import":
            if len(args) < 2:
                raise SystemExit("Need xml file to import")
            num_params = 0
            parser = XMLImport()
            params = parser.parse_file(args[1])
            for (param, value) in params:
                print "ADDING", param, value
                cfg.add(param, value, version=options.version, overwrite=True)
                num_params += 1
                
            print "Imported %d parameters"%num_params
        elif command == "serialize":
            if len(args) > 1:
                root = args[1]
            else:
                root = ""

            print cfg.serialize(root=root, version=options.version)

        elif command == "deserialize":
            if len(args) > 1:
                root = args[1]
            else:
                root = ""

            if len(args) > 2:
                data = open(args[2], "r").read()
            else:
                data = sys.stdin.read()
            cfg.deserialize(data, root=root, version=options.version, 
                            overwrite=options.overwrite)


        else:
            usage()
    finally:
        shutdown()
