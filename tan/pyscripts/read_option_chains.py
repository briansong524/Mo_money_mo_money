from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.utils import iswrapper
from ibapi.contract import Contract
from ibapi.ticktype import TickTypeEnum
from threading import Thread
import queue

class MarketReader(EWrapper, EClient):
	''' Serves as the client and the wrapper '''

	def __init__(self, addr, port, client_id):
		EWrapper.__init__(self)
		EClient. __init__(self, self)

		# Connect to TWS
		self.connect(addr, port, client_id)

		# Launch the client thread
		thread = Thread(target=self.run)
		thread.start()

		# remove
		self.current_price = 999.74
		self.chain = {}
	# @iswrapper
	# def tickByTickMidPoint(self, reqId, tick_time, midpoint):
	# 	''' Called in response to reqTickByTickData '''
	# 	print('tickByTickMidPoint - Midpoint tick: {}'.
	# 		format(midpoint))

	# @iswrapper
	# def tickPrice(self, reqId, field, price, attribs):
	# 	''' Called in response to reqMktData '''
	# 	print('tickPrice - field: {}, price: {}'.format(field,
	# 		price))

	# @iswrapper
	# def tickSize(self, reqId, field, size):
	# 	''' Called in response to reqMktData '''
	# 	print('tickSize - field: {}, size: {}'.format(field,
	# 		size))

	# @iswrapper
	# def realtimeBar(self, reqId, time, open, high, low,
	# 	close, volume, WAP, count):
	# 	''' Called in response to reqRealTimeBars '''
	# 	self.current_price = close
	# 	print('realtimeBar - Opening price: {}'.format(open))
	@iswrapper
	def realtimeBar(self, reqId, time:int, open_: float, high: float, 
						low: float, close: float, volume: int, wap: float, 
						count: int):
		self.current_price = close
		print('got realtime bar data')

	@iswrapper
	def historicalData(self, reqId, bar):
		''' Called in response to reqHistoricalData '''
		print('historicalData - Close price: {}'
			.format(bar.close))

	@iswrapper
	def fundamentalData(self, reqId, data):
		''' Called in response to reqFundamentalData '''
		print('Fundamental data: ' + data)
	
	@iswrapper
	def error(self, reqId, code, msg):
		print('Error {}: {}'.format(code, msg))


	@iswrapper
	def contractDetails(self, reqId, desc):
		''' Obtain contract ID '''
		self.conid = desc.contract.conId
		self.exchange = desc.contract.exchange
		# print(desc.validExchanges)

	@iswrapper
	def tickByTickMidPoint(self, reqId, time, midpoint):
		''' Obtain current price '''
		self.current_price = midpoint
		# print('current price: ' + str(midpoint))

	@iswrapper
	def securityDefinitionOptionParameter(self, reqId, exchange, 
		underlyingConId, tradingClass, multiplier, expirations, strikes):
		''' Provide strike prices and expiration dates '''

		# Save expiration dates and strike prices
		# if exchange == 'SMART':
		self.exchange = exchange
		self.expirations = expirations
		self.strikes = strikes

	@iswrapper
	def securityDefinitionOptionParameterEnd(self, reqId):
		''' Process data after receiving strikes/expirations '''

		# Find strike price closest to current price
		print(self.strikes)
		self.strikes = sorted(self.strikes)
		min_dist = 99999.0
		print('current_price: ' + str(self.current_price))
		for i, strike in enumerate(self.strikes):
			if strike - self.current_price < min_dist:
				min_dist = abs(strike - self.current_price)
				self.atm_index = i
				print('new min_dist: ' + str(strike))
		self.atm_price = self.strikes[self.atm_index]

		# Limit strike prices to +7/-7 around ATM
		print(self.atm_index)
		front = self.atm_index - 7
		back = len(self.strikes) - (self.atm_index + 7)
		if front > 0:
			del self.strikes[:front]
		if back > 0:
			del self.strikes[-(back-1):]

		# Find an expiration date just over a month away
		self.expirations = sorted(self.expirations)
		for date in self.expirations:
			exp_date = datetime.strptime(date, '%Y%m%d')
			current_date = datetime.now()
			interval = exp_date - current_date
			if interval.days > 21:
				self.expiration = date
				print('Expiration: {}'.format(self.expiration))
				break

		# aggregate option details to a neat graph
		# if self.exchange = 'SMART':
		# print('called')
		# print(self.exchange, self.expirations, self.strikes)


	@iswrapper
	def tickPrice(self, req_id, field, price, attribs):
		''' Provide option's ask price/bid price '''

		if (field != 1 and field != 2) or price == -1.0:
			print('skipped')
			print(field,price)
			return
		
		# Determine the strike price and right
		strike = self.strikes[(req_id - 3)//2]
		right = 'C' if req_id & 1 else 'P'

		# Update the option chain
		if field == 1:
			self.chain[strike][right]['bid_price'] = price
		elif field == 2:
			self.chain[strike][right]['ask_price'] = price
		print(field,price)

	@iswrapper
	def tickSize(self, req_id, field, size):
		''' Provide option's ask size/bid size '''

		if (field != 0 and field != 3) or size == 0:
			return
		
		# Determine the strike price and right
		strike = self.strikes[(req_id - 3)//2]
		right = 'C' if req_id & 1 else 'P'

		# Update the option chain
		if field == 0:
			self.chain[strike][right]['bid_size'] = size
		elif field == 3:
			self.chain[strike][right]['ask_size'] = size

def read_option_chain(client, ticker):
	print('get contract details')
	# Define a contract for the underlying stock
	contract = Contract()
	contract.symbol = ticker
	contract.secType = 'STK'
	contract.exchange = 'SMART'
	contract.currency = 'USD'
	client.reqContractDetails(0, contract)
	time.sleep(2)
	print(client.conid)

	# Get the current price of the stock
	print('get tick data')
	# client.reqTickByTickData(1, contract, "MidPoint", 1, True)
	client.reqRealTimeBars(1, contract, 5,'TRADES',0,[])
	time.sleep(30)
	# client.cancelTickByTickData(1)
	client.cancelRealTimeBars(1)
	print('current_price: ' + str(client.current_price) + '\n')
	# Request strike prices and expirations
	print('get strike prices')
	if client.conid:
		client.reqSecDefOptParams(2, ticker, '',
			'STK', client.conid)
		time.sleep(2)
	else:
		print('Failed to obtain contract identifier.')
		exit()

	# Create contract for stock option
	req_id = 3
	client.reqMarketDataType(1)
	if client.strikes:
		for strike in client.strikes:
			print('strike price:' + str(strike))
			client.chain[strike] = {}
			for right in ['C', 'P']:
				# Add to the option chain
				client.chain[strike][right] = {}
				# Define the option contract
				contract.secType = 'OPT'
				contract.right = right
				contract.strike = strike
				contract.exchange = 'SMART'
				contract.lastTradeDateOrContractMonth = client.expiration
				print(contract)
				# Request option data
				client.reqMktData(req_id, contract,
					'100', False, False, [])
				req_id += 1
	else:
		print('Failed to access strike prices')
		exit()
	print('b')
	time.sleep(5)

	# # Remove empty elements
	# for strike in client.chain:
	# 	if (client.chain[strike]['C'] == {}) or (client.chain[strike]['P'] == {}):
	# 		client.chain.pop(strike)
	return client.chain, client.atm_price


from datetime import datetime
import time
import traceback

def main():
	try:
		# Create the client and connect to TWS
		client = MarketReader('127.0.0.1', 7497, 0)

		# Request the current time
		# con = Contract()
		# con.symbol = 'AAPL'
		# con.secType = 'STK'
		# con.exchange = 'SMART'
		# con.currency = 'USD'

		# # Request ten ticks containing midpoint data
		# client.reqTickByTickData(0, con, 'MidPoint', 10, True)

		# Request market data
		# client.reqMktData(1, con, '', False, False, [])

		# # Request current bars
		# client.reqRealTimeBars(2, con, 5, 'MIDPOINT', True, [])

		# # Request historical bars
		# now = datetime.now().strftime("%Y%m%d, %H:%M:%S")
		# client.reqHistoricalData(3, con, now, '2 w', '1 day',
		# 	'MIDPOINT', False, 1, False, [])

		# # Request fundamental data
		# client.reqFundamentalData(4, con, 'ReportSnapshot', [])

		chains, atm_prices = read_option_chain(client, 'MSFT')
		print('chains')
		print(chains)
		print('\n\n')
		print('atm prices')
		print(atm_prices)
		time.sleep(5)
		client.disconnect()
	except Exception as e:
		print(e)

if __name__ == "__main__":
	main()