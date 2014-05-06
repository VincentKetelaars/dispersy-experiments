#!/bin/sh
gnuplot << EOF
set terminal png nocrop font small size 640,480
# lt, lc, lw, pt, 
set title "My Test"
set xlabel "Time (s)"
set y2label "Quality"
set ylabel "Rate (KB/s)"
# ${HOME}/Desktop/mysql/
set output '/home/vincent/Desktop/mysql/plot.png'
set datafile separator ","
set ytics nomirror
set y2tics
set tics out
set autoscale y
set autoscale y2 
plot "$1" using 93:94 axes x1y1 title "Upload rate" with lines,\
 "$1" using 159:160 axes x1y2 title "Quality" with lines

EOF