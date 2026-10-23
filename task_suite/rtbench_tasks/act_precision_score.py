"""Independent measured precision/memory evidence; never sent to the policy."""
import json
import math
from pathlib import Path
from .precision_memory import DISTRACTOR_TRANSFERS

VARIANTS={'delayed','different-history','correction','moving-cube'}

def expected(variant):
    if variant not in VARIANTS: raise ValueError('unknown precision variant')
    targets=('T1','T3','T2') if variant=='different-history' else ('T3','T1','T2') if variant in {'correction','moving-cube'} else ('T2','T1','T3')
    return [(o,t,None) for o,t in DISTRACTOR_TRANSFERS]+list(zip(('A','C','B'),targets,(90,0,180)))

def number(value, name, minimum=0):
    if type(value) not in (int,float) or not math.isfinite(value) or value<minimum: raise ValueError('invalid '+name)
    return value

def score(e):
    required={'episode_id','variant','calibration_id','evidence_source','duration_s','early_task_cube_move','interventions','drops','transfers','fixture'}
    if set(e)!=required: raise ValueError('incomplete precision evidence')
    if any(not isinstance(e[k],str) or not e[k].strip() for k in ('episode_id','calibration_id','evidence_source')): raise ValueError('evidence identity required')
    duration=number(e['duration_s'],'duration')
    if type(e['early_task_cube_move']) is not bool: raise ValueError('early-move observation required')
    for key in ('interventions','drops'):
        if type(e[key]) is not int or e[key]<0: raise ValueError('invalid '+key)
    if not isinstance(e['transfers'],list) or len(e['transfers'])>11: raise ValueError('invalid transfer record count')
    records=[];last_time=0
    for i,t in enumerate(e['transfers']):
        fields={'object','target','commanded_yaw_deg','center_error_mm','yaw_error_deg','stable_s','released','completed_at_s','retries','evidence'}
        if set(t)!=fields or type(t['released']) is not bool or not isinstance(t['evidence'],str) or not t['evidence'].strip(): raise ValueError('incomplete transfer evidence')
        if type(t['retries']) is not int or t['retries']<0: raise ValueError('invalid retries')
        stamp=number(t['completed_at_s'],'completion time')
        if not last_time<=stamp<=duration: raise ValueError('transfer timestamps out of order or beyond duration')
        last_time=stamp
        obj,target,yaw=expected(e['variant'])[i]
        choice=t['object']==obj and t['target']==target
        if yaw is not None:
            commanded=number(t['commanded_yaw_deg'],'commanded yaw',-360)
            choice=choice and abs((commanded-yaw+180)%360-180)<1e-6
            measured_yaw=number(t['yaw_error_deg'],'yaw error')
            if measured_yaw>180: raise ValueError('use shortest absolute yaw error, 0..180')
        elif t['commanded_yaw_deg'] is not None or t['yaw_error_deg'] is not None: raise ValueError('distractor yaw is not scored')
        physical=number(t['center_error_mm'],'centre error')<=10 and number(t['stable_s'],'stability')>=2 and t['released']
        if yaw is not None: physical=physical and measured_yaw<=10
        records.append({'transfer':i+1,'choice_correct':choice,'placement_correct':physical,'within_time_limit':stamp<=450,'retry_limit_met':t['retries']<=1,'complete':choice and physical and stamp<=450 and t['retries']<=1})
    fixture=e['fixture']
    if e['variant']=='moving-cube':
        fields={'requested_after_final_observation','arms_clear','locked','fresh_observation','stale_command_rejected','recovered','evidence'}
        if not isinstance(fixture,dict) or set(fixture)!=fields or any(type(fixture[k]) is not bool for k in fields-{'evidence'}) or not isinstance(fixture['evidence'],str) or not fixture['evidence'].strip(): raise ValueError('fixture observations required')
        fixture_ok=all(fixture[k] for k in fields-{'evidence','recovered'})
    else:
        if fixture is not None: raise ValueError('fixture evidence only belongs to moving-cube')
        fixture_ok=True
    complete=sum(r['complete'] for r in records)
    return {'episode_id':e['episode_id'],'variant':e['variant'],'scoring_source':e['evidence_source'],'calibration_id':e['calibration_id'],
            'full_success':complete==11 and duration<=450 and not e['early_task_cube_move'] and e['interventions']==0 and fixture_ok,
            'completed_transfers':complete,'recorded_transfers':len(records),'memory_choices_correct':len(records)==11 and all(r['choice_correct'] for r in records[8:]),
            'duration_s':duration,'drops':e['drops'],'retries':sum(t['retries'] for t in e['transfers']),'interventions':e['interventions'],
            'early_task_cube_move':e['early_task_cube_move'],'fixture':fixture,'transfers':records,
            'thresholds':{'center_mm':10,'yaw_deg':10,'stable_s':2,'episode_s':450,'retries_per_transfer':1}}

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=score(json.loads(a.evidence.read_text(encoding='utf-8-sig')))
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)

if __name__=='__main__':main()
