from utils import *
import time
import argparse


parser = argparse.ArgumentParser()


parser.add_argument(
	'--debug', type=bool, default=False,
	help = 'Config file for all configuration info')


def main():
	try:
		conn_cred = {
					    "dbservername":"localhost",
					    "dbname":"main_schema",
					    "dbuser":"minx",
					    "dbpassword":"!xobILE!!!111!"
					}
		symbols = ['AAPL','TSLA','AMZN','GOOGL']
		app = RealTimeTickApp()
		app.connect("127.0.0.1", 7497, 1)
		if not debug:
			app.mysqlConfig(conn_cred)
		for i in range(len(symbols)):
			# try:
			contract = basicContract(symbols[i])
			app.start_reqRealTimeBars(i+1,contract,10,'TRADES',0,[]) # 1 for rth, 0 for extended
			# except Exception as e:
			# 	print('Error with ' + str(symbols[i]) + ': ' + str(e))
			# 	app.reset()  # clear out any prior socket connections/issues
			# 	app.connect("127.0.0.1", 7497, 1)
		app.run()
	except KeyboardInterrupt:
		print('closing connections and ending script')
		app.conn.disconnect()
	except Exception as e:
		print('error in run_realtime: ' + str(e))

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