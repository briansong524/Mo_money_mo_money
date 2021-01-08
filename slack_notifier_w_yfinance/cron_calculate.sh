#!/bin/bash

/home/minx/venv/py3/bin/python /home/minx/Documents/GitHub/Mo_money_mo_money/slack_notifier_w_yfinance/calculate_technical_indicators.py --rsi_bars 9 --period 1d --interval 1m
/home/minx/venv/py3/bin/python /home/minx/Documents/GitHub/Mo_money_mo_money/slack_notifier_w_yfinance/calculate_technical_indicators.py --rsi_bars 12 --period 5d --interval 5m
/home/minx/venv/py3/bin/python /home/minx/Documents/GitHub/Mo_money_mo_money/slack_notifier_w_yfinance/calculate_technical_indicators.py --rsi_bars 14 --period 1mo --interval 15m

