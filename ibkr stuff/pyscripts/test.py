from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.utils import iswrapper
from ibapi.contract import Contract
from ibapi.ticktype import TickTypeEnum
from threading import Thread
import queue
import json

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

	# @iswrapper
	# def realtimeBar(self, reqId, time:int, open_: float, high: float, 
	# 					low: float, close: float, volume: int, wap: float, 
	# 					count: int):
	# 	self.current_price = close
	# 	print('got realtime bar data')

	@iswrapper
	def historicalData(self, reqId, bar):
		''' Called in response to reqHistoricalData '''
		# print('historicalData - Close price: {}'
		# 	.format(bar.close))
		self.current_price = bar.close

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

	@iswrapper
	def tickPrice(self, req_id, field, price, attribs):
		''' Provide option's ask price/bid price '''

		if (field != 1 and field != 2) or price == -1.0:
			# print('price skipped')
			# print(field,price)
			return

		# Determine the strike price and right
		strike = self.strikes[(req_id - 3)//2]
		right = 'C' if req_id & 1 else 'P'

		# Update the option chain
		if field == 1:
			self.chain[strike][right]['bid_price'] = price
		elif field == 2:
			self.chain[strike][right]['ask_price'] = price
		# print(field,price)

	@iswrapper
	def tickSize(self, req_id, field, size):
		''' Provide option's ask size/bid size '''

		if (field != 0 and field != 3) or size == 0:
			# print('size skipped')
			# print(field,size)
			return

		# Determine the strike price and right
		strike = self.strikes[(req_id - 3)//2]
		right = 'C' if req_id & 1 else 'P'

		# Update the option chain
		if field == 0:
			self.chain[strike][right]['bid_size'] = size
		elif field == 3:
			self.chain[strike][right]['ask_size'] = size

	# @iswrapper
	# def tickOptionComputation(self, reqId, tickType,
	# 	impliedVol:float, delta:float, optPrice:float, pvDividend:float,
	# 	gamma:float, vega:float, theta:float, undPrice:float):

	# 	strike = self.strikes[((reqId - 100) - 3)//2]
	# 	right = 'C' if reqId & 1 else 'P' # odds are C, evens are P
	# 	self.chain[strike][right]['IV'] = impliedVol
	# 	self.chain[strike][right]['delta'] = delta
	# 	self.chain[strike][right]['gamma'] = gamma
	# 	self.chain[strike][right]['vega'] = vega
	# 	self.chain[strike][right]['theta'] = theta

def read_option_chain(client, ticker):
	print('get contract details')
	# Define a contract for the underlying stock
	contract = Contract()
	contract.symbol = ticker
	contract.secType = 'STK'
	contract.exchange = 'SMART'
	contract.currency = 'USD'
	client.reqContractDetails(0, contract)
	time.sleep(5)
	print(client.conid)

	# Get the current price of the stock
	print('get tick data')
	# client.reqTickByTickData(1, contract, "MidPoint", 1, True)
	# client.reqRealTimeBars(1, contract, 5,'TRADES',0,[])
	now = datetime.now().strftime("%Y%m%d, %H:%M:%S")
	client.reqHistoricalData(1, contract, now, '1 D', '1 day',
		'MIDPOINT', False, 1, False, [])
	time.sleep(2)
	# client.cancelTickByTickData(1)
	# client.cancelHistoricalData(1)
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
	# client.reqMarketDataType(1)
	if client.strikes:
		for strike in client.strikes:
			# print('strike price:' + str(strike))
			client.chain[strike] = {}
			for right in ['C', 'P']:
				# Add to the option chain
				client.chain[strike][right] = {}
				# Define the option contract
				contract.secType = 'OPT'
				contract.right = right
				contract.strike = strike
				contract.exchange = client.exchange
				contract.lastTradeDateOrContractMonth = client.expiration
				# print(contract)
				# Request option data
				# refer to https://interactivebrokers.github.io/tws-api/tick_types.html for generic tick types
				client.reqMktData(req_id, contract,
					'100', False, False, [])
				# iv_req_id = 100 + req_id
				# client.calculateImpliedVolatility(iv_req_id, contract, 
					# strike, client.current_price, [])
				req_id += 1
	else:
		print('Failed to access strike prices')
		exit()
	return client.chain, client.atm_price


from datetime import datetime
import time
import traceback
import sys

def main():
	try:
		# Create the client and connect to TWS
		client = MarketReader('127.0.0.1', 7497, 0)
		# client.disconnect(); return
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

		# Request historical bars
		# now = datetime.now().strftime("%Y%m%d, %H:%M:%S")
		# client.reqHistoricalData(3, con, now, '1 D', '1 day',
		# 	'MIDPOINT', False, 1, False, [])

		# # Request fundamental data
		# client.reqFundamentalData(4, con, 'ReportSnapshot', [])

		chains, atm_prices = read_option_chain(client, 'AAPL')
		# # Remove empty elements
		# for strike in chains:
		# 	if (chains[strike]['C'] == {}) or (chains[strike]['P'] == {}):
		# 		del chains[strike]
		print('chains')
		printable_chain = json.dumps(chains, indent=2)
		print(printable_chain)
		print('\n\n')
		print('atm prices')
		print(atm_prices)
		time.sleep(2)
		client.disconnect()
	except Exception as e:
		type_, value_, traceback_ = sys.exc_info()
		tb = traceback.format_exception(type_, value_, traceback_)
		tb = '\n' + ' '.join(tb)
		print(tb)

if __name__ == "__main__":
	main()