#!/usr/bin/gnuplot -persist
set terminal png nocrop font small size 640,480
# lt, lc, lw, pt, 
set style line 1 lt 2 lw 1 pt 3 ps 1
set title "My Test"
set xlabel "Time (s)"
set ylabel "Rate (Mb/s)"
# ${HOME}/Desktop/mysql/
set output '/home/vincent/Desktop/mysql/plot.png'
set datafile separator ","
plot "/home/vincent/Desktop/mysql/20140410_00:00:00_cz.csv" using 83:84 notitle