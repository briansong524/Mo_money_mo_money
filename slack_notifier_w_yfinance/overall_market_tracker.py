'''
# Overall Market Tracker

Tracks the overall market health, and makes notes accordingly

Indicators Used:
- RSI
- MACD
- Epsilon
  - This one is self defined. The distance between true price and 
    predicted price from linear regression

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
from utils import calculate_ema, calculate_macd
from utils import calculate_epsilon, simple_lr

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
	help = 'Number of bars used to calculate rsi')
parser.add_argument(
	'--interval', type=str, default='30m',
	help = 'Size of bar')
parser.add_argument(
	'--which_values', type=str, default='Close',
	help = 'Close or Midpoint values to use')
parser.add_argument(
	'--overbought', type=int, default=70,
	help = 'Threshold for overbought rsi')
parser.add_argument(
	'--oversold', type=int, default=30,
	help = 'Threshold for oversold rsi')

def main(config):
	
	main_dir = os.path.dirname(os.path.realpath(__file__))
	os.chdir(main_dir)
	# initialize
	# logger,handler = global_logger_init('/home/minx/Documents/logs/')
	slack_hook = config['overall_market_webhook']
	symbols = 'NDAQ,SPY,DIA'.split(',')
	n = int(config['rsi_bars'])
	interval = str(config['interval'])
	which_values = str(config['which_values'])
	try:
		overbought = int(config['overbought_threshold'])
	except:
		overbought = 70
	try:
		oversold = int(config['oversold_threshold'])
	except:
		oversold = 30
	send_message = False # swaps to True if any of the symbols were to be sent
	text = ''
	status_dict = {'h':'high', 'n':'normal','l':'low'}

	# make slack gate file to repress redundant messages
	new_instance = False
	if os.path.exists('overall_market_last_status.json'):
		with open('overall_market_last_status.json','r') as f:
			slack_gate = json.load(f)
	else:
		slack_gate = {}
		new_instance = True

	# pull yfinance data
	ticker = yf.Ticker(symbol)
	start_date = str((datetime.now() - timedelta(days=59)).date())
	data = ticker.history(interval = interval, start = start_date).reset_index()

	# calculate technical indicators
	for symbol in symbols:
		try:
			df = data[symbol].copy()

			# just do midpoint as default option 
			if which_values == 'Close':
				rows = df['Close'].values
			else:
				rows = df[['Open','Close']].mean(axis = 1).values # midpoint 

			rsi = mult_rsi(rows, n_int = 14)
			macd = mult_macd(rows)
			epsilon = calculate_epsilon(df, last_epsilon_only = True)

			message, status, recommendation = market_status(macd, rsi, epsilon)
			try:
				last_status = slack_gate[symbol][interval]['last_status']
			except:
				last_status = ''
				
			if last_status == '':
				text = "New Instance\n"
				text += 'Trend for ' + symbol + '\n'
				text += 'MACD: ' + str(status_dict[status[0]]) + '\n'
				text += 'RSI: ' + str(status_dict[status[1]]) + '\n'
				text += 'Epsilon: ' + str(status_dict[status[2]]) + '\n'
				text += 'Note: ' + str(message)
				myobj = {"text":text}
				send_message_slack(slack_hook, myobj)
			else:
				if last_status != status:

					text = 'Trend for ' + symbol + '\n'
					text += 'Change in status:\n'
					text += 'MACD: ' + str(status_dict[last_status[0]]) + ' -> ' + str(status_dict[status[0]]) + '\n'
					text += 'RSI: ' + str(status_dict[last_status[1]]) + ' -> ' + str(status_dict[status[1]]) + '\n'
					text += 'Epsilon: ' + str(status_dict[last_status[2]]) + ' -> ' + str(status_dict[status[2]]) + '\n'
					text += 'Note: ' + str(message)
					myobj = {"text":text}
					send_message_slack(slack_hook, myobj)

			slack_gate[symbol] = {
									'last_epoch':round(time.time(),2),
									'last_rsi':round(rsi,2)
							     }

		except Exception as e:
			type_, value_, traceback_ = sys.exc_info()
			tb = traceback.format_exception(type_, value_, traceback_)
			tb = '\n' + ' '.join(tb)
			# logger.error('\n' + ' '.join(tb))
			# logger.error('exception occured %s',str(e))
			myobj = {"text":'something happened with ' + str(symbol) + ": " + str(tb)}
			send_message_slack(slack_hook, myobj)

	# with open('overall_market_last_status.txt','w') as f:
	# 	f.write(status)
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
	config['overbought_threshold'] = FLAGS.overbought
	config['oversold_threshold'] = FLAGS.oversold
	main(config)