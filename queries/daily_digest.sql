select coalesce(t.channel_key, 'unknown') as channel, count(*) as leads
from int_funnel__leads as l
left join int_funnel__touches as t on t.touch_evidence_key = l.first_touch_evidence_key
where l.submitted_date_local = @day
group by channel
order by leads desc, channel
