def record(agent,previous,new,round_no,existing):
    delta=new-previous; span=agent.range_span()
    cumulative=sum(abs(x.delta) for x in existing if x.agent_id==agent.id)+abs(delta)
    return {'agent_id':agent.id,'round':round_no,'previous_value':previous,'new_value':new,'delta':round(delta,2),'pct_of_range':round(abs(delta)/span*100,2),'cumulative_pct':round(cumulative/span*100,2)}
