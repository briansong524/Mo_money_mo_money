## RSI Notifier ##
# Calculate the RSI based on the aggregate market data from MySQL
# Send message to Slack when the RSI reaches certain ranges of values
#
# TODO:
# modify the rsi calculations
# fix the time.sleep() logic
# fix the last_datetime update logic

 
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
		info_dict[i] = {'first_rsi':True, 'message_sent': False}  

	message_sent = False
	while 1==1:

		query = "WITH amzn AS ( \
				select * from {dbname}.bar_15min where symbol = 'AMZN' order by datetime_rounded desc limit 9 \
				), \
				aapl as ( \
				select * from {dbname}.bar_15min where symbol = 'AAPL' order by datetime_rounded desc limit 9 \
				), \
				tsla as ( \
				select * from {dbname}.bar_15min where symbol = 'TSLA' order by datetime_rounded desc limit 9 \
				), \
				googl as ( \
				select * from {dbname}.bar_15min where symbol = 'GOOGL' order by datetime_rounded desc limit 9 \
				) \
				SELECT * FROM amzn \
				UNION  \
				SELECT * FROM aapl \
				UNION \
				SELECT * FROM tsla \
				UNION \
				SELECT * FROM googl".format(dbname=conn_cred['dbname'])
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
			union_str = "SELECT * FROM {symbol}".format(symbol = symbol)
			query += union_str
			if symbol != symbols[-1]:
				query += " UNION "

		rows = run_query(conn_cred, query, selectBool = True)
		df = pd.DataFrame(rows, columns = ['symbol','datetime','open','close','high','low','volume'])
		# print(df.head())
		for symbol in symbols:
			try:
				df_part = df[df['symbol'] == symbol].copy()
				if df_part.shape[0] != 0:
					vals = (df_part['close'] - df_part['open']).astype(float).values
					# print(vals)
					if info_dict[symbol]['first_rsi']:
						rsi_, prevU, prevD = rsi(vals) 
						info_dict[symbol]['first_rsi'] = False
						print('first rsi calculated for ' + str(symbol) + ': ' + str(rsi_))
					else:
						if info_dict[symbol]['last_datetime'] == df['datetime'].iloc[0]:
							rsi_, _, _ = rsi(vals, prevU, prevD) 
							# print(rsi_)
						else:
							print('rsi @ ' + str(info_dict[symbol]['last_datetime']) + ' = ' + str(rsi_))
							rsi_, prevU, prevD = rsi(vals, prevU, prevD)
						
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

def rsi(vals, prevU = 0, prevD = 0, n = 9):
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