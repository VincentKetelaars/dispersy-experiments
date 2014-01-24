UAV_HOME=${HOME}/svn/norut/uav/trunk

export PYTHONPATH=$PWD:$UAV_HOME
cd $UAV_HOME
python -m Tools.ConfigTool delete version -v default
./prepare_mysql.sh # We want to make sure we have the latest configuration
cd -

python -m src.uav_api &> $HOME/Desktop/logs5