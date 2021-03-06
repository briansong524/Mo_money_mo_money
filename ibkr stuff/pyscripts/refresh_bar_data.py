## Refresh/Repopulate bar_data
#
# In case of needed refreshing, clear out bar_data table and 
# repopulate with a week's worth of 5-second data. This is probably 
# best run during after-hours to get full historical data. 
#


import sys
import requests
import time
import json
import argparse
from datetime import datetime

import pymysql as MySQLdb
import pandas as pd
from utils import run_query, mysql_conn, db_conn_close

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

global DEFAULT_HISTORIC_DATA_ID, DEFAULT_GET_CONTRACT_ID, FINISHED, STARTED, TIME_OUT
DEFAULT_HISTORIC_DATA_ID=50
DEFAULT_GET_CONTRACT_ID=43

## marker for when queue is finished
FINISHED = object()
STARTED = object()
TIME_OUT = object()

class finishableQueue(object):

	def __init__(self, queue_to_finish):

		self._queue = queue_to_finish
		self.status = STARTED

	def get(self, timeout):
		"""
		Returns a list of queue elements once timeout is finished, or a FINISHED flag is received in the queue
		:param timeout: how long to wait before giving up
		:return: list of queue elements
		"""
		contents_of_queue=[]
		finished=False

		while not finished:
			try:
				current_element = self._queue.get(timeout=timeout)
				if current_element is FINISHED:
					finished = True
					self.status = FINISHED
				else:
					contents_of_queue.append(current_element)
					## keep going and try and get more data

			except queue.Empty:
				## If we hit a time out it's most probable we're not getting a finished element any time soon
				## give up and return what we have
				finished = True
				self.status = TIME_OUT


		return contents_of_queue

	def timed_out(self):
		return self.status is TIME_OUT





class TestWrapper(EWrapper):
	"""
	The wrapper deals with the action coming back from the IB gateway or TWS instance
	We override methods in EWrapper that will get called when this action happens, like currentTime
	Extra methods are added as we need to store the results in this object
	"""

	def __init__(self):
		self._my_contract_details = {}
		self._my_historic_data_dict = {}
		self._my_market_data_dict = {}
		
	## error handling code
	def init_error(self):
		error_queue=queue.Queue()
		self._my_errors = error_queue

	def get_error(self, timeout=5):
		if self.is_error():
			try:
				return self._my_errors.get(timeout=timeout)
			except queue.Empty:
				return None

		return None

	def is_error(self):
		an_error_if=not self._my_errors.empty()
		return an_error_if

	def error(self, id, errorCode, errorString):
		## Overriden method
		errormsg = "IB error id %d errorcode %d string %s" % (id, errorCode, errorString)
		self._my_errors.put(errormsg)


	## get contract details code
	def init_contractdetails(self, reqId):
		contract_details_queue = self._my_contract_details[reqId] = queue.Queue()

		return contract_details_queue

	def contractDetails(self, reqId, contractDetails):
		## overridden method

		if reqId not in self._my_contract_details.keys():
			self.init_contractdetails(reqId)

		self._my_contract_details[reqId].put(contractDetails)

	def contractDetailsEnd(self, reqId):
		## overriden method
		if reqId not in self._my_contract_details.keys():
			self.init_contractdetails(reqId)

		self._my_contract_details[reqId].put(FINISHED)

	## Historic data code
	def init_historicprices(self, tickerid):
		historic_data_queue = self._my_historic_data_dict[tickerid] = queue.Queue()

		return historic_data_queue


	def historicalData(self, tickerid , bar):

		## Overriden method
		## Note I'm choosing to ignore barCount, WAP and hasGaps but you could use them if you like
		bardata=(bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume)

		historic_data_dict=self._my_historic_data_dict

		## Add on to the current data
		if tickerid not in historic_data_dict.keys():
			self.init_historicprices(tickerid)

		historic_data_dict[tickerid].put(bardata)

	def historicalDataEnd(self, tickerid, start:str, end:str):
		## overriden method

		if tickerid not in self._my_historic_data_dict.keys():
			self.init_historicprices(tickerid)

		self._my_historic_data_dict[tickerid].put(FINISHED)


