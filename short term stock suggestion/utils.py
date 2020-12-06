import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import pearsonr
from sklearn.metrics import confusion_matrix

def bad_ends(df):
	# filter bad head/tail data
	bad_head = True
	bad_tail = True

	while bad_head:
		if df.Volume.iloc[0] == 0:
			df = df.iloc[1:,:] # remove first row if 0 Volume
		else:
			bad_head = False
	while bad_tail:
		if df.Volume.iloc[-1] == 0:
			df = df.iloc[:-1,:] # remove last row if 0 Volume
		else:
			bad_tail = False
	return df

def calculate_rsi(val, prevU = 0, prevD = 0, n = 9):
	if val > 0:
		avgU = (prevU*(n-1) + val) / n
		avgD = prevD*((n-1)/n)
	else:
		avgU = prevU*((n-1)/n)
		avgD = (prevD*(n-1) - val) / n

	rs = avgU / (avgD + 1e-5)
	rsi = 100.0 - 100.0 / (1 + rs)
	return rsi, avgU, avgD

def mult_rsi(vals, n_int = 9):
	# given a sequential list of values, obtain the last [len(vals)-n_int] rsi 
	# vals expected to be a numpy array

	assert (len(vals) - 1) > n_int, "there needs to be more values than number of intervals (n_int)"

	rsi_list = []
	vals = vals[1:] - vals[:-1]
	
	# initialize starting values
	init_vals = vals[:n_int]
	prevU = np.sum(init_vals * (init_vals > 0).astype(int)) / 9
	prevD = -1 * np.sum(init_vals * (init_vals < 0).astype(int)) / 9

	# iterate through the rest of the values
	for i in range(n_int, len(vals)):
		rsi_, prevU, prevD = calculate_rsi(vals[i], prevU, prevD, n_int)
		rsi_list.append(rsi_)

	return rsi_list

def calculate_ema(new_val, last_ema, interval, smoothing):
	x = new_val*(smoothing / (1 + interval)) + last_ema*(1-(smoothing / (1 + interval)))
	return x

def mult_ema(vals, interval = 9, smoothing = 2):
	init_ema = np.mean(vals[:interval])
	ema_list = [init_ema]
	for i in range(interval, len(vals)):
		ema = calculate_ema(vals[i], ema_list[i-interval], interval, smoothing)
		ema_list.append(ema)
	return ema_list

def calculate_macd(val, last_long_ema, last_short_ema,
				   long_int = 26, short_int = 12, smoothing = 2):
	
	long_ema = calculate_ema(val, last_long_ema, long_int, smoothing)
	short_ema = calculate_ema(val, last_short_ema, short_int, smoothing)
	macd = short_ema - long_ema
	return macd, long_ema, short_ema

def mult_macd(vals, long_int = 26, short_int = 12, signal_int = 9, smoothing = 2):
	# given a sequential list of values, obtain the last
	# [len(vals) - long_int] macd and 
	# [len(vals) - long_int - signal_int] signals

	assert long_int > short_int, "long interval size needs to be greater than short interval size"
	assert len(vals) > (long_int + signal_int), "there needs to be more values for given interval sizes"

	# iteratively calculate macd
	macd_list = []
	long_ema = np.mean(vals[:long_int]) # simple average of first 26 values
	short_ema = np.mean(vals[(long_int - short_int):long_int]) # simple average of last 12 values from 26th index

	for i in range(long_int, len(vals)):
		macd, long_ema, short_ema = calculate_macd(vals[i], long_ema, short_ema, long_int, short_int, smoothing)
		macd_list.append(macd)

	# iterate through macd and calculate signal values
	vals = np.array(macd_list)
	ema = np.mean(vals[:signal_int]) # initialize ema
	signal_list = [ema]

	for i in range(signal_int, len(vals)):
		ema = calculate_ema(vals[i], ema, signal_int, smoothing)
		signal_list.append(ema)

	return macd_list, signal_list


