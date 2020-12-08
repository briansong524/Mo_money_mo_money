import time

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
			latest_dt = data['Datetime'].iloc[-1]
			if latest_dt != last_dt:
				last_dt = latest_dt
				for symbol in symbols:
					latest_data = data[symbol].iloc[-1,:].copy()
					bardata = (convert_dt_to_epoch(last_dt),
							   latest_data.Open, 
							   latest_data.High, 
							   latest_data.Low, 
							   latest_data.Close, 
							   latest_data.Volume
							   )
					csvOutputs = ','.join(map(lambda x: "'" + str(x) + "'",list_vals))
					query = 'INSERT INTO {dbname}.bar_data_yfS (symbol, epoch, open, high, \
							 low, close, volume) \
							 VALUES ({symbol},{csv})'.format(dbname = conn_creds['dbname'],
							 					  symbol = "'" + symbols[i] + "'",
												  csv = csvOutputs)
					run_query(conn_cred, query)

	except Exception as e:
		print('error in run_realtime: ' + str(e))

if __name__ == '__main__':
	FLAGS, unparsed = parser.parse_known_args()
	with open(FLAGS.config,'r') as in_:
		config = json.load(in_)
	main(config)
