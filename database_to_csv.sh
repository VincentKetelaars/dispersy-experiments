export PYTHONPATH=${HOME}/svn/norut/uav/trunk/
FOLDER=${HOME}/Desktop/mysql/

usage() {
	echo "Usage"
	echo "-e | --endtime 		to set endtime"
	echo "-h | --help 		to display usage"
	echo "-s | --starttime 	to set starttime"
	echo "-v | --verbose 		to show python command"
	echo "-z | --zeroed 		to normalize time to start at zero"
}

ENDTIME="23:59:59"
STARTTIME="00:00:00"
VERBOSE=false
ZEROED=""
DATE=`date +%d-%m-%Y`
while [ "$1" != "" ]; do
    case $1 in
    	-d | --date )			DATE=$2;
								shift
								;;
    	-e | --endtime )		ENDTIME=$2;
								shift
								;;
		-h | --help )			usage
								exit 0
								;;
        -s | --starttime )      STARTTIME=$2;
								shift
                                ;;
        -v | --verbose )		VERBOSE=true
								;;
        -z | --zeroed )			ZEROED=" -z"
								;;
        * )                     echo "You are not doing it right..;)"
								usage
                                exit 1
    esac
    shift
done

FILEDATE=`date +%Y%m%d`
FILE=${FILEDATE}_${STARTTIME}

if [ ! -z "$ZEROED" ]; then
	FILE="${FILE}_z"
fi

FILEPATH=${FOLDER}${FILE}.csv

STARTDATETIME="${STARTTIME}_${DATE}"
ENDDATETIME="${ENDTIME}_${DATE}"

if $VERBOSE; then
	set -v
fi
python -m src.tools.mysql_to_csv -d uav -f ${FILEPATH} -c Network.Dispersy -s ${STARTDATETIME} -e ${ENDDATETIME} $ZEROED