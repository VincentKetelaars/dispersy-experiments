#!/bin/sh
gnuplot << EOF
set terminal unknown



set xlabel "Time (s)"
set y2label "Round Trip Time (ms)"
set ylabel "Transfer Rate (KB/s)"
set output '/home/vincent/Desktop/mysql/plot.png'
# set output '/home/vincent/Documents/master_thesis/intro/includes/fly_by.png'
set datafile separator ","
set ytics nomirror
set y2tics
set tics in
set autoscale y
set y2range [0:150] 
plot "$1" using 65:66 axes x1y1 title "Upload rate" with linespoints,\
  "$1" using 61:(\$62/1000) axes x1y2 title "Average RTT" with linespoints

# plot "$1" using 25:26 axes x1y1 title "Download rate" with linespoints,\
# "$1" using 131:132 axes x1y1 title "Upload rate" with linespoints,\
#  "$1" using 173:174 axes x1y2 title "Signal" with linespoints

set terminal png large size 1280,720
set xrange [0:GPVAL_DATA_X_MAX]
replot





# set xlabel "Time (s)"
# set ylabel "Transfer Rate (KB/s)"
# set output '/home/vincent/Desktop/mysql/plot.png'
# # set output '/home/vincent/Documents/master_thesis/intro/includes/fly_by.png'
# set datafile separator ","
# set ytics nomirror
# set tics in
# set autoscale y
# # plot "$1" using 65:66 axes x1y1 title "eth, wlan" with linespoints,\
# #  "$1" using 89:90 axes x1y1 title "eth, eth" with linespoints,\
# #  "$1" using 119:120 axes x1y1 title "wlan, wlan" with linespoints,\
# #  "$1" using 143:144 axes x1y1 title "wlan, eth" with linespoints,\
# #  "$1" using 175:176 axes x1y1 title "total" with linespoints

# # plot "$1" using 107:108 axes x1y1 title "upload rate" with linespoints

# plot "$1" using 75:76 axes x1y1 title "eth, wlan" with linespoints,\
#  "$1" using 99:100 axes x1y1 title "eth, eth" with linespoints,\
#  "$1" using 131:132 axes x1y1 title "total" with linespoints

# set terminal png large size 1280,720
# # set xrange [0:GPVAL_DATA_X_MAX]
# set xrange [0:600]
# replot


# set xlabel "Time (s)"
# set y2label "Signal Level (dBm)"
# set ylabel "Quality"
# set output '/home/vincent/Desktop/mysql/plot.png'
# # set output '/home/vincent/Documents/master_thesis/intro/includes/fly_by.png'
# set datafile separator ","
# set ytics nomirror
# set y2tics
# set tics in
# set autoscale y
# set autoscale y2 
# plot "$1" using 179:180 axes x1y1 title "Quality" with linespoints,\
#  "$1" using 181:182 axes x1y2 title "Signal" with linespoints

# set terminal png large size 1280,720
# set xrange [GPVAL_DATA_X_MIN:GPVAL_DATA_X_MAX]
# replot




EOF