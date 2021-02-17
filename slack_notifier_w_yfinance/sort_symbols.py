'''
Alphabetize symbols file 

Just a QoL script that alphabetizes a list of symbols
'''

import argparse


parser = argparse.ArgumentParser()

parser.add_argument(
	'--symbols', type=str, default='symbols.txt',
	help = 'Directory of text file containing all symbols separated by new line')


def main(symbols):
	with open(symbols,'r') as in_:
		lines = in_.readlines()

	lines = list(map(lambda x: x.replace('\n',''),lines))
	lines = sorted(lines)
	lines = '\n'.join(lines)
	with open(symbols,'w') as out_:
		out_.writelines(lines)
	print('finished')

if __name__ == '__main__':

	FLAGS, unparsed = parser.parse_known_args()	
	main(FLAGS.symbols)