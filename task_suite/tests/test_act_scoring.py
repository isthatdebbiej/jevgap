import copy,json,unittest,tempfile
from pathlib import Path
from google.protobuf.json_format import MessageToDict
from se3labs.interface.wire import policy_session_pb2 as pb
from rtbench_tasks.act_run import load_task,task_spec
from rtbench_tasks.act_scoring import validate,calculate,from_episode
from rtbench_tasks.act_precision_score import score,expected
ROOT=Path(__file__).resolve().parents[2]
# Tests work in the checkout too, when the task profiles are synced alongside it.
PROFILES=ROOT/'act-config/tasks'
class RubricTests(unittest.TestCase):
 def setUp(self):self.task=load_task(PROFILES/'pack-objects-into-box.json')
 def answers(self,task=None,grade=2,gp=None):
  task=task or self.task;n=len(task['rubric']['intervals'])
  return dict(task_success=gp is None,general_progress=n if gp is None else gp,**{f'q_{i}_{j}':grade for i in range(n) for j in range(3)})
 def test_all_profiles_construct_real_sdk_sheets_and_total_quality_100(self):
  count=0
  for p in PROFILES.glob('*.json'):
   task=load_task(p);spec=task_spec(task);self.assertEqual(spec.max_rollout_time,450)
   if 'rubric' not in task:continue
   count+=1;validate(task['rubric']);a=self.answers(task)
   self.assertEqual(calculate(task,a)['breakdown_quality'],100)
   self.assertEqual(spec.scoring.total(a),0) # Never blend GP and quality in SDK aggregate.
   self.assertEqual(spec.scoring.max_total,0)
  self.assertEqual(count,13)
 def test_recovered_trajectory_keeps_progress_but_loses_quality(self):
  a=self.answers();a['q_0_0']=1
  r=calculate(self.task,a);self.assertEqual(r['general_progress'],100);self.assertEqual(r['breakdown_quality'],98.5)
 def test_next_interval_can_score_after_lower_milestone(self):
  a=self.answers(grade=0,gp=1);a['q_0_0']=2;a['q_0_1']=2;a['q_0_2']=2;a['q_1_0']=1
  self.assertEqual(calculate(self.task,a)['breakdown_quality'],12.25)
  a['q_2_0']=1
  with self.assertRaises(ValueError):calculate(self.task,a)
 def test_missing_extra_bool_or_out_of_range_answers_rejected(self):
  for update in ({'general_progress':True},{'q_0_0':3},{'q_0_0':-1},{'task_success':1},{'extra':0}):
   a=self.answers();a.update(update)
   with self.assertRaises(ValueError):calculate(self.task,a)
  a=self.answers();del a['q_0_0']
  with self.assertRaises(ValueError):calculate(self.task,a)
  a=self.answers(gp=0);a['task_success']=True
  with self.assertRaises(ValueError):calculate(self.task,a)
 def test_unscored_is_not_failed_and_proto_zero_answers_survive(self):
  self.assertIsNone(from_episode(self.task,{'scored':False})['task_success'])
  ep=pb.EpisodeResult(scored=True,success=False)
  for k,v in self.answers(grade=0,gp=0).items():
   item=ep.items.add();item.item.key=k
   if type(v) is bool:item.yes=v
   else:item.choice=v
  r=from_episode(self.task,MessageToDict(ep,preserving_proto_field_name=True))
  self.assertEqual(r['general_progress'],0);self.assertFalse(r['task_success'])
 def test_adapted_milestones_and_balanced_language(self):
  for name,levels in [('hang-mugs',[0,40,100]),('insert-tubes',[0,50,100]),('play-stacking-toy',[0,10,25,45,70,100])]:
   d=load_task(PROFILES/(name+'.json'));self.assertEqual([m['points'] for m in d['rubric']['milestones']],levels);self.assertFalse(d['rubric']['comparable_to_robodojo'])
  language=[load_task(p)['instruction'] for p in (ROOT/'act-config/language-permutations').glob('*.json')]
  self.assertEqual(len(set(language)),6)
class PacketTests(unittest.TestCase):
 def test_packet_pairing_tamper_and_incomplete_commissioning(self):
  from rtbench_tasks.act_prepare import build,verify_packet
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'packet';r=build(ROOT,out)
   self.assertEqual(r['task_count'],17);self.assertEqual(r['episodes'],44)
   self.assertTrue(verify_packet(out)['offline_packet_valid'])
   with self.assertRaises(ValueError):verify_packet(out,True)
   plan=json.loads((out/'plan.json').read_text());p=out/plan[0]['task_file'];d=json.loads(p.read_text());d['instruction']+=' changed';p.write_text(json.dumps(d))
   with self.assertRaises(ValueError):verify_packet(out)
class PrecisionTests(unittest.TestCase):
 def evidence(self,variant='delayed'):
  return {'episode_id':'test','variant':variant,'calibration_id':'board-1','evidence_source':'observer-video','duration_s':100,'early_task_cube_move':False,'interventions':0,'drops':0,'fixture':None,'transfers':[{'object':o,'target':t,'commanded_yaw_deg':y,'center_error_mm':10,'yaw_error_deg':10 if y is not None else None,'stable_s':2,'released':True,'completed_at_s':i+1,'retries':0,'evidence':f'video:{i+1}'} for i,(o,t,y) in enumerate(expected(variant))]}
 def test_all_variants_and_threshold_boundaries(self):
  for variant in ('delayed','different-history','correction','moving-cube'):
   e=self.evidence(variant)
   if variant=='moving-cube':e['fixture']={k:True for k in ('requested_after_final_observation','arms_clear','locked','fresh_observation','stale_command_rejected','recovered')};e['fixture']['evidence']='video:fixture'
   self.assertTrue(score(e)['full_success'])
   e['transfers'][-1]['center_error_mm']=10.01
   r=score(e);self.assertFalse(r['full_success']);self.assertTrue(r['memory_choices_correct'])
 def test_wrong_choice_separate_from_geometry_and_retry_limit(self):
  e=self.evidence();e['transfers'][-1]['target']='T2';r=score(e)
  self.assertFalse(r['memory_choices_correct']);self.assertTrue(r['transfers'][-1]['placement_correct'])
  e=self.evidence();e['transfers'][0]['retries']=2;self.assertFalse(score(e)['full_success'])
 def test_timeout_missing_and_bad_evidence(self):
  e=self.evidence();e['duration_s']=451;self.assertFalse(score(e)['full_success'])
  e=self.evidence();e['transfers']=[];self.assertEqual(score(e)['completed_transfers'],0)
  e=self.evidence();e['transfers'][0]['center_error_mm']=float('nan')
  with self.assertRaises(ValueError):score(e)
  e=self.evidence('moving-cube')
  with self.assertRaises(ValueError):score(e)
if __name__=='__main__':unittest.main()
