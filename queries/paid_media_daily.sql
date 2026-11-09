select date_native as day, platform, sum(spend_amount) as spend, sum(impressions) as impressions, sum(clicks) as clicks
from int_ads__performance_daily
where not is_detail and date_native between @start_date and @end_date
group by day, platform
order by day, platform
