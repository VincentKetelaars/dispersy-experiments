dispersy-experiments
====================

Dispersy - Libswift Framework with the purpose of allowing multiple sockets to be used in parallel.

INSTALL:

First install Libevent:

cd libevent
./autogen.sh (Uses aclocal which can be found in automake)
./configure && make
sudo make install

Then install Libswift:

cd ../libswift
make
sudo make install
Set LD_LIBRARY_PATH to Libevent location (Or you could edit the LIBEVENT_LIBRARY variable in src/definitions.py)

RUN:

The run scripts allow you to run instance of the framework easily. Set the parameters according to your needs.
In addition it might be useful to go through the src/definitions.py to adjust certain constants to your specific needs.

UAVAPI:
To run the UAVAPI, ensure that you set the path UAV in ./run_uav.sh correctly to the directory of 'trunk'
use ./moveToTrunk.sh (again set the path) to overwrite certain files
The defaultConfiguration file is used in prepare_mysql.sh in case you want to change the location. 
Paramaters to the UAVAPI are set by the child tags of Dispersy.paramaters in the defaultConfiguration file.
Furthermore you can use the ./change_user.sh script to change username and password.
./clear_database.sh clears the uav mysql database from stats and logs.
./database_to_csv.sh outputs the uav mysql database to csv.
