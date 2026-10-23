"""Build a frozen operator packet and matched-pair plan without robot access."""
import argparse
import hashlib
import json
from pathlib import Path
from .act_run import load_task, task_spec
from .act_precision_score import expected

PROTOCOL={
 'version':'se3-physical-protocol-v1', 'max_rollout_s':450, 'max_model_decisions':52,
 'thresholds':{'placement_center_mm':10,'placement_yaw_deg':10,'stable_s':2,
  'alignment_perpendicular_center_error_mm':10,'alignment_pairwise_yaw_deg':10,
  'no_lift_bottom_clearance_mm':2,'insertion_reference_depth_error_mm':1,
  'origin_joint_error_deg':3},
 'provenance':'Precision thresholds come from the local proposal; other numerical thresholds are explicit local operational choices, not claims about RoboDojo defaults.',
 'measurement':'Fixed board coordinates measured with calibrated overhead views; side view verifies bottom clearance and insertion depth. Use shortest absolute yaw difference. Fit the alignment line through the first and last ordered centers; score the middle perpendicular error. Both origin poses compared joint-by-joint with saved neutral telemetry.',
 'resolution_requirement':'Before scored collection demonstrate <=2 mm planar, <=2 degree yaw and <=0.5 mm depth/height measurement uncertainty; otherwise revise the protocol version before any matched pair, never between methods.',
 'container':'Entire object footprint inside the container below its rim, settled and unsupported. No partial inclusion credit toward a completed unit.',
 'fixture':'Observer-requested relocation after final decision observation, controller hold, physically clear arms, locked carrier, fresh frames, new model decision. Only this prescribed intervention is excluded from assistance.',
 'evidence':'Save initial/terminal images, continuous synchronized top/side video for sequence/no-lift/press evidence, ACT telemetry, full model inputs/outputs and independent scores. If evidence cannot establish a criterion, mark scoring invalid rather than inventing success.',
}

def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

