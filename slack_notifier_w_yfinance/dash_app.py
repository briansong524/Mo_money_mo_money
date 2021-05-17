''' Dash Frontend For Control 

Have a frontend to configure config.json without the need to login to the 
aws/gcp instance

'''

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State

app = dash.Dash()
colors = {
    'background': '#000000',
    'text': '#7FDBFF'
}

test = {
        'symbols':['AAPL','TSLA'],
        'bar_size':'15'
        }
app.layout = html.Div(style={'backgroundColor': colors['background']}, children=[
    html.H1(
        children='RSI Notifier Configuration',
        style={
            'textAlign': 'center',
            'color': colors['text']
        }
    ),
    html.Div(children=[
        html.Label("Add Symbols (separate multiple with commas): ",
            style={
                'color':colors['text']        
            }),
        dcc.Input(id='add-symbol', value='', type='text')
    ]),
    html.Div(children=[
        html.Label("Remove Symbols (separate multiple with commas): ",
            style={
                'color':colors['text']        
            }),
        dcc.Input(id='remove-symbol', value='', type='text')
    ]),
    html.Div(children=[
        html.Label("New Bar Size (minutes) [1,2,5,15,30]: ",
            style={
                'color':colors['text']        
            }),
        dcc.Input(id='bar-size', value='', type='text')
    ]),

    html.Button(id='submit-button-state', n_clicks=0, children='Submit'),

    html.Div(id='output-state')
])

@app.callback(
    Output('output-state','children'),
    Input('submit-button-state','children'),
    State('add-symbol','children'),
    State('remove-symbol','children'),
    State('bar-size','children')
    )
def update_config(button, add_symbols, remove_symbols, bar_size):
    print_output = ''

    if add_symbols != '':
        #maybe add space remover
        symbols = add_symbols.split(',')
        temp = test['symbols']
        temp.extend(symbols)
        test['symbols'] = temp
        print_output += 'added ' + add_symbols + ' to list\n'
    if remove_symbols != '':
        symbols = remove_symbols.split(',')
        temp = test['symbols']
        for symbol in symbols:
            try:
                temp.remove(symbol)
            except:
                pass
        print_output += 'removed ' + remove_symbols + ' from list\n'
    if bar_size != '':
        try:
            old_bar_size = test['bar_size']
            bar_size = int(bar_size)
            test['bar_size'] = bar_size
        except Exception as e:
            print('bar_size input incorrect: ' + str(e))
        print_output += ' changed bar size from ' + str(old_bar_size) \
                        + ' to ' + str(bar_size)
    return print_output

if __name__ == '__main__':
    app.run_server(debug=True)
