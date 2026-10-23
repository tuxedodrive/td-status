#!/opt/homebrew/bin/python3
import os,sys
args=[a for a in sys.argv[1:] if not a.startswith('--user-data-dir=')]
profile='/tmp/independent-run006-chrome-'+str(os.getpid())
os.execv('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['Google Chrome','--user-data-dir='+profile]+args)
