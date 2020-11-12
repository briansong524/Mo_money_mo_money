from utils import *
import time

def main():

	conn_cred = {
				    "dbservername":"localhost",
				    "dbname":"main_schema",
				    "dbuser":"minx",
				    "dbpassword":"!xobILE!!!111!"
				}
	symbols = ['AAPL','TSLA','AMZN','GOOGL']
	app = RealTimeTickApp()
	app.connect("127.0.0.1", 7497, 1)
	app.mysqlConfig(conn_cred)
	for i in range(len(symbols)):
		try:
			contract = basicContract(symbols[i])
			app.start_reqRealTimeBars(i+1,contract,5,'TRADES',0,[])
		except Exception as e:
			print('Error with ' + str(symbols[i]) + ': ' + str(e))
			app.reset()  # clear out any prior socket connections/issues
			app.connect("127.0.0.1", 7497, 1)
	app.run()

if __name__ == '__main__':
	main()

# from utils import *
# conn_cred = {
# 				    "dbservername":"localhost",
# 				    "dbname":"main_schema",
# 				    "dbuser":"minx",
# 				    "dbpassword":"!xobILE!!!111!"
# 				}
# symbols = ['AAPL','TSLA','AMZN','GOOGL']
# app = RealTimeTickApp()
# app.connect("127.0.0.1", 7497, 1)
# app.mysqlConfig(conn_cred)
# for i in range(len(symbols)):
# 	contract = basicContract(symbols[i])
# 	app.start_reqRealTimeBars(i+1,contract,5,'TRADES',0,[])

# app.reset()