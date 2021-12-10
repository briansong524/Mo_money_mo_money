with `cte1` as (select `id` AS `id`,
    `symbol` AS `symbol`,
    `epoch_gmt` AS `epoch_gmt`,
    `datetime_pst` AS `datetime_pst`,
    `open` AS `open`,`high` AS `high`,
    `low` AS `low`,`close` AS `close`,
    `volume` AS `volume`,
    `rounded_epoch` AS `rounded_epoch`,
    from_unixtime((`rounded_epoch` * 900)) AS `datetime_rounded` 
    from (
        select `id` AS `id`,
        `symbol` AS `symbol`,
        `epoch_gmt` AS `epoch_gmt`,
        `datetime_pst` AS `datetime_pst`,
        `open` AS `open`,
        `high` AS `high`,
        `low` AS `low`,
        `close` AS `close`,
        `volume` AS `volume`,
        (`epoch_gmt` DIV 900) AS `rounded_epoch` 
        from `bar_5sec`) `a`), 

`cte2` as (select `id` AS `id`,
    `symbol` AS `symbol`,
    `epoch_gmt` AS `epoch_gmt`,
    `datetime_pst` AS `datetime_pst`,
    `open` AS `open`,
    `high` AS `high`,
    `low` AS `low`,
    `close` AS `close`,
    `volume` AS `volume`,
    `rounded_epoch` AS `rounded_epoch`,
    `datetime_rounded` AS `datetime_rounded`,
    first_value(`open`) 
        OVER (PARTITION BY `symbol`,
        `datetime_rounded` 
        ORDER BY `epoch_gmt` )  AS `rounded_open`,
    first_value(`close`) 
        OVER (PARTITION BY `symbol`,
        `datetime_rounded` ORDER BY `epoch_gmt` desc )  AS `rounded_close` 
    from `cte1`
    ) 

select `cte2`.`symbol` AS `symbol`,
`cte2`.`datetime_rounded` AS `datetime_rounded`,
min(`cte2`.`rounded_open`) AS `open`,
min(`cte2`.`rounded_close`) AS `close`,
max(`cte2`.`high`) AS `high`,
min(`cte2`.`low`) AS `low`,
sum(`cte2`.`volume`) AS `volume`
 from `cte2` 
 group by `cte2`.`symbol`,`cte2`.`datetime_rounded`;
