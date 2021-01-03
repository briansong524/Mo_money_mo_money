'''
obtain realtime data from yahoo finance through yfinance.
because 'live' data is incomplete and useless - data will be one min delayed
'''

import time
import argparse
import json

import yfinance as yf
from pytz import timezone
import numpy as np

from utils import *

parser = argparse.ArgumentParser()


parser.add_argument(
	'--config', type=str, default='/home/minx/Documents/config.conf',
	help = 'Config file for all configuration info')


def mod_time():
	# return the hour modulo of epoch time
	# the returned value represents the seconds passed that day
	current_time = time.time()
	return np.floor(current_time % 86400)

def main(config):
	last_dt = 0
	try:
		conn_cred = config['conn_cred']
		symbols = config['symbols'].split(',')
	
		# define to run only during regular trading hours
		open_seconds = 14.5*60*60. # 2:30pm GMT
		close_seconds = 21*60*60. # 9pm GMT	
		mark_epoch = open_seconds + 30 ## 30 seconds after opening	

		while (mod_time() >= open_seconds) & (mod_time() <= close_seconds): 
			while mark_epoch > mod_time():
				time.sleep(5)

			# update mark_epoch when it breaks the while loop
			mark_epoch += 60 # add a minute

			data = yf.download(tickers = config['symbols'].replace(',',' '), period = '1d', 
							   interval = '1m', group_by = 'ticker')

			# dropping incomplete data
			data = data.dropna() 
			for symbol in symbols:
				data = data[data[(symbol,'Volume')] != 0] # this maybe overkill
			latest_dt = data.index[-1] # index contains datetime for multi symbols
			if latest_dt != last_dt:
				last_dt = latest_dt
				for symbol in symbols:
					latest_data = data[symbol].iloc[-1,:].copy()
					# print(latest_data)
					bardata = (convert_dt_to_epoch(last_dt),
							   latest_data.Open, 
							   latest_data.High, 
							   latest_data.Low, 
							   latest_data.Close, 
							   latest_data.Volume
							   )
					# print(bardata)
					csvOutputs = ','.join(map(lambda x: "'" + str(x) + "'",bardata))
					query = 'INSERT INTO {dbname}.bar_data_yf (symbol, epoch, open, high, \
							 low, close, volume) \
							 VALUES ({symbol},{csv})'.format(dbname = conn_cred['dbname'],
							 					  symbol = "'" + symbol + "'",
												  csv = csvOutputs)
					run_query(conn_cred, query)
			else:
				print('last_dt == latest_dt, so didnt update this minute block')
	except Exception as e:
		print('error in run_realtime: ' + str(e))

if __name__ == '__main__':
	FLAGS, unparsed = parser.parse_known_args()
	with open(FLAGS.config,'r') as in_:
		config = json.load(in_)
	main(config)
