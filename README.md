dispersy-experiments
====================

Dispersy - Libswift Framework with the purpose of allowing multiple sockets to be used in parallel for disseminating data to multiple peers.

###INSTALL

Created for Python 2.7, and allows only IPv4 for now.

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

``` sh
cd ../libswift
make
```

Set LD_LIBRARY_PATH to Libevent location (*/usr/local/lib* by default). Or you could edit the LIBEVENT_LIBRARY variable in *src/definitions.py*)

The *cmdgw.cpp* in Libswift uses the following headers, limiting portability. They can be removed with care.
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
- *database_to_csv.sh* outputs the uav mysql database to csv.