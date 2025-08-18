#! /bin/sh

tgtd -f &
volexport server &
wait
