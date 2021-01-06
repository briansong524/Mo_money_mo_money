from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.ticktype import TickTypeEnum

import pymysql as MySQLdb

import time
from datetime import datetime


def basicContract(symbol, secType = 'STK', exchange = 'SMART', 
					currency = 'USD', primaryExchange = 'NASDAQ'):
	# for the most part, the stock of interest share the same basic details,  
	# so just setting a bunch of defaults 
	contract = Contract()
	contract.symbol = symbol
	contract.secType = secType
	contract.exchange = exchange
	contract.currency = currency
	contract.primaryExchange = primaryExchange
	return contract


# def rsi(prices, n = 14, avg_method = 'simple'):
# 	# given a list of sequential price changes (prices), use len(prices) 
# 	# changes to calculate rsi.
# 	#
# 	# prices = numpy array
# 	# n = int
# 	# avg_method = str
	
# 	assert len(prices) > n, 'list of price delta less than rsi period'
	
# 	rsi_list = [np.nan] * n
	
# 	n_prices = len(prices)
# 	if avg_method == 'simple':
# 		alpha = 1
# 	elif avg_method == 'exponential':
# 		alpha = 2 / (n+1)
# 	elif avg_method == 'wilder':
# 		alpha = 1 / n
# 	for i in range(n, n_prices):
# 		vals = prices[(i-n):i]
# 		U = np.sum(vals * (vals > 0).astype(int)) / n_prices
# 		D = -1 * np.sum(vals * (vals < 0).astype(int)) / n_prices
# 		if i == n:
# 			avgU = U
# 			avgD = D
# 		else:
# 			U = np.sum(vals * (vals > 0).astype(int)) / n_prices
# 			D = -1 * np.sum(vals * (vals < 0).astype(int)) / n_prices
# 			avgU = alpha * U + (1 - alpha) * prevU
# 			avgD = alpha * D + (1 - alpha) * prevD
# 		prevU = avgU
# 		prevD = avgD
# 		rs = avgU / avgD
# 		rsi = 100.0 - 100.0 / (1 + rs)
# 		rsi_list.append(rsi)
# 	return rsi_list

class RealTimeTickApp(EWrapper, EClient):

	def __init__(self):
		EClient.__init__(self,self)
		self.ticker_dict = {}
		self.creds = {}
		self.outFormat = 'print'

	def error(self, reqId, errorCode, errorString):
		print("Error: ", reqId, " ", errorCode, " ", errorString)
		if reqId in self.ticker_dict.keys():
			print('restarting from bust event for reqId: ' + str(reqId) +
				   ' (' + str(self.ticker_dict[reqId]['symbol']) + 
				   '). check to make sure this makes sense')
			try:
				print('restarting request')
				self.cancelRealTimeBars(reqId)
				self.reqRealTimeBars(reqId, self.ticker_dict[reqId]['contract'],
								 self.ticker_dict[reqId]['barSize'],
								 self.ticker_dict[reqId]['whatToShow'],
								 self.ticker_dict[reqId]['useRTH'],
								 self.ticker_dict[reqId]['realTimeBarsOptions'])
			except Exception as e:
				print('restarting request failed')
				print('error: ' + str(e))		


	## realtimebar stuff

	def start_reqRealTimeBars(self, reqId, contract, barSize, whatToShow,
								useRTH,realTimeBarsOptions):
		# start requesting live 5 second tick data 
		# 
		# outFormat can be either 'print' or 'mysql', depending on if you
		# want to just print out the data being received, or sent to a MySQL
		# database based on mysqlConfig()

		self.ticker_dict[reqId] = {
								   'symbol':contract.symbol,
								   'contract':contract,
								   'barSize':barSize,
								   'whatToShow':whatToShow,
								   'useRTH':useRTH,
								   'realTimeBarsOptions':realTimeBarsOptions
								  }
		print('Starting requests for ' + str(self.ticker_dict[reqId]['symbol']))
		self.reqRealTimeBars(reqId, contract, barSize, 
								whatToShow,useRTH,realTimeBarsOptions)

	def realtimeBar(self, reqId, time:int, open_: float, high: float, 
						low: float, close: float, volume: int, wap: float, 
						count: int):
		# output the real time tick data as it is being obtained. 
		# 
		# outFormat can be either 'print' or 'mysql', depending on if you
		# want to just print out the data being received, or sent to a MySQL
		# database based on mysqlConfig()
		# 
		# note that time is returned as epoch time for GMT
		# Volume for US stocks has a multiplier of 100

		if self.outFormat == 'print':
			print(self.ticker_dict[reqId]['symbol'],time, open_, high, low, close, 
				  volume, wap, count)
		elif self.outFormat == 'mysql':
			now = datetime.now() # basing these numbers on pst
			rth_start = (now.hour >= 6) & (now.minute >= 30)
			rth_end = (now.hour < 13) 
			if rth_start & rth_end:
				list_vals = [self.ticker_dict[reqId]['symbol'],time, open_, 
								high, low, close, volume]
				csvOutputs = ','.join(map(lambda x: "'" + str(x) + "'",list_vals))
				query = 'INSERT INTO {dbname}.bar_data (symbol, epoch, open, high, \
						 low, close, volume) \
						 VALUES ({csv})'.format(dbname = self.creds['dbname'],
											  csv = csvOutputs)
				run_query(self.creds, query)

	def mysqlConfig(self, creds):
		# load in MySQL credentials
		self.creds = creds
		self.outFormat = 'mysql'

def run_query(creds, query, selectBool = False):
	conn, cursor = mysql_conn(creds)

	try:
		cursor.execute(query)
		if selectBool:
			rows = cursor.fetchall()
	except Exception as e:
		print('Error in running query: ' + str(e))
	finally:
		db_conn_close(conn, cursor)
		if selectBool:
			return rows


def mysql_conn(db_conn_info):
	'''
	Call to connect to the database
	'''
	try:
		dbconn_ = MySQLdb.connect(host=db_conn_info['dbservername'],
					db = db_conn_info['dbname'],
					user = db_conn_info['dbuser'],
					passwd = db_conn_info['dbpassword']
					)
		cursor_ = dbconn_.cursor()
		return dbconn_, cursor_

	except Exception as e:
		print('Error: ' + str(e))

def db_conn_close(dbconn, cursor):
	# closing connections to free up sockets
	dbconn.commit()
	cursor.close()
	dbconn.close()