def build(root,output):
 root,output=Path(root),Path(output)
 output.mkdir(parents=True,exist_ok=False)
 (output/'tasks').mkdir();(output/'scores').mkdir()
 tasks={};plan=[];sheets=[]
 for path in sorted((root/'act-config/tasks').glob('*.json')):
  task=load_task(path);tasks[path.stem]=task
  with (output/'tasks'/path.name).open('x',encoding='utf-8') as f:json.dump(task,f,indent=2)
  spec=task_spec(task)
  lines=[f'# {task["name"]}',task['instruction'],'## Reset',task['reset_instruction'],'## Scoring']
  for item in spec.scoring.all_items:
   lines.append(f'**{item.key}** — {item.prompt}')
   if item.choices: lines.extend(f'- {i}: {c.description}' for i,c in enumerate(item.choices))
  (output/'scores'/(path.stem+'.md')).write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
  if 'rubric' in task:
   answers={'task_success':None,'general_progress':None,**{f'q_{i}_{j}':None for i in range(len(task['rubric']['intervals'])) for j in range(3)}}
   (output/'scores'/(path.stem+'-answers.json')).write_text(json.dumps(answers,indent=2),encoding='utf-8')
  else:
   variant=task['name'].removeprefix('precision-memory-')
   evidence={'episode_id':'','variant':variant,'calibration_id':'','evidence_source':'','duration_s':None,'early_task_cube_move':None,'interventions':None,'drops':None,'fixture':None,'transfers':[]}
   for o,t,y in expected(variant):
    evidence['transfers'].append({'object':None,'target':None,'commanded_yaw_deg':None,'center_error_mm':None,'yaw_error_deg':None,'stable_s':None,'released':None,'completed_at_s':None,'retries':None,'evidence':''})
   if variant=='moving-cube':evidence['fixture']={**{k:None for k in ('requested_after_final_observation','arms_clear','locked','fresh_observation','stale_command_rejected','recovered')},'evidence':''}
   (output/'scores'/(path.stem+'-measurements.json')).write_text(json.dumps(evidence,indent=2),encoding='utf-8')
  variants=list(sorted((root/'act-config/language-permutations').glob('*.json'))) if path.stem=='classify-objects-by-language' else [path]
  for variant_path in variants:
   v=load_task(variant_path)
   key=path.stem+('-'+variant_path.stem if variant_path!=path else '')
   if key!=path.stem:(output/'tasks'/(key+'.json')).write_text(json.dumps(v,indent=2),encoding='utf-8')
   pair=len(plan)//2+1
   policies=('native-gap','cap') if pair%2 else ('cap','native-gap')
   for policy in policies:
    plan.append({'pair':pair,'policy':policy,'task_file':'tasks/'+key+'.json','task_sha256':digest(v),'max_rollout_s':450,'max_model_decisions':52,'reset_required':True,'run_id':f'{pair:02d}-{policy}', 'cover_layout_permutation':(pair-1)%6+1 if key=='cover-blocks' else None})
 protocol=dict(PROTOCOL,task_sha256={k:digest(v) for k,v in tasks.items()},plan_sha256=digest(plan))
 (output/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
 (output/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
 commissioning={'protocol_sha256':digest(protocol),'station':'se3-labs-yam-2','address':'100.107.161.92:7443','operator':'','calibration_id':'','evidence_directory':'', 'verified':{k:False for k in ('start_pose','reachable_workspace','stop_control','three_camera_labels_readable','continuous_video','measurement_resolution','reset_layouts','fixture_hold_clear_lock','model_budget_for_selected_pairs')}}
 (output/'commissioning.json').write_text(json.dumps(commissioning,indent=2),encoding='utf-8')
 return {'task_count':len(tasks),'matched_pairs':len(plan)//2,'episodes':len(plan),'protocol_sha256':digest(protocol),'hardware_accessed':False}

def verify_packet(output,require_commissioned=False):
 output=Path(output)
 protocol=json.loads((output/'protocol.json').read_text(encoding='utf-8-sig'))
 plan=json.loads((output/'plan.json').read_text(encoding='utf-8-sig'))
 if digest(plan)!=protocol['plan_sha256']:raise ValueError('matched plan changed after freezing')
 if len(plan)%2 or not plan:raise ValueError('invalid matched-pair plan')
 for i in range(0,len(plan),2):
  a,b=plan[i:i+2]
  if a['pair']!=b['pair'] or a['task_sha256']!=b['task_sha256'] or {a['policy'],b['policy']}!={'native-gap','cap'}:raise ValueError('unmatched pair')
 for entry in plan:
  path=(output/entry['task_file']).resolve()
  if not path.is_relative_to((output/'tasks').resolve()):raise ValueError('task path outside packet')
  task=load_task(path)
  if digest(task)!=entry['task_sha256'] or task_spec(task).max_rollout_time!=450:raise ValueError('task changed after freezing')
 if require_commissioned:
  c=json.loads((output/'commissioning.json').read_text(encoding='utf-8-sig'))
  required={'start_pose','reachable_workspace','stop_control','three_camera_labels_readable','continuous_video','measurement_resolution','reset_layouts','fixture_hold_clear_lock','model_budget_for_selected_pairs'}
  if c['protocol_sha256']!=digest(protocol) or set(c['verified'])!=required or any(v is not True for v in c['verified'].values()) or any(not isinstance(c[k],str) or not c[k].strip() for k in ('operator','calibration_id','evidence_directory')):raise ValueError('physical commissioning evidence is incomplete or protocol changed')
 return {'offline_packet_valid':True,'commissioned':require_commissioned,'episodes':len(plan)}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--output',type=Path,required=True);p.add_argument('--verify',action='store_true');p.add_argument('--require-commissioned',action='store_true');a=p.parse_args()
 print(json.dumps(verify_packet(a.output,a.require_commissioned) if a.verify else build(a.root,a.output),indent=2))
if __name__=='__main__':main()
