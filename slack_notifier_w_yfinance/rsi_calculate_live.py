## RSI Notifier ##
# Calculate the RSI based on the aggregate market data from MySQL
# Send message to Slack when the RSI reaches certain ranges of values
#
 
import requests
import time
import json
import argparse
from datetime import datetime

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
	symbols = config['symbols'].split(',')
	bar_range = config['bar_range']
	info_dict = {}

	print('initializing RSI calculations with last 250 data points')
	for symbol in symbols:
		# initialize a dict that keeps track of stuff 
		prevU, prevD, last_val, last_epoch = initilize_prevUD(conn_cred, bar_range, symbol)
		info_dict[symbol] = {
						'avgU':prevU,
						'avgD':prevD,  
						'last_val':last_val,
						'last_epoch':last_epoch,
						'last_message':0, # epoch of last message sent
						'rsi':0
					   }  
	print('Done initializing')
	no_update_timer = 0
	while True:
		# constantly running until halted

		query = query_gen(conn_cred, bar_range, symbols)
		rows = run_query(conn_cred, query, selectBool = True)
		df_cols = ['symbol','datetime','epoch','open','close',
				   'high','low','volume']
		df = pd.DataFrame(rows, columns = df_cols)
		df['close'] = df['close'].astype(float)
		df.set_index('symbol', inplace = True)
		
		df_dict = df.to_dict('index')
		for symbol in symbols:
			try:
				
				# values to measure rsi with
				val = df_dict[symbol]['close'] - info_dict[symbol]['last_val']
				info_dict[symbol]['last_val'] = df_dict[symbol]['close']
				prevU = info_dict[symbol]['avgU']
				prevD = info_dict[symbol]['avgD']

				if info_dict[symbol]['last_epoch'] == df_dict[symbol]['epoch']:
					if time.time() > (no_update_timer + 300):
						print('no new update in database')
						no_update_timer = time.time()
					rsi_, _, _ = calculate_rsi(val, prevU, prevD) 

				else:
					rsi_, prevU, prevD = calculate_rsi(val, prevU, prevD)

					# update new prevU/prevD
					info_dict[symbol]['avgU'] = prevU
					info_dict[symbol]['avgD'] = prevD

				# print(symbol + ' rsi: ' + str(round(rsi_,2)))
					
				

				# send slack message based on rsi
				bool1 = (rsi_ <= 20) | (rsi_ >= 80)
				bool2 = info_dict[symbol]['last_epoch'] != df_dict[symbol]['epoch']
				
				if bool1 & bool2:
					epoch_ = info_dict[symbol]['last_epoch']
					datetime_ = datetime.fromtimestamp(epoch_)
					text = symbol + ' hit RSI ' + str(round(rsi_,2)) + ' at ' + str(datetime_)
					myobj = {"text":text}
				
					five_min_buffer = time.time() > info_dict[symbol]['last_message'] + 300
					no_repeat = rsi_ != info_dict[symbol]['rsi']

					if five_min_buffer & no_repeat: # five minutes after last message sent for specific symbol 
						send_message_slack(slack_hook, myobj)
						info_dict[symbol]['last_message'] = time.time()
				
				# update info_dict
				info_dict[symbol]['last_epoch'] = df_dict[symbol]['epoch']
				info_dict[symbol]['rsi'] = rsi_
			except Exception as e:
				myobj = {"text":'something happened with ' + str(symbol) + ": " + str(e)}
				send_message_slack(slack_hook, myobj)


		time.sleep(5) # controlling the rate of the loop with 5 second delays

def send_message_slack(slack_hook, myobj):
	try:
		requests.post(slack_hook, json = myobj)
	except Exception as e:
		print('request failed for some reason, probably internet connection lost. not sending message to slack')

def initilize_prevUD(conn_cred, bar_range, symbol):
	# get last 100 close values
	# only important values are prevU and prevD 

	
	query = "WITH cte AS ( \
			 SELECT close, rounded_epoch from {dbname}.bar_{bar_range}min \
			 WHERE symbol = '{symbol}' \
			 ORDER BY rounded_epoch DESC LIMIT 250 \
			 ) \
			 SELECT close,rounded_epoch FROM cte \
			 ORDER BY rounded_epoch".format(
						dbname = conn_cred['dbname'], 
						bar_range = bar_range,
						symbol = symbol)
	rows = run_query(conn_cred, query, selectBool = True) 
	last_epoch = int(rows[-1][1])
	rows = np.array(list(map(lambda x: float(x[0]), rows)))
	last_val = rows[-1]
	
	rows = rows[1:] - rows[:-1]

	# initial calculation

	vals = rows[:9]
	prevU = np.sum(vals * (vals > 0).astype(int)) / 9
	prevD = -1 * np.sum(vals * (vals < 0).astype(int)) / 9

	for i in range(9, len(rows)):
		_, prevU, prevD = calculate_rsi(rows[i], prevU, prevD, 9)
		
	return prevU, prevD, last_val, last_epoch


def query_gen(conn_cred, bar_range, symbols):
	# get most recent value to calculate rsi with
	query = 'WITH '
	for symbol in symbols:
		cte = "{symbol} AS ( \
			   SELECT * FROM {dbname}.bar_{bar_range}min \
			   WHERE symbol = '{symbol}' \
			   ORDER BY datetime_rounded DESC LIMIT 1 \
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

# def calculate_rsi(vals, prevU = 0, prevD = 0, n = 9):
# 	alpha = 2 / (n+1) # exponential method
# 	U = np.sum(vals * (vals > 0).astype(int)) / n
# 	D = -1 * np.sum(vals * (vals < 0).astype(int)) / n
# 	avgU = alpha * U + (1 - alpha) * prevU
# 	avgD = alpha * D + (1 - alpha) * prevD

# 	prevU = avgU
# 	prevD = avgD
# 	rs = avgU / avgD
# 	rsi = 100.0 - 100.0 / (1 + rs)
# 	return rsi, prevU, prevD


def calculate_rsi(val, prevU = 0, prevD = 0, n = 9):
	if val > 0:
		avgU = (prevU*(n-1) + val) / n
		avgD = prevD*((n-1)/n)
	else:
		avgU = prevU*((n-1)/n)
		avgD = (prevD*(n-1) - val) / n
		
	rs = avgU / (avgD + 1e-5)
	rsi = 100.0 - 100.0 / (1 + rs)
	return rsi, avgU, avgD


if __name__ == '__main__':
	FLAGS, unparsed = parser.parse_known_args()
	with open(FLAGS.config,'r') as in_:
		config = json.load(in_)
	main(config)