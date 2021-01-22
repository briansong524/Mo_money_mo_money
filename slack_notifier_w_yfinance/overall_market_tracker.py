'''
# Overall Market Tracker

Tracks the overall market health, and makes notes accordingly

Notes: 
-These will note the general mid-long term market status, so
 should look to make intraday decisions with it in mind, but only 30%
 consideration, as the stock itself could be on it's own trend
- Using SPY, DJI, and NDAQ for references of overall market
- Maybe will start with just NDAQ, as it's more to do with tech
- Status can be better defined by considering the previous status
  - e.g. nhh to nnh could say 'Bubble mightve popped'

'''


import os,sys
import argparse
import json
import traceback
import time

import yfinance as yf
import pytz
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from utils import calculate_rsi, send_message_slack
from utils import calculate_ema, calculate_macd, simple_lr

# from utils import global_logger_init, global_logger_cleanup

## logger specs ##
# import logging
# from logging.handlers import RotatingFileHandler

##################

parser = argparse.ArgumentParser()

parser.add_argument(
	'--config', type=str, default='/home/minx/Documents/config.conf',
	help = 'Config file for all configuration info')
parser.add_argument(
	'--rsi_bars', type=int, default=14,
	help = 'number of bars used to calculate rsi')
parser.add_argument(
	'--interval', type=str, default='30m',
	help = 'size of bar')




def main(config):
	
	main_dir = os.path.dirname(os.path.realpath(__file__))
	os.chdir(main_dir)
	if os.path.exists('overall_market_last_status.txt'):
		with open('overall_market_last_status.txt','r') as f:
			last_status = f.read()
	else:
		last_status = ''
	
	# initialize
	# logger,handler = global_logger_init('/home/minx/Documents/logs/')
	slack_hook = config['overall_market_webhook']
	n = int(config['rsi_bars'])
	interval = str(config['interval'])
	symbol = 'NDAQ'
	status_dict = {'h':'high', 'n':'normal','l':'low'}

	# pull yfinance data

	ticker = yf.Ticker(symbol)
	start_date = str((datetime.now() - timedelta(days=59)).date())
	data = ticker.history(interval = interval, start = start_date).reset_index()

	# # dropping incomplete data
	# data = data.dropna() 
	# latest_dt = data.index[-1] # index contains datetime for multi symbols
	# latest_dt = latest_dt.astimezone(pytz.timezone('America/Los_Angeles'))

	# calculate technical indicators


	try:
		data['Upper'] = data[['Open','Close']].max(axis = 1)
		data['Lower'] = data[['Open','Close']].min(axis = 1)
		data['Midpoint'] = data[['Open','Close']].mean(axis = 1)
		data['pos'] = data['Datetime'].map(lambda x: (x - data['Datetime'].iloc[0]).total_seconds() / 60 / 60) # for linear regression

		x = data['pos']
		lr1, m, b = simple_lr(np.array(x).reshape(-1, 1), data['Midpoint'])
		pred = lr1.predict(np.array(x).reshape(-1,1)) 
		data['prop_dist_1'] = (pred - data['Midpoint']).abs() / pred
		cutoff = np.percentile(data['prop_dist_1'], 65)
		cutoff2 = np.percentile(data['prop_dist_1'], 50)
		df = data[data['prop_dist_1'] < cutoff].copy()
		x = np.array(df['pos']).reshape(-1,1)
		lr2, m, b = simple_lr(x, df['Midpoint'])
		pred = lr2.predict(np.array(x).reshape(-1,1))
		df['prop_dist_2'] = (pred - df['Midpoint']).abs() / df['Midpoint']
		df2 = df[df['prop_dist_2'] < cutoff2].copy()
		x = np.array(df2['pos']).reshape(-1,1)
		lr3, m, b = simple_lr(x, df2['Midpoint'])
		pred = lr3.predict(data['pos'].values.reshape(-1,1))
		data['epsilon'] = data['Midpoint'] - pred
		epsilon = data['epsilon'].iloc[-1]

		
		rsi_list = []
		n = 14
		rows = data['Close'].values
		# print(rows[-5:])
		rows = rows[1:] - rows[:-1] # make prices to deltas

		# initial calculation
		vals = rows[:n]
		prevU = np.sum(vals * (vals > 0).astype(int)) / n
		prevD = -1 * np.sum(vals * (vals < 0).astype(int)) / n

		for i in range(n, len(rows)):
		    rsi, prevU, prevD = calculate_rsi(rows[i], prevU, prevD, n)

		# initialize 
		vals = data['Close'].values
		smoothing = 2
		long_int = 26; short_int = 12 # accepted norm of ema lengths for macd
		long_ema = np.mean(vals[:long_int]) # simple average of first 26 values
		short_ema = np.mean(vals[(long_int - short_int):long_int]) # simple average of last 12 values from 26th index


		# measure macd
		for i in range(long_int, len(vals)):
		    macd, long_ema, short_ema = calculate_macd(vals[i], long_ema, short_ema, long_int, short_int, smoothing)


		message, status, recommendation = market_status(macd, rsi, epsilon)
		print(last_status, status)

		if last_status != status:

			text = 'Trend for ' + symbol + '\n'
			text += 'Change in status:' + '\n'
			text += 'MACD: ' + str(status_dict[last_status[0]]) + ' -> ' + str(status_dict[status[0]]) + '\n'
			text += 'RSI: ' + str(status_dict[last_status[1]]) + ' -> ' + str(status_dict[status[1]]) + '\n'
			text += 'Epsilon: ' + str(status_dict[last_status[2]]) + ' -> ' + str(status_dict[status[2]]) + '\n'
			text += 'Recommendation: ' + str(message)
			myobj = {"text":text}
			send_message_slack(slack_hook, myobj)

	except Exception as e:
		type_, value_, traceback_ = sys.exc_info()
		tb = traceback.format_exception(type_, value_, traceback_)
		tb = '\n' + ' '.join(tb)
		# logger.error('\n' + ' '.join(tb))
		# logger.error('exception occured %s',str(e))
		myobj = {"text":'something happened with ' + str(symbol) + ": " + str(tb)}
		send_message_slack(slack_hook, myobj)

	with open('overall_market_last_status.txt','w') as f:
		f.write(status)
	# send_message_slack(slack_hook,{'text':'sent'})


