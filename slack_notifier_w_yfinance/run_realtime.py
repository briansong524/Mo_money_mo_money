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
			data = yf.download(tickers = config['symbols'].replace(',',' '), period = '1d', 
							   interval = '1m', group_by = 'ticker')
			print(data.tail())
			latest_dt = data.index[-1] # index contains datetime for multi symbols
			if latest_dt != last_dt:
				last_dt = latest_dt
				for symbol in symbols:
					latest_data = data[symbol].iloc[-1,:].copy()
					print(latest_data)
					bardata = (convert_dt_to_epoch(last_dt),
							   latest_data.Open, 
							   latest_data.High, 
							   latest_data.Low, 
							   latest_data.Close, 
							   latest_data.Volume
							   )
					print(bardata)
					csvOutputs = ','.join(map(lambda x: "'" + str(x) + "'",bardata))
					query = 'INSERT INTO {dbname}.bar_data_yf (symbol, epoch, open, high, \
							 low, close, volume) \
							 VALUES ({symbol},{csv})'.format(dbname = conn_cred['dbname'],
							 					  symbol = "'" + symbol + "'",
												  csv = csvOutputs)
					run_query(conn_cred, query)
			time.sleep(30)

	except Exception as e:
		print('error in run_realtime: ' + str(e))

if __name__ == '__main__':
	FLAGS, unparsed = parser.parse_known_args()
	with open(FLAGS.config,'r') as in_:
		config = json.load(in_)
	main(config)