class TestClient(EClient):
	"""
	The client method
	We don't override native methods, but instead call them from our own wrappers
	"""
	def __init__(self, wrapper):
		## Set up with a wrapper inside
		EClient.__init__(self, wrapper)
		self._market_data_q_dict = {}


	def resolve_ib_contract(self, ibcontract, reqId=DEFAULT_GET_CONTRACT_ID):

		"""
		From a partially formed contract, returns a fully fledged version
		:returns fully resolved IB contract
		"""

		## Make a place to store the data we're going to return
		contract_details_queue = finishableQueue(self.init_contractdetails(reqId))

		print("Getting full contract details from the server... ")

		self.reqContractDetails(reqId, ibcontract)

		## Run until we get a valid contract(s) or get bored waiting
		MAX_WAIT_SECONDS = 30
		new_contract_details = contract_details_queue.get(timeout = MAX_WAIT_SECONDS)

		while self.wrapper.is_error():
			print(self.get_error())

		if contract_details_queue.timed_out():
			print("Exceeded maximum wait for wrapper to confirm finished - seems to be normal behaviour")

		if len(new_contract_details)==0:
			print("Failed to get additional contract details: returning unresolved contract")
			return ibcontract

		if len(new_contract_details)>1:
			print("got multiple contracts using first one")

		new_contract_details=new_contract_details[0]

		resolved_ibcontract=new_contract_details.contract

		return resolved_ibcontract


	def get_IB_historical_data(self, ibcontract, durationStr="1 D", barSizeSetting="5 secs",
							   tickerid=DEFAULT_HISTORIC_DATA_ID):

		"""
		Returns historical prices for a contract, up to today
		ibcontract is a Contract
		:returns list of prices in 4 tuples: Open high low close volume
		"""


		## Make a place to store the data we're going to return
		historic_data_queue = finishableQueue(self.init_historicprices(tickerid))

		# Request some historical data. Native method in EClient
		self.reqHistoricalData(
			tickerid,  # tickerId,
			ibcontract,  # contract,
			datetime.today().strftime("%Y%m%d %H:%M:%S %Z"),  # endDateTime,
			durationStr,  # durationStr,
			barSizeSetting,  # barSizeSetting,
			"TRADES",  # whatToShow,
			1,  # useRTH,
			1,  # formatDate
			False,  # KeepUpToDate <<==== added for api 9.73.2
			[] ## chartoptions not used
		)


		## Wait until we get a completed data, an error, or get bored waiting
		MAX_WAIT_SECONDS = 200
		print("Getting historical data from the server... could take %d seconds to complete " % MAX_WAIT_SECONDS)

		historic_data = historic_data_queue.get(timeout = MAX_WAIT_SECONDS)

		while self.wrapper.is_error():
			print(self.get_error())

		if historic_data_queue.timed_out():
			print("Exceeded maximum wait for wrapper to confirm finished - seems to be normal behaviour")
		self.cancelHistoricalData(tickerid)


		return historic_data
	

class TestApp(TestWrapper, TestClient):
	def __init__(self, ipaddress, portid, clientid):
		error_queue=queue.Queue()
		self._my_errors = error_queue
		
		TestWrapper.__init__(self)
		TestClient.__init__(self, wrapper=self)

		self.connect(ipaddress, portid, clientid)

		thread = Thread(target = self.run)
		thread.start()

		setattr(self, "_thread", thread)

		self.init_error()
	def kill_thread(self):
		self._thread.release()

def update(config, symbol):

	conn_cred = config['conn_cred']



	app = TestApp("127.0.0.1", 7497, 1)
	ibcontract = IBcontract()
	ibcontract.secType = "STK"
	# ibcontract.lastTradeDateOrContractMonth="202011"
	ibcontract.symbol=symbol
	ibcontract.exchange="SMART"
	ibcontract.currency = "USD"
	ibcontract.primaryExchange = "NASDAQ"
	resolved_ibcontract=app.resolve_ib_contract(ibcontract)
	# print(resolved_ibcontract)
	historic_data = app.get_IB_historical_data(resolved_ibcontract, durationStr = "1 W", barSizeSetting = "10 secs")
	print('pulled historical data. converting data to something mysql expects')
	df = pd.DataFrame(historic_data, columns = ['datetime','open','high','low','close','volume'])
	df['symbol'] = symbol
	df['datetime'] = pd.to_datetime(df['datetime'],format = '%Y%m%d  %H:%M:%S')
	 
	df['epoch'] = (df['datetime'] - datetime(1970,1,1)).dt.total_seconds() + (480*60)
	list_vals = df[['symbol','epoch','open','high','low','close','volume']].values.tolist()
	# list_vals = (tuple(i) for i in list_vals) # for executemany()


	print('inserting to sql database')
	## robust one-by-one insertion
	for i in range(len(list_vals)):
		query = "INSERT INTO {dbname}.bar_data (symbol, epoch,\
					open, high,low, close, volume\
					) VALUES ({csv})".format(dbname = conn_cred['dbname'],
									  csv = ','.join(map(lambda x: "'" + str(x) + "'",list_vals[i])))
		run_query(conn_cred, query)
	## executemany (supposed to be a gajillion times faster)
	## dunno how to make this work tho
	# query = "INSERT INTO {dbname}.bar_data (symbol, epoch,\
	#  				open, high,low, close, volume\
	#  				) VALUES (%s)".format(dbname=conn_cred['dbname'],
	#  												symbol=symbol)
	# dbconn, cursor = mysql_conn(conn_cred['dbname'])
	# cursor.executemany(query, list_vals)
	# db_conn_close()
	print('done updating')
	# app.conn.disconnect()
	# app.done = True
	sys.exit()

if __name__ == '__main__':
	FLAGS, unparsed = parser.parse_known_args()
	with open(FLAGS.config,'r') as in_:
		config = json.load(in_)
	update(config, FLAGS.symbol)