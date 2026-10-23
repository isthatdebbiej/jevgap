"""Operator rubric: independent cumulative progress and interval quality.

All SDK choices carry zero weight: its aggregate is not either study metric.
The validated export below is the authoritative calculation, including gates.
"""
import json
from pathlib import Path

GRADES = ('Failure: no valid progress, wrong target/sequence or unrecovered error.',
          'Partial: purposeful progress, incomplete/unstable or completed after retry/correction.',
          'Success: clean stable completion without avoidable retry, recovery or error.')


def validate(r):
    if set(r) != {'version','source','variant','comparable_to_robodojo','milestones','intervals'}:
        raise ValueError('invalid rubric fields')
    if r['version'] != 'se3-interval-v1' or type(r['comparable_to_robodojo']) is not bool:
        raise ValueError('invalid rubric version/comparability')
    levels=[x['points'] for x in r['milestones']]
    if len(levels)<2 or levels[0]!=0 or levels[-1]!=100 or any(type(x) is not int for x in levels) or levels!=sorted(set(levels)):
        raise ValueError('milestones must increase from 0 to 100')
    if any(set(x)!={'points','criterion'} or not x['criterion'].strip() for x in r['milestones']):
        raise ValueError('invalid milestone criterion')
    if len(r['intervals']) != len(levels)-1:
        raise ValueError('one interval per adjacent milestone pair required')
    for i,item in enumerate(r['intervals']):
        if set(item)!={'phases'} or len(item['phases'])!=3 or any(not isinstance(p,str) or not p.strip() for p in item['phases']):
            raise ValueError('each interval requires three task-specific phase questions')
    return r


def sheet(task):
    from se3labs.interface.eval.task import Task_ScoreSheet, Task_ScoreItem, Task_ScoreKind, Task_ScoreChoice
    r=validate(task['rubric'])
    choices=tuple(Task_ScoreChoice(0,f"{m['points']}: {m['criterion']}") for m in r['milestones'])
    items=[Task_ScoreItem('general_progress','Furthest cumulative milestone reached during the rollout (review trajectory).',Task_ScoreKind.Choice,choices)]
    for i,interval in enumerate(r['intervals']):
        lo,hi=(r['milestones'][j]['points'] for j in (i,i+1))
        for j,question in enumerate(interval['phases']):
            items.append(Task_ScoreItem(f'q_{i}_{j}',f'{lo}->{hi}, phase {j+1}: {question} If milestone {lo} was never reached, select Failure. Grade the whole phase, including retries.',Task_ScoreKind.Choice,tuple(Task_ScoreChoice(0,g) for g in GRADES)))
    return Task_ScoreSheet(Task_ScoreItem('task_success',task['success_question']+' Judge final state independently of the furthest milestone.',Task_ScoreKind.Binary,weight=0),tuple(items))


def calculate(task, answers):
    r=validate(task['rubric'])
    keys={'task_success','general_progress'}|{f'q_{i}_{j}' for i in range(len(r['intervals'])) for j in range(3)}
    if set(answers)!=keys or type(answers['task_success']) is not bool:
        raise ValueError('missing, extra or invalid scoring answers')
    gp=answers['general_progress']
    if type(gp) is not int or not 0<=gp<len(r['milestones']): raise ValueError('invalid milestone choice')
    progress=r['milestones'][gp]['points']
    if answers['task_success'] and progress!=100: raise ValueError('success requires full progress')
    intervals=[]
    for i,interval in enumerate(r['intervals']):
        low,high=(r['milestones'][j]['points'] for j in (i,i+1))
        points=[]
        for j,weight in enumerate((.3,.3,.4)):
            grade=answers[f'q_{i}_{j}']
            if type(grade) is not int or grade not in (0,1,2): raise ValueError('invalid phase choice')
            if progress<low and grade!=0: raise ValueError('ineligible interval has nonzero grade')
            points.append(round((high-low)*weight*grade/2,6))
        intervals.append({'lower':low,'upper':high,'eligible':progress>=low,'phase_points':points,'points':round(sum(points),6)})
        if all(answers[f'q_{i}_{j}']==2 for j in range(3)) and progress<high:
            raise ValueError('all phases successful but interval milestone not reached')
    quality=round(sum(x['points'] for x in intervals),6)
    return {'task':task['name'],'rubric_version':r['version'],'variant':r['variant'],
            'comparable_to_robodojo':r['comparable_to_robodojo'],'task_success':answers['task_success'],
            'general_progress':progress,'breakdown_quality':quality,'breakdown_quality_fraction':quality/100,
            'intervals':intervals,'scoring_source':'independent operator','answers':answers}


def from_episode(task, episode):
    if not episode.get('scored',False): return {'scored':False,'task_success':None,'general_progress':None,'breakdown_quality':None}
    answers={}
    for item in episode.get('items',[]):
        key=item['item']['key']
        if key in answers: raise ValueError('duplicate score answer')
        if ('yes' in item)==('choice' in item): raise ValueError('score answer must have one value')
        answers[key]=item['yes'] if 'yes' in item else item['choice']
    result=calculate(task,answers)
    if episode.get('success',False)!=result['task_success']:
        raise ValueError('episode success disagrees with its success answer')
    return dict(result,scored=True)


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--task',type=Path,required=True);p.add_argument('--answers',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=calculate(json.loads(a.task.read_text(encoding='utf-8-sig')),json.loads(a.answers.read_text(encoding='utf-8-sig')))
    with a.output.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2)

if __name__=='__main__': main()
