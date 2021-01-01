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

def main(config):
	last_dt = 0
	try:
		conn_cred = config['conn_cred']
		symbols = config['symbols'].split(',')
		while True:
			
			# define to run only during regular trading hours
			current_time = time.time()
			open_seconds = 14.5*60*60. # 2:30pm GMT
			close_seconds = 21*60*60. # 9pm GMT
			
			if  >= open_seconds 
			curr_time = time.time()
			mod_time = np.floor(curr_time % 60)
			if (mod_time >= 30) & (mod_time <= 32):
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
					time.sleep(3) # stops checking for this minute
			
	except Exception as e:
		print('error in run_realtime: ' + str(e))

if __name__ == '__main__':
	FLAGS, unparsed = parser.parse_known_args()
	with open(FLAGS.config,'r') as in_:
		config = json.load(in_)
	main(config)
