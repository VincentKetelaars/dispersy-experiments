UAV_HOME=${HOME}/svn/norut/uav/trunk

cp uav/defaultConfiguration_vincent.xml ${UAV_HOME}/Config
cp uav/disable_uav_processes.sh ${UAV_HOME}
cp uav/change_user.sh ${UAV_HOME}
cp uav/prepare_mysql.sh ${UAV_HOME}
cp uav/create_db.sql ${UAV_HOME}
cp uav/allow_logging.sh ${UAV_HOME}
cp logger.conf ${UAV_HOME}