## Refresh/Repopulate bar_data
#
# In case of needed refreshing, clear out bar_data table and 
# repopulate with a week's worth of 5-second data. This is probably 
# best run during after-hours to get full historical data. 
#



import requests
import time
import json
import argparse
from datetime import datetime

import pymysql as MySQLdb
import pandas as pd
from utils import run_query, mysql_conn, db_conn_close, basicContract

from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.contract import Contract as IBcontract
from threading import Thread
import queue



parser = argparse.ArgumentParser()


parser.add_argument(
	'--config', type=str, default='/home/minx/Documents/config.conf',
	help = 'Config file for all configuration info')

parser.add_argument(
	'--symbol', type=str, 
	help = 'Which symbol to update with data')

parser.add_argument(
	'--reset_database', type=bool, default=False,
	help = 'If the database should be wiped out')


def main(config):
	conn_cred = config['conn_cred']
	slack_hook = config['slack_webhook']
	symbols = config['symbols'].split(',')
	app = historicalApp()
	app.connect("127.0.0.1", 7497, 1)
	app.mysqlConfig(conn_cred)

	for i in range(len(symbols)):
		print('running for ' + symbols[i]) 
		contract = basicContract(symbols[i])
		app.start_historicalBar(reqId = i+1, 
								  contract = contract, 
								  durationStr = "1 W", 
								  barSizeSetting = "10 secs"
								 )


class historicalApp(EWrapper, EClient):

	def __init__(self):
		EClient.__init__(self,self)
		self.creds = {}
		self.ticker_dict = {}
		self.outFormat = 'print'

	def start_historicalBar(self, reqId, contract, durationStr, barSizeSetting):
		self.reqHistoricalData(
			reqId,  # reqId,
			contract,  # contract,
			datetime.today().strftime("%Y%m%d %H:%M:%S %Z"),  # endDateTime,
			durationStr,  # durationStr,
			barSizeSetting,  # barSizeSetting,
			"TRADES",  # whatToShow,
			1,  # useRTH,
			2,  # formatDate (1 for 'yyyymmdd  hh:mm:dd', 2 for epoch)
			False,  # KeepUpToDate <<==== added for api 9.73.2
			[] ## chartoptions not used
		)
		self.ticker_dict[reqId] = {
								   'symbol':contract.symbol
								  }

	def historicalData(self, reqId, bar):
		bardata=(bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume)

		print('historical data received for ' + str(self.ticker_dict[reqId]['symbol']))
		print('received ' + str(len(bardata)) + ' rows to insert. inserting')
		for list_vals in bardata:
			csvOutputs = ','.join(map(lambda x: "'" + str(x) + "'",list_vals))
			query = 'INSERT INTO {dbname}.bar_data (symbol, epoch, open, high, \
							 low, close, volume) \
							 VALUES ({symbol},{csv})'.format(dbname = self.creds['dbname'],
							 					  symbol = "'" + self.ticker_dict[reqId]['symbol'] + "'",
												  csv = csvOutputs)
			run_query(self.creds, query)
		print('done inserting ' + str(self.ticker_dict[reqId]['symbol']) + ' to database')
		self.cancelHistoricalData(reqId)
		

	def mysqlConfig(self, creds):
		# load in MySQL credentials
		self.creds = creds
		self.outFormat = 'mysql'
if __name__ == '__main__':
	FLAGS, unparsed = parser.parse_known_args()
	with open(FLAGS.config,'r') as in_:
		config = json.load(in_)
	main(config)