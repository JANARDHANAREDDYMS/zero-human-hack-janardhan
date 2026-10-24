import unittest
from terac_integration.briefs import prepare_expert_brief
from terac_integration.policy import feasibility_arguments

class PreparedBriefTests(unittest.TestCase):
 def concern(self,role='Interview-preparation curriculum specialist'):
  return {'title':'Interview formats are unclear','explanation':'Customers cannot tell which interviews are covered.',
   'suggested_expertise':role,'review_question':'Which formats can this service credibly cover?',
   'proposed_test':'Review a sample lesson and practice exercise.'}
 def test_uses_transferable_category_and_prepares_screening(self):
  product={'name':'CodeSensei interview preparation','category':'Coding interview preparation'}
  concern=self.concern();brief=prepare_expert_brief(product,concern)
  self.assertEqual(brief['product_domain'],'Coding interview preparation')
  self.assertEqual(len(brief['qualification_checks']),2);self.assertEqual(len(brief['relevant_experience']),2)
  self.assertNotIn('CodeSensei',str(brief));self.assertIn(concern['review_question'],brief['qualification_checks'][1])
  args=feasibility_arguments(product,{**concern,'expert_brief':brief})
  self.assertIn('United States',args['panelDescription']);self.assertEqual(args['submissionCount'],1)
 def test_distinct_product_categories_and_roles_remain_distinct(self):
  audio=prepare_expert_brief({'name':'Sony concept','category':'Portable Bluetooth speakers'},self.concern('Battery-powered audio hardware engineer'))
  web=prepare_expert_brief({'name':'PrivateApp','category':'Full-stack web applications'},self.concern('Full-stack developer'))
  self.assertNotEqual(audio['product_domain'],web['product_domain']);self.assertIn('full-stack developer',web['relevant_experience'][0])
 def test_branded_category_does_not_require_private_product_access(self):
  brief=prepare_expert_brief({'name':'CodeSensei interview preparation','category':'CodeSensei interview preparation'},self.concern())
  self.assertNotIn('CodeSensei',brief['product_domain']);self.assertEqual(brief['work_type'],'review')
