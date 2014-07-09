dispersy-experiments
====================

Dispersy - Libswift Framework with the purpose of allowing multiple sockets to be used in parallel for disseminating data to multiple peers.

###INSTALL

Created for Python 2.7, and allows only IPv4 addresses.

First get the entire repository (includings its submodules)

> git clone --recursive git://github.com/VincentKetelaars/dispersy-experiments.git

####Install Libevent:

``` sh
cd libevent
./autogen.sh
./configure && make
sudo make install
```

For *autogen.sh* you will need (to install) aclocal in automake, and libtool

####Install Libswift:

If not already installed, make sure to install *scons*.
Before calling *scons*, make sure to point *CPPPATH* to the directory of Libevent. Also ensure that *LIBPATH* points to directory where libevent is installed (*/usr/local/lib* by default). Finally Libswift uses OpenSSL, which means that you have to make sure that the *opensslpath* variable, in the *SConstruct* file, holds the path to the openssl directory.

``` sh
cd ../libswift
scons
```

Set LD_LIBRARY_PATH to Libevent location (*/usr/local/lib* by default). Or you could edit the LIBEVENT_LIBRARY variable in *src/definitions.py*)

The *cmdgw.cpp* in Libswift uses the following headers, limiting portability. They can be removed with little loss of functionality.
``` cpp
#include <sys/ioctl.h>
#include <linux/sockios.h>
```

####Python Packages
- python-netifaces
- M2Crypto

###RUN

The run scripts allow you to run instance of the framework easily. Set the parameters according to your needs.
In addition it might be useful to go through the src/definitions.py to adjust certain constants to your specific needs.

###UAVAPI

- To run the UAVAPI, ensure that you set the path UAV in *run_uav.sh* correctly to the directory of *uav/trunk*
- Use *moveToTrunk.sh* (again set the path) to overwrite certain files
- The *defaultConfiguration.xml* file is used in *prepare_mysql.sh* in case you want to change the location. 
- Paramaters to the UAVAPI are set by the child tags of **Dispersy.parameters** in the *defaultConfiguration.xml* file.
- Furthermore you can use the *change_user.sh* script to change username and password.
- *clear_database.sh* clears the uav mysql database from stats and logs.

###DELFTAPI

- In *prepare_mysql.sh* there is a reference to an XML file. This file configures the *DelftAPI*.

###POST USE
- *database_to_csv.sh* outputs the uav mysql database to csv.
- *create_gnu_plot.sh* can be used to create a gnuplot from a csv file. Note that the csv file needs to be column aligned. (Use the *-c* option for *database_to_csv.sh*)