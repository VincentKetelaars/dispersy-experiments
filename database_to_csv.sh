export PYTHONPATH=${HOME}/svn/norut/uav/trunk/
FOLDER=${HOME}/Desktop/mysql/

usage() {
	echo "Usage"
	echo "-c | --columns		Use columns"
	echo "-d | --date		to set date (yyyy-mm-dd), defaults to today"
	echo "-e | --endtime 		to set endtime (default 23:59:59)"
	echo "-h | --help 		to display usage"
	echo "-r | --rows		Use rows"
	echo "-s | --starttime 	to set starttime (default 00:00:00)"
	echo "-v | --verbose 		to show python command"
	echo "-z | --zeroed 		to normalize timestamps to start at zero"
}

ENDTIME="23:59:59"
STARTTIME="00:00:00"
VERBOSE=false
DATE=`date +%Y-%m-%d`
NO_PARAMS=""
while [ "$1" != "" ]; do
    case $1 in
    	-c | --columns )		NO_PARAMS="${NO_PARAMS} -C"
								;;
    	-d | --date )			DATE=$2;
								shift
								;;
    	-e | --endtime )		ENDTIME=$2;
								shift
								;;
		-h | --help )			usage
								exit 0
								;;
    	-r | --rows )			NO_PARAMS="${NO_PARAMS} -r"
								;;
        -s | --starttime )      STARTTIME=$2;
								shift
                                ;;
        -v | --verbose )		VERBOSE=true
								;;
        -z | --zeroed )			NO_PARAMS="${NO_PARAMS} -z"
								;;
        * )                     echo "You are not doing it right..;)"
								usage
                                exit 1
    esac
    shift
done

FILE=${DATE}_${STARTTIME}

APPEND_FILE=$(echo ${NO_PARAMS} | sed 's/[^a-zA-Z]*//g' | tr '[:upper:]' '[:lower:]' | grep -o . | sort -n | tr -d '\n')
if [ ! -z "${APPEND_FILE}" ]; then
	FILE="${FILE}_${APPEND_FILE}"
fi

FILEPATH=${FOLDER}${FILE}.csv

STARTDATETIME="${DATE}_${STARTTIME}"
ENDDATETIME="${DATE}_${ENDTIME}"

if $VERBOSE; then
	set -v
fi
python -m src.tools.mysql_to_csv -d uav -f ${FILEPATH} -c Network.Dispersy -s ${STARTDATETIME} -e ${ENDDATETIME} ${NO_PARAMS}