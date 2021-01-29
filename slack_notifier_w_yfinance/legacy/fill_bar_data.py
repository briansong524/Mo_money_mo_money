## Refresh/Repopulate bar_data
#
# In case of needed refreshing, clear out bar_data table and 
# repopulate with a week's worth of 1 minute data. This is probably 
# best run during after-hours to get full historical data. 
#



import requests
import time
import json
import argparse

import yfinance as yf
from pytz import timezone
import pymysql as MySQLdb
import pandas as pd
import numpy as np
from utils import run_query, mysql_conn, db_conn_close, convert_dt_to_epoch



parser = argparse.ArgumentParser()


parser.add_argument(
	'--config', type=str, default='/home/minx/Documents/config.conf',
	help = 'Config file for all configuration info')

parser.add_argument(
	'--symbol', type=str, 
	help = 'Which symbol to update with data')



def main(config):
	conn_cred = config['conn_cred']
	slack_hook = config['slack_webhook']
	symbols = config['symbols'].split(',')
	
	for i in range(len(symbols)):
		print('running for ' + symbols[i]) 
		ticker = yf.Ticker(symbols[i])
		data = ticker.history(period = '1d',
		                   interval = '1m').reset_index()
		data['Epoch'] = data.Datetime.map(convert_dt_to_epoch)
		for _, bar in data.iterrows():
			bardata = (bar.Epoch, bar.Open, bar.High, bar.Low, bar.Close, bar.Volume)
			csvOutputs = ','.join(map(lambda x: "'" + str(x) + "'",bardata))
			query = 'INSERT INTO {dbname}.bar_data_yf (symbol, epoch, open, high, \
							 low, close, volume) \
							 VALUES ({symbol},{csv})'.format(dbname = conn_cred['dbname'],
							 					  symbol = "'" + symbols[i] + "'",
												  csv = csvOutputs)
			run_query(conn_cred, query)
		print('done inserting ' + symbols[i] + ' to database')


if __name__ == '__main__':
	FLAGS, unparsed = parser.parse_known_args()
	with open(FLAGS.config,'r') as in_:
		config = json.load(in_)
	main(config)