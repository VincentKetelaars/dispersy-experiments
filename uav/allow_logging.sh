set -o noclobber
{ > ./UAVConfig.log ; } &> /dev/null
{ > ./dbHandler_exceptions.txt.root ; } &> /dev/null
set +o noclobber
chmod 777 ./UAVConfig.log
chmod 777 ./dbHandler_exceptions.txt.*