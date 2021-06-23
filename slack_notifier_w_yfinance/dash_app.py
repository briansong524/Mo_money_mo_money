''' Dash Frontend For Control 

Have a frontend to configure config.json without the need to login to the 
aws/gcp instance

'''

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import plotly.express as px

import yfinance as yf
from pytz import timezone
import numpy as np
from datetime import datetime, timedelta

from sklearn.linear_model import LinearRegression


from utils import midpoint_imputation, simple_lr, calculate_rsi


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
colors = {
    'background': '#000000',
    'text': '#7FDBFF'
}


## Page Layout
app.layout = html.Div(style={'backgroundColor': colors['background']}, children=[
    html.H1(
        children='RSI Notifier Visualizer',
        style={
            'textAlign': 'center',
            'color': colors['text']
        }
    ),
    html.Div(children=[
        html.Label("Symbol: ",
            style={
                'color':colors['text']        
            }),
        dcc.Input(id='symbol', value='SPY', type='text')
    ]),
    html.Div(children=[
        html.Label("Graph Style ('Line' or 'Bar'): ",
            style={
                'color':colors['text']        
            }),
        dcc.Input(id='graph-style', value='Line', type='text')
    ]),
    html.Div(children=[
        html.Label("New Bar Size (minutes) [1,2,5,15,30]: ",
            style={
                'color':colors['text']        
            }),
        dcc.Input(id='bar-size', value='15', type='text')
    ]),

    html.Button(id='submit-button-state', n_clicks=0, children='Submit'),

    # html.Div(id='output-state', style={
    #             'color':colors['text']        
    #         })
    dcc.Graph(id='output-state')
])

@app.callback(
    Output('output-state','figure'),
    Input('submit-button-state','n_clicks'), #n_clicks needed to update
    State('symbol','value'),
    State('graph-style','value'),
    State('bar-size','value')
    )
def update_config(button, symbol, graph_style, bar_size):
    ticker = str(symbol)
    period = '1mo'
    interval = str(bar_size) + 'm'
    data = yf.download(tickers = ticker, period = period, interval = interval, 
                        group_by = 'ticker', prepost = True).reset_index()
    print(ticker,graph_style,period,interval,' seems to work')
    data['Upper'] = data[['Open','Close']].max(axis = 1)
    data['Lower'] = data[['Open','Close']].min(axis = 1)
    data['Midpoint'] = data[['Open','Close']].mean(axis = 1)
    vals = data['Datetime']
    v1 = vals.iloc[1:]
    v2 = vals.iloc[:-1]
    vals = list(map(lambda i: (v1.iloc[i]-v2.iloc[i]).total_seconds() / 60. / 60., range(len(v1))))
    vals = [0] + vals
    data['New Day'] = list(map(lambda x: x > 0.25, vals))
    data['pos'] = data['Datetime'].map(lambda x: (x - data['Datetime'].iloc[0]).total_seconds() / 60 / 60) # for linear regression
    x = data['pos']
    lr1, m, b = simple_lr(np.array(x).reshape(-1, 1), data['Midpoint'])
    pred = lr1.predict(np.array(x).reshape(-1,1)) 
    data['prop_dist_1'] = (pred - data['Midpoint']).abs() / pred
    cutoff = np.percentile(data['prop_dist_1'], 65)
    cutoff2 = np.percentile(data['prop_dist_1'], 50)
    df = data[data['prop_dist_1'] < cutoff].copy()
    x = np.array(df['pos']).reshape(-1,1)
    lr2, m, b = simple_lr(x, df['Midpoint'])
    pred = lr2.predict(np.array(x).reshape(-1,1))
    df['prop_dist_2'] = (pred - df['Midpoint']).abs() / df['Midpoint']

    df2 = df[df['prop_dist_2'] < cutoff2].copy()
    x = np.array(df2['pos']).reshape(-1,1)
    lr3, m3, b3 = simple_lr(x, df2['Midpoint'])
    pred = lr3.predict(data['pos'].values.reshape(-1,1))
    data['epsilon'] = data['Midpoint'] - pred
    # fig = px.scatter(x=data['pos'].values, y=pred)
    # fig.update_layout(margin={'l': 40, 'b': 40, 't': 10, 'r': 0}, hovermode='closest')

# ##plot bar chart
# import plotly.graph_objects as go

# fig = go.Figure(data=[go.Candlestick(x=data['Datetime'],
#                 open=data['Open'],
#                 high=data['High'],
#                 low=data['Low'],
#                 close=data['Close'])])
# y_trace = lr3.predict(data['pos'].values.reshape(-1,1))
# fig.add_trace(go.Scatter(x=data['Datetime'], y=y_trace,
#                     mode='lines',
#                     name='lines'))
# fig.show()

    rsi_list = []
    n = 14
    rows = data['Close'].values
    rows = midpoint_imputation(rows)
    # print(rows[-5:])
    rows = rows[1:] - rows[:-1] # make prices to deltas

    # initial calculation
    vals = rows[:n]
    prevU = np.sum(vals * (vals > 0).astype(int)) / n
    prevD = -1 * np.sum(vals * (vals < 0).astype(int)) / n

    for i in range(n, len(rows)):
        rsi, prevU, prevD = calculate_rsi(rows[i], prevU, prevD, n)
        rsi_list.append(rsi)

    # modify shape to match indices with original data
    rsi_list_modified = [np.nan] * (data.shape[0] - len(rsi_list)) + rsi_list
    rsi = np.array(rsi_list_modified)
    fig = px.scatter(x = range(len(rsi)), y = rsi)
    return fig




if __name__ == '__main__':
    app.run_server(debug=True)
