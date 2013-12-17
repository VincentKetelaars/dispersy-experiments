UAV_HOME=${HOME}/svn/norut/uav/trunk

updateConf=false
VERBOSE=""

while [ "$1" != "" ]; do
    case $1 in
        -c | --conf )           updateConf=true
                                ;;
        -v | --verbose )		VERBOSE="-v"
								;;
        * )                     usage
                                exit 1
    esac
    shift
done

if $updateConf; then
	cp $VERBOSE uav/defaultConfiguration_vincent.xml ${UAV_HOME}/Config
fi
cp $VERBOSE uav/disable_uav_processes.sh ${UAV_HOME}
cp $VERBOSE uav/change_user.sh ${UAV_HOME}
cp $VERBOSE uav/prepare_mysql.sh ${UAV_HOME}
cp $VERBOSE uav/create_db.sql ${UAV_HOME}
cp $VERBOSE uav/allow_logging.sh ${UAV_HOME}
cp $VERBOSE logger.conf ${UAV_HOME}