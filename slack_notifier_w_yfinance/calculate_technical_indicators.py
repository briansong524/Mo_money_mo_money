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
	help = 'number of bars used to calculate rsi')
parser.add_argument(
	'--period', type=str, default='',
	help = 'how much historical data to use')
parser.add_argument(
	'--interval', type=str, default='',
	help = 'size of bar')




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
	info_dict = {}
	try:
		overbought = int(config['overbought_threshold'])
	except:
		overbought = 70
	try:
		oversold = int(config['oversold_threshold'])
	except:
		oversold = 30

	# make slack gate file to repress redundant messages
	new_instance = False
	rsi_dict = {}
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

	latest_dt = data.index[-1] # index contains datetime for multi symbols
	latest_dt = latest_dt.astimezone(pytz.timezone('America/Los_Angeles'))
	localFormat = "%Y-%m-%d %H:%M:%S"
	latest_dt = latest_dt.strftime(localFormat)
	print('last datetime: ' + str(latest_dt))

	# calculate technical indicators

	for symbol in symbols:
		try:
			# dropping incomplete data
			df = data[symbol].dropna() 
			df = df[df['Volume'] != 0] # this maybe overkill


			rows = df['Close'].values
			rsi = mult_rsi(rows, n_int = n, last_rsi_only = True)
			# print(rows[-5:])
			# rows = rows[1:] - rows[:-1] # make prices to deltas

			# # initial calculation
			# vals = rows[:n]
			# prevU = np.sum(vals * (vals > 0).astype(int)) / n
			# prevD = -1 * np.sum(vals * (vals < 0).astype(int)) / n

			# for i in range(n, len(rows)):
			# 	rsi, prevU, prevD = calculate_rsi(rows[i], prevU, prevD, n)

			print('RSI: ' + str(rsi))
			# send slack message based on rsi

			## state of the stock


			status = rsi_as_category(rsi, overbought, oversold)
			
			# save rsi somewhere
			# rsi_dict[symbol] = {'rsi':str(round(rsi,2)), 'status':status}


			# send to slack if conditions are met
			bool1 = status in ['Oversold','Overbought']
			bool2 = send_slack_gate(slack_gate,symbol,interval)


			if bool1 & bool2 & ~new_instance:
				# dont send redundant message if the rsi is less oversold/overbought when it previously was
				send_message = False
				try:
					if status == 'Oversold':
						if slack_gate[symbol][interval]['last_rsi'] > rsi:
							send_message = True
					elif status == 'Overbought':
						if slack_gate[symbol][interval]['last_rsi'] < rsi:
							send_message = True
				except:
					send_message = True

				# make slack message
				if send_message:
					print('sending message')
					text = '(' + status + ') ' + symbol + ' RSI' + str(n)  + ' (' + str(interval) + ' bars)' + ': ' + str(round(rsi,2))
					## add time to the message
					# curr = datetime.now()
					# curr_pst = curr.astimezone(pytz.timezone('America/Los_Angeles'))
					# localFormat = "%Y-%m-%d %H:%M:%S"
					# curr_pst = curr_pst.strftime(localFormat)
					# text += ' on ' + str(curr_pst) 

					myobj = {"text":text}
					send_message_slack(slack_hook, myobj)

				## add to slack_gate
				if symbol not in slack_gate:
					slack_gate[symbol] = {}
				slack_gate[symbol][interval] = {
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
			# send_message_slack(slack_hook, myobj)
			print(myobj['text'])

	# send a message if its the first time with new config
	# regardless of rsi 

	if new_instance:

		rsi_text = ''
		for i in rsi_dict.keys():
			rsi_text += str(i) + ': ' + str(rsi_dict[i]['rsi']) + ' (' + str(rsi_dict[i]['status']) + ')\n'

		text = 'New instance running for symbols: ' + str(config['symbols']) + '\n\n'
		text += 'Current RSI(s):\n'
		text += rsi_text
		# print(text)
		myobj = {"text":text}
		send_message_slack(slack_hook, myobj)

	with open('slack_gate.json','w') as f:
		json.dump(slack_gate, f)
	# send_message_slack(slack_hook,{'text':'sent'})


def send_slack_gate(slack_gate, symbol, interval):
	try:
		last_epoch = float(slack_gate[symbol][interval]['last_epoch'])
	except:
		return True

	silence_time = 300 # 5 minutes
	if time.time() - last_epoch > silence_time:
		return True
	else:
		return False

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
	if FLAGS.interval != '':
		config['interval'] = FLAGS.interval
	main(config)