def send_last_status(last_status, symbol, interval):
	try:
		last_epoch = float(last_status[interval])
	except:
		return True

	silence_time = 600 # 10 minutes
	if time.time() - last_epoch > silence_time:
		return True
	else:
		return False

def market_status(macd, rsi, epsilon):
	macd_high = 1; macd_low = -1
	rsi_high = 65; rsi_low = 35
	eps_high = 2; eps_low = -2 

	if macd >= macd_high:
		if rsi >= rsi_high:
			if epsilon >= eps_high:
				return 'Currently in a big bubble, care for pop', 'hhh', 'Sell'
			elif epsilon <= eps_low:
				return 'Possible bull trap. Might go back up', 'hhl', 'Hold/Buy'
			else:
				return 'Quick crash, should go back up', 'hhn', 'Hold/Buy'
		elif rsi <= rsi_low:
			if epsilon >= eps_high:
				return 'Toss up', 'hlh','No Action Recommended'
			elif epsilon <= eps_low:
				return 'Toss up', 'hll','No Action Recommended'
			else:
				return 'Toss up', 'hln','No Action Recommended'
		else:
			if epsilon >= eps_high:
				return 'Possible early stages of crashing from a bubble burst. Keep an eye for potential burst', 'hnh', 'Hold/Sell'
			elif epsilon <= eps_low:
				return 'Toss up', 'hnl','No Action Recommended'
			else:
				return 'Toss up', 'hnn','No Action Recommended'
	elif macd <= macd_low:
		if rsi >= rsi_high:
			if epsilon >= eps_high:
				return 'Toss up', 'lhh','No Action Recommended'
			elif epsilon <= eps_low:
				return 'Toss up', 'lhl','No Action Recommended'
			else:
				return 'Toss up', 'lhn','No Action Recommended'
		elif rsi <= rsi_low:
			if epsilon >= eps_high:
				return 'Toss up', 'llh','No Action Recommended'
			elif epsilon <= eps_low:
				return 'Possible lowest point of crash. Look to buy', 'lll', 'Buy'
			else:
				return 'Toss up', 'lln','No Action Recommended'
		else:
			if epsilon >= eps_high:
				return 'Toss up', 'lnh','No Action Recommended'
			elif epsilon <= eps_low:
				return 'recovering from crash', 'lnl', 'Hold/Buy'
			else:
				return 'Toss up', 'lnn','No Action Recommended'
	else:
		if rsi >= rsi_high:
			if epsilon >= eps_high:
				return 'Early signs of imminent crash, take care', 'nhh', 'Hold/Sell'
			elif epsilon <= eps_low:
				return 'Toss up', 'nhl','No Action Recommended'
			else:
				return 'Toss up', 'nhn','No Action Recommended'
		elif rsi <= rsi_low:
			if epsilon >= eps_high:
				return 'Toss up', 'nlh','No Action Recommended'
			elif epsilon <= eps_low:
				return 'early stages of a crash; reaching bottom', 'nll', 'Hold/Buy'
			else:
				return 'early stages of a crash', 'nln', 'Hold/Buy'
		else:
			if epsilon >= eps_high:
				return 'Kinda in a bubble. Could pop, but possibly not imminent', 'nnh', 'Hold'
			elif epsilon <= eps_low:
				return 'Recovering market', 'nnl', 'Hold'
			else:
				return 'Toss up', 'nnn','No Action Recommended'



if __name__ == '__main__':
	# logger = ''
	# handler = ''
	# console_handler = ''
	# global logger, handler, console_handler

	FLAGS, unparsed = parser.parse_known_args()
	with open(FLAGS.config,'r') as in_:
		config = json.load(in_)
	if FLAGS.rsi_bars != 14:
		config['rsi_bars'] = FLAGS.rsi_bars
	if FLAGS.interval != '30m':
		config['interval'] = FLAGS.interval
	main(config)