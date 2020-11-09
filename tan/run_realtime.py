from utils import *
import time

def main():
	symbols = ['AAPL','TSLA','AMZN','GOOGL']
	for i in range(len(symbols)):
		try:
			contract = basicContract(symbols[i])
			app = RealTimeTickApp()
			app.connect("127.0.0.1", 7497, 1)
			app.start_reqRealTimeBars((i+1),contract,5,'TRADES',0,[])
		except Exception as e:
			print('Error with ' + str(symbols[i]) + ': ' + str(e))
	curr = time.time()
	while 1 == 1: # until close
		if time.time() - curr  > 5:
			print('5 seconds passed')
			curr = time.time()
			print(app.ticker_dict)

if __name__ == '__main__':
	main()