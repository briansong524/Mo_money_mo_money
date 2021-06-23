'''
# Technical Indicator Calculations

Since yfinance pulls data in one big chunk of historic 
data (delayed 1 min), use the whole pulled dataset to calculate
various technical indicators
Refer to [1] for documentation

## Technical Indicators ##
- RSI
  - RSI measured relative to interval range used
    - period of data used to calculate the starting RSI will 
      be as such:
      - 1 day (~390 bars) for 1 minute interval
      - 5 days (~390 bars) for 5 minute interval
      - 1 month (~535 bars) for 15 minute interval
    - Possibly, it would be wise to be consistent and just use the 
      last 300 points of data or so 
  - The number of bars used to calculate RSI is gonna be defaulted to:
    - 9 for 1 min interval
    - 12 for 5 min interval
    - 14 for 15 min interval
- MACD

## Process ##
- load in symbols based on config
- pull data from yahoo finance
- calculate technical indicators
- (currently) if rsi is <30 or >70, send data to slack


## Dev Notes ##
- RSI is more in line with broker's calculations when more historical
  data is used [2], so will use >250 data points for each calculation

## Links ##
[1] https://pypi.org/project/yfinance/
[2] https://school.stockcharts.com/doku.php?id=technical_indicators:relative_strength_index_rsi
'''

import os,sys
import argparse
import json
import traceback
import time

import yfinance as yf
import pytz
from datetime import datetime
import pandas as pd
import numpy as np
from utils import calculate_rsi, mult_rsi, rsi_as_category
from utils import send_message_slack
from utils import epoch_check_slack_gate, rsi_peak_check_slack_gate
from utils import midpoint_imputation

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
	'--rsi_bars', type=int, default=0,
	help = 'Number of bars used to calculate rsi')
parser.add_argument(
	'--period', type=str, default='',
	help = 'How much historical data to use')
parser.add_argument(
	'--interval', type=str, default='',
	help = 'Size of bar')
parser.add_argument(
	'--which_values', type=str, default='Close',
	help = 'Close or Midpoint values to use')




def main(config):
	
	main_dir = os.path.dirname(os.path.realpath(__file__))
	os.chdir(main_dir)

	
	# initialize
	# logger,handler = global_logger_init('/home/minx/Documents/logs/')
	slack_hook = config['slack_webhook']
	symbols = config['symbols'].split(',')
	n = int(config['rsi_bars'])
	period = str(config['period'])
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

	# make slack gate file to repress redundant messages
	new_instance = False
	if os.path.exists('slack_gate.json'):
		with open('slack_gate.json','r') as f:
			slack_gate = json.load(f)
	else:
		slack_gate = {}
		new_instance = True

	# pull yfinance data

	tickers = ' '.join(symbols)
	data = yf.download(tickers = tickers, 
		period = period, interval = interval, group_by = 'ticker', prepost = True)

	# latest_dt = data.index[-1] # index contains datetime for multi symbols
	# latest_dt = latest_dt.astimezone(pytz.timezone('America/Los_Angeles'))
	# localFormat = "%Y-%m-%d %H:%M:%S"
	# latest_dt = latest_dt.strftime(localFormat)
	# print('last datetime: ' + str(latest_dt))

	# calculate technical indicators

	for symbol in symbols:
		try:
			# dropping incomplete data
			df = data[symbol].copy() 
			# df = df[df['Volume'] != 0] # this maybe overkill

			# just do midpoint as default option 
			if which_values == 'Close':
				rows = df['Close'].values
			else:
				rows = df[['Open','Close']].mean(axis = 1).values # midpoint 

			rows = midpoint_imputation(rows) # fill in missing values
			rsi = mult_rsi(rows, n_int = n, last_val_only = True)
			print('RSI: ' + str(rsi))
			
			# send slack message based on rsi

			## state of the stock
			status = rsi_as_category(rsi, overbought, oversold)
			
			try:
				rsi_max = slack_gate[symbol][interval]['max_rsi']
				rsi_min = slack_gate[symbol][interval]['min_rsi']
			except:
				rsi_max = 50.
				rsi_min = 50.

			# send to slack if conditions are met
			bool1 = status in ['Oversold','Overbought']
			try:
				last_epoch = slack_gate[symbol][interval]['last_epoch']
				bool2 = epoch_check_slack_gate(last_epoch)
			except:
				last_epoch = 0.0
				bool2 = True
			bool3 = rsi_peak_check_slack_gate([rsi_max,rsi_min],rsi,status)

			if bool1 & bool2 & bool3 & ~new_instance:
				send_message = True

				# make slack message
				print('sending message')
				text += '(' + status + ') ' + symbol + ' RSI' + str(n)  + ' (' 
				text += str(interval) + ' bars)' + ': ' + str(round(rsi,2)) + '\n'
				last_epoch = round(time.time(),2)
				# slack_gate[symbol][interval]['last_epoch'] = round(time.time(),2)

			## reset peaks if rsi within 'very normal' bounds
			if (rsi < (overbought - 5)) & (rsi > (oversold + 5)):
				rsi_max = 50.
				rsi_min = 50.
			else:
				rsi_max = max(rsi_max, rsi)
				rsi_min = min(rsi_min, rsi)

			## add to slack_gate
			if symbol not in slack_gate:
				slack_gate[symbol] = {}
			if interval not in slack_gate[symbol]:
				slack_gate[symbol][interval] = {}
	
			slack_gate[symbol][interval].update({
												'last_rsi':round(rsi,2),
												'max_rsi':rsi_max,
												'min_rsi':rsi_min,
												'status':status,
												'last_epoch':last_epoch
											   })

		except Exception as e:
			type_, value_, traceback_ = sys.exc_info()
			tb = traceback.format_exception(type_, value_, traceback_)
			tb = '\n' + ' '.join(tb)
			# logger.error('\n' + ' '.join(tb))
			# logger.error('exception occured %s',str(e))
			myobj = {"text":'something happened with ' + str(symbol) + ": " + str(tb)}
			# send_message_slack(slack_hook, myobj)
			print(myobj['text'])

	# send a message if its the first time with new config
	# regardless of rsi 

	if send_message:
		myobj = {"text":text}
		send_message_slack(slack_hook, myobj)		

	if new_instance:
		rsi_text = ''
		for i in slack_gate.keys():
			rsi_text += str(i) + ': ' + str(slack_gate[i][interval]['last_rsi']) 
			rsi_text += ' (' + str(slack_gate[i][interval]['status']) + ')\n'

		text = 'New instance running for symbols: ' + str(config['symbols']) + '\n\n'
		text += 'Current RSI(s):\n'
		text += rsi_text
		myobj = {"text":text}
		send_message_slack(slack_hook, myobj)									   
	with open('slack_gate.json','w') as f:
		json.dump(slack_gate, f)
	# send_message_slack(slack_hook,{'text':'sent'})



if __name__ == '__main__':
	# logger = ''
	# handler = ''
	# console_handler = ''
	# global logger, handler, console_handler

	FLAGS, unparsed = parser.parse_known_args()
	with open(FLAGS.config,'r') as in_:
		config = json.load(in_)
	if FLAGS.rsi_bars != 0:
		config['rsi_bars'] = FLAGS.rsi_bars
	if FLAGS.period != '':
		config['period'] = FLAGS.period
	# if FLAGS.interval != '':
		# config['interval'] = FLAGS.interval
	config['which_values'] = FLAGS.which_values
	main(config)
