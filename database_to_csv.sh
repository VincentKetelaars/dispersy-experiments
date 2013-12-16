PYTHONPATH=${HOME}/svn/norut/uav/trunk/
FOLDER=${HOME}/Desktop/mysql/

if [ $# -gt 0 ]
then
	TIME=$1
else
	TIME="00:00:00"
fi
FILEDATE=`date +%Y%m%d`
FILE=${FILEDATE}_${TIME}.csv
FILEPATH=${FOLDER}${FILE}
DATE=`date +%d-%m-%Y`
DATETIME="${TIME}_${DATE}"
echo $DATETIME
python -m src.tools.mysql_to_csv -d uav -f ${FILEPATH} -z -c Network.Dispersy -s ${DATETIME}