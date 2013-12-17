chmod 777 ./UAVConfig.log
set -o noclobber
{ > ./dbHandler_exceptions.txt.root ; } &> /dev/null
set +o noclobber
chmod 777 ./dbHandler_exceptions.txt.*