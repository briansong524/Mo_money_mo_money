with amzn as (
	select * from main_schema.bar_data where symbol = 'AMZN' order by epoch desc limit 9
),
aapl as (
	select * from main_schema.bar_data where symbol = 'AAPL' order by epoch desc limit 9
),
tsla as (
	select * from main_schema.bar_data where symbol = 'TSLA' order by epoch desc limit 9
),
googl as (
	select * from main_schema.bar_data where symbol = 'GOOGL' order by epoch desc limit 9
)

SELECT * FROM amzn
UNION 
SELECT * FROM aapl
UNION
SELECT * FROM tsla
UNION
SELECT * FROM googl
;

