## RSI Notifier ##
# Calculate the RSI based on the aggregate market data from MySQL
# Send message to Slack when the RSI reaches certain ranges of values
#
# TODO:
# fix the time.sleep() logic
# modify the rsi calculations
# fix the last_datetime update logic
# add a 'starting point' rsi/U/D that runs at startup
 
import requests
import time
import json
import argparse

import pandas as pd
import numpy as np
import pymysql as MySQLdb

from utils import *

parser = argparse.ArgumentParser()


parser.add_argument(
	'--config', type=str, default='/home/minx/Documents/config.conf',
	help = 'Config file for all configuration info')

def main(config):
	
	# initialize
	conn_cred = config['conn_cred']
	slack_hook = config['slack_webhook']
	symbols = ','.split(config['symbols'])
	bar_range = config['bar_range']
	info_dict = {}

	for i in symbols:
		# initialize a dict that keeps track of stuff 
		info_dict[i] = {
						'avgU':0,
						'avgD':0,  
						'last_message':0 # epoch of last message sent
					   }  

	while True:
		# constantly running until halted

		query = query_gen(conn_cred, bar_range, symbols)
		rows = run_query(conn_cred, query, selectBool = True)
		df_cols = ['symbol','datetime','epoch','open','close',
				   'high','low','volume']
		df = pd.DataFrame(rows, columns = df_cols)

		for symbol in symbols:
			try:
				df_part = df[df['symbol'] == symbol].copy()
				if df_part.shape[0] != 0:
					
					# values to measure rsi with
					vals = (df_part['close'] - df_part['open'])
					vals = vals.astype(float).values

					if info_dict[symbol]['first_rsi']:
						rsi_, prevU, prevD = calculate_rsi(vals) 
						info_dict[symbol]['first_rsi'] = False
						print('first rsi calculated for ' + 
							  str(symbol) + ': ' + str(rsi_))
					else:
						if info_dict[symbol]['last_datetime'] == df['datetime'].iloc[0]:
							rsi_, _, _ = calculate_rsi(vals, prevU, prevD) 

						else:
							print('rsi @ ' + str(info_dict[symbol]['last_datetime']) + ' = ' + str(rsi_))
							rsi_, prevU, prevD = calculate_rsi(vals, prevU, prevD)
						
					info_dict[symbol]['last_datetime'] = df['datetime'].iloc[0]

					# send slack message based on rsi
					if (rsi_ <= 20) | (rsi_ >= 80):
						text = symbol + ' hit RSI ' + str(round(rsi_,2)) + ' at ' + str(info_dict[symbol]['last_datetime'])
						myobj = {"text":text}
						requests.post(slack_hook, json = myobj)
						message_sent = True

			except Exception as e:
				myobj = {"text":'something happened with ' + str(symbol) + ": " + str(e)}
				requests.post(slack_hook, json = myobj)


		# suppress slack messages for five minute if a message was sent
		if message_sent:
			time.sleep(300)
			message_sent = False
		else:
			time.sleep(5)

def rsi_initialize(*args, **kwargs):
	# get last 100 close values
	query = "WITH cte AS ( \
			 SELECT close from {dbname}.bar_{bar_range}min \
			 WHERE symbol = '{symbol}' \
			 ORDER BY datetime_rounded DESC LIMIT 100 \
			 ) \
			 SELECT * FROM cte \
			 ORDER BY datetime_rounded".format(
			 			dbname = conn_cred['dbname'], 
			   		    bar_range = bar_range,
			   		    symbol = symbol)
	run_query(query)

def query_gen(*args, **kwargs):
	query = ''
	for symbol in symbols:
		cte = "WITH {symbol} AS ( \
			   SELECT * FROM {dbname}.bar_{bar_range}min \
			   WHERE symbol = '{symbol}' \
			   ORDER BY datetime_rounded DESC LIMIT 9 \
			   )".format(dbname = conn_cred['dbname'], 
			   			 bar_range = bar_range,
			   			 symbol = symbol)
		query += cte
		if symbol != symbols[-1]:
			query += ", "
	for symbol in symbols:
		union_str = "SELECT * \
					 FROM {symbol}".format(symbol = symbol)
		query += union_str
		if symbol != symbols[-1]:
			query += " UNION "
	return query

def calculate_rsi(vals, prevU = 0, prevD = 0, n = 9):
	alpha = 2 / (n+1) # exponential method
	U = np.sum(vals * (vals > 0).astype(int)) / n
	D = -1 * np.sum(vals * (vals < 0).astype(int)) / n
	avgU = alpha * U + (1 - alpha) * prevU
	avgD = alpha * D + (1 - alpha) * prevD

	prevU = avgU
	prevD = avgD
	rs = avgU / avgD
	rsi = 100.0 - 100.0 / (1 + rs)
	return rsi, prevU, prevD


if __name__ == '__main__':
	FLAGS, unparsed = parser.parse_known_args()
	with open(FLAGS.config,'r') as in_:
		config = json.load(in_)
	main(config)