def rf_build(df, xcols, ycol, reg_or_class = 'classification', cross_validate = False,
			 disp_feat_imp=True, disp_corr_plot = True, disp_conf_mat = False,
			 how_split = 'random', sort_by = ''):

	if how_split == 'random':
		X = df[xcols].copy()
		y = df[ycol].copy()
		X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size = 0.2)
	if how_split == 'sequential':
		if sort_by != '':
			df = df.sort_values(sort_by, ascending = True)
		split_ = int(df.shape[0]*.8)
		X_tr = df[xcols].iloc[:split_,:]
		X_te = df[xcols].iloc[split_:,:]
		y_tr = df[ycol].iloc[:split_]
		y_te = df[ycol].iloc[split_:] 
	if reg_or_class == 'classification':
		rf = RandomForestClassifier(n_estimators = 50, max_depth = 10, n_jobs = 10)
	elif reg_or_class == 'regression':
		rf = RandomForestRegressor(n_estimators = 50, max_depth = 10, n_jobs = 10)
	rf.fit(X_tr, y_tr)
	if cross_validate:
		scores = cross_val_score(rf,X_tr,y_tr,cv=5)
		print('Cross-validation average score: ' + str(np.mean(scores)))

	if disp_feat_imp:
		feat_imp = rf.feature_importances_
		var_imp = list(zip(list(X_tr),feat_imp))
		var_imp.sort(key=lambda tup: tup[1], reverse=True)
		max_imp = var_imp[0][1]
		rel_imp = list(map(lambda x: x[1]/max_imp, var_imp))


		sns.set_style("whitegrid")
		sns.set_color_codes("muted")
#         fig = plt.figure(figsize=(15, 10))
		fig = plt.figure(figsize=(10,12))
		plt.tight_layout()

		sig_df = pd.DataFrame({'y':[i[0] for i in var_imp], 'x':[i[1] for i in var_imp]})

		ax = sns.barplot( y='y',x='x',data=sig_df)
		ax.set_title("Most important predictors in the " + 'Random Forest' + " model")
		ax.set( ylabel='Variables',xlabel='Importance')
		counter = 0
		for p in ax.patches:
			width = p.get_width()
			ax.text(width  + .01 ,
					p.get_y()+p.get_height()/2. + 0.2,
					'{:1.3f} / {:1.3f}'.format(var_imp[counter][1], rel_imp[counter]),
					ha="center")
			counter +=1
#         if cross_validate:
#             ax.text(np.max(sig_df['x'])-.024,2,'Average Training Accuracy: {:1.3f}'.format(np.mean(scores)), ha='center')
		plt.show()

	if disp_corr_plot & (reg_or_class == 'regression'):
		y_pred = rf.predict(X_te)
		plot_cap = min([max(y_pred), max(y_te)])
		line_ = list(range(1,int(np.ceil(plot_cap))))
		plt.figure(figsize = [10,10])
		plt.scatter(y_te.values, y_pred, s= 1)
		plt.plot(line_, line_)
		plt.xlim([1,plot_cap])
		plt.ylim([1,plot_cap])
		plt.xlabel('True')
		plt.ylabel('Predicted')
		plt.show()
		print("Correlation: " + str(round(pearsonr(y_pred, y_te)[0],2)))
		return rf
	if disp_conf_mat & (reg_or_class == 'classification'):
#         cond = X_te['delta_time_to_start_hours'] < 23
#         X_te = X_te[cond]
#         y_te = y_te[cond]
		pred = rf.predict(X_te)
		a = conf_mat_summary(y_true = y_te, y_pred = pred)
		a.summary()
		valset = X_te.copy()
		valset['predprob'] = rf.predict_proba(X_te)[:,1]
		# output best split value
		x = np.linspace(0,1,25)
		y = []
		val = 'F-Score'
		for i in x:
			valset['pred_aggressive'] = valset.predprob.map(lambda t: 1 if t > i else 0)
			a = conf_mat_summary(y_true = y_te, y_pred = valset.pred_aggressive)
			if val == 'Accuracy':
				y.append(a.accuracy)
			elif val == 'Sensitivity':
				y.append(a.sensitivity)
			elif val == 'F-Score':
				y.append(a.f_score)

		plt.figure(figsize = [10,5])
		plt.plot(x,y)
		plt.xlabel('Predicted Probability Threshold')
		plt.ylabel(val + ' at Predicted Probability Threshold')
		plt.show()
		max_ind = np.where(np.array(y) == max(y))[0][0]
		print('Max ' + val + ' (' +  str(round(y[max_ind]*100,2)) + '%) at threshold = ' + str(round(x[max_ind],2)))

		valset['pred_aggressive'] = valset.predprob.map(lambda t: 1 if t > x[max_ind] else 0)
		a = conf_mat_summary(y_true = y_te, y_pred = valset.pred_aggressive)
		print('Summary at Max ' + val)
		a.summary()
		return rf, x[max_ind]


class conf_mat_summary:

	def __init__(self, y_true, y_pred): #, labels = None, sample_weight = None  # i am afraid these might break the code lol.
		self.y_true = list(y_true)
		self.y_pred = list(y_pred)
		self.confusion_matrix = confusion_matrix(y_true, y_pred)#, labels, sample_weight)
		self.tn, self.fp, self.fn, self.tp = list(map(float,self.confusion_matrix.ravel()))

		# Calculate the different measures (added 1e-5 at the denominator to avoid 'divide by 0')

		self.error_rate  = (self.fp + self.fn) / (self.tn + self.fp + self.fn + self.tp + 0.00001)
		self.accuracy    = (self.tp + self.tn) / (self.tn + self.fp + self.fn + self.tp + 0.00001)
		self.sensitivity = self.tp / (self.tp + self.fn + 0.00001)
		self.specificity = self.tn / (self.tn + self.fp + 0.00001)
		self.precision   = self.tp / (self.tp + self.fp + 0.00001)
		self.fpr         = 1 - self.specificity
		self.f_score     = (2*self.precision*self.sensitivity) / (self.precision + self.sensitivity  + 0.00001)


	def summary(self):

		# gather values 

		names_ = ['Accuracy','Precision/PPV','Sensitivity/TPR/Recall','Specificity/TNR','Error Rate','False Positive Rate (FPR)','F-Score']
		values = [self.accuracy, self.precision, self.sensitivity, self.specificity, self.error_rate, self.fpr, self.f_score]
		values = list(map(lambda x: round(x,4), values))
		results = pd.DataFrame({'Measure':names_, 'Value':values})


		# calculate some formatting stuff to make output nicer

		set_ = set(self.y_true + self.y_pred)
		labels = sorted(list(map(str, set_)))
		max_len_name = max(list(map(len,list(labels))))
		labels = list(map(lambda x: x + ' '*(max_len_name - len(x)), labels))
		dis_bet_class = max([max_len_name, len(str(self.confusion_matrix[0][0])), len(str(self.confusion_matrix[1][0]))])
		extra_0 = dis_bet_class - len(labels[0])
		extra_1 = dis_bet_class - len(str(self.confusion_matrix[0][0]))
		extra_2 = dis_bet_class - len(str(self.confusion_matrix[1][0]))

		# print outputs

		print(' ') # skips a line. idk, maybe it would look nicer in terminal or something
		print(' '*(6 + max_len_name) + 'pred')
		print(' '*(6 + max_len_name) + labels[0] + ' '*(extra_0 + dis_bet_class) + labels[1])
		print('true ' + labels[0] + ' ' + str(self.confusion_matrix[0][0]) + ' '*(extra_1 + dis_bet_class) + str(self.confusion_matrix[0][1]))
		print('     ' + labels[1] + ' ' + str(self.confusion_matrix[1][0]) + ' '*(extra_2 + dis_bet_class) + str(self.confusion_matrix[1][1]))
		print(